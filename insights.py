import os
import re
import json
import requests

def fetch_deepwiki_insight(repo):
    """Try to get insight from DeepWiki. Returns insight string or None."""
    owner, name = repo.split("/", 1)

    # Try API first
    try:
        r = requests.get(
            f"https://api.deepwiki.com/v1/repos/{owner}/{name}/summary",
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            summary = data.get("summary") or data.get("description") or ""
            if summary:
                return summary.strip()
    except Exception:
        pass

    # Fallback: scrape HTML page for intro
    try:
        r = requests.get(
            f"https://deepwiki.com/{owner}/{name}",
            timeout=10,
            headers={"User-Agent": "StarGazer-Newsletter/1.0"}
        )
        if r.status_code == 200 and r.text:
            text = r.text
            match = re.search(r'<meta[^>]*property="og:description"[^>]*content="([^"]*)"', text)
            if match and match.group(1):
                return match.group(1).strip()
    except Exception:
        pass

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
