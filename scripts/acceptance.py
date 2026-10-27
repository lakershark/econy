"""
Acceptance gate for one published issue.

update.py used to report "success" whenever the pipeline didn't crash, and three
times (07-18, 10-17, 10-24) Tao found the gaps before the system did. Now an
issue only counts as done when all of these hold:

  data    — enough sections/articles for a full issue, every article has a real
            summary and a Chinese title
  local   — docs/ carries the same json and app.js lists the issue
  live    — GitHub Pages actually serves the new issue, and the served json
            passes the data check too

Usage (manual check of an issue, defaults to the newest):
  python3 scripts/acceptance.py [YYYY-MM-DD] [--no-live]
"""

import sys, json, re, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
SITE = 'https://lakershark.github.io/econy'

# Calibrated on 2026-07-11..10-24: every full Economist issue had 19-20
# sections and 71-79 articles; a partial TOC lands far below this.
MIN_SECTIONS = {'economist': 17}
MIN_ARTICLES = {'economist': 65}
# Real summaries are 250-800 zh chars; anything this short is a stub/error.
MIN_SUMMARY_CHARS = 100
CJK = re.compile(r'[\u4e00-\u9fff]')
# NotebookLM echoes the "[Section] " prompt prefix into its translations
# ("[本周世界] 政治"); 6 of 8 issues 09-05..10-24 went out like that unnoticed.
SECTION_PREFIX = re.compile(r'^\s*[\[【][^\]】]*[\]】]\s*')

LIVE_WAIT = 900       # Pages usually deploys in 1-3 min; allow for slow ones
LIVE_POLL = 30


def check_data(issue, magazine='economist'):
    """Return a list of problems (empty = pass)."""
    problems = []
    toc = issue.get('toc') or []
    arts = [a for s in toc for a in s.get('articles', [])]
    if len(toc) < MIN_SECTIONS.get(magazine, 1):
        problems.append(f'只有 {len(toc)} 个栏目（应 ≥{MIN_SECTIONS.get(magazine, 1)}）')
    if len(arts) < MIN_ARTICLES.get(magazine, 1):
        problems.append(f'只有 {len(arts)} 篇文章（应 ≥{MIN_ARTICLES.get(magazine, 1)}）')
    no_sum = [a['title'] for a in arts if len(a.get('summary') or '') < MIN_SUMMARY_CHARS]
    if no_sum:
        problems.append(f'{len(no_sum)}/{len(arts)} 篇缺摘要')
    no_zh = [a['title'] for a in arts if not CJK.search(a.get('title_zh') or '')]
    if no_zh:
        problems.append(f'{len(no_zh)}/{len(arts)} 个标题没有中文')
    prefixed = [a['title_zh'] for a in arts if SECTION_PREFIX.match(a.get('title_zh') or '')]
    if prefixed:
        problems.append(f'{len(prefixed)}/{len(arts)} 个中文标题带栏目前缀')
    return problems


def _issues_in_app_js(text):
    return set(re.findall(r"date: '(\d{4}-\d{2}-\d{2})'", text))


def check_local(magazine, date):
    problems = []
    src = ROOT / 'data' / magazine / f'{date}.json'
    dst = ROOT / 'docs' / 'data' / magazine / f'{date}.json'
    if not dst.exists():
        problems.append('docs/ 里没有这期的 json')
    elif dst.read_bytes() != src.read_bytes():
        problems.append('docs/ 里的 json 与 data/ 不一致')
    app_js = (ROOT / 'docs' / 'app.js').read_text(encoding='utf-8')
    if date not in _issues_in_app_js(app_js):
        problems.append('docs/app.js 的期刊列表里没有这期')
    return problems


def _fetch(url):
    # Cache-buster: Pages sits behind a CDN that can serve the old copy.
    req = urllib.request.Request(f'{url}?t={int(time.time())}',
                                 headers={'Cache-Control': 'no-cache'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8')


def check_live(magazine, date, wait=LIVE_WAIT, poll=LIVE_POLL):
    """Poll the live site until it serves a complete copy of the issue."""
    deadline = time.time() + wait
    problems = ['线上还没检查']
    while True:
        try:
            if date not in _issues_in_app_js(_fetch(f'{SITE}/app.js')):
                problems = ['线上网站还没有这期（app.js 未更新）']
            else:
                live = json.loads(_fetch(f'{SITE}/data/{magazine}/{date}.json'))
                problems = [f'线上：{p}' for p in check_data(live, magazine)]
        except Exception as e:
            problems = [f'线上取不到：{e}']
        if not problems or time.time() >= deadline:
            return problems
        time.sleep(poll)


def repair(issue, magazine, translate_titles, log=print):
    """One extra round of re-asking whatever the data check found missing,
    on the issue's existing notebook. Mutates `issue`; caller saves it."""
    sys.path.insert(0, str(ROOT / 'scripts'))
    import pipeline
    nb_id = issue.get('notebook_id')
    if not nb_id:
        log('  repair skipped: no notebook_id')
        return
    for a in (a for s in issue['toc'] for a in s['articles']):
        if len(a.get('summary') or '') < MIN_SUMMARY_CHARS:
            a.pop('summary', None)    # stubs count as missing, re-ask them too
    filled = pipeline.fill_missing_summaries(issue, nb_id, magazine)
    log(f'  repair: filled {filled} summaries')
    for a in (a for s in issue['toc'] for a in s['articles']):
        zh = a.get('title_zh') or ''
        if SECTION_PREFIX.match(zh):
            a['title_zh'] = zh = SECTION_PREFIX.sub('', zh)
        if not CJK.search(zh):
            a.pop('title_zh', None)   # translate_titles retries only these
    translate_titles(nb_id, issue)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    magazine = 'economist'
    data_dir = ROOT / 'data' / magazine
    date = args[0] if args else max(p.stem for p in data_dir.glob('????-??-??.json'))
    issue = json.loads((data_dir / f'{date}.json').read_text(encoding='utf-8'))
    problems = check_data(issue, magazine) + check_local(magazine, date)
    if '--no-live' not in sys.argv:
        problems += check_live(magazine, date, wait=0)
    print(f'{date}: ' + ('PASS' if not problems else 'FAIL — ' + '；'.join(problems)))
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
