# StarGazer Swipe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Tinder-like swiping interface to StarGazer that lets users discover and act on repos starred by their GitHub network, deployed as a static GitHub Pages site.

**Architecture:** Extend `newsletter.py` to also generate a self-contained `dist/index.html` with all repo data (metadata, README HTML, AI insights) baked in as JSON. GitHub Actions deploys it to GitHub Pages. Three-tier insight pipeline: DeepWiki (free) → LLM (Claude/OpenAI/Gemini) → heuristics-only.

**Tech Stack:** Python 3.11, requests, GitHub API, DeepWiki, anthropic/openai/google-generativeai SDKs (optional), vanilla HTML/CSS/JS, GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-03-23-stargazer-swipe-design.md`

**Deliberate deviations from spec:**
- Code split into 3 files (`newsletter.py`, `insights.py`, `template.py`) instead of everything in `newsletter.py` — better maintainability
- JSON data is a flat array `[...]` instead of `{"repos": [...]}` — simpler, both producer and consumer are ours

---

## File Structure

```
stargazer_newsletter/
  newsletter.py              # extend: add README fetch, insights, HTML generation
  insights.py                # new: DeepWiki + LLM + heuristics insight pipeline
  template.py                # new: HTML template constant + generate_html() function
  dist/                      # new: generated output directory (gitignored)
    index.html               # generated at build time
  .github/workflows/
    newsletter.yml            # extend: add Pages deploy step + new env vars
  .gitignore                  # new: ignore dist/
```

**Why split into 3 Python files:**
- `newsletter.py` stays focused on data collection + issue creation (existing responsibility) + orchestration
- `insights.py` handles the 3-tier insight pipeline (DeepWiki, LLM, heuristics) — isolated and testable
- `template.py` holds the HTML template and generation logic — keeps the ~200-line HTML string out of `newsletter.py`

---

### Task 1: Add README fetch function to newsletter.py

**Files:**
- Modify: `newsletter.py` (add `get_repo_readme` function after `get_repo_metadata`)

- [ ] **Step 1: Add `get_repo_readme` function**

Add after the `get_repo_metadata` function:

```python
readme_cache = {}

def get_repo_readme(repo):
    """Fetch rendered README HTML for a repo. Returns HTML string or empty string."""
    if repo in readme_cache:
        return readme_cache[repo]

    r = requests.get(
        f"{BASE_URL}/repos/{repo}/readme",
        headers={**HEADERS, "Accept": "application/vnd.github.html"}
    )

    if r.status_code != 200:
        readme_cache[repo] = ""
        return ""

    html = r.text
    if len(html) > 50000:
        html = html[:50000] + "<!-- truncated -->"

    readme_cache[repo] = html
    return html
```

- [ ] **Step 2: Verify it works locally**

Run in Python REPL (requires `GITHUB_TOKEN` env var):
```bash
GITHUB_TOKEN=<your-pat> python -c "
from newsletter import get_repo_readme
html = get_repo_readme('vercel/next.js')
print(f'Length: {len(html)}, starts with: {html[:50]}')
"
```

Expected: prints HTML length and first 50 chars of rendered README.

- [ ] **Step 3: Commit**

```bash
git add newsletter.py
git commit -m "feat: add README HTML fetch with caching and truncation"
```

---

### Task 2: Create insights pipeline (insights.py)

**Files:**
- Create: `insights.py`

- [ ] **Step 1: Create `insights.py` with DeepWiki fetch**

```python
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
            # Look for meta description or first paragraph
            text = r.text
            # Try og:description meta tag
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
        readme_excerpt = (repo.get("readme") or "")[:4000]
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
    # Strip markdown code fences if present
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    items = json.loads(text)
    return {item["name"]: item["insight"] for item in items}


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
```

- [ ] **Step 2: Commit**

```bash
git add insights.py
git commit -m "feat: add insights pipeline (DeepWiki + LLM fallback)"
```

---

### Task 3: Create HTML template (template.py)

**Files:**
- Create: `template.py`

- [ ] **Step 1: Create `template.py` with the full swipe UI template**

```python
import json
import os


