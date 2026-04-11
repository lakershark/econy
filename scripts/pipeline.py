"""
Full pipeline for one magazine issue:
1. Create NotebookLM notebook
2. Upload PDF, wait for processing
3. Extract TOC
4. Generate long summaries (2 batches)
5. Save structured JSON

Usage: python3 scripts/pipeline.py <pdf_path> <magazine> <date>
  magazine: economist | new_yorker
  date: YYYY-MM-DD
"""

import sys, os, json, re, subprocess, time

def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

def notebooklm(args, timeout=120):
    cmd = f"notebooklm {args}"
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip()

def extract_json_block(text):
    text = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), text)
    m = re.search(r'```json\n(\{.*?\})\n```', text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    return None

def normalize(s):
    return s.replace('\u2019', "'").replace('\u2018', "'").replace('\u201c', '"').replace('\u201d', '"')

def get_answer(raw_output):
    """Extract answer string from notebooklm --json output, handling truncation."""
    try:
        data = json.loads(raw_output)
        return data.get('answer', '')
    except:
        idx = raw_output.find('"answer": "') + len('"answer": "')
        end = raw_output.find('",\n  "conversation_id"')
        if end == -1:
            end = raw_output.find('",\n "conversation_id"')
        if idx > 0 and end > 0:
            raw = raw_output[idx:end]
            answer = raw.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
            answer = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), answer)
            return answer
    return ''

def process_issue(pdf_path, magazine, date):
    mag_dir = 'data/economist' if magazine == 'economist' else 'data/new_yorker'
    out_path = f'{mag_dir}/{date}.json'
    os.makedirs(mag_dir, exist_ok=True)

    mag_label = 'The Economist' if magazine == 'economist' else 'The New Yorker'
    print(f'\n{"="*60}')
    print(f'Processing: {mag_label} {date}')
    print(f'{"="*60}')

    # 1. Create notebook
    print('1. Creating notebook...')
    out = notebooklm(f'create "{mag_label} {date}" --json')
    nb = json.loads(out)
    nb_id = nb['notebook']['id']
    print(f'   Notebook ID: {nb_id}')

    # 2. Add source
    print('2. Uploading PDF...')
    out = notebooklm(f'source add {pdf_path} --notebook {nb_id} --json')
    src = json.loads(out)
    src_id = src['source']['id']
    print(f'   Source ID: {src_id}')

    # 3. Wait for source
    print('3. Waiting for PDF processing...')
    notebooklm(f'source wait {src_id} --notebook {nb_id} --timeout 300', timeout=320)
    print('   Ready.')

    # 4. Get TOC
    print('4. Extracting table of contents...')
    if magazine == 'economist':
        toc_prompt = '请列出这期杂志的完整目录，包括每篇文章的：1) 栏目名称，2) 文章标题，3) 副标题（如有）。按杂志顺序列出所有文章，输出为JSON格式：{"sections": [{"section": "栏目名", "articles": [{"title": "标题", "subtitle": "副标题"}]}]}'
    else:
        toc_prompt = '请列出这期《纽约客》杂志的完整目录，包括每篇文章的：1) 栏目名称（如The Talk of the Town, Comment, Profiles, Fiction, Poetry, Reporting等），2) 文章标题，3) 副标题或作者（如有）。按杂志顺序列出所有文章，输出为JSON格式：{"sections": [{"section": "栏目名", "articles": [{"title": "标题", "subtitle": "副标题"}]}]}'

    out = notebooklm(f'ask "{toc_prompt}" --notebook {nb_id} --json', timeout=120)
    answer = get_answer(out)
    toc_data = extract_json_block(answer)

    if not toc_data:
        print('   ERROR: Could not parse TOC. Saving raw answer.')
        toc_data = {'sections': []}

    total_articles = sum(len(s['articles']) for s in toc_data.get('sections', []))
    print(f'   Found {len(toc_data.get("sections", []))} sections, {total_articles} articles')

    # Save intermediate
    issue = {
        'magazine': mag_label,
        'issue_date': date,
        'notebook_id': nb_id,
        'toc': toc_data.get('sections', [])
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(issue, f, ensure_ascii=False, indent=2)

    # 5. Generate briefing doc
    print('5. Generating briefing document...')
    out = notebooklm(f'generate report --format briefing-doc --notebook {nb_id} --language zh_Hans --json', timeout=60)
    try:
        task = json.loads(out)
        task_id = task['task_id']
        print(f'   Task ID: {task_id} — waiting...')
        notebooklm(f'artifact wait {task_id} --notebook {nb_id} --timeout 900', timeout=910)
        briefing_path = f'{mag_dir}/{date}_briefing.md'
        notebooklm(f'download report {briefing_path} --notebook {nb_id} --artifact {task_id}', timeout=60)
        print(f'   Briefing saved: {briefing_path}')
    except Exception as e:
        print(f'   Briefing doc failed (non-critical): {e}')

    # 6. Get per-article summaries
    articles_all = [(s['section'], a) for s in issue['toc'] for a in s['articles']]
    mid = len(articles_all) // 2

    def build_summary_prompt(articles_slice, mag):
        if mag == 'economist':
            header = '请为以下《经济学人》文章写详细中文摘要。Leaders和Briefing栏目每篇600-800字，其他栏目250-400字。涵盖核心论点、关键数据、背景分析和结论。输出JSON：{"summaries": {"英文标题": "中文摘要"}}\n\n'
        else:
            header = '请为以下《纽约客》文章写详细中文摘要，每篇300-500字，涵盖主题、叙事风格、核心观点和结论。输出JSON：{"summaries": {"英文标题": "中文摘要"}}\n\n'
        lines = []
        for section, art in articles_slice:
            lines.append(f'[{section}] {art["title"]}')
        return header + '\n'.join(lines)

    def fetch_summaries(prompt, nb_id):
        # Escape for shell
        escaped = prompt.replace('"', '\\"').replace('\n', '\\n')
        out = notebooklm(f'ask "{escaped}" --notebook {nb_id} --json', timeout=180)
        answer = get_answer(out)
        data = extract_json_block(answer)
        return data.get('summaries', {}) if data else {}

    print('6. Fetching summaries (batch 1/2)...')
    s1 = fetch_summaries(build_summary_prompt(articles_all[:mid], magazine), nb_id)
    print(f'   Got {len(s1)} summaries')

    print('   Fetching summaries (batch 2/2)...')
    s2 = fetch_summaries(build_summary_prompt(articles_all[mid:], magazine), nb_id)
    print(f'   Got {len(s2)} summaries')

    all_summaries = {normalize(k): v for d in [s1, s2] for k, v in d.items()}
    print(f'   Total: {len(all_summaries)} summaries')

    # Merge summaries
    matched = 0
    for section in issue['toc']:
        for article in section['articles']:
            key = normalize(article['title'])
            if key in all_summaries:
                article['summary'] = all_summaries[key]
                matched += 1
    print(f'   Merged {matched}/{total_articles}')

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(issue, f, ensure_ascii=False, indent=2)

    print(f'Done: {out_path}')
    return issue


if __name__ == '__main__':
    pdf_path = sys.argv[1]
    magazine = sys.argv[2]
    date = sys.argv[3]
    process_issue(pdf_path, magazine, date)
