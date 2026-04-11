# Econy — Magazine Digest

A local + GitHub-hosted website that shows Chinese summaries of The Economist and The New Yorker, auto-updated weekly via NotebookLM.

Live site: **https://lakershark.github.io/econy/**

---

## What It Does

For each issue of The Economist and The New Yorker (since 2026):
- Downloads the PDF from [hehonghui/awesome-english-ebooks](https://github.com/hehonghui/awesome-english-ebooks)
- Uses NotebookLM to extract the table of contents and generate detailed Chinese summaries per article
- Displays everything on a clean website with collapsible articles, search, and keyboard navigation

---

## Project Structure

```
econy/
├── docs/                        ← GitHub Pages root (auto-generated, do not edit manually)
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── data/
│       ├── economist/           ← per-issue JSON files
│       └── new_yorker/
├── data/                        ← master data (source of truth)
│   ├── economist/
│   │   ├── 2026-04-11.json
│   │   ├── 2026-04-11_briefing.md
│   │   └── ...
│   └── new_yorker/
├── pdfs/                        ← downloaded PDFs (not committed to git)
├── web/                         ← development web files (source of truth for HTML/CSS/JS)
│   ├── index.html
│   ├── style.css
│   └── app.js
└── scripts/
    ├── pipeline.py              ← full processing pipeline for one issue
    ├── apply_translations.py    ← add Chinese title translations
    ├── update.py                ← weekly auto-update script (run by cron)
    └── update.log               ← log of all auto-update runs
```

---

## Setup Steps Performed

### 1. NotebookLM Authentication
```bash
notebooklm login          # opens browser for Google OAuth
notebooklm status         # verify authentication
notebooklm language set zh_Hans   # set output language to Simplified Chinese
```

### 2. Magazine Sources
PDFs are downloaded from:
- **Economist:** `https://raw.githubusercontent.com/hehonghui/awesome-english-ebooks/master/01_economist/te_YYYY.MM.DD/TheEconomist.YYYY.MM.DD.pdf`
- **New Yorker:** `https://raw.githubusercontent.com/hehonghui/awesome-english-ebooks/master/02_new_yorker/YYYY.MM.DD/new_yorker.YYYY.MM.DD.pdf`

Update schedule in source repo:
- **Economist:** every Friday at 11 PM
- **New Yorker:** every Saturday morning

### 3. Processing Pipeline (per issue)
For each issue, `scripts/pipeline.py` does:

1. **Create NotebookLM notebook** — `notebooklm create "The Economist YYYY-MM-DD"`
2. **Upload PDF** — `notebooklm source add issue.pdf`
3. **Wait for processing** — `notebooklm source wait`
4. **Extract TOC** — ask NotebookLM for all sections and article titles as JSON
5. **Generate briefing doc** — `notebooklm generate report --format briefing-doc --language zh_Hans` (saved as `_briefing.md`)
6. **Generate per-article summaries** — two batches of ~35 articles each, 250–800 characters per article in Chinese
7. **Save** to `data/economist/YYYY-MM-DD.json`

### 4. Title Translation
`scripts/apply_translations.py` adds `title_zh` and `subtitle_zh` fields to every article in the JSON. New issues processed by `update.py` auto-translate via NotebookLM in batches of 20.

### 5. Data File Format
Each `data/economist/YYYY-MM-DD.json` looks like:
```json
{
  "magazine": "The Economist",
  "issue_date": "2026-04-11",
  "notebook_id": "fb464a0e-...",
  "toc": [
    {
      "section": "Leaders",
      "articles": [
        {
          "title": "Donald Trump is the war's biggest loser",
          "title_zh": "特朗普是这场战争的最大输家",
          "subtitle": "There is a reason he wants an exit from Iran",
          "subtitle_zh": "他急于从伊朗脱身是有原因的",
          "summary": "详细中文摘要..."
        }
      ]
    }
  ]
}
```

### 6. Website
Built with plain HTML/CSS/JS — no frameworks. Features:
- Left sidebar: magazine → year → issue navigation
- Collapsible article rows with Chinese titles and summaries
- Keyboard navigation: `j/k` move, `Space` expand/collapse, `/` search, `Esc` clear
- Section names translated to Chinese (e.g. Leaders → 社论, Briefing → 深度报道)
- Expand all / Collapse all buttons

### 7. GitHub Pages Deployment
- Repo: `https://github.com/lakershark/econy`
- GitHub Pages serves from the `/docs` folder on the `main` branch
- Settings: **repo → Settings → Pages → Branch: main, Folder: /docs**
- Live URL: `https://lakershark.github.io/econy/`

To push a manual update:
```bash
cd /Users/Nimmersatt/Documents/claude_projects/econy
cp web/style.css web/app.js web/index.html docs/
cp data/economist/*.json docs/data/economist/
cp data/new_yorker/*.json docs/data/new_yorker/
git add docs/
git commit -m "Manual update"
git push
```

### 8. Weekly Auto-Update (cron)
`scripts/update.py` runs every Saturday at noon. It:
1. Checks the source GitHub repo API for new issues
2. Downloads the PDF
3. Runs the full pipeline
4. Translates titles
5. Updates `docs/` and pushes to GitHub

---

## Issues Processed

| Magazine | Issue Date | Articles | Summaries |
|---|---|---|---|
| The Economist | 2026-04-11 | 75 | 69 |
| The Economist | 2026-04-04 | 72 | 72 |
| The Economist | 2026-03-28 | 84 | 84 |
| The New Yorker | 2026-04-13 | 26 | 26 |
| The New Yorker | 2026-04-06 | 22 | 22 |
| The New Yorker | 2026-03-30 | 23 | 23 |

---

## Mac System Changes

### Cron Job (weekly auto-update)

A cron job was added to your Mac's user crontab.

**To view:**
```bash
crontab -l
```

**Current entry:**
```
0 12 * * 6 /Library/Frameworks/Python.framework/Versions/3.10/bin/python3 /Users/Nimmersatt/Documents/claude_projects/econy/scripts/update.py >> /Users/Nimmersatt/Documents/claude_projects/econy/scripts/update.log 2>&1
```
This runs every **Saturday at 12:00 PM**.

**To remove the cron job:**
```bash
crontab -l | grep -v "econy" | crontab -
```

**To pause temporarily** (comment it out):
```bash
crontab -e
# Add a # at the start of the econy line
```

### NotebookLM CLI
Installed via pip:
```bash
pip install notebooklm-py
```
Auth stored at: `~/.notebooklm/storage_state.json`

**To remove:**
```bash
pip uninstall notebooklm-py
rm -rf ~/.notebooklm
```

### Local HTTP Server (development only)
A Python HTTP server was started for local testing:
```bash
# Start
cd /Users/Nimmersatt/Documents/claude_projects/econy
python3 -m http.server 8765 &

# Stop
pkill -f "http.server 8765"
```
This is **not persistent** — it does not survive reboots and is only needed for local development. The live site on GitHub Pages does not require it.

---

## How to Process a New Issue Manually

```bash
cd /Users/Nimmersatt/Documents/claude_projects/econy

# 1. Download PDF
curl -L -o pdfs/TheEconomist.2026.05.02.pdf \
  "https://raw.githubusercontent.com/hehonghui/awesome-english-ebooks/master/01_economist/te_2026.05.02/TheEconomist.2026.05.02.pdf"

# 2. Run pipeline
python3 scripts/pipeline.py pdfs/TheEconomist.2026.05.02.pdf economist 2026-05-02

# 3. Translate titles (add entries to scripts/apply_translations.py first, then run)
python3 scripts/apply_translations.py

# 4. Update docs/ and push
cp data/economist/2026-05-02.json docs/data/economist/
# Update ISSUES array in docs/app.js to include the new date
git add docs/
git commit -m "Add Economist 2026-05-02"
git push
```

---

## Dependencies

- Python 3.10+
- `notebooklm-py` (`pip install notebooklm-py`)
- Git + GitHub account (lakershark)
- Google account with NotebookLM access (free tier)