def generate_html(repos_json):
    """Generate the self-contained swipe page HTML.

    Args:
        repos_json: list of repo dicts matching the JSON schema from the spec.

    Returns:
        Complete HTML string ready to write to dist/index.html.
    """
    # Escape </script> in README HTML to prevent XSS/breaking the page
    data_blob = json.dumps(repos_json, ensure_ascii=False)
    data_blob = data_blob.replace("</script>", "<\\/script>")
    return TEMPLATE.replace("{{DATA}}", data_blob)


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>StarGazer Swipe</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.5.1/github-markdown-dark.min.css">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg: #0f172a;
    --surface: #1e293b;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --accent: #818cf8;
    --insight-from: rgba(99,102,241,0.1);
    --insight-to: rgba(139,92,246,0.1);
    --insight-border: rgba(99,102,241,0.2);
    --skip: #ef4444;
    --like: #22c55e;
    --radius: 12px;
    --transition: 200ms ease;
  }

  body {
    font-family: Inter, system-ui, sans-serif;
    background: var(--bg);
    color: var(--text-primary);
    min-height: 100vh;
    overflow-x: hidden;
  }

  /* Progress bar */
  .progress-bar {
    position: fixed; top: 0; left: 0; right: 0;
    height: 4px; background: var(--surface); z-index: 100;
  }
  .progress-fill {
    height: 100%; background: var(--accent);
    transition: width 300ms ease;
  }
  .progress-text {
    position: fixed; top: 8px; right: 16px;
    font-size: 12px; color: var(--text-secondary); z-index: 100;
  }

  /* Main container */
  .container {
    display: flex; height: 100vh; padding-top: 4px;
  }

  /* Left panel — info card */
  .info-panel {
    width: 40%; padding: 24px; display: flex; flex-direction: column;
    overflow-y: auto; border-right: 1px solid var(--surface);
  }

  .repo-header {
    display: flex; align-items: center; gap: 12px; margin-bottom: 16px;
  }
  .repo-avatar {
    width: 44px; height: 44px; border-radius: var(--radius);
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 18px; color: white; flex-shrink: 0;
  }
  .repo-name { font-weight: 600; font-size: 16px; }
  .repo-stars { font-size: 12px; color: var(--text-secondary); }

  .repo-desc {
    font-size: 14px; color: var(--text-secondary);
    line-height: 1.6; margin-bottom: 16px;
  }

  .topics {
    display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 16px;
  }
  .topic {
    background: var(--surface); color: var(--accent);
    padding: 4px 10px; border-radius: 12px; font-size: 11px;
  }

  .insight-box {
    background: linear-gradient(135deg, var(--insight-from), var(--insight-to));
    border: 1px solid var(--insight-border);
    border-radius: 10px; padding: 14px; margin-bottom: 16px;
  }
  .insight-label {
    font-size: 11px; font-weight: 600; color: var(--accent);
    text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;
  }
  .insight-text {
    font-size: 13px; color: #c4b5fd; line-height: 1.5;
  }

  .network-info {
    font-size: 12px; color: var(--text-secondary);
    border-top: 1px solid var(--surface); padding-top: 12px; margin-top: auto;
  }
  .network-info span { color: var(--accent); }

  /* Swipe buttons */
  .swipe-buttons {
    display: flex; gap: 16px; justify-content: center;
    margin-top: 20px; padding-top: 16px;
    border-top: 1px solid var(--surface);
  }
  .btn-skip, .btn-like {
    width: 56px; height: 56px; border-radius: 50%;
    border: 2px solid; display: flex; align-items: center;
    justify-content: center; font-size: 22px;
    cursor: pointer; background: transparent;
    transition: all var(--transition);
  }
  .btn-skip { border-color: var(--skip); color: var(--skip); }
  .btn-skip:hover { background: rgba(239,68,68,0.1); }
  .btn-like { border-color: var(--like); color: var(--like); }
  .btn-like:hover { background: rgba(34,197,94,0.1); }
  .btn-skip:focus-visible, .btn-like:focus-visible {
    outline: 2px solid var(--accent); outline-offset: 2px;
  }

  /* Right panel — README */
  .readme-panel {
    width: 60%; padding: 24px; overflow-y: auto;
  }
  .readme-panel .markdown-body {
    background: transparent; font-size: 14px;
  }
  .readme-empty {
    display: flex; align-items: center; justify-content: center;
    height: 100%; color: var(--text-secondary); font-size: 14px;
  }

  /* Card animation */
  .card-wrapper {
    transition: transform 300ms ease, opacity 300ms ease;
  }
  .card-wrapper.swipe-left {
    transform: translateX(-120%); opacity: 0;
  }
  .card-wrapper.swipe-right {
    transform: translateX(120%); opacity: 0;
  }

  /* Summary screen */
  .summary { padding: 40px; max-width: 680px; margin: 0 auto; }
  .summary h1 { font-size: 28px; margin-bottom: 8px; }
  .summary .stats {
    display: flex; gap: 24px; margin: 16px 0 32px;
    font-size: 14px; color: var(--text-secondary);
  }
  .summary .stats strong { color: var(--text-primary); }
  .summary .liked-list { list-style: none; }
  .summary .liked-list li {
    padding: 12px 0; border-bottom: 1px solid var(--surface);
  }
  .summary .liked-list a {
    color: var(--accent); text-decoration: none; font-weight: 500;
  }
  .summary .liked-list a:hover { text-decoration: underline; }
  .summary .liked-list .desc {
    font-size: 13px; color: var(--text-secondary); margin-top: 4px;
  }

  /* Mobile */
  @media (max-width: 768px) {
    .container { flex-direction: column; }
    .info-panel { width: 100%; border-right: none; }
    .readme-panel { display: none; }
  }

  /* Reduced motion */
  @media (prefers-reduced-motion: reduce) {
    .card-wrapper, .progress-fill { transition: none; }
  }
