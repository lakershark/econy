"""
Batch translate untranslated article titles using NotebookLM.

Usage: python3 scripts/translate_titles_batch.py <date> <magazine>
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
    try:
        data = json.loads(raw_output)
        answer = data.get('answer', '')
        # Unescape unicode sequences
        answer = answer.encode('utf-8').decode('utf-8')
        return answer
    except:
        return ''

def translate_titles_batch(date, magazine):
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

    print(f'\nTranslating untranslated titles for {magazine} {date}')
    print(f'Notebook ID: {nb_id}')

    # Find untranslated titles
    untranslated = []
    for section in issue['toc']:
        for article in section['articles']:
            if article.get('title_zh') == article['title'] or not article.get('title_zh'):
                untranslated.append((section['section'], article['title']))

    print(f'Found {len(untranslated)} untranslated titles')
    if not untranslated:
        return True

    # Translate in batches of 20
    batch_size = 20
    translations = {}

    for i in range(0, len(untranslated), batch_size):
        batch = untranslated[i:i+batch_size]
        batch_num = i // batch_size + 1
        print(f'\nBatch {batch_num}: {len(batch)} titles')

        lines = '\n'.join(f'[{sec}] {title}' for sec, title in batch)
        prompt = f'请将以下文章标题翻译成中文，保持简洁准确。输出JSON格式：{{"titles": {{"英文标题": "中文标题"}}}}\n\n{lines}'
        escaped = prompt.replace('"', '\\"').replace('\n', '\\n')

        out = notebooklm(f'ask "{escaped}" --notebook {nb_id} --json', timeout=120)
        answer = get_answer(out)
        data = extract_json_block(answer)

        if data and 'titles' in data:
            translations.update({normalize(k): v for k, v in data['titles'].items()})
            print(f'  Got {len(data["titles"])} translations')

        time.sleep(2)

    print(f'\nTotal translations: {len(translations)}')

    # Apply translations
    matched = 0
    for section in issue['toc']:
        for article in section['articles']:
            key = normalize(article['title'])
            if key in translations:
                article['title_zh'] = translations[key]
                matched += 1

    print(f'Applied {matched} translations')

    # Save updated issue
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(issue, f, ensure_ascii=False, indent=2)

    print(f'✓ Saved updated issue to {out_path}')
    return True

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: python3 translate_titles_batch.py <date> <magazine>')
        print('  date: YYYY-MM-DD')
        print('  magazine: economist | new_yorker')
        sys.exit(1)

    date = sys.argv[1]
    magazine = sys.argv[2]
    success = translate_titles_batch(date, magazine)
    sys.exit(0 if success else 1)
