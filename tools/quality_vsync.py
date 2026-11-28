#!/usr/bin/env python3
"""Read-only: list vSyncCount for every quality level in a game's globalgamemanagers.

On Metal, vSyncCount=0 makes Unity turn off CAMetalLayer.displaySyncEnabled, so frame pacing and GPU
load depend on the quality level the player boots into (see docs/ROADMAP.md, frame pacing). This only
reads; it does not change the file and does not prove what the running player does.

    python3 tools/quality_vsync.py <App.app | Data folder | globalgamemanagers>
"""
import os
import sys

import UnityPy


def find(path):
    if os.path.isfile(path):
        return path
    for sub in ('Contents/Resources/Data', 'Data', ''):
        f = os.path.join(path, sub, 'globalgamemanagers')
        if os.path.isfile(f):
            return f
    raise SystemExit('no globalgamemanagers under %s' % path)


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    env = UnityPy.load(find(argv[1]))
    for o in env.objects:
        if o.type.name != 'QualitySettings':
            continue
        t = o.read_typetree()
        current = t.get('m_CurrentQuality')
        for i, q in enumerate(t['m_QualitySettings']):
            print('%s%d  %-12s vSyncCount=%d' % ('*' if i == current else ' ', i, q['name'], q['vSyncCount']))
        print('* = serialized current level (the player may boot a different one; check at runtime)')
        return 0
    print('no QualitySettings object', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