</style>
</head>
<body>

<div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
<div class="progress-text" id="progressText"></div>

<div id="app"></div>

<script>
const REPOS = {{DATA}};
let currentIndex = 0;
const liked = [];
const skipped = [];

function render() {
  if (currentIndex >= REPOS.length) {
    renderSummary();
    return;
  }
  const repo = REPOS[currentIndex];
  updateProgress();

  const app = document.getElementById("app");
  app.innerHTML = `
    <div class="container card-wrapper" id="card">
      <div class="info-panel">
        <div class="repo-header">
          <div class="repo-avatar">${repo.name.charAt(0).toUpperCase()}</div>
          <div>
            <div class="repo-name">${escHtml(repo.name)}</div>
            <div class="repo-stars">\u2B50 ${formatNum(repo.stars)}</div>
          </div>
        </div>
        <div class="repo-desc">${escHtml(repo.description || "No description")}</div>
        <div class="topics">
          ${(repo.topics || []).map(t => `<span class="topic">${escHtml(t)}</span>`).join("")}
        </div>
        ${repo.insight ? `
          <div class="insight-box">
            <div class="insight-label"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:-2px;margin-right:4px;"><path d="M12 2l2.4 7.4H22l-6 4.6 2.3 7L12 16.4 5.7 21l2.3-7L2 9.4h7.6z"/></svg>AI Insight</div>
            <div class="insight-text">${escHtml(repo.insight)}</div>
          </div>
        ` : ""}
        <div class="network-info">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:-2px;margin-right:4px;"><path d="M16 11c1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3 1.34 3 3 3zm-8 0c1.66 0 3-1.34 3-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>
          starred by <span>${(repo.network_users || []).join(", ")}</span>
        </div>
        <div class="swipe-buttons">
          <button class="btn-skip" onclick="swipe('left')" aria-label="Skip"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg></button>
          <button class="btn-like" onclick="swipe('right')" aria-label="Like"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M20 6L9 17l-5-5"/></svg></button>
        </div>
      </div>
      <div class="readme-panel">
        ${repo.readme_html
          ? `<div class="markdown-body">${repo.readme_html}</div>`
          : `<div class="readme-empty">No README available</div>`}
      </div>
    </div>
  `;
}

function swipe(direction) {
  const card = document.getElementById("card");
  const repo = REPOS[currentIndex];

  if (direction === "right") {
    liked.push(repo);
    window.open(`https://github.com/${repo.name}`, "_blank");
    card.classList.add("swipe-right");
  } else {
    skipped.push(repo);
    card.classList.add("swipe-left");
  }

  setTimeout(() => { currentIndex++; render(); }, 300);
}

