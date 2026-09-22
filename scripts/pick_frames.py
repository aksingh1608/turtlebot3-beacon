#!/usr/bin/env python3
"""Copy one debug frame per state from trial 1 into docs/screenshots.

Looks in docs/screenshots/frames for trial_1_<STATE>_*.png.
For each state the largest file is kept, on the assumption it is the clearest.
Writes debug_search.png, debug_align.png, debug_approach.png, debug_stop.png.
"""

import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES = os.path.join(REPO, 'docs', 'screenshots', 'frames')
OUT = os.path.join(REPO, 'docs', 'screenshots')
STATES = ('SEARCH', 'ALIGN', 'APPROACH', 'STOP')


def candidates(state):
    prefix = 'trial_1_%s_' % state
    if not os.path.isdir(FRAMES):
        return []
    found = []
    for name in os.listdir(FRAMES):
        if name.startswith(prefix) and name.endswith('.png'):
            found.append(os.path.join(FRAMES, name))
    return found


def main():
    os.makedirs(OUT, exist_ok=True)
    missing = []
    for state in STATES:
        found = candidates(state)
        dest_name = 'debug_%s.png' % state.lower()
        dest = os.path.join(OUT, dest_name)
        if not found:
            missing.append(state)
            print('no frame for %s in %s' % (state, FRAMES))
            continue
        best = max(found, key=os.path.getsize)
        shutil.copyfile(best, dest)
        print('copied %s -> %s' % (os.path.basename(best), dest_name))
    if missing:
        print('missing states: %s' % ', '.join(missing))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
