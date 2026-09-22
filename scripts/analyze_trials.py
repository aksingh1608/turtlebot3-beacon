#!/usr/bin/env python3
"""Plot and summarise Beacon trials.

Reads trials/results.csv and trials/logs/*.csv, writes five PNG figures to
docs/figures and prints summary numbers. Headless: matplotlib only, Agg.

    python3 scripts/analyze_trials.py
    python3 scripts/analyze_trials.py --trials-dir ~/ros2_ws/src/beacon/trials
"""

import argparse
import csv
import glob
import math
import os
import re
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402

try:
    import yaml
except ImportError:
    yaml = None

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# One colour per trial, fixed order, validated for colour vision deficiency.
TRIAL_COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4',
                '#008300', '#4a3aa7', '#e34948', '#1c5cab', '#8a6a00']
STATE_COLORS = {'SEARCH': '#9ec5f4', 'ALIGN': '#5598e7', 'APPROACH': '#1c5cab',
                'STOP': '#008300', 'TIMEOUT': '#e34948'}
STATE_ORDER = ['SEARCH', 'ALIGN', 'APPROACH', 'STOP', 'TIMEOUT']
MARKER_COLOR = '#e34948'
INK = '#0b0b0b'
INK_SOFT = '#52514e'
GRID = '#e6e5e1'
SURFACE = '#fcfcfb'


def load_shared(params_path):
    """Room geometry and centre tolerance from params.yaml."""
    fallback = {'room_size_m': 6.0, 'wall_thickness_m': 0.2, 'box_size_m': 0.4,
                'box1_x': 1.0, 'box1_y': 0.8, 'box2_x': -1.2, 'box2_y': -0.9,
                'center_tol': 0.10}
    if yaml is None or not os.path.exists(params_path):
        print('warning: params.yaml not read, using built in geometry', file=sys.stderr)
        return fallback
    with open(params_path) as f:
        data = yaml.safe_load(f)
    shared = dict(data['beacon_shared']['ros__parameters'])
    shared['center_tol'] = data['controller_node']['ros__parameters']['center_tol']
    return shared


def read_results(path):
    if not os.path.exists(path):
        return {}
    rows = {}
    with open(path, newline='') as f:
        for r in csv.DictReader(f):
            rows[r['trial']] = r  # last row per trial wins
    return rows


def read_log(path):
    cols = {}
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        for name in reader.fieldnames:
            cols[name] = []
        for r in reader:
            for name in reader.fieldnames:
                cols[name].append(r[name])

    def floats(name):
        out = []
        for v in cols.get(name, []):
            try:
                out.append(float(v))
            except ValueError:
                out.append(math.nan)
        return out
    return {
        't': floats('t'), 'x': floats('x'), 'y': floats('y'),
        'state': cols.get('state', []), 'offset': floats('offset'),
        'found': floats('found'),
    }


def trial_sort_key(tid):
    m = re.match(r'^\d+$', tid)
    return (0, int(tid)) if m else (1, tid)


def load_logs(logs_dir):
    logs = {}
    for path in glob.glob(os.path.join(logs_dir, 'trial_*.csv')):
        tid = os.path.basename(path)[len('trial_'):-len('.csv')]
        try:
            logs[tid] = read_log(path)
        except Exception as e:
            print('skipping %s: %s' % (path, e), file=sys.stderr)
    return logs


def color_for(index):
    return TRIAL_COLORS[index % len(TRIAL_COLORS)]


