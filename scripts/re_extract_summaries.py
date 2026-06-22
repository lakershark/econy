"""
Re-extract summaries for an existing issue with improved batching.
Splits articles into 4 batches instead of 2 for better completion.

Usage: python3 scripts/re_extract_summaries.py <date> <magazine>
  date: YYYY-MM-DD (e.g., 2026-05-02)
  magazine: economist | new_yorker
"""

import sys, json, re, subprocess, time
from pathlib import Path

ROOT = Path(__file__).parent.parent

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
    """Extract answer string from notebooklm --json output."""
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

def re_extract_summaries(date, magazine):
    mag_dir = ROOT / 'data' / magazine
    out_path = mag_dir / f'{date}.json'

    if not out_path.exists():
        print(f'ERROR: {out_path} not found')
        return False

    with open(out_path, encoding='utf-8') as f:
        issue = json.load(f)

    nb_id = issue.get('notebook_id')
    if not nb_id:
        print(f'ERROR: No notebook_id in {out_path}')
        return False

    print(f'\nRe-extracting summaries for {magazine} {date}')
    print(f'Notebook ID: {nb_id}')

    # Collect all articles
    articles_all = [(s['section'], a) for s in issue['toc'] for a in s['articles']]
    print(f'Total articles: {len(articles_all)}')

    # Split into 4 batches for better completion
    batch_size = (len(articles_all) + 3) // 4  # Ceiling division
    batches = [articles_all[i:i+batch_size] for i in range(0, len(articles_all), batch_size)]
    print(f'Splitting into {len(batches)} batches (~{batch_size} articles each)')

    def build_summary_prompt(articles_slice, mag):
        if mag == 'economist':
            header = '请为以下《经济学人》文章写详细中文摘要。Leaders和Briefing栏目每篇600-800字，其他栏目250-400字。涵盖核心论点、关键数据、背景分析和结论。输出JSON：{"summaries": {"英文标题": "中文摘要"}}\n\n'
        else:
            header = '请为以下《纽约客》文章写详细中文摘要，每篇300-500字，涵盖主题、叙事风格、核心观点和结论。输出JSON：{"summaries": {"英文标题": "中文摘要"}}\n\n'
        lines = []
        for section, art in articles_slice:
            lines.append(f'[{section}] {art["title"]}')
        return header + '\n'.join(lines)

    def fetch_summaries(prompt, nb_id, batch_num):
        escaped = prompt.replace('"', '\\"').replace('\n', '\\n')
        print(f'  Batch {batch_num}: requesting...')
        out = notebooklm(f'ask "{escaped}" --notebook {nb_id} --json', timeout=360)
        answer = get_answer(out)
        data = extract_json_block(answer)
        summaries = data.get('summaries', {}) if data else {}
        print(f'  Batch {batch_num}: got {len(summaries)} summaries')
        return summaries

    # Fetch summaries from all batches
    all_summaries_dict = {}
    for i, batch in enumerate(batches, 1):
        summaries = fetch_summaries(build_summary_prompt(batch, magazine), nb_id, i)
        all_summaries_dict.update({normalize(k): v for k, v in summaries.items()})
        time.sleep(2)  # Rate limit

    print(f'\nTotal summaries collected: {len(all_summaries_dict)}')

    # Merge summaries into issue
    matched = 0
    total = len(articles_all)
    for section in issue['toc']:
        for article in section['articles']:
            key = normalize(article['title'])
            if key in all_summaries_dict:
                article['summary'] = all_summaries_dict[key]
                matched += 1

    print(f'Matched: {matched}/{total}')

    # Save updated issue
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(issue, f, ensure_ascii=False, indent=2)

    print(f'✓ Saved updated issue to {out_path}')
    return True

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: python3 re_extract_summaries.py <date> <magazine>')
        print('  date: YYYY-MM-DD (e.g., 2026-05-02)')
        print('  magazine: economist | new_yorker')
        sys.exit(1)

    date = sys.argv[1]
    magazine = sys.argv[2]
    success = re_extract_summaries(date, magazine)
    sys.exit(0 if success else 1)
