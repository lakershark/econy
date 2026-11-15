"""Keep the Mac awake for the lifetime of this process.

2026-11-14: launchd fires the Saturday job via a DarkWake that lasts ~45s,
then the iMac drops back into Maintenance Sleep. The run then only advanced
during brief upkeep wakes: subprocess timeouts count monotonic time (frozen
while asleep), so a "180s" ask stretched to hours of wall clock, sockets died
on every sleep ("chat.ask network error", "no streamed chat bytes for 180s"),
and the TOC failed 3/3 over five hours. 11-07 and the 19-hour title
translation of 11-08 were the same thing.

caffeinate -s (PreventSystemSleep, AC only — the iMac is always on AC) plus
-i holds the machine awake; -w ties it to our pid so it ends with us.
"""
import os, subprocess, time


def stay_awake():
    try:
        subprocess.Popen(['/usr/bin/caffeinate', '-i', '-s', '-w', str(os.getpid())],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


class SleepWatch:
    """Wall clock minus monotonic clock = time spent asleep (macOS stops
    CLOCK_MONOTONIC during sleep). Lets the log say so instead of leaving
    a mystery multi-hour gap."""

    def __init__(self):
        self.wall0, self.mono0 = time.time(), time.monotonic()

    def slept_minutes(self):
        return ((time.time() - self.wall0) - (time.monotonic() - self.mono0)) / 60
