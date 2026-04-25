"""
Weekly update script for Econy.
- Checks hehonghui/awesome-english-ebooks for new Economist and New Yorker issues
- Downloads new PDFs, runs full pipeline, translates titles
- Copies to docs/, commits and pushes to GitHub

Run: python3 scripts/update.py
Schedule: every Saturday at noon (see cron setup below)
"""

import os, sys, json, re, subprocess, urllib.request, time
from pathlib import Path

ROOT = Path(__file__).parent.parent
PDFS = ROOT / 'pdfs'
DOCS = ROOT / 'docs'
LOG  = ROOT / 'scripts' / 'update.log'

MAGAZINES = {
    'economist': {
        'api':    'https://api.github.com/repos/hehonghui/awesome-english-ebooks/contents/01_economist',
        'raw':    'https://raw.githubusercontent.com/hehonghui/awesome-english-ebooks/master/01_economist/{folder}/{filename}',
        'folder': lambda name: name,                            # e.g. te_2026.04.18
        'date':   lambda name: name.replace('te_', '').replace('.', '-', 2),  # 2026-04-18
        'prefix': 'te_',
        'pdf':    lambda date: f'TheEconomist.{date.replace("-",".")}.pdf',
        'label':  'The Economist',
        'data':   ROOT / 'data' / 'economist',
    },
    'new_yorker': {
        'api':    'https://api.github.com/repos/hehonghui/awesome-english-ebooks/contents/02_new_yorker',
        'raw':    'https://raw.githubusercontent.com/hehonghui/awesome-english-ebooks/master/02_new_yorker/{folder}/{filename}',
        'folder': lambda name: name,                            # e.g. 2026.04.20
        'date':   lambda name: name.replace('.', '-', 2),      # 2026-04-20
        'prefix': '20',
        'pdf':    lambda date: f'new_yorker.{date.replace("-",".")}.pdf',
        'label':  'The New Yorker',
        'data':   ROOT / 'data' / 'new_yorker',
    },
}

# ── Helpers ──────────────────────────────────────────────────────────────────

def log(msg):
    line = f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {msg}'
    print(line)
    with open(LOG, 'a') as f:
        f.write(line + '\n')

def api_get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'econy-updater'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def run(cmd, timeout=600):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

def notebooklm(args, timeout=120):
    out, err, code = run(f'notebooklm {args}', timeout=timeout)
    return out

def normalize(s):
    return (s.replace('\u2019',"'").replace('\u2018',"'")
             .replace('\u201c','"').replace('\u201d','"')
             .replace('\u2014','--'))

def get_answer(raw):
    try:
        data = json.loads(raw)
        return data.get('answer', '')
    except:
        idx = raw.find('"answer": "') + len('"answer": "')
        end = raw.find('",\n  "conversation_id"')
        if end == -1:
            end = raw.find('",\n "conversation_id"')
        if idx > 0 and end > 0:
            s = raw[idx:end].replace('\\n','\n').replace('\\"','"').replace('\\\\','\\')
            return re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1),16)), s)
    return ''

