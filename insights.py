import os
import re
import json
import requests
from dotenv import load_dotenv

load_dotenv()

def fetch_deepwiki_insight(repo):
    """Try to get insight from DeepWiki. Returns insight string or None.

    DeepWiki uses Next.js App Router with RSC streaming. The page source
    contains wiki content in self.__next_f.push() chunks alongside meta tags.

    Strategy (in priority order):
      1. Extract "What is {name}" section from embedded RSC content
      2. Parse og:description for direct descriptions
      3. Return None if nothing useful found
    """
    owner, name = repo.split("/", 1)

    try:
        r = requests.get(
            f"https://deepwiki.com/{owner}/{name}",
            timeout=10,
            headers={"User-Agent": "StarGazer-Newsletter/1.0"}
        )
        if r.status_code != 200 or not r.text:
            return None

        html = r.text

        # Check if repository is not indexed
        if re.search(r'repository\s+not\s+indexed', html, re.IGNORECASE):
            return None

        # Strategy 1: Extract "What is {name}" from server-rendered HTML
        what_is = _extract_what_is_section(html, name)
        if what_is:
            return what_is

        # Strategy 2: Fall back to og:description
        match = re.search(
            r'<meta[^>]*property="og:description"[^>]*content="([^"]*)"', html
        )
        if not match or not match.group(1).strip():
            return None

        desc = match.group(1).strip()

        # False positive — generic DeepWiki boilerplate
        if "DeepWiki provides up-to-date documentation" in desc:
            return None

        # Document-style — try to extract purpose
        if desc.startswith(("This document", "This page")):
            return _extract_purpose_sentence(desc, name)

        # Direct description — use as-is (truncate if very long)
        if len(desc) > 300:
            truncated = desc[:300]
            last_period = truncated.rfind(".")
            if last_period > 100:
                return truncated[:last_period + 1]
            return truncated + "..."
        return desc

    except Exception:
        return None


def _extract_what_is_section(html, name):
    """Extract the 'What is {name}' section from DeepWiki's server-rendered HTML.

    DeepWiki server-renders wiki content as real HTML (headings, paragraphs).
    We find the 'What is {name}' heading and grab the first <p> after it.
    Returns cleaned paragraph text, or None.
    """
    # Find "What is {name}" heading — allow hyphens/spaces/case variations
    # e.g. repo "deer-flow" matches heading "DeerFlow" or "Deer Flow" or "deer-flow"
    flexible_name = re.escape(name).replace(r'\-', '[-\\s]?')
    pattern = rf'What\s+is\s+{flexible_name}'
    match = re.search(pattern, html, re.IGNORECASE)
    if not match:
        return None

    after_heading = html[match.start():]

    # Grab the first <p>...</p> after the heading
    p_match = re.search(r'<p[^>]*>(.*?)</p>', after_heading, re.DOTALL)
    if not p_match:
        return None

    # Strip HTML tags from paragraph content
    para = re.sub(r'<[^>]+>', '', p_match.group(1))
    para = re.sub(r'\s+', ' ', para).strip()

    if not para or len(para) < 20:
        return None

    if len(para) > 300:
        truncated = para[:300]
        last_period = truncated.rfind(".")
        if last_period > 100:
            para = truncated[:last_period + 1]
        else:
            para = truncated + "..."

    return para


