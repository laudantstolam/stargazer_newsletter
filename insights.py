import os
import re
import json
import requests
from dotenv import load_dotenv

load_dotenv()

def fetch_deepwiki_insight(repo):
    """Try to get insight from DeepWiki by scraping the page. Returns insight string or None."""
    owner, name = repo.split("/", 1)

    try:
        r = requests.get(
            f"https://deepwiki.com/{owner}/{name}",
            timeout=10,
            headers={"User-Agent": "StarGazer-Newsletter/1.0"}
        )
        if r.status_code == 200 and r.text:
            text = r.text

            # Check if repository is not indexed
            if re.search(r'repository\s+not\s+indexed', text, re.IGNORECASE):
                return None

            match = re.search(r'<meta[^>]*property="og:description"[^>]*content="([^"]*)"', text)
            if not match or not match.group(1):
                return None

            description = match.group(1).strip()

            # Case 1: False positive - generic DeepWiki message
            if description.startswith("DeepWiki provides up-to-date documentation you can talk to, for"):
                return None

            # Case 2: Document-style description - try to extract "### What is [repo]" section
            if description.startswith("This document") or description.startswith("This page"):
                # Try multiple variations of "What is" section
                what_is_patterns = [
                    r'###\s*What\s+is\s*' + re.escape(name) + r'\s*\n*(.+?)(?:\n###|\n##|$)',
                    r'###\s*What\s+is\s*the\s*' + re.escape(name) + r'\s*\n*(.+?)(?:\n###|\n##|$)',
                    r'###\s*What\s+is\s*' + re.escape(owner) + r'\s*\n*(.+?)(?:\n###|\n##|$)',
                    r'###\s*What\s+is\s*the\s*' + re.escape(owner) + r'\s*\n*(.+?)(?:\n###|\n##|$)',
                    r'###\s*What\s+is\s+[A-Z]\w+\s*\n*(.+?)(?:\n###|\n##|$)',  # Generic "What is X"
                ]

                for pattern in what_is_patterns:
                    what_is_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                    if what_is_match:
                        what_is_content = what_is_match.group(1).strip()
                        # Clean up HTML tags and extract first paragraph
                        what_is_content = re.sub(r'<[^>]+>', ' ', what_is_content)
                        # Handle literal \n, \t escape sequences
                        what_is_content = what_is_content.replace('\\n', ' ').replace('\\t', ' ')
                        what_is_content = re.sub(r'\s+', ' ', what_is_content).strip()
                        # Get first sentence/paragraph
                        first_sentence = re.split(r'[.!?]', what_is_content)[0].strip()

                        # Filter out specific features that are not about the project itself
                        # Skip if it's about a specific technical concept or feature
                        skip_patterns = [
                            r'^(the\s+)?process\s+of',
                            r'^(a\s+)?technique\s+for',
                            r'^(an\s+)?algorithm\s+that',
                            r'^(a\s+)?method\s+to',
                            r'^(the\s+)?act\s+of',
                            r'^inline',  # Skip inlining-related content
                            r'^inlining',
                        ]

                        matched = False
                        for p in skip_patterns:
                            if re.match(p, first_sentence.lower().lstrip()):
                                matched = True
                                break

                        if len(first_sentence) > 20 and not matched:
                            return first_sentence + "."

                # Fallback to pattern matching if "What is" section not found
                # Pattern 1: "[repo] is a [description]" (e.g., "VMkatz is a forensic credential extraction tool")
                purpose_match = re.search(rf'{re.escape(name)}\s+is\s+(.+?)(?:\.|,|that|which|and|with)', description, re.IGNORECASE)
                if purpose_match:
                    result = purpose_match.group(1).strip()
                    # Filter out useless document-style phrases
                    useless = ['repository at', 'repository structure', 'architecture', 'overview', 'introduction', 'components']
                    if not any(u in result.lower() for u in useless):
                        return result + "."

                # Pattern 2: "explaining its purpose as a [description]" (e.g., "explaining its purpose as a JavaScript library")
                purpose_as_match = re.search(r'explaining its purpose as\s+(.+?)(?:\.|,|and|providing)', description, re.IGNORECASE)
                if purpose_as_match:
                    result = purpose_as_match.group(1).strip()
                    # Filter out useless document-style phrases
                    useless = ['repository at', 'repository structure', 'architecture', 'overview', 'introduction', 'components']
                    if not any(u in result.lower() for u in useless):
                        return result + "."

                # If no good pattern found, return None as this is not a useful insight
                return None

            # Case 3: Good description - use as is
            return description

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
