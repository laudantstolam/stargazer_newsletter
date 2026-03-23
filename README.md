# StarGazer Newsletter

Discover what your GitHub network is starring. Generates a weekly newsletter (GitHub Issue) and a Tinder-like swipe UI (GitHub Pages) to browse repos starred by people you follow.

## Features

- **Weekly Newsletter** — auto-posted as a GitHub Issue with trending repos, topics, shared interests, and weak-signal discoveries
- **Swipe UI** — a static HTML page where you swipe right to open a repo on GitHub, or left to skip. Includes AI-generated insights per repo
- **AI Insights** — 3-tier pipeline: DeepWiki (free) -> LLM (Claude/OpenAI/Gemini) -> no insight. Minimizes token cost by trying free sources first

## Setup

1. Fork this repo
2. Add `GH_PAT` in repo secrets — a Personal Access Token with `read:user` and `user:follow` scopes
3. (Optional) Add one of these for AI insights: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GEMINI_API_KEY`
4. Enable GitHub Pages (source: `gh-pages` branch) in repo settings
5. Trigger the workflow manually or wait for the Monday 9 AM UTC cron

## How It Works

The pipeline runs weekly via GitHub Actions:

1. Fetches your followed users and their recent stars (past 7 days)
2. Aggregates trending repos, topics, shared interests, and weak signals
3. Creates a GitHub Issue with the newsletter
4. Fetches README HTML and generates AI insights for each repo
5. Builds a self-contained `dist/index.html` with all data baked in
6. Deploys to GitHub Pages via `gh-pages` branch

## Swipe UI

Desktop: 40/60 split — repo info card on the left, rendered README on the right. Mobile: info card only with touch swipe gestures.

- Swipe right / arrow right / Enter — opens the repo on GitHub
- Swipe left / arrow left — skip to next
- End screen shows all liked repos with direct links

## Configuration

| Env Variable | Required | Description |
|---|---|---|
| `GH_PAT` | Yes | GitHub PAT with `read:user`, `user:follow` |
| `DAYS` | No | Lookback window in days (default: 7) |
| `ANTHROPIC_API_KEY` | No | Claude API key for AI insights |
| `OPENAI_API_KEY` | No | OpenAI API key (fallback) |
| `GEMINI_API_KEY` | No | Gemini API key (fallback) |

## Schedule

```
cron: '0 9 * * 1'  # Monday 9:00 AM UTC
```

Format: `<minutes> <hours> <day> <month> <weekday>`, `*` means all. Also supports manual trigger via `workflow_dispatch`.

## Sample

See newsletter samples in [Issues](https://github.com/laudantstolam/stargazer_newsletter/issues)