def style_axes(ax):
    ax.set_facecolor(SURFACE)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    for side in ('left', 'bottom'):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_SOFT, labelsize=9)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def new_figure(w=8.0, h=6.0):
    fig, ax = plt.subplots(figsize=(w, h), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    style_axes(ax)
    return fig, ax


def plot_paths(trials, results, logs, shared, out):
    fig, ax = new_figure(7.5, 7.5)
    half = float(shared['room_size_m']) / 2.0
    wall = float(shared['wall_thickness_m'])
    inner = half - wall / 2.0
    ax.add_patch(Rectangle((-half - wall / 2, -half - wall / 2), 2 * half + wall, 2 * half + wall,
                           facecolor='#d8d7d2', edgecolor='none'))
    ax.add_patch(Rectangle((-inner, -inner), 2 * inner, 2 * inner,
                           facecolor=SURFACE, edgecolor='none'))
    box = float(shared['box_size_m'])
    for bx, by in ((shared['box1_x'], shared['box1_y']), (shared['box2_x'], shared['box2_y'])):
        ax.add_patch(Rectangle((float(bx) - box / 2, float(by) - box / 2), box, box,
                               facecolor='#c3c2b7', edgecolor=INK_SOFT, linewidth=0.8))
    ax.plot([0], [0], marker='^', color=INK, markersize=9, linestyle='none', zorder=5)
    ax.annotate('start', (0, 0), xytext=(6, 6), textcoords='offset points',
                fontsize=8, color=INK_SOFT)
    for i, tid in enumerate(trials):
        c = color_for(i)
        log = logs.get(tid)
        if log and log['x']:
            ax.plot(log['x'], log['y'], color=c, linewidth=2, label='trial %s' % tid, zorder=3)
            ax.annotate(tid, (log['x'][-1], log['y'][-1]), xytext=(4, 4),
                        textcoords='offset points', fontsize=8, color=INK)
        r = results.get(tid, {})
        try:
            mx, my = float(r['marker_x']), float(r['marker_y'])
        except (KeyError, ValueError):
            continue
        ax.plot([mx], [my], marker='o', color=MARKER_COLOR, markersize=8, linestyle='none',
                markeredgecolor=SURFACE, markeredgewidth=1.5, zorder=6)
    ax.plot([], [], marker='o', color=MARKER_COLOR, linestyle='none', label='marker')
    ax.set_xlim(-half - wall, half + wall)
    ax.set_ylim(-half - wall, half + wall)
    ax.set_aspect('equal')
    ax.set_xlabel('x (m)', color=INK_SOFT)
    ax.set_ylabel('y (m)', color=INK_SOFT)
    ax.set_title('Robot paths, top view (odom frame)', color=INK, loc='left')
    ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1.0), frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)


def plot_time_to_reach(trials, results, out):
    fig, ax = new_figure(8.0, 4.5)
    xs = list(range(len(trials)))
    heights = []
    for i, tid in enumerate(trials):
        r = results.get(tid, {})
        reached = r.get('reached') == '1'
        try:
            t = float(r['time_to_reach_s']) if reached else math.nan
        except (KeyError, ValueError):
            t = math.nan
        heights.append(t)
        if reached and not math.isnan(t):
            ax.bar(i, t, width=0.7, color=color_for(i), edgecolor=SURFACE, linewidth=2)
            ax.annotate('%.1f s' % t, (i, t), xytext=(0, 3), textcoords='offset points',
                        ha='center', fontsize=8, color=INK)
        else:
            ax.bar(i, 0, width=0.7, color=SURFACE)
            ax.annotate('fail', (i, 0), xytext=(0, 4), textcoords='offset points',
                        ha='center', fontsize=9, color=STATE_COLORS['TIMEOUT'], fontweight='bold')
            ax.plot([i], [0], marker='x', color=STATE_COLORS['TIMEOUT'], markersize=10,
                    markeredgewidth=2, linestyle='none', zorder=5)
    ax.set_xticks(xs)
    ax.set_xticklabels(['trial %s' % t for t in trials], rotation=30, ha='right')
    ax.set_ylabel('time to STOP (s)', color=INK_SOFT)
    ax.set_title('Time to reach the marker', color=INK, loc='left')
    finite = [h for h in heights if not math.isnan(h)]
    ax.set_ylim(0, (max(finite) if finite else 1.0) * 1.2)
    ax.grid(axis='x', visible=False)
    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)


def segments(log):
    """List of (state, t_start, t_end) runs from a log."""
    out = []
    if not log['t']:
        return out
    cur = log['state'][0]
    t0 = log['t'][0]
    for t, s in zip(log['t'], log['state']):
        if s != cur:
            out.append((cur, t0, t))
            cur, t0 = s, t
    out.append((cur, t0, log['t'][-1]))
    return out


def plot_state_timeline(trials, results, logs, out):
    fig, ax = new_figure(9.0, 0.45 * max(len(trials), 4) + 1.5)
    ymax = 0.0
    for i, tid in enumerate(trials):
        log = logs.get(tid)
        if not log:
            continue
        for state, t0, t1 in segments(log):
            ax.barh(i, t1 - t0, left=t0, height=0.6, color=STATE_COLORS.get(state, '#999999'),
                    edgecolor=SURFACE, linewidth=1)
            ymax = max(ymax, t1)
        r = results.get(tid, {})
        end_state = 'STOP' if r.get('reached') == '1' else 'TIMEOUT'
        if log['t']:
            ax.plot([log['t'][-1]], [i], marker='|' if end_state == 'STOP' else 'x',
                    color=STATE_COLORS[end_state], markersize=10, markeredgewidth=2)
    ax.set_yticks(range(len(trials)))
    ax.set_yticklabels(['trial %s' % t for t in trials])
    ax.invert_yaxis()
    ax.set_xlabel('time since trial start (s)', color=INK_SOFT)
    ax.set_title('State timeline per trial', color=INK, loc='left')
    ax.grid(axis='y', visible=False)
    handles = [Patch(facecolor=STATE_COLORS[s], label=s) for s in STATE_ORDER]
    ax.legend(handles=handles, loc='upper left', bbox_to_anchor=(1.01, 1.0), frameon=False,
              fontsize=8)
    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)


