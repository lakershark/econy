"""Phone alerts for econy: every macOS banner is also sent as an iMessage.

2026-10-31: the failure banner only shows on the iMac for a few seconds, so
07-18, 09-16, 10-17, 10-24 and 10-31 were all found by Tao, not by us.
An iMessage to Tao's own handle pushes to the iPhone.

The handle lives outside the (public) repo in ~/.config/econy/alert.json:
  {"imessage_to": "<apple id or +49...>"}
"""
import json, subprocess
from pathlib import Path

CONFIG = Path.home() / '.config' / 'econy' / 'alert.json'

def _handle():
    try:
        return json.loads(CONFIG.read_text()).get('imessage_to')
    except Exception:
        return None

def banner(title, message, sound='default'):
    script = (f'display notification {json.dumps(message)} '
              f'with title {json.dumps(title)} sound name {json.dumps(sound)}')
    subprocess.run(['/usr/bin/osascript', '-e', script], capture_output=True, timeout=15)

def imessage(text):
    """Send text via Messages. Returns (ok, error)."""
    to = _handle()
    if not to:
        return False, f'no imessage_to in {CONFIG}'
    # Text and handle go in as argv, never spliced into the script (quotes).
    script = '''on run argv
  tell application "Messages"
    set svc to 1st account whose service type = iMessage
    send (item 1 of argv) to participant (item 2 of argv) of svc
  end tell
end run'''
    r = subprocess.run(['/usr/bin/osascript', '-e', script, text, to],
                       capture_output=True, text=True, timeout=30)
    return r.returncode == 0, r.stderr.strip()

def send(title, message, sound='default', log=print):
    """Banner on the iMac + iMessage to the phone; never raises."""
    try:
        banner(title, message, sound)
    except Exception as e:
        log(f'  banner failed (non-critical): {e}')
    try:
        ok, err = imessage(f'{title}\n{message}')
        if not ok:
            log(f'  ALERT iMessage failed: {err[:300]}')
    except Exception as e:
        log(f'  ALERT iMessage failed: {e}')

if __name__ == '__main__':
    import sys
    send('Econy 测试', ' '.join(sys.argv[1:]) or '手机报警测试：收到这条说明通道正常')
