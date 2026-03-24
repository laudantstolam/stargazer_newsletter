import os
import sys
import pathlib
import json
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

from insights import generate_insights
from template import generate_html

TOKEN = os.getenv("GITHUB_TOKEN")
DAYS = int(os.getenv("DAYS", 7))

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json"
}

BASE_URL = "https://api.github.com"
ISSUE_REPO = os.getenv("GITHUB_REPOSITORY")

repo_cache = {}

def get_current_user():
    return requests.get(
        f"{BASE_URL}/user",
        headers=HEADERS
    ).json()["login"]


def get_following():
    users = []
    page = 1

    while True:
        r = requests.get(
            f"{BASE_URL}/user/following",
            headers=HEADERS,
            params={"per_page": 100, "page": page}
        )

        data = r.json()
        if not data:
            break

        users.extend([u["login"] for u in data])
        page += 1

    return users


def get_repo_metadata(repo):
    if repo in repo_cache:
        return repo_cache[repo]

    r = requests.get(
        f"{BASE_URL}/repos/{repo}",
        headers={
            **HEADERS,
            "Accept": "application/vnd.github+json"
        }
    )

    if r.status_code != 200:
        return None

    repo_cache[repo] = r.json()
    return repo_cache[repo]



def get_user_all_stars(username):
    starred = set()
    page = 1
    while True:
        r = requests.get(
            f"{BASE_URL}/users/{username}/starred",
            headers=HEADERS,
            params={"per_page": 100, "page": page}
        )
        data = r.json()
        if not data:
            break
        for repo in data:
            starred.add(repo["full_name"])
        page += 1
    return starred


def get_user_star_events(username, cutoff_time):
    stars = []
    page = 1

    while True:
        r = requests.get(
            f"{BASE_URL}/users/{username}/starred",
            headers={**HEADERS, "Accept": "application/vnd.github.star+json"},
            params={"per_page": 100, "page": page, "sort": "created", "direction": "desc"}
        )

        if r.status_code != 200:
            break

        data = r.json()
        if not data:
            break

        for item in data:
            starred_at = datetime.strptime(
                item["starred_at"],
                "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc)

            if starred_at < cutoff_time:
                return stars

            stars.append({
                "user": username,
                "repo": item["repo"]["full_name"],
                "time": starred_at
            })

        page += 1

    return stars


def create_issue(title, body):

    payload = {
        "title": title,
        "body": body,
        "labels": ["newsletter"]
    }

    r = requests.post(
        f"{BASE_URL}/repos/{ISSUE_REPO}/issues",
        headers=HEADERS,
        json=payload
    )

    if r.status_code == 201:
        print("Issue created:", r.json()["html_url"])
    else:
        print("Issue creation failed:", r.text)


def fetch_common_data():
    """Fetch stars data shared by both newsletter and swipe UI."""
    username = get_current_user()
    following = get_following()
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=DAYS)

    all_stars = []
    repo_star_count = {}
    topic_counter = {}
    weak_signal_repos = set()

    for user in following:
        stars = get_user_star_events(user, cutoff_time)
        for star in stars:
            repo = star["repo"]
            all_stars.append(star)
            repo_star_count.setdefault(repo, []).append(user)

    for repo, users in repo_star_count.items():
        meta = get_repo_metadata(repo)
        if not meta:
            continue
        topics = meta.get("topics", [])
        for t in topics:
            topic_counter[t] = topic_counter.get(t, 0) + 1
        if meta["stargazers_count"] < 200 and len(users) >= 2:
            weak_signal_repos.add(repo)

    trending_network = sorted(
        repo_star_count.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )[:10]

    trending_topics = sorted(
        topic_counter.items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]

    user_all_stars = get_user_all_stars(username)

    shared_repos = set(r for r in repo_star_count if r in user_all_stars)

    all_stars.sort(key=lambda x: x["time"], reverse=True)

    return {
        "username": username,
        "repo_star_count": repo_star_count,
        "all_stars": all_stars,
        "trending_network": trending_network,
        "trending_topics": trending_topics,
        "shared_repos": shared_repos,
        "weak_signal_repos": weak_signal_repos,
    }


