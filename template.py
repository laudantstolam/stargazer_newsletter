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

  /* Unstar effect */
  .unstar-effect {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 1000;
    pointer-events: none;
    opacity: 0;
  }
  .unstar-effect.active {
    opacity: 1;
  }
  .star-container {
    position: relative;
    width: 80px;
    height: 80px;
  }
  .star {
    position: absolute;
    font-size: 64px;
    top: 0;
    left: 0;
    color: #fbbf24;
  }
  .star.left {
    clip-path: inset(0 50% 0 0);
    animation: breakLeft 0.6s cubic-bezier(0.68, -0.55, 0.265, 1.55) forwards;
  }
  .star.right {
    clip-path: inset(0 0 0 50%);
    animation: breakRight 0.6s cubic-bezier(0.68, -0.55, 0.265, 1.55) forwards;
  }
  @keyframes breakLeft {
    0% {
      transform: translateX(0) rotate(0);
      opacity: 1;
    }
    100% {
      transform: translateX(-30px) translateY(60px) rotate(-35deg);
      opacity: 0;
    }
  }
  @keyframes breakRight {
    0% {
      transform: translateX(0) rotate(0);
      opacity: 1;
    }
    100% {
      transform: translateX(30px) translateY(60px) rotate(35deg);
      opacity: 0;
    }
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

<div class="unstar-effect" id="unstarEffect">
  <div class="star-container">
    <span class="star left">⭐</span>
    <span class="star right">⭐</span>
  </div>
</div>

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
            <div class="repo-stars"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:-2px;margin-right:2px;"><path d="M12 2l2.4 7.4H22l-6 4.6 2.3 7L12 16.4 5.7 21l2.3-7L2 9.4h7.6z"/></svg>${formatNum(repo.stars)}</div>
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
    // Show unstar effect
    const unstarEffect = document.getElementById("unstarEffect");
    unstarEffect.classList.add("active");
    setTimeout(() => {
      unstarEffect.classList.remove("active");
    }, 600);
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
}, {passive: true});
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
