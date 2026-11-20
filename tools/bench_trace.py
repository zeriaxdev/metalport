#!/usr/bin/env python3
"""Measure one running game from a Metal System Trace: real FPS, frame-time percentiles, render resolution, GPU load, CPU, memory.
Works for the native port and for the Windows build under CrossOver (any process that presents with Metal).  See docs/BENCHMARKING.md.

usage: bench_trace.py run <process pattern> <label> [--secs 20] [--wait-front] [--out bench/results.jsonl] [--note "..."]
       bench_trace.py report [bench/results.jsonl]       (mean ± sd per label)
--wait-front: wait until the game's window is frontmost (CrossOver games pause when unfocused), then 10 s more before recording."""
import argparse, json, os, platform, re, statistics, subprocess, sys, tempfile, threading, time, xml.etree.ElementTree as ET

def sh(*c): return subprocess.run(c, capture_output=True, text=True).stdout

def find_pid(pat):
    for line in sh('ps', '-axo', 'pid=,command=').splitlines():
        pid, cmd = line.strip().split(' ', 1)
        if re.search(pat, cmd) and 'bench_trace' not in cmd and 'Crash' not in cmd: return int(pid), cmd
    sys.exit(f'no process matches {pat!r}')

def front_name(): return sh('lsappinfo', 'info', '-only', 'name', sh('lsappinfo', 'front').strip())

def rows(trace, schema):
    """Rows of one table as dicts {mnemonic: (fmt, text)}; resolves xctrace's id/ref compression."""
    xml = sh('xcrun', 'xctrace', 'export', '--input', trace, '--xpath', f'/trace-toc/run[@number="1"]/data/table[@schema="{schema}"]')
    if not xml.strip(): return
    root = ET.fromstring(xml); ids = {}; cols = [c.findtext('mnemonic') for c in root.iter('col')]
    for r in root.iter('row'):
        out = {}
        for c, e in zip(cols, list(r)):
            if 'ref' in e.attrib: e = ids[e.attrib['ref']]
            else:
                for x in e.iter():
                    if 'id' in x.attrib: ids[x.attrib['id']] = x
            out[c] = (e.attrib.get('fmt'), e.text)
        yield out

def pct(xs, p): xs = sorted(xs); return xs[min(len(xs) - 1, int(p / 100 * len(xs)))]

def run(a):
    pid, cmd = find_pid(a.pattern)
    if a.wait_front:
        exe = os.path.basename(cmd.split(' -')[0].split('\\')[-1]).strip()
        print(f'waiting for {exe} to be frontmost...', flush=True)
        while exe.lower() not in front_name().lower(): time.sleep(2)
        time.sleep(10)
    cpu = []; stop = threading.Event()
    def sample():                                       # CPU % of one core and RSS, once a second, alongside the trace
        while not stop.wait(1):
            o = sh('ps', '-o', 'pcpu=,rss=', '-p', str(pid)).split()
            if o: cpu.append((float(o[0]), int(o[1])))
    th = threading.Thread(target=sample); th.start()
    tr = os.path.join(tempfile.mkdtemp(), 'bench.trace')
    sh('xcrun', 'xctrace', 'record', '--template', 'Metal System Trace', '--attach', str(pid), '--time-limit', f'{a.secs}s', '--output', tr)
    stop.set(); th.join()
    tag = f'({pid})'
    frames = []                                         # (time ns, n) of this process's present requests (labelled by process even when composited)
    for r in rows(tr, 'ca-client-present-request'):
        if tag in (r['process'][0] or ''): frames.append(int(r['timestamp'][1]))
    frames = [(t, i) for i, t in enumerate(sorted(frames))]
    if len(frames) < 10: sys.exit(f'only {len(frames)} frames captured: was the game running and in front?')
    ft = [(b[0] - a_[0]) / 1e6 for a_, b in zip(frames, frames[1:])]              # frame times, ms
    span = (frames[-1][0] - frames[0][0]) / 1e9
    sizes = {}
    for r in rows(tr, 'metal-io-surface-access'):
        if tag in (r['process'][0] or ''): k = f"{r['width'][0]}x{r['height'][0]}"; sizes[k] = sizes.get(k, 0) + 1
    busy = []
    for r in rows(tr, 'metal-gpu-intervals'):
        if tag in (r['process'][0] or ''):
            s = int(r['start'][1]); busy.append((s, s + int(r['duration'][1])))
    busy.sort(); union = 0; cur = None
    for s, e in busy:
        if cur is None or s > cur[1]:
            if cur: union += cur[1] - cur[0]
            cur = [s, e]
        else: cur[1] = max(cur[1], e)
    if cur: union += cur[1] - cur[0]
    gspan = (busy[-1][1] - busy[0][0]) if busy else 1
    therm = sorted({r.get('thermal-state', (None,))[0] for r in rows(tr, 'device-thermal-state-intervals')} - {None})
    res = dict(label=a.label, note=a.note, when=time.strftime('%Y-%m-%d %H:%M'), process=cmd.split(' -')[0][-60:],
               chip=sh('sysctl', '-n', 'machdep.cpu.brand_string').strip(), macos=platform.mac_ver()[0],
               secs=round(span, 1), frames=len(frames),
               fps_avg=round((frames[-1][1] - frames[0][1]) / span, 1),
               ft_median_ms=round(statistics.median(ft), 2), ft_p99_ms=round(pct(ft, 99), 2),
               fps_1pct_low=round(1000 / pct(ft, 99), 1), stutters=sum(t > 2.5 * statistics.median(ft) for t in ft),
               drawable=max(sizes, key=sizes.get) if sizes else None,
               gpu_busy_pct=round(100 * union / gspan, 1), gpu_ms_per_frame=round(union / 1e6 / len(frames), 2),
               cpu_pct_avg=round(statistics.mean(c for c, _ in cpu), 0) if cpu else None,
               rss_mb=round(max(r for _, r in cpu) / 1024) if cpu else None, thermal=therm)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, 'a') as f: f.write(json.dumps(res) + '\n')
    print(json.dumps(res, indent=1))

def report(path):
    by = {}
    for line in open(path):
        r = json.loads(line); by.setdefault(r['label'], []).append(r)
    keys = ('fps_avg', 'fps_1pct_low', 'ft_median_ms', 'ft_p99_ms', 'gpu_ms_per_frame', 'gpu_busy_pct', 'cpu_pct_avg', 'rss_mb')
    print('| label | runs | drawable | ' + ' | '.join(keys) + ' |'); print('|' + '---|' * (len(keys) + 3))
    for lab, rs in by.items():
        cells = []
        for k in keys:
            v = [r[k] for r in rs if r.get(k) is not None]
            cells.append('-' if not v else f'{statistics.mean(v):.1f}' + (f' ± {statistics.stdev(v):.1f}' if len(v) > 1 else ''))
        print(f"| {lab} | {len(rs)} | {', '.join(sorted({str(r['drawable']) for r in rs}))} | " + ' | '.join(cells) + ' |')

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest='cmd', required=True)
    r = sp.add_parser('run'); r.add_argument('pattern'); r.add_argument('label'); r.add_argument('--secs', type=int, default=20)
    r.add_argument('--wait-front', action='store_true'); r.add_argument('--out', default='bench/results.jsonl'); r.add_argument('--note', default='')
    p = sp.add_parser('report'); p.add_argument('path', nargs='?', default='bench/results.jsonl')
    a = ap.parse_args()
    run(a) if a.cmd == 'run' else report(a.path)