def build_newsletter(data):
    """Generate and post the newsletter issue."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    body = f"# StarGazer Weekly Newsletter\nGenerated {today}\n\n"

    body += "## Trending by network\n"
    for repo, users in data["trending_network"]:
        body += f"- [{repo}](https://github.com/{repo}) ({len(users)} stars)\n"

    body += "\n## Trending by topic\n"
    for topic, count in data["trending_topics"]:
        body += f"- `{topic}` ({count})\n"

    body += "\n## Shared-interest repos\n"
    shared = data["shared_repos"]
    if shared:
        for repo in list(shared)[:10]:
            body += f"- [{repo}](https://github.com/{repo})\n"
    else:
        body += "None\n"

    body += "\n## Weak-signal discovery repos\n"
    weak = sorted(
        [(r, data["repo_star_count"][r]) for r in data["weak_signal_repos"]
         if r in data["repo_star_count"]],
        key=lambda x: len(x[1]), reverse=True
    )
    for repo, users in weak[:10]:
        body += f"- [{repo}](https://github.com/{repo}) ({len(users)} insiders)\n"

    body += "\n## Recent activity\n"
    for star in data["all_stars"][:20]:
        meta = get_repo_metadata(star["repo"])
        desc = (meta.get("description") or "") if meta else ""
        topics = ((meta.get("topics") or [])[:3]) if meta else []
        line = f"- {star['user']} starred [{star['repo']}](https://github.com/{star['repo']})"
        if desc:
            line += f"\n  > {desc}"
        if topics:
            line += f"\n  `{'` `'.join(topics)}`"
        body += line + "\n"

    create_issue(
        f"StarGazer Newsletter — {today}",
        body
    )


def build_swipe_ui(data):
    """Generate the swipe UI HTML with categorized repos."""
    print("\n--- Generating Swipe UI ---")

    # Load pre-generated insights from parallel CI jobs
    pre_generated_insights = {}
    insights_dir = pathlib.Path("temp/insights")
    if insights_dir.exists():
        print("  Loading pre-generated insights from parallel jobs...")
        for chunk_file in insights_dir.glob("chunk_*.json"):
            with open(chunk_file, 'r', encoding='utf-8') as f:
                chunk_data = json.load(f)
                for repo in chunk_data:
                    if repo.get("insight"):
                        pre_generated_insights[repo["name"]] = repo["insight"]
        print(f"  Loaded {len(pre_generated_insights)} pre-generated insights")

    # Also check temp/repos_data.json for pre-computed flags
    pre_flags = {}
    repos_data_path = pathlib.Path("temp/repos_data.json")
    if repos_data_path.exists():
        with open(repos_data_path, 'r', encoding='utf-8') as f:
            for r in json.load(f):
                pre_flags[r["name"]] = {
                    "is_shared": r.get("is_shared", False),
                    "is_weak_signal": r.get("is_weak_signal", False),
                }

    trending_set = set(r for r, _ in data["trending_network"])

    # Categorize repos: trending → shared → weak signal → others
    cat_trending = []
    cat_shared = []
    cat_weak = []
    cat_other = []

    for repo_name, users in data["repo_star_count"].items():
        meta = get_repo_metadata(repo_name)
        if not meta:
            continue

        insight = pre_generated_insights.get(repo_name)

        # Determine flags from pre-computed data or live data
        flags = pre_flags.get(repo_name, {})
        is_shared = flags.get("is_shared", repo_name in data["shared_repos"])
        is_weak = flags.get("is_weak_signal", repo_name in data["weak_signal_repos"])

        entry = {
            "name": repo_name,
            "description": meta.get("description") or "",
            "topics": (meta.get("topics") or [])[:3],
            "stars": meta.get("stargazers_count", 0),
            "network_users": users,
            "insight": insight,
        }

        if repo_name in trending_set:
            entry["category"] = "trending"
            cat_trending.append(entry)
        elif is_shared:
            entry["category"] = "shared"
            cat_shared.append(entry)
        elif is_weak:
            entry["category"] = "weak-signal"
            cat_weak.append(entry)
        else:
            entry["category"] = "other"
            cat_other.append(entry)

    # Sort each category by network star count (descending)
    for cat in (cat_trending, cat_shared, cat_weak, cat_other):
        cat.sort(key=lambda x: len(x["network_users"]), reverse=True)

    swipe_repos = cat_trending + cat_shared + cat_weak + cat_other

    # Generate insights for repos without pre-generated ones
    repos_needing_insights = [r for r in swipe_repos if r["insight"] is None]
    if repos_needing_insights:
        print(f"\n  Generating insights for {len(repos_needing_insights)} remaining repos...")
        insights = generate_insights(repos_needing_insights)
        for repo in swipe_repos:
            if repo["insight"] is None:
                repo["insight"] = insights.get(repo["name"])

    # Write dist/index.html
    dist_dir = pathlib.Path("dist")
    dist_dir.mkdir(exist_ok=True)

    html = generate_html(swipe_repos)
    (dist_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"\n  Wrote dist/index.html ({len(html):,} bytes, {len(swipe_repos)} repos)")


def main():
    mode = "both"
    if "--newsletter-only" in sys.argv:
        mode = "newsletter"
    elif "--swipe-only" in sys.argv:
        mode = "swipe"

    data = fetch_common_data()

    if mode in ("both", "newsletter"):
        build_newsletter(data)

    if mode in ("both", "swipe"):
        build_swipe_ui(data)


if __name__ == "__main__":
    main()
