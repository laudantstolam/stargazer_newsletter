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

        # False positive? deepwiki sometimes uses generic descriptions
        if len(desc) < 20 or any(generic in desc.lower() for generic in ["learn", "wiki", "documentation"]):
            return None

        return desc

    except Exception:
        return None


def _extract_what_is_section(html, name):
    """Extract the 'What is {name}' section from DeepWiki RSC content."""
    # Look for "What is <name>" or similar in HTML
    pattern = re.compile(
        r'What\s+is\s+' + re.escape(name) + r'[^.<]*(?:<[^>]*>)*[^<]*',
        re.IGNORECASE
    )
    matches = pattern.findall(html)
    if matches:
        # Take the first match and clean HTML tags
        candidate = re.sub(r'<[^>]+>', '', matches[0])
        return candidate.strip()
    return None


def generate_insights(repos):
    """Generate insights for a list of repo strings."""
    insights = {}
    for repo in repos:
        insight = fetch_deepwiki_insight(repo)
        if insight:
            insights[repo] = insight
    return insights
