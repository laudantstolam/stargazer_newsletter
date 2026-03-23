import os
import requests
from datetime import datetime, timedelta, timezone

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


def get_user_star_events(username, cutoff_time):
    stars = []

    for page in range(1, 11):

        r = requests.get(
            f"{BASE_URL}/users/{username}/events",
            headers=HEADERS,
            params={"per_page": 30, "page": page}
        )

        events = r.json()

        if not events:
            break

        for event in events:

            if event["type"] != "WatchEvent":
                continue

            created_at = datetime.strptime(
                event["created_at"],
                "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc)

            if created_at < cutoff_time:
                return stars

            stars.append({
                "user": username,
                "repo": event["repo"]["name"],
                "time": created_at
            })

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


def main():

    username = get_current_user()

    following = get_following()

    cutoff_time = datetime.now(timezone.utc) - timedelta(days=DAYS)

    all_stars = []
    repo_star_count = {}
    topic_counter = {}
    weak_signal = []

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
            weak_signal.append((repo, users))

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

    shared_repos = [
        r for r, users in repo_star_count.items()
        if username in users
    ]

    weak_signal.sort(
        key=lambda x: len(x[1]),
        reverse=True
    )

    all_stars.sort(
        key=lambda x: x["time"],
        reverse=True
    )

    today = datetime.utcnow().strftime("%Y-%m-%d")

    body = f"# 🌟 StarGazer Weekly Newsletter\nGenerated {today}\n\n"

    body += "## 🔥 Trending by network\n"

    for repo, users in trending_network:
        body += f"- [{repo}](https://github.com/{repo}) ({len(users)} stars)\n"

    body += "\n## 🔥 Trending by topic\n"

    for topic, count in trending_topics:
        body += f"- `{topic}` ({count})\n"

    body += "\n## 🤝 Shared-interest repos\n"

    if shared_repos:
        for repo in shared_repos[:10]:
            body += f"- [{repo}](https://github.com/{repo})\n"
    else:
        body += "None\n"

    body += "\n## 🧪 Weak-signal discovery repos\n"

    for repo, users in weak_signal[:10]:
        body += f"- [{repo}](https://github.com/{repo}) ({len(users)} insiders)\n"

    body += "\n## 👥 Recent activity\n"

    for star in all_stars[:20]:
        body += f"- {star['user']} ⭐ [{star['repo']}](https://github.com/{star['repo']})\n"

    create_issue(
        f"📰 StarGazer Newsletter — {today}",
        body
    )


if __name__ == "__main__":
    main()