def _extract_purpose_sentence(desc, name):
    """Extract the core purpose from a document-style og:description.

    Tries multiple patterns in priority order:
      1. "{name} is a/an ..." sentence
      2. "introduces {name}...as a {description}" rewrite
      3. "purpose as a {description}" fallback
    Returns cleaned sentence or None.
    """
    esc = re.escape(name)

    # Split into sentences (handle truncated last sentence)
    sentences = re.split(r'(?<=[.!?])\s+', desc)

    # Pattern 1: sentence containing "{name} is a/an ..."
    for sent in sentences:
        if re.search(rf'\b{esc}\b\s+is\s+', sent, re.IGNORECASE):
            noise = ['repository at', 'repository structure', 'architecture overview',
                     'introduction to', 'table of contents']
            if any(n in sent.lower() for n in noise):
                continue
            sent = sent.strip().strip('`')
            if not sent.endswith(('.', '!', '?')):
                sent += "."
            return sent

    # Pattern 2: "introduces {name}...as a/an {description}" — rewrite to "{name} is a ..."
    as_match = re.search(
        rf'\b{esc}\b[^.]*?\bas\s+a(?:n)?\s+(.+?)(?:\.\s|$)',
        desc, re.IGNORECASE
    )
    if as_match:
        result = as_match.group(1).strip().rstrip('.')
        if len(result) > 15:
            return f"{name} is a {result}."

    # Pattern 3: "purpose as a {description}"
    purpose_as = re.search(
        r'purpose as\s+(.+?)(?:\.|,|\sand\s)', desc, re.IGNORECASE
    )
    if purpose_as:
        result = purpose_as.group(1).strip()
        if len(result) > 15:
            return result + "."

    return None


def fetch_llm_insights(repos_data):
    """Generate insights for multiple repos via LLM. Returns dict of repo_name -> insight."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    provider = "anthropic"

    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")
        provider = "openai"

    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")
        provider = "gemini"

    if not api_key:
        return {}

    # Build prompt
    repo_entries = []
    for repo in repos_data:
        readme_excerpt = (repo.get("readme_html") or "")[:4000]
        repo_entries.append(
            f"Repo: {repo['name']}\n"
            f"Description: {repo.get('description', 'N/A')}\n"
            f"Topics: {', '.join(repo.get('topics', []))}\n"
            f"Stars: {repo.get('stars', 0)}\n"
            f"README excerpt:\n{readme_excerpt}\n"
        )

    prompt = (
        "For each GitHub repo below, write a concise insight (2-3 sentences max) covering:\n"
        "1. What it does (core purpose)\n"
        "2. Spotlight (what makes it stand out)\n"
        "3. Who it's for\n\n"
        "Return ONLY a JSON array of objects with 'name' and 'insight' keys.\n\n"
        + "\n---\n".join(repo_entries)
    )

    try:
        if provider == "anthropic":
            return _call_anthropic(api_key, prompt)
        elif provider == "openai":
            return _call_openai(api_key, prompt)
        elif provider == "gemini":
            return _call_gemini(api_key, prompt)
    except Exception as e:
        print(f"LLM insight generation failed: {e}")
        return {}


def _call_anthropic(api_key, prompt):
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=60
    )
    r.raise_for_status()
    text = r.json()["content"][0]["text"]
    return _parse_insights_json(text)


def _call_openai(api_key, prompt):
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096
        },
        timeout=60
    )
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    return _parse_insights_json(text)


def _call_gemini(api_key, prompt):
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
        headers={"Content-Type": "application/json"},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=60
    )
    r.raise_for_status()
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return _parse_insights_json(text)


def _parse_insights_json(text):
    """Parse LLM response into {repo_name: insight} dict."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    try:
        items = json.loads(text)
        return {item["name"]: item["insight"] for item in items}
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"  Warning: malformed LLM JSON response, skipping batch: {e}")
        return {}


def generate_insights(repos_data):
    """Main entry point. Try DeepWiki first, then batch LLM for remainder.

    Args:
        repos_data: list of dicts with keys: name, description, topics, stars, readme

    Returns:
        dict of repo_name -> insight string
    """
    insights = {}
    needs_llm = []

    for repo in repos_data:
        name = repo["name"]
        print(f"  DeepWiki: {name}...", end=" ", flush=True)
        insight = fetch_deepwiki_insight(name)
        if insight:
            insights[name] = insight
            print("found")
        else:
            needs_llm.append(repo)
            print("not found")

    if needs_llm:
        print(f"  LLM: generating insights for {len(needs_llm)} repos...")
        # Batch in chunks of 10
        for i in range(0, len(needs_llm), 10):
            chunk = needs_llm[i:i + 10]
            llm_results = fetch_llm_insights(chunk)
            insights.update(llm_results)

    return insights