function renderSummary() {
  document.getElementById("progressFill").style.width = "100%";
  document.getElementById("progressText").textContent = "Done!";

  document.getElementById("app").innerHTML = `
    <div class="summary">
      <h1>All caught up!</h1>
      <div class="stats">
        <div><strong>${REPOS.length}</strong> repos seen</div>
        <div><strong>${liked.length}</strong> liked</div>
        <div><strong>${skipped.length}</strong> skipped</div>
      </div>
      ${liked.length > 0 ? `
        <h2 style="margin-bottom: 16px;">Repos you liked</h2>
        <ul class="liked-list">
          ${liked.map(r => `
            <li>
              <a href="https://github.com/${r.name}" target="_blank">${escHtml(r.name)}</a>
              <span style="color: var(--text-secondary); font-size: 12px;"> \u2B50 ${formatNum(r.stars)}</span>
              <div class="desc">${escHtml(r.description || "")}</div>
            </li>
          `).join("")}
        </ul>
      ` : `<p style="color: var(--text-secondary);">No repos liked this time.</p>`}
    </div>
  `;
}

function updateProgress() {
  const pct = ((currentIndex) / REPOS.length) * 100;
  document.getElementById("progressFill").style.width = pct + "%";
  document.getElementById("progressText").textContent =
    `${currentIndex + 1} / ${REPOS.length}`;
}

function escHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function formatNum(n) {
  if (n >= 1000) return (n / 1000).toFixed(1) + "k";
  return String(n);
}

// Keyboard navigation
document.addEventListener("keydown", (e) => {
  if (currentIndex >= REPOS.length) return;
  if (e.key === "ArrowLeft") swipe("left");
  if (e.key === "ArrowRight" || e.key === "Enter") swipe("right");
});

// Touch swipe
let touchStartX = 0;
let touchCurrentX = 0;
document.addEventListener("touchstart", (e) => {
  touchStartX = e.touches[0].clientX;
  touchCurrentX = touchStartX;
}, {passive: true});
document.addEventListener("touchmove", (e) => {
  touchCurrentX = e.touches[0].clientX;
  const card = document.getElementById("card");
  if (card) {
    const dx = touchCurrentX - touchStartX;
    card.style.transform = `translateX(${dx}px)`;
    card.style.opacity = Math.max(0.5, 1 - Math.abs(dx) / 400);
  }
});
document.addEventListener("touchend", () => {
  const dx = touchCurrentX - touchStartX;
  const card = document.getElementById("card");
  if (Math.abs(dx) > 80 && currentIndex < REPOS.length) {
    swipe(dx > 0 ? "right" : "left");
  } else if (card) {
    card.style.transform = "";
    card.style.opacity = "";
  }
});

