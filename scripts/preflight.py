#!/usr/bin/env python3
"""Friday-evening preflight for the Saturday econy run (launchd com.econy.preflight).

1. notebooklm-py version vs PyPI — behind → upgrade, smoke test, roll back
   if the new version breaks the smoke test.
   (2026-08-01: 0.3.4 broken by a Google auth change; 2026-10-31: 0.7.3's
   50MB chat-stream cap killed the TOC — 0.8.x had been out since 10-27.)
2. `notebooklm auth check --test` must say "Authentication is valid".
3. Smoke test with exactly the commands/JSON shapes pipeline.py relies on:
   create → source add (file) → source wait → ask --json --new → delete.

Any failure → iMessage + banner (alert.py), so it gets fixed before Saturday.
Pass → one short iMessage, so silence never has to be read as "fine".
Manual run: python3 scripts/preflight.py   (--no-upgrade to only check)
Install:    cp scripts/com.econy.preflight.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.econy.preflight.plist
"""
import json, subprocess, sys, tempfile, time, urllib.request
import importlib.metadata as md
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import alert

PKG = 'notebooklm-py'

def log(msg):
    line = f'[{datetime.now():%Y-%m-%d %H:%M:%S}] PREFLIGHT {msg}'
    # stdout only — launchd sends it to ~/Library/Logs/econy-preflight.log.
    # Not update.log: the dashboard status block parses that file's last run.
    print(line, flush=True)

def nlm(*args, timeout=180):
    r = subprocess.run(['notebooklm', *args], capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()

def installed():
    return md.version(PKG)

def latest():
    with urllib.request.urlopen(f'https://pypi.org/pypi/{PKG}/json', timeout=30) as r:
        return json.loads(r.read())['info']['version']

def vkey(v):
    return tuple(int(p) if p.isdigit() else 0 for p in v.split('.'))

def pip_install(version):
    r = subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', f'{PKG}=={version}'],
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f'pip install {version} failed: {r.stderr[-300:]}')

def auth_check():
    code, out, err = nlm('auth', 'check', '--test', timeout=120)
    if 'Authentication is valid' not in out + err:
        tail = (out + err).strip().splitlines()[-3:]
        return [f'auth check 未通过：{" / ".join(tail)[:200]}']
    return []

def smoke_test():
    """Returns a list of problems (empty = pass). Always deletes its notebook."""
    nb_id = None
    try:
        code, out, err = nlm('create', f'econy-preflight {datetime.now():%Y-%m-%d}', '--json')
        try:
            nb_id = json.loads(out)['notebook']['id']
        except (ValueError, KeyError):
            return [f'create 失败：{(out or err)[:200]}']
        # resolve(): tempdir is under /var → /private/var, and 0.8.x refuses
        # to upload through a symlink without --follow-symlinks.
        tmpdir = Path(tempfile.gettempdir()).resolve()
        with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False, dir=tmpdir) as f:
            f.write('Econy preflight test document.\n'
                    'Section: Leaders. Article title: The cat sat on the mat.\n'
                    'Section: Business. Article title: Markets rose on Friday.\n')
            src_path = f.name
        code, out, err = nlm('source', 'add', src_path, '--notebook', nb_id, '--json')
        try:
            src_id = json.loads(out)['source']['id']
        except (ValueError, KeyError):
            return [f'source add 失败：{(out or err)[:200]}']
        code, out, err = nlm('source', 'wait', src_id, '--notebook', nb_id, '--timeout', '300', timeout=320)
        if code != 0:
            return [f'source wait 失败：{(err or out)[:200]}']
        prompt = ('列出这份文档里的所有文章，输出为JSON格式：'
                  '{"sections": [{"section": "栏目名", "articles": [{"title": "标题"}]}]}')
        for attempt in (1, 2):
            code, out, err = nlm('ask', prompt, '--notebook', nb_id, '--json', '--new')
            try:
                j = json.loads(out)
            except ValueError:
                j = {}
            if j.get('answer') and '"sections"' in j['answer']:
                return []
            problem = (f'ask 失败：{j.get("code")}: {str(j.get("message"))[:200]}' if j.get('error')
                       else f'ask 返回空或无 JSON（rc={code}）：{(err or out)[:200]}')
            time.sleep(30)
        return [problem]
    except Exception as e:
        return [f'冒烟测试异常：{type(e).__name__}: {str(e)[:200]}']
    finally:
        if nb_id:
            nlm('delete', '-n', nb_id, '-y', timeout=60)

def main():
    upgrade = '--no-upgrade' not in sys.argv
    notes, problems = [], []

    cur = installed()
    try:
        new = latest()
    except Exception as e:
        new = None
        notes.append(f'查不到 PyPI 最新版（{e}）')
    log(f'{PKG} installed {cur}, latest {new}')

    tested = False
    if new and vkey(new) > vkey(cur):
        if not upgrade:
            problems.append(f'{PKG} 落后：{cur} → {new}（--no-upgrade，未升级）')
        else:
            pip_install(new)
            log(f'upgraded {cur} → {new}; smoke testing')
            p = auth_check() or smoke_test()
            if p:
                # Keep Saturday on the version that worked last week.
                log(f'new version failed ({"；".join(p)}), rolling back to {cur}')
                pip_install(cur)
                problems.append(f'新版 {new} 冒烟测试失败，已回滚 {cur}：{"；".join(p)}')
            else:
                notes.append(f'已自动升级 {cur} → {new}')
                cur, tested = new, True

    if not tested:
        problems += auth_check() or smoke_test()

    if problems:
        log('FAIL: ' + '；'.join(problems))
        alert.send('Econy 周五预检失败 ❌',
                   '；'.join(problems) + '——明早 07:00 自动更新前需要处理', sound='Basso', log=log)
    else:
        log('PASS' + (f' ({"；".join(notes)})' if notes else ''))
        alert.send('Econy 周五预检通过 ✓',
                   f'notebooklm {cur}，认证与冒烟测试正常' + (f'；{"；".join(notes)}' if notes else ''), log=log)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        log('FATAL:\n' + traceback.format_exc())
        alert.send('Econy 周五预检崩溃 ❌', str(e)[:200] or '未知错误', sound='Basso', log=log)
        raise
