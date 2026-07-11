"""
Weekly update script for Econy.
- Checks hehonghui/awesome-english-ebooks for new issues (see ACTIVE_MAGAZINES)
- Downloads new PDFs, runs full pipeline, translates titles
- Copies to docs/, commits and pushes to GitHub

Run: python3 scripts/update.py
Schedule: every Saturday at noon (see cron setup below)
"""

import os, sys, json, re, subprocess, urllib.request, time, difflib
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

# Magazines actively checked for new issues each run.
# New Yorker disabled 2026-06-15 (per Tao): only The Economist is updated going
# forward. Existing New Yorker data stays on the site — it's just no longer
# fetched, processed, or sent to NotebookLM. To re-enable, add 'new_yorker' back.
ACTIVE_MAGAZINES = ['economist']

# ── Helpers ──────────────────────────────────────────────────────────────────

def log(msg):
    line = f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {msg}'
    print(line)
    with open(LOG, 'a') as f:
        f.write(line + '\n')

def notify(title, message, sound='default'):
    """Post a macOS Notification Center banner (works from the LaunchAgent's GUI session)."""
    try:
        script = (f'display notification {json.dumps(message)} '
                  f'with title {json.dumps(title)} sound name {json.dumps(sound)}')
        subprocess.run(['/usr/bin/osascript', '-e', script],
                       capture_output=True, timeout=15)
    except Exception as e:
        log(f'  notify failed (non-critical): {e}')

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

