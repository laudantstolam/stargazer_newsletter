import os
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("GITHUB_TOKEN")
DAYS = int(os.getenv("DAYS", 7))

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json"
}

BASE_URL = "https://api.github.com"

# GitHub issue configuration
ISSUE_REPO = os.getenv("ISSUE_REPO")  # e.g., "username/newsletter"
ISSUE_LABELS = os.getenv("ISSUE_LABELS", "newsletter")  # comma-separated


def get_following():
    """Fetch list of users you follow (handles pagination)."""
    users = []
    page = 1

    while True:
        url = f"{BASE_URL}/user/following"
        params = {"per_page": 100, "page": page}

        r = requests.get(url, headers=HEADERS, params=params)
        r.raise_for_status()

        data = r.json()
        if not data:
            break

        users.extend([u["login"] for u in data])
        page += 1

    return users


def get_current_user():
    """Get current authenticated user."""
    r = requests.get(f"{BASE_URL}/user", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def get_user_starred_this_week(username, cutoff_time):
    """Get repos starred by user in the last N days."""
    starred = []
    page = 1

    while True:
        url = f"{BASE_URL}/users/{username}/starred"
        params = {"per_page": 100, "page": page, "sort": "created"}

        r = requests.get(url, headers=HEADERS, params=params)
        if r.status_code != 200:
            break

        data = r.json()
        if not data:
            break

        for repo in data:
            # Check if this endpoint returns starred_at; if not, we can't filter by time
            # The list endpoint doesn't return starred_at, so we'll get all and filter client-side
            starred.append({
                "name": repo["full_name"],
                "stars": repo["stargazers_count"],
                "description": repo["description"],
                "topics": repo["topics"][:5] if repo["topics"] else []
            })

        page += 1

    return starred


def get_following():
    """Fetch list of users you follow (handles pagination)."""
    users = []
    page = 1

    while True:
        url = f"{BASE_URL}/user/following"
        params = {"per_page": 100, "page": page}

        r = requests.get(url, headers=HEADERS, params=params)
        r.raise_for_status()

        data = r.json()
        if not data:
            break

        users.extend([u["login"] for u in data])
        page += 1

    return users


def get_user_star_events(username, cutoff_time):
    """Fetch recent star events from a user."""
    stars = []
    page = 1

    while page <= 10:  # REST API limit (~300 events max)
        url = f"{BASE_URL}/users/{username}/events"
        params = {"per_page": 30, "page": page}

        r = requests.get(url, headers=HEADERS, params=params)

        if r.status_code != 200:
            break

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

        page += 1

    return stars


def get_user_star_events(username, cutoff_time):
    """Fetch recent star events from a user."""
    stars = []
    page = 1

    while page <= 10:  # REST API limit (~300 events max)
        url = f"{BASE_URL}/users/{username}/events"
        params = {"per_page": 30, "page": page}

        r = requests.get(url, headers=HEADERS, params=params)

        if r.status_code != 200:
            break

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

        page += 1

    return stars


def create_github_issue(repo, title, body):
    """Create an issue in a GitHub repository."""
    if not repo:
        print("Warning: ISSUE_REPO not configured. Cannot create issue.")
        return False

    url = f"{BASE_URL}/repos/{repo}/issues"
    payload = {
        "title": title,
        "body": body,
        "labels": ISSUE_LABELS.split(",") if ISSUE_LABELS else []
    }

    r = requests.post(url, headers=HEADERS, json=payload)

    if r.status_code == 201:
        issue = r.json()
        print(f"Issue created: {issue['html_url']}")
        return True
    else:
        print(f"Failed to create issue: {r.status_code} {r.text}")
        return False


def main():
    print("=== StarGazer Newsletter Generator ===\n")

    # Get current user
    print("1. Getting current user...")
    current_user = get_current_user()
    username = current_user["login"]
    print(f"   Logged in as: {username}\n")

    # Get user's starred repos
    print("2. Fetching your starred repositories...")
    user_starred = get_user_starred_this_week(username, None)
    user_starred_names = {r["name"] for r in user_starred}
    print(f"   Total starred: {len(user_starred)}\n")

    # Get following list
    print("3. Fetching your following list...")
    following = get_following()
    print(f"   You follow {len(following)} users\n")

    # Get star activity from following
    print("4. Fetching star activity from your following...")
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=DAYS)

    all_stars = []
    repo_star_count = {}  # Track which repos are starred by following

    for user in following:
        print(f"   Checking {user}...", end=" ", flush=True)
        stars = get_user_star_events(user, cutoff_time)
        all_stars.extend(stars)

        # Count stars per repo
        for star in stars:
            repo_name = star["repo"]
            if repo_name not in repo_star_count:
                repo_star_count[repo_name] = []
            repo_star_count[repo_name].append(user)

        print(f"({len(stars)} stars)")

    all_stars.sort(key=lambda x: x["time"], reverse=True)

    # Find trending repos (most starred among following)
    trending_repos = sorted(
        repo_star_count.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )[:10]

    # Find shared repos (starred by both user and following)
    shared_repos = []
    for repo_name, users in repo_star_count.items():
        if repo_name in user_starred_names:
            shared_repos.append({
                "name": repo_name,
                "starred_by_following": len(users),
                "users": users
            })

    shared_repos.sort(key=lambda x: x["starred_by_following"], reverse=True)

    # Build markdown newsletter
    print("\n5. Building newsletter...\n")

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    body = f"""# 🌟 StarGazer Weekly Newsletter
Generated on {date_str}

## 📊 Your Activity
- **Total starred repos:** {len(user_starred)}
- **Following:** {len(following)} users
- **Recent activity period:** Last {DAYS} days

## 🔥 Trending Repos (Most starred by your following)
"""

    if trending_repos:
        for i, (repo_name, users) in enumerate(trending_repos, 1):
            starred_count = len(users)
            body += f"\n{i}. **[{repo_name}](https://github.com/{repo_name})** ⭐ ({starred_count} by: {', '.join(users[:3])}{'...' if len(users) > 3 else ''})"
    else:
        body += "\nNo trending repos this week."

    body += f"""

## 🤝 Repos You Share with Your Following
Found {len(shared_repos)} repo(s) you both starred:
"""

    if shared_repos:
        for i, repo in enumerate(shared_repos, 1):
            body += f"\n- **[{repo['name']}](https://github.com/{repo['name']})** — Starred by {repo['starred_by_following']} of your following: {', '.join(repo['users'])}"
    else:
        body += "\nNo shared repos yet."

    body += f"""

## 👥 Recent Star Activity (Top 20)
"""

    if all_stars:
        for star in all_stars[:20]:
            body += f"\n- {star['time'].strftime('%Y-%m-%d %H:%M')} — **{star['user']}** ⭐ [{star['repo']}](https://github.com/{star['repo']})"
        if len(all_stars) > 20:
            body += f"\n\n... and {len(all_stars) - 20} more activities"
    else:
        body += "\nNo recent activity."

    body += "\n\n---\n*Generated by StarGazer Newsletter*"

    # Create GitHub issue
    print("6. Creating GitHub issue...")
    title = f"📰 StarGazer Newsletter — {date_str}"

    if create_github_issue(ISSUE_REPO, title, body):
        print("Newsletter created successfully!")
    else:
        print("Failed to create issue. Printing content:")
        print(body)


if __name__ == "__main__":
    main()