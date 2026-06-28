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
        if r.status_code != 200:
            break
        data = r.json()
        if not data:
            break
        for repo in data:
            starred.add(repo["full_name"])
        page += 1
    return starred


def get_user_stars_since(username, since):
    starred = []
    page = 1
    while True:
        r = requests.get(
            f"{BASE_URL}/users/{username}/starred",
            headers=HEADERS,
            params={"per_page": 100, "page": page}
        )
        if r.status_code != 200:
            break
        data = r.json()
        if not data:
            break
        for repo in data:
            starred_at = repo.get("starred_at")
            if starred_at:
                starred_time = datetime.fromisoformat(starred_at.replace("Z", "+00:00"))
                if starred_time > since:
                    starred.append((username, repo))
        page += 1
    return starred


def compute_trending(star_events, followers_count):
    from collections import Counter
    repo_counter = Counter()
    for _, repo in star_events:
        repo_counter[repo["full_name"]] += 1
    trending = repo_counter.most_common(10)
    return trending


def compute_weak_signals(repos, follower_set, activity_repos):
    weak = []
    for repo in repos:
        if repo in activity_repos:
            continue
        metadata = get_repo_metadata(repo)
        if metadata is None:
            continue
        stargazers = metadata.get("stargazers_count", 0)
        # weak signal: low total stars but multiple followers starred recently
        if stargazers < 50:
            # count followers who starred it from star_events
            count = 0
            for follower, r in activity_repos:
                if r["full_name"] == repo:
                    count += 1
            if count >= 2:
                weak.append((repo, count))
    return weak


def build_newsletter():
    current_user = get_current_user()
    following = get_following()
    all_users = [current_user] + following

    since = datetime.now(timezone.utc) - timedelta(days=DAYS)
    star_events = []
    for user in all_users:
        events = get_user_stars_since(user, since)
        star_events.extend(events)

    # trending repos by network (count of stars from network)
    trending = compute_trending(star_events, len(following))

    # topics from trending repos
    topic_counter = {}
    for repo_name, count in trending:
        meta = get_repo_metadata(repo_name)
        if meta and meta.get("topics"):
            for t in meta["topics"]:
                topic_counter[t] = topic_counter.get(t, 0) + count
    top_topics = sorted(topic_counter.items(), key=lambda x: -x[1])[:5]

    # shared interest repos (starred by multiple followers)
    repo_follower_count = {}
    for follower, repo in star_events:
        fn = repo["full_name"]
        if fn not in repo_follower_count:
            repo_follower_count[fn] = set()
        repo_follower_count[fn].add(follower)
    shared = [repo for repo, followers in repo_follower_count.items() if len(followers) >= 2]

    # weak signals
    activity_repos = [(f, r) for f, r in star_events]
    activity_repo_names = [r["full_name"] for _, r in star_events]
    weak = compute_weak_signals(
        list(repo_follower_count.keys()),
        set(following),
        activity_repos
    )
    weak = sorted(weak, key=lambda x: -x[1])[:5]

    # recent activity: last 10 stars
    recent = star_events[-10:] if len(star_events) >= 10 else star_events

    # generate markdown
    lines = []
    lines.append(f"# StarGazer Weekly Newsletter")
    lines.append(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append("## Trending by network")
    for repo, count in trending:
        lines.append(f"- [{repo}](https://github.com/{repo}) ({count} stars)")
    lines.append("")
    lines.append("## Trending by topic")
    for topic, count in top_topics:
        lines.append(f"- `{topic}` ({count})")
    lines.append("")
    lines.append("## Shared-interest repos")
    for repo in shared[:5]:
        lines.append(f"- [{repo}](https://github.com/{repo})")
    lines.append("")
    lines.append("## Weak-signal discovery repos")
    for repo, count in weak:
        lines.append(f"- [{repo}](https://github.com/{repo}) ({count} insiders)")
    lines.append("")
    lines.append("## Recent activity")
    for follower, repo in reversed(recent):
        repo_name = repo["full_name"]
        description = repo.get("description", "")
        topics = repo.get("topics", [])
        line = f"- {follower} starred [{repo_name}](https://github.com/{repo_name})"
        lines.append(line)
        if description:
            lines.append(f"  > {description}")
        if topics:
            lines.append(f"  `{'` `'.join(topics)}`")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    newsletter = build_newsletter()
    print(newsletter)