def notebooklm_ask(prompt, nb_id, timeout=180):
    # argv, not shell: prompts contain JSON templates and article titles whose
    # quotes/$ the shell would mangle (root cause of past TOC/translation loss).
    r = subprocess.run(['notebooklm', 'ask', prompt, '--notebook', nb_id, '--json'],
                       capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip()

def normalize(s):
    return (s.replace('\u2019',"'").replace('\u2018',"'")
             .replace('\u201c','"').replace('\u201d','"')
             .replace('\u2014','--'))

def merge_key(s):
    # NotebookLM does not echo titles verbatim (2026-07-11 it kept the
    # "[Section] " prefix from the prompt), so match on a normalized form.
    s = normalize(s).strip()
    s = re.sub(r'^\[[^\]]*\]\s*', '', s)
    return s.casefold()

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

def translate_titles(nb_id, issue, max_attempts=3):
    """Translate all article titles in batches of 20.

    NotebookLM often returns only a partial batch, so we retry the still-missing
    titles up to `max_attempts` times before falling back to the English title.
    """
    all_articles = [(s['section'], a) for s in issue['toc'] for a in s['articles']]
    batch_size = 20

    def pending():
        # A title counts as untranslated if missing or still equal to the English.
        return [(sec, a) for sec, a in all_articles
                if not a.get('title_zh') or a['title_zh'] == a['title']]

    for attempt in range(1, max_attempts + 1):
        todo = pending()
        if not todo:
            break
        log(f'   title translation attempt {attempt}: {len(todo)} remaining')
        translations = {}
        for i in range(0, len(todo), batch_size):
            batch = todo[i:i+batch_size]
            lines = '\n'.join(f'[{sec}] {a["title"]}' for sec, a in batch)
            prompt = f'请将以下文章标题翻译成中文，保持简洁准确。输出JSON格式：{{"titles": {{"英文标题": "中文标题"}}}}\n\n{lines}'
            out = notebooklm_ask(prompt, nb_id, timeout=120)
            answer = get_answer(out)
            data = extract_json_block(answer)
            if data and 'titles' in data:
                translations.update({merge_key(k): v for k, v in data['titles'].items()})
            time.sleep(3)
        for sec, a in todo:
            key = merge_key(a['title'])
            zh = translations.get(key)
            if zh is None:
                close = difflib.get_close_matches(key, list(translations), n=1, cutoff=0.8)
                if close:
                    zh = translations[close[0]]
            if zh and zh != a['title']:
                a['title_zh'] = zh

    # Fall back to English for anything still untranslated; fill subtitles.
    matched = 0
    for section in issue['toc']:
        for article in section['articles']:
            if article.get('title_zh') and article['title_zh'] != article['title']:
                matched += 1
            else:
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

KEEP_ISSUES = 5  # Keep only this many most recent issues per magazine in the UI

def update_app_js(all_issues):
    """Rebuild the ISSUES constant in docs/app.js with the latest KEEP_ISSUES issues."""
    app_js = DOCS / 'app.js'
    with open(app_js, encoding='utf-8') as f:
        content = f.read()

    def build_list(issues):
        lines = []
        dates = sorted(issues, reverse=True)[:KEEP_ISSUES]
        for date in dates:
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
    """Commit everything a run produced (site + source data + log) in ONE
    commit and push once. Multiple pushes minutes apart make GitHub Pages
    cancel the in-flight deployment and the follow-up one tends to 504
    (seen 2026-07-06)."""
    os.chdir(ROOT)
    run('git add docs/ data/ scripts/update.log')
    msg = f'Auto-update: add {", ".join(new_dates)}'
    out, err, code = run(f'git commit -m "{msg}"')
    if code != 0:
        log(f'  Nothing to commit or error: {err}')
    # Push failures are usually transient (Wi-Fi/DNS right after wake), so
    # retry with growing pauses. An unpushed commit rides along next week.
    for attempt in range(1, 4):
        out, err, code = run('git push', timeout=120)
        if code == 0:
            log(f'  Pushed to GitHub.')
            return True
        log(f'  Push failed (attempt {attempt}/3): {err}')
        if attempt < 3:
            time.sleep(60 * attempt)
    return False

# ── NotebookLM housekeeping ───────────────────────────────────────────────────

# Matches ONLY econy-generated notebooks, e.g. "The Economist 2026-06-13".
# Anything else (Bible studies, ARK reports, etc.) is never touched.
ECONY_NB_RE = re.compile(r'^The (Economist|New Yorker) (\d{4}-\d{2}-\d{2})$')

def cleanup_notebooks(keep=KEEP_ISSUES):
    """Delete old econy NotebookLM notebooks, keeping the `keep` most recent per
    magazine. Notebooks are just scratchpads — summaries/titles already live in
    data/*.json — so old ones only waste NotebookLM space."""
    out = notebooklm('list --json', timeout=60)
    try:
        data = json.loads(out)
    except Exception as e:
        log(f'  notebook cleanup skipped (list failed): {e}')
        return
    nbs = data if isinstance(data, list) else data.get('notebooks', [])

    by_mag = {}
    for n in nbs:
        title = n.get('title') or n.get('name', '')
        m = ECONY_NB_RE.match(title)
        if m:
            by_mag.setdefault(m.group(1), []).append((m.group(2), n.get('id'), title))

    deleted = 0
    for items in by_mag.values():
        items.sort(reverse=True)                 # newest date first
        for _date, nb_id, title in items[keep:]:  # everything past the kept window
            notebooklm(f'delete -n {nb_id} -y', timeout=60)
            deleted += 1
            log(f'  cleaned up old notebook: {title}')
    if deleted:
        log(f'  notebook cleanup: deleted {deleted}, kept up to {keep} per magazine')

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log('=== Econy weekly update started ===')
    PDFS.mkdir(exist_ok=True)
    new_dates = []
    failures = []

    for mag_key in ACTIVE_MAGAZINES:
        existing = get_existing_dates(mag_key)
        log(f'{mag_key}: {len(existing)} existing issues')

        available = get_available_issues(mag_key)
        # Forward-only: process issues newer than the newest we already have.
        # Never backfill old gaps — the UI shows only the 5 most recent anyway,
        # and backfilling would burn a NotebookLM notebook on issues nobody sees.
        latest = max(existing) if existing else '0000-00-00'
        new = [i for i in available if i['date'] > latest]

        if not new:
            log(f'{mag_key}: no new issues found')
            continue

        # Process only the latest new issue per run to limit API usage
        issue = new[0]
        log(f'{mag_key}: new issue found — {issue["date"]}')
        try:
            success = process_new_issue(mag_key, issue['name'], issue['date'])
        except Exception as e:
            success = False
            log(f'  ERROR processing {mag_key} {issue["date"]}: {e}')
        if success:
            new_dates.append(issue['date'])
        else:
            failures.append(f'{mag_key} {issue["date"]}')

    pushed = True
    if new_dates:
        log('Updating docs/ and pushing to GitHub...')
        update_docs()
        update_app_js(None)
        pushed = git_push(new_dates)
        cleanup_notebooks()
    else:
        log('No new issues. Nothing to push.')

    # Notify the outcome so Tao doesn't have to check manually each week
    if failures and new_dates:
        notify('Econy 部分更新 ⚠️',
               f'成功：{", ".join(new_dates)}；失败：{", ".join(failures)}（见 update.log）',
               sound='Basso')
    elif failures:
        notify('Econy 更新失败 ❌',
               f'失败：{", ".join(failures)}（见 update.log）', sound='Basso')
    elif new_dates and not pushed:
        notify('Econy 已处理、未发布 ⚠️',
               f'{", ".join(new_dates)} 已生成并提交本地，但 push 失败——网站还是旧的（见 update.log）',
               sound='Basso')
    elif new_dates:
        notify('Econy 更新成功 ✅', f'已添加 {", ".join(new_dates)}')
    else:
        notify('Econy 已检查 ✓', '本周没有新刊，无需更新')

    log('=== Done ===\n')

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        log('FATAL:\n' + traceback.format_exc())
        notify('Econy 更新崩溃 ❌', str(e)[:200] or '未知错误', sound='Basso')
        raise
