import json


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
    --bg: #0d1117;
    --surface: #161b22;
    --card-bg: #1c2128;
    --border: #30363d;
    --text-primary: #e6edf3;
    --text-secondary: #8b949e;
    --accent: #818cf8;
    --insight-from: rgba(99,102,241,0.08);
    --insight-to: rgba(139,92,246,0.08);
    --insight-border: rgba(99,102,241,0.2);
    --skip: #f85149;
    --like: #3fb950;
    --radius: 16px;
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
    height: 3px; background: var(--surface); z-index: 100;
  }
  .progress-fill {
    height: 100%; background: linear-gradient(90deg, var(--accent), #a78bfa);
    transition: width 300ms ease;
  }
  .progress-text {
    position: fixed; top: 10px; right: 20px;
    font-size: 12px; color: var(--text-secondary); z-index: 100;
  }

  /* Card scene — centers the card */
  .card-scene {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: 40px 24px 24px;
  }

  /* The card itself */
  .card {
    width: 100%;
    max-width: 900px;
    max-height: calc(100vh - 80px);
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    box-shadow: 0 8px 32px rgba(0,0,0,0.4), 0 2px 8px rgba(0,0,0,0.2);
    display: flex;
    overflow: hidden;
    transition: transform 300ms ease, opacity 300ms ease;
  }
  .card.swipe-left {
    transform: translateX(-120%) rotate(-8deg); opacity: 0;
  }
  .card.swipe-right {
    transform: translateX(120%) rotate(8deg); opacity: 0;
  }

  /* Left side — repo info */
  .card-front {
    width: 40%;
    min-width: 320px;
    padding: 28px;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    border-right: 1px solid var(--border);
  }

  .repo-header {
    display: flex; align-items: center; gap: 12px; margin-bottom: 16px;
  }
  .repo-avatar {
    width: 48px; height: 48px; border-radius: 12px;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 20px; color: white; flex-shrink: 0;
  }
  .repo-name { font-weight: 600; font-size: 15px; word-break: break-all; }
  .repo-stars { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }

  .repo-desc {
    font-size: 14px; color: var(--text-secondary);
    line-height: 1.6; margin-bottom: 16px;
  }

  .topics {
    display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 16px;
  }
  .topic {
    background: rgba(129,140,248,0.1); color: var(--accent);
    padding: 4px 10px; border-radius: 12px; font-size: 11px;
    border: 1px solid rgba(129,140,248,0.15);
  }

  .insight-box {
    background: linear-gradient(135deg, var(--insight-from), var(--insight-to));
    border: 1px solid var(--insight-border);
    border-radius: 12px; padding: 14px; margin-bottom: 16px;
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
    border-top: 1px solid var(--border); padding-top: 12px; margin-top: auto;
  }
  .network-info span { color: var(--accent); }

  /* Swipe buttons */
  .swipe-buttons {
    display: flex; gap: 20px; justify-content: center;
    margin-top: 20px; padding-top: 16px;
    border-top: 1px solid var(--border);
  }
  .btn-skip, .btn-like {
    width: 56px; height: 56px; border-radius: 50%;
    border: 2px solid; display: flex; align-items: center;
    justify-content: center; cursor: pointer; background: transparent;
    transition: all var(--transition);
  }
  .btn-skip { border-color: var(--skip); color: var(--skip); }
  .btn-skip:hover { background: rgba(248,81,73,0.1); transform: scale(1.1); }
  .btn-like { border-color: var(--like); color: var(--like); }
  .btn-like:hover { background: rgba(63,185,80,0.1); transform: scale(1.1); }
  .btn-skip:focus-visible, .btn-like:focus-visible {
    outline: 2px solid var(--accent); outline-offset: 2px;
  }

  /* Right side — README */
  .card-back {
    flex: 1; padding: 24px; overflow-y: auto;
  }
  .card-back .markdown-body {
    background: transparent; font-size: 14px;
  }
  .readme-empty {
    display: flex; align-items: center; justify-content: center;
    height: 100%; color: var(--text-secondary); font-size: 14px;
  }
  .readme-loading {
    display: flex; align-items: center; justify-content: center;
    height: 200px; color: var(--text-secondary); font-size: 14px;
  }
  .readme-loading .spinner {
    width: 20px; height: 20px; border: 2px solid var(--border);
    border-top-color: var(--accent); border-radius: 50%;
    animation: spin 0.6s linear infinite; margin-right: 10px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .readme-links {
    display: flex; gap: 10px; margin-bottom: 16px;
    padding-bottom: 12px; border-bottom: 1px solid var(--border);
  }
  .readme-links a {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 6px 14px; border-radius: 8px; font-size: 13px;
    font-weight: 500; text-decoration: none; transition: all var(--transition);
  }
  .readme-links a.gh-link {
    background: var(--surface); color: var(--text-primary);
  }
  .readme-links a.gh-link:hover { background: #2d333b; }
  .readme-links a.dw-link {
    background: rgba(99,102,241,0.12); color: var(--accent);
  }
  .readme-links a.dw-link:hover { background: rgba(99,102,241,0.22); }

  /* Unstar broken-star effect */
  .unstar-effect {
    position: fixed; top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    z-index: 1000; pointer-events: none; opacity: 0;
  }
  .unstar-effect.active { opacity: 1; }
  .star-container { position: relative; width: 80px; height: 80px; }
  .star-half {
    position: absolute; font-size: 64px; top: 0; left: 0;
  }
  .star-half.left {
    clip-path: inset(0 50% 0 0);
  }
  .star-half.right {
    clip-path: inset(0 0 0 50%);
  }
  /* Only animate when .active — so it replays each skip */
  .unstar-effect.active .star-half.left {
    animation: breakLeft 0.6s cubic-bezier(0.68, -0.55, 0.265, 1.55) forwards;
  }
  .unstar-effect.active .star-half.right {
    animation: breakRight 0.6s cubic-bezier(0.68, -0.55, 0.265, 1.55) forwards;
  }
  @keyframes breakLeft {
    0% { transform: translateX(0) rotate(0); opacity: 1; }
    100% { transform: translateX(-30px) translateY(60px) rotate(-35deg); opacity: 0; }
  }
  @keyframes breakRight {
    0% { transform: translateX(0) rotate(0); opacity: 1; }
    100% { transform: translateX(30px) translateY(60px) rotate(35deg); opacity: 0; }
  }

  /* Category badge */
  .category-badge {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 3px 10px; border-radius: 12px; font-size: 10px;
    font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;
    margin-bottom: 12px;
  }
  .category-badge.trending { background: rgba(248,81,73,0.12); color: #f85149; }
  .category-badge.shared { background: rgba(63,185,80,0.12); color: #3fb950; }
  .category-badge.weak-signal { background: rgba(210,153,34,0.12); color: #d29922; }
  .category-badge.other { background: rgba(139,148,158,0.12); color: #8b949e; }

  /* Card navigator */
  .nav-toggle {
    position: fixed; top: 10px; left: 16px; z-index: 101;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 6px 12px; color: var(--text-primary);
    font-size: 12px; font-family: inherit; cursor: pointer;
    display: flex; align-items: center; gap: 6px;
    transition: background var(--transition);
  }
  .nav-toggle:hover { background: #2d333b; }

  .nav-drawer {
    position: fixed; top: 0; left: 0; bottom: 0; width: 320px;
    background: var(--card-bg); border-right: 1px solid var(--border);
    z-index: 200; transform: translateX(-100%);
    transition: transform 250ms ease;
    display: flex; flex-direction: column;
    box-shadow: 4px 0 24px rgba(0,0,0,0.4);
  }
  .nav-drawer.open { transform: translateX(0); }

  .nav-header {
    padding: 16px; border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between;
  }
  .nav-header h3 { font-size: 14px; font-weight: 600; }
  .nav-close {
    background: none; border: none; color: var(--text-secondary);
    cursor: pointer; padding: 4px; font-size: 18px; line-height: 1;
  }

  .nav-section-label {
    font-size: 10px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.5px; padding: 12px 16px 4px;
    color: var(--text-secondary);
  }

  .nav-list {
    flex: 1; overflow-y: auto; list-style: none;
  }
  .nav-item {
    padding: 8px 16px; cursor: pointer; font-size: 13px;
    border-left: 3px solid transparent;
    transition: background var(--transition);
    display: flex; align-items: center; gap: 8px;
  }
  .nav-item:hover { background: var(--surface); }
  .nav-item.active {
    background: rgba(129,140,248,0.08);
    border-left-color: var(--accent);
    color: var(--accent);
  }
  .nav-item.seen { opacity: 0.5; }
  .nav-item .nav-stars {
    font-size: 11px; color: var(--text-secondary); margin-left: auto;
  }

  .nav-overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.5);
    z-index: 199; opacity: 0; pointer-events: none;
    transition: opacity 200ms ease;
  }
  .nav-overlay.open { opacity: 1; pointer-events: auto; }

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
    padding: 12px 0; border-bottom: 1px solid var(--border);
  }
  .summary .liked-list a {
    color: var(--accent); text-decoration: none; font-weight: 500;
  }
  .summary .liked-list a:hover { text-decoration: underline; }
  .summary .liked-list .desc {
    font-size: 13px; color: var(--text-secondary); margin-top: 4px;
  }

  /* ===== Mobile: card flip ===== */
  @media (max-width: 768px) {
    .card-scene { padding: 40px 12px 12px; align-items: flex-start; }

    .card {
      flex-direction: column;
      max-width: 100%;
      max-height: none;
      background: transparent;
      border: none;
      box-shadow: none;
      overflow: visible;
      /* 3D flip setup */
      perspective: 1200px;
    }

    /* Flip container */
    .card-inner {
      position: relative;
      width: 100%;
      min-height: calc(100vh - 60px);
      transition: transform 0.5s ease;
      transform-style: preserve-3d;
    }
    .card.flipped .card-inner {
      transform: rotateY(180deg);
    }

    .card-front, .card-back {
      position: absolute; top: 0; left: 0; width: 100%; height: 100%;
      backface-visibility: hidden;
      -webkit-backface-visibility: hidden;
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: 0 8px 32px rgba(0,0,0,0.4);
      overflow-y: auto;
    }

    .card-front {
      min-width: unset;
      border-right: none;
    }

    .card-back {
      transform: rotateY(180deg);
    }

    .flip-hint {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      font-size: 12px;
      color: var(--text-secondary);
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid var(--border);
    }

    /* Back button on back face */
    .back-btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 16px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      color: var(--text-primary);
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      margin-bottom: 16px;
      transition: background var(--transition);
    }
    .back-btn:hover { background: #2d333b; }
  }

  /* Desktop: no flip, side-by-side */
  @media (min-width: 769px) {
    .card-inner { display: contents; }
    .flip-hint { display: none; }
    .back-btn { display: none; }
  }

  /* Reduced motion */
  @media (prefers-reduced-motion: reduce) {
    .card, .progress-fill, .card-inner { transition: none; }
  }
</style>
</head>
<body>

<div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
<div class="progress-text" id="progressText"></div>

<div class="unstar-effect" id="unstarEffect">
  <div class="star-container">
    <span class="star-half left">&#11088;</span>
    <span class="star-half right">&#11088;</span>
  </div>
</div>

<button class="nav-toggle" onclick="toggleNav()" aria-label="Open card navigator">
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12h18M3 6h18M3 18h18"/></svg>
  <span id="navLabel">Browse</span>
</button>

<div class="nav-overlay" id="navOverlay" onclick="toggleNav()"></div>
<div class="nav-drawer" id="navDrawer">
  <div class="nav-header">
    <h3>All Repos</h3>
    <button class="nav-close" onclick="toggleNav()" aria-label="Close">&times;</button>
  </div>
  <ul class="nav-list" id="navList"></ul>
</div>

<div id="app"></div>

<script>
const REPOS = {{DATA}};
let currentIndex = 0;
const liked = [];
const skipped = [];
const readmeCache = {};
let cardFlipped = false;
const seenSet = new Set();

const CATEGORY_LABELS = {
  "trending": "Trending",
  "shared": "Shared Interest",
  "weak-signal": "Weak Signal",
  "other": "Others"
};

function buildNav() {
  const list = document.getElementById("navList");
  let currentCat = null;
  let html = "";
  REPOS.forEach((r, i) => {
    const cat = r.category || "other";
    if (cat !== currentCat) {
      currentCat = cat;
      html += `<li class="nav-section-label">${CATEGORY_LABELS[cat] || cat}</li>`;
    }
    const shortName = r.name.split("/")[1] || r.name;
    html += `<li class="nav-item${i === currentIndex ? ' active' : ''}${seenSet.has(i) ? ' seen' : ''}" data-idx="${i}" onclick="jumpTo(${i})">
      <span>${escHtml(shortName)}</span>
      <span class="nav-stars">${formatNum(r.stars)}</span>
    </li>`;
  });
  list.innerHTML = html;
}

function toggleNav() {
  const d = document.getElementById("navDrawer");
  const o = document.getElementById("navOverlay");
  const open = d.classList.toggle("open");
  o.classList.toggle("open", open);
  if (open) buildNav();
}

function jumpTo(idx) {
  currentIndex = idx;
  toggleNav();
  render();
}

function render() {
  if (currentIndex >= REPOS.length) {
    renderSummary();
    return;
  }
  const repo = REPOS[currentIndex];
  seenSet.add(currentIndex);
  cardFlipped = false;
  updateProgress();
  const cat = repo.category || "other";
  const catLabel = CATEGORY_LABELS[cat] || cat;

  const app = document.getElementById("app");
  app.innerHTML = `
    <div class="card-scene">
      <div class="card" id="card">
        <div class="card-inner" id="cardInner">
          <div class="card-front">
            <span class="category-badge ${cat}">${catLabel}</span>
            <div class="repo-header">
              <div class="repo-avatar">${repo.name.charAt(0).toUpperCase()}</div>
              <div>
                <div class="repo-name">${escHtml(repo.name)}</div>
                <div class="repo-stars"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:-2px;margin-right:2px;"><path d="M12 2l2.4 7.4H22l-6 4.6 2.3 7L12 16.4 5.7 21l2.3-7L2 9.4h7.6z"/></svg>${formatNum(repo.stars)}</div>
              </div>
            </div>
            <div class="repo-desc">${escHtml(repo.description || "No description")}</div>
            <div class="topics">
              ${(repo.topics || []).map(t => `<span class="topic">${escHtml(t)}</span>`).join("")}
            </div>
            ${repo.insight ? `
              <div class="insight-box">
                <div class="insight-label"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:-2px;margin-right:4px;"><path d="M12 2l2.4 7.4H22l-6 4.6 2.3 7L12 16.4 5.7 21l2.3-7L2 9.4h7.6z"/></svg>Deepwiki/AI Insight</div>
                <div class="insight-text">${escHtml(repo.insight)}</div>
              </div>
            ` : ""}
            <div class="network-info">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:-2px;margin-right:4px;"><path d="M16 11c1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3 1.34 3 3 3zm-8 0c1.66 0 3-1.34 3-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>
              starred by <span>${(repo.network_users || []).join(", ")}</span>
            </div>
            <div class="flip-hint" onclick="flipCard()">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>
              Tap to see README
            </div>
            <div class="swipe-buttons">
              <button class="btn-skip" onclick="event.stopPropagation();swipe('left')" aria-label="Skip"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg></button>
              <button class="btn-like" onclick="event.stopPropagation();swipe('right')" aria-label="Like"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M20 6L9 17l-5-5"/></svg></button>
            </div>
          </div>
          <div class="card-back">
            <button class="back-btn" onclick="event.stopPropagation();flipCard()">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>
              Back to card
            </button>
            <div class="readme-links">
              <a class="gh-link" href="https://github.com/${repo.name}" target="_blank" onclick="event.stopPropagation()">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
                GitHub
              </a>
              <a class="dw-link" href="https://deepwiki.com/${repo.name}" target="_blank" onclick="event.stopPropagation()">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>
                DeepWiki
              </a>
            </div>
            <div id="readmeContent" class="readme-loading"><div class="spinner"></div>Loading README...</div>
          </div>
        </div>
      </div>
    </div>
  `;
  fetchReadme(repo.name);
}

function flipCard() {
  const card = document.getElementById("card");
  if (!card) return;
  cardFlipped = !cardFlipped;
  card.classList.toggle("flipped", cardFlipped);
}

function fetchReadme(repoName) {
  const el = document.getElementById("readmeContent");
  if (!el) return;

  if (readmeCache[repoName] !== undefined) {
    el.className = "markdown-body";
    el.innerHTML = readmeCache[repoName] || '<div class="readme-empty">No README available</div>';
    return;
  }

  fetch(`https://api.github.com/repos/${repoName}/readme`, {
    headers: { "Accept": "application/vnd.github.html" }
  })
  .then(r => {
    if (!r.ok) throw new Error(r.status);
    return r.text();
  })
  .then(html => {
    readmeCache[repoName] = html;
    const current = REPOS[currentIndex];
    if (current && current.name === repoName) {
      el.className = "markdown-body";
      el.innerHTML = html;
    }
  })
  .catch(() => {
    readmeCache[repoName] = "";
    const current = REPOS[currentIndex];
    if (current && current.name === repoName) {
      el.className = "";
      el.innerHTML = '<div class="readme-empty">No README available</div>';
    }
  });
}

function swipe(direction) {
  const card = document.getElementById("card");
  const repo = REPOS[currentIndex];

  // If card is flipped, flip back first
  if (cardFlipped) {
    cardFlipped = false;
    card.classList.remove("flipped");
  }

  if (direction === "right") {
    liked.push(repo);
    window.open(`https://github.com/${repo.name}`, "_blank");
    card.classList.add("swipe-right");
  } else {
    skipped.push(repo);
    const fx = document.getElementById("unstarEffect");
    // Force animation restart by cloning inner content
    fx.classList.remove("active");
    const sc = fx.querySelector(".star-container");
    const clone = sc.cloneNode(true);
    sc.replaceWith(clone);
    // Trigger reflow then activate
    void fx.offsetWidth;
    fx.classList.add("active");
    setTimeout(() => fx.classList.remove("active"), 700);
    card.classList.add("swipe-left");
  }

  setTimeout(() => { currentIndex++; render(); }, 350);
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
              <span style="color: var(--text-secondary); font-size: 12px;"> <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:-1px;"><path d="M12 2l2.4 7.4H22l-6 4.6 2.3 7L12 16.4 5.7 21l2.3-7L2 9.4h7.6z"/></svg> ${formatNum(r.stars)}</span>
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
    `Card ${currentIndex + 1} of ${REPOS.length}`;
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
  else if (e.key === "ArrowRight" || e.key === "Enter") swipe("right");
  else if (e.key === " ") { e.preventDefault(); flipCard(); }
});

// Touch swipe (horizontal) — only on card-front, not while scrolling back
let touchStartX = 0;
let touchStartY = 0;
let touchCurrentX = 0;
let isSwiping = false;

document.addEventListener("touchstart", (e) => {
  touchStartX = e.touches[0].clientX;
  touchStartY = e.touches[0].clientY;
  touchCurrentX = touchStartX;
  isSwiping = false;
}, {passive: true});

document.addEventListener("touchmove", (e) => {
  const dx = e.touches[0].clientX - touchStartX;
  const dy = e.touches[0].clientY - touchStartY;

  // Determine swipe intent: horizontal if dx > dy early on
  if (!isSwiping && Math.abs(dx) > 10 && Math.abs(dx) > Math.abs(dy) * 1.5) {
    isSwiping = true;
  }
  if (!isSwiping) return;

  touchCurrentX = e.touches[0].clientX;
  const card = document.getElementById("card");
  if (card && !cardFlipped) {
    card.style.transform = `translateX(${dx}px) rotate(${dx * 0.05}deg)`;
    card.style.opacity = Math.max(0.5, 1 - Math.abs(dx) / 400);
  }
}, {passive: true});

document.addEventListener("touchend", () => {
  if (!isSwiping) return;
  const dx = touchCurrentX - touchStartX;
  const card = document.getElementById("card");
  if (Math.abs(dx) > 80 && currentIndex < REPOS.length && !cardFlipped) {
    swipe(dx > 0 ? "right" : "left");
  } else if (card) {
    card.style.transform = "";
    card.style.opacity = "";
  }
  isSwiping = false;
});

// Init
render();
</script>
</body>
</html>"""
