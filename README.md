# 2028 Democratic Primary — Event Tracker

An auto-updating tracker for public events, appearances, and press clips for 2028 Democratic presidential primary contenders. Built with the same GitHub Actions + Vercel architecture as the Poll Tracker.

## Candidates Tracked
AOC · Newsom · Harris · Pritzker · Kelly · Booker · Shapiro · Khanna · Crow · Slotkin · Murphy · Buttigieg · Ossoff

## Features
- **Auto-fetched daily** via GitHub Actions + Anthropic API (web search)
- **5 views**: Overview, All Events, By Candidate, Early States, Press Clips
- **Fully editable**: Add, edit, and delete events manually from the UI
- **Early state matrix**: Tracks visits to IA, NH, NV, SC, GA
- **Press clips**: Links to media coverage, associated per event

## File Structure

```
├── .github/
│   └── workflows/
│       └── fetch-events.yml    ← GitHub Actions daily schedule
├── public/
│   └── events.json             ← Auto-updated event database
├── scripts/
│   └── fetch_events.py         ← Event-fetching script (Anthropic API)
├── src/
│   ├── App.jsx                 ← React tracker UI
│   └── main.jsx
├── index.html
├── package.json
└── vite.config.js
```

## Setup (~10 minutes)

### 1. Create your GitHub repo

```bash
git init
git add .
git commit -m "Initial commit"
gh repo create dem-event-tracker --public
git push -u origin main
```

### 2. Add your Anthropic API key as a GitHub Secret

1. Go to your repo on GitHub
2. Click **Settings → Secrets and variables → Actions**
3. Click **New repository secret**
4. Name: `ANTHROPIC_API_KEY`
5. Value: your key from https://console.anthropic.com

### 3. Enable workflow write permissions

1. Go to **Settings → Actions → General**
2. Scroll to **Workflow permissions**
3. Select **Read and write permissions**
4. Click **Save**

### 4. Deploy to Vercel

1. Go to https://vercel.com and sign in with GitHub
2. Click **Add New Project**
3. Import your `dem-event-tracker` repo
4. Leave all settings as default — Vercel will detect Vite automatically
5. Click **Deploy**

### 5. Test it

- Go to your repo → **Actions** tab
- Click **Fetch Candidate Events** → **Run workflow**
- Watch the logs — it should search the web per candidate and commit `public/events.json`
- Your Vercel site auto-redeploys with fresh data

## Editing Events

**Add/edit/delete** events directly from the UI using the forms. Manual changes are stored in your browser's localStorage and merged with the auto-fetched data. You can also edit `public/events.json` directly in GitHub's browser editor.

## Cost Estimate

- GitHub Actions: **free**
- Vercel hosting: **free**
- Anthropic API: ~$0.10–0.30 per daily run (searches for all 13 candidates with web search)

## Notes

- The script searches for events in the past 14 days for each candidate
- Deduplication is by `id` field — the script won't add duplicates
- Early states flagged: IA, NH, NV, SC, GA
- Significance is scored by the AI (high/medium/low) and can be overridden in the UI