def extract_json_block(text):
    m = re.search(r'```json\n(\{.*?\})\n```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except:
            pass
    return None

# ── Detect new issues ─────────────────────────────────────────────────────────

def get_existing_dates(mag_key):
    data_dir = MAGAZINES[mag_key]['data']
    return {p.stem for p in data_dir.glob('????-??-??.json')}

def get_available_issues(mag_key):
    cfg = MAGAZINES[mag_key]
    folders = api_get(cfg['api'])
    issues = []
    for item in folders:
        name = item['name']
        if name.startswith(cfg['prefix']) and item['type'] == 'dir':
            date = cfg['date'](name)
            issues.append({'name': name, 'date': date})
    return sorted(issues, key=lambda x: x['date'], reverse=True)

def find_pdf_in_folder(mag_key, folder_name):
    """Find PDF, EPUB, or MOBI file in folder (tries PDF first as fallback)."""
    cfg = MAGAZINES[mag_key]
    api_url = cfg['api'] + '/' + folder_name
    extensions = ['.pdf', '.epub', '.mobi']

    try:
        files = api_get(api_url)
        for ext in extensions:
            for f in files:
                if f['name'].endswith(ext):
                    return f['name'], f['download_url']
    except:
        pass
    return None, None

# ── Translation via NotebookLM ────────────────────────────────────────────────

def translate_titles(nb_id, issue):
    """Translate all article titles in batches of 20."""
    all_articles = [(s['section'], a) for s in issue['toc'] for a in s['articles']]
    batch_size = 20
    translations = {}

    for i in range(0, len(all_articles), batch_size):
        batch = all_articles[i:i+batch_size]
        lines = '\n'.join(f'[{sec}] {a["title"]}' for sec, a in batch)
        prompt = f'请将以下文章标题翻译成中文，保持简洁准确。输出JSON格式：{{"titles": {{"英文标题": "中文标题"}}}}\\n\\n{lines}'
        escaped = prompt.replace('"', '\\"')
        out = notebooklm(f'ask "{escaped}" --notebook {nb_id} --json', timeout=120)
        answer = get_answer(out)
        data = extract_json_block(answer)
        if data and 'titles' in data:
            translations.update({normalize(k): v for k, v in data['titles'].items()})
        time.sleep(3)

    matched = 0
    for section in issue['toc']:
        for article in section['articles']:
            key = normalize(article['title'])
            if key in translations:
                article['title_zh'] = translations[key]
                matched += 1
            elif not article.get('title_zh'):
                article['title_zh'] = article['title']
            if not article.get('subtitle_zh'):
                article['subtitle_zh'] = article.get('subtitle', '')

    log(f'   Translated {matched}/{len(all_articles)} titles')

# ── Full pipeline for one new issue ──────────────────────────────────────────

def process_new_issue(mag_key, folder_name, date):
    cfg = MAGAZINES[mag_key]
    log(f'Processing {cfg["label"]} {date}')

    # Download file (PDF, EPUB, or MOBI)
    pdf_filename, dl_url = find_pdf_in_folder(mag_key, folder_name)
    if not pdf_filename:
        log(f'  ERROR: No file found (PDF/EPUB/MOBI) in {folder_name}')
        return False

    file_path = PDFS / pdf_filename
    if not file_path.exists():
        log(f'  Downloading {pdf_filename}...')
        urllib.request.urlretrieve(dl_url, file_path)
        log(f'  Downloaded: {file_path.stat().st_size // 1024}KB')

    # Import pipeline
    sys.path.insert(0, str(ROOT / 'scripts'))
    from pipeline import process_issue
    issue = process_issue(str(file_path), mag_key, date)

    # Translate titles using the notebook created by pipeline
    log(f'  Translating titles...')
    translate_titles(issue['notebook_id'], issue)

    # Save updated issue
    out_path = cfg['data'] / f'{date}.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(issue, f, ensure_ascii=False, indent=2)

    return True

# ── Update docs/ and app.js ───────────────────────────────────────────────────

def update_docs():
    """Sync data files and web assets into docs/."""
    import shutil

    # Sync data
    for mag_key in MAGAZINES:
        src = MAGAZINES[mag_key]['data']
        dst = DOCS / 'data' / mag_key
        dst.mkdir(parents=True, exist_ok=True)
        for f in src.glob('????-??-??.json'):
            shutil.copy2(f, dst / f.name)

    # Sync web assets
    for fname in ['index.html', 'style.css', 'app.js']:
        src = ROOT / 'web' / fname
        if src.exists():
            shutil.copy2(src, DOCS / fname)

def update_app_js(all_issues):
    """Rebuild the ISSUES constant in docs/app.js with all available issues."""
    app_js = DOCS / 'app.js'
    with open(app_js, encoding='utf-8') as f:
        content = f.read()

    def build_list(issues):
        lines = []
        for date in sorted(issues, reverse=True):
            lines.append(f"    {{ date: '{date}', label: '{date}', file: 'data/{issues[date]}/{date}.json' }},")
        return '\n'.join(lines)

    econ = {p.stem: 'economist' for p in (MAGAZINES['economist']['data']).glob('????-??-??.json')}
    ny   = {p.stem: 'new_yorker' for p in (MAGAZINES['new_yorker']['data']).glob('????-??-??.json')}

    new_issues = f"""const ISSUES = {{
  economist: [
{build_list(econ)}
  ],
  new_yorker: [
{build_list(ny)}
  ],
}};"""

    content = re.sub(r'const ISSUES = \{.*?\};', new_issues, content, flags=re.DOTALL)
    with open(app_js, 'w', encoding='utf-8') as f:
        f.write(content)
    log(f'  app.js updated: {len(econ)} Economist, {len(ny)} New Yorker issues')

# ── Git push ──────────────────────────────────────────────────────────────────

def git_push(new_dates):
    os.chdir(ROOT)
    run('git add docs/')
    msg = f'Auto-update: add {", ".join(new_dates)}'
    out, err, code = run(f'git commit -m "{msg}"')
    if code != 0:
        log(f'  Nothing to commit or error: {err}')
        return
    out, err, code = run('git push', timeout=60)
    if code == 0:
        log(f'  Pushed to GitHub.')
    else:
        log(f'  Push failed: {err}')

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log('=== Econy weekly update started ===')
    PDFS.mkdir(exist_ok=True)
    new_dates = []

    for mag_key in MAGAZINES:
        existing = get_existing_dates(mag_key)
        log(f'{mag_key}: {len(existing)} existing issues')

        available = get_available_issues(mag_key)
        new = [i for i in available if i['date'] not in existing]

        if not new:
            log(f'{mag_key}: no new issues found')
            continue

        # Process only the latest new issue per run to limit API usage
        issue = new[0]
        log(f'{mag_key}: new issue found — {issue["date"]}')
        success = process_new_issue(mag_key, issue['name'], issue['date'])
        if success:
            new_dates.append(issue['date'])

    if new_dates:
        log('Updating docs/ and pushing to GitHub...')
        update_docs()
        update_app_js(None)
        git_push(new_dates)
    else:
        log('No new issues. Nothing to push.')

    log('=== Done ===\n')

if __name__ == '__main__':
    main()