def plot_offset_vs_time(trials, logs, shared, out):
    fig, ax = new_figure(9.0, 4.5)
    tol = float(shared['center_tol'])
    ax.axhspan(-tol, tol, color='#f0efec', zorder=0)
    ax.axhline(0.0, color=INK_SOFT, linewidth=0.8)
    for i, tid in enumerate(trials):
        log = logs.get(tid)
        if not log or not log['t']:
            continue
        ts = [t for t, f in zip(log['t'], log['found']) if f == 1.0]
        offs = [o for o, f in zip(log['offset'], log['found']) if f == 1.0]
        ax.plot(ts, offs, color=color_for(i), linewidth=1.5, label='trial %s' % tid)
    ax.set_ylim(-1.05, 1.05)
    ax.set_xlabel('time since trial start (s)', color=INK_SOFT)
    ax.set_ylabel('horizontal offset (image half widths)', color=INK_SOFT)
    ax.set_title('Marker offset while visible, centre band shaded', color=INK, loc='left')
    ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1.0), frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)


RESULT_COLUMNS = ['trial', 'marker_x', 'marker_y', 'bearing_deg', 'occluded', 'first_seen_s',
                  'reached', 'time_to_reach_s', 'final_range_m', 'path_length_m',
                  'search_time_s', 'align_time_s', 'approach_time_s']


def plot_results_table(trials, results, out):
    cells = []
    for tid in trials:
        r = results.get(tid, {})
        cells.append([r.get(c, '') or '' for c in RESULT_COLUMNS])
    fig, ax = plt.subplots(figsize=(13.0, 0.4 * len(trials) + 1.2), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.axis('off')
    table = ax.table(cellText=cells, colLabels=RESULT_COLUMNS, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1.0, 1.4)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor(GRID)
        if row == 0:
            cell.set_facecolor('#f0efec')
            cell.set_text_props(color=INK, fontweight='bold')
        else:
            cell.set_facecolor(SURFACE)
            cell.set_text_props(color=INK)
    ax.set_title('Trial results', color=INK, loc='left')
    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)


def summarise(trials, results):
    n = len(trials)
    reached = [results[t] for t in trials if results.get(t, {}).get('reached') == '1']
    times = []
    ranges = []
    for r in reached:
        try:
            times.append(float(r['time_to_reach_s']))
        except ValueError:
            pass
        try:
            ranges.append(float(r['final_range_m']))
        except ValueError:
            pass
    print('trials: %d, reached: %d, success rate: %.0f%%' % (
        n, len(reached), 100.0 * len(reached) / n if n else 0.0))
    if times:
        print('time to reach: mean %.1f s, max %.1f s' % (sum(times) / len(times), max(times)))
    else:
        print('time to reach: no successful trials')
    if ranges:
        print('final front range: mean %.2f m' % (sum(ranges) / len(ranges)))
    else:
        print('final front range: no values')


def main():
    ap = argparse.ArgumentParser(description='Plot and summarise Beacon trials.')
    ap.add_argument('--trials-dir', default=os.environ.get('BEACON_TRIALS_DIR')
                    or os.path.join(REPO, 'beacon', 'trials'))
    ap.add_argument('--params', default=os.path.join(REPO, 'beacon', 'config', 'params.yaml'))
    ap.add_argument('--out', default=os.path.join(REPO, 'docs', 'figures'))
    args = ap.parse_args()

    shared = load_shared(args.params)
    results = read_results(os.path.join(args.trials_dir, 'results.csv'))
    logs = load_logs(os.path.join(args.trials_dir, 'logs'))
    trials = sorted(set(results) | set(logs), key=trial_sort_key)
    if not trials:
        print('no trials found in %s' % args.trials_dir)
        return 1
    os.makedirs(args.out, exist_ok=True)

    plot_paths(trials, results, logs, shared, os.path.join(args.out, 'paths_topdown.png'))
    plot_time_to_reach(trials, results, os.path.join(args.out, 'time_to_reach.png'))
    plot_state_timeline(trials, results, logs, os.path.join(args.out, 'state_timeline.png'))
    plot_offset_vs_time(trials, logs, shared, os.path.join(args.out, 'offset_vs_time.png'))
    plot_results_table(trials, results, os.path.join(args.out, 'results_table.png'))
    print('figures written to %s' % args.out)
    summarise(trials, results)
    return 0


if __name__ == '__main__':
    sys.exit(main())