// Init
render();
</script>
</body>
</html>"""
```

- [ ] **Step 2: Commit**

```bash
git add template.py
git commit -m "feat: add self-contained swipe UI HTML template"
```

---

### Task 4: Integrate everything in newsletter.py main()

**Files:**
- Modify: `newsletter.py` (extend `main()` to call insights + generate HTML)

- [ ] **Step 1: Add imports at top of `newsletter.py`**

After the existing imports at the top of the file, add:

```python
from insights import generate_insights
from template import generate_html
```

- [ ] **Step 2: Add HTML generation to end of `main()`**

Add after the `create_issue(...)` call at the end of `main()`, before `if __name__`:

```python
    # --- Swipe page generation ---
    print("\n7. Generating swipe page...")

    # Build repo data for swipe UI
    swipe_repos = []
    unique_repos = list(dict.fromkeys(
        star["repo"] for star in all_stars
    ))

    for repo_name in unique_repos:
        meta = get_repo_metadata(repo_name)
        if not meta:
            continue
        swipe_repos.append({
            "name": repo_name,
            "description": meta.get("description") or "",
            "topics": (meta.get("topics") or [])[:3],
            "stars": meta.get("stargazers_count", 0),
            "network_users": repo_star_count.get(repo_name, []),
            "readme": get_repo_readme(repo_name),
        })

    # Generate insights
    print("8. Generating insights...")
    insights = generate_insights([
        {
            "name": r["name"],
            "description": r["description"],
            "topics": r["topics"],
            "stars": r["stars"],
            "readme": r["readme"][:4000] if r["readme"] else "",
        }
        for r in swipe_repos
    ])

    # Merge insights and rename readme field
    for repo in swipe_repos:
        repo["insight"] = insights.get(repo["name"])
        repo["readme_html"] = repo.pop("readme")

    # Generate and write HTML
    print("9. Writing dist/index.html...")
    os.makedirs("dist", exist_ok=True)
    html = generate_html(swipe_repos)
    with open("dist/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"   Swipe page generated with {len(swipe_repos)} repos")
```

- [ ] **Step 3: Commit**

```bash
git add newsletter.py
git commit -m "feat: integrate insights + HTML generation into newsletter pipeline"
```

---

### Task 5: Add .gitignore for dist/

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Create `.gitignore`**

```
dist/
__pycache__/
*.pyc
.env
.superpowers/
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add gitignore for dist/ and pycache"
```

---

### Task 6: Update GitHub Actions workflow

**Files:**
- Modify: `.github/workflows/newsletter.yml`

- [ ] **Step 1: Update permissions and add deploy step**

Replace the full file with:

```yaml
name: StarGazer Weekly Newsletter

on:
  schedule:
    - cron: '0 9 * * 1'
  workflow_dispatch:

permissions:
  issues: write
  contents: write
  pages: write
  id-token: write

jobs:
  newsletter:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4.2.2

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install requests

      - name: Generate newsletter and swipe page
        run: python newsletter.py
        env:
          GITHUB_TOKEN: ${{ secrets.GH_PAT }}
          DAYS: 7
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./dist
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/newsletter.yml
git commit -m "feat: add GitHub Pages deploy step and LLM API key env vars"
```

---

### Task 7: Remove python-dotenv dependency

**Files:**
- Modify: `.github/workflows/newsletter.yml` (already done in Task 6)
- Verify: `newsletter.py` no longer imports `dotenv`

- [ ] **Step 1: Verify newsletter.py doesn't use dotenv**

Check current `newsletter.py` imports — the file currently does NOT import dotenv (it was removed in a previous refactor). The workflow previously installed `python-dotenv` but Task 6 already removed it from `pip install`. Nothing to do.

- [ ] **Step 2: Commit (skip if no changes)**

No changes needed — already handled by Task 6.

---

### Task 8: End-to-end local test

**Files:** None (verification only)

- [ ] **Step 1: Run the pipeline locally**

```bash
GITHUB_TOKEN=<your-pat> python newsletter.py
```

Expected output:
```
1. Getting current user...
...
7. Generating swipe page...
8. Generating insights...
  DeepWiki: owner/repo... found
  DeepWiki: owner/repo2... not found
  LLM: generating insights for N repos...
9. Writing dist/index.html...
   Swipe page generated with N repos
```

- [ ] **Step 2: Verify dist/index.html exists and opens correctly**

```bash
ls -la dist/index.html
```

Open `dist/index.html` in a browser. Verify:
- Cards render with repo info, topics, star count
- AI insight box shows when insight data exists
- README panel shows rendered HTML on desktop
- Swipe buttons work (skip / like)
- Arrow keys work
- Summary page shows after all cards
- Mobile view (resize to <768px) hides README panel

- [ ] **Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: address issues found during local testing"
```

---

### Task 9: Enable GitHub Pages in repo settings

**Files:** None (manual GitHub configuration)

- [ ] **Step 1: Enable GitHub Pages**

Go to repo Settings → Pages → Source: select "Deploy from a branch" → Branch: `gh-pages` / root.

This is a one-time manual step. After the first workflow run pushes to `gh-pages`, the site will be live at `https://<username>.github.io/stargazer_newsletter/`.

- [ ] **Step 2: Trigger workflow to verify deployment**

```bash
gh workflow run newsletter.yml
```

Wait for completion, then verify the Pages URL loads the swipe interface.
