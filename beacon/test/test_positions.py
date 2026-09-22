"""Unit tests for trials/positions.csv. No ROS needed."""

import math
import os

from beacon.spawn_marker import (
    generate_positions,
    line_of_sight_blocked,
    load_shared_params,
    read_positions,
    resolve_trials_dir,
)

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSITIONS = os.path.join(PKG, 'trials', 'positions.csv')


def shared():
    return load_shared_params(PKG)


def inner_half(params):
    """Distance from the origin to the inner face of a wall."""
    return (float(params['room_size_m']) / 2.0
            - float(params['wall_thickness_m']) / 2.0)


def gap_to_wall(x, y, params):
    """Metres from the marker centre to the nearest inner wall face."""
    limit = inner_half(params)
    return min(limit - abs(x), limit - abs(y))


def gap_to_box(x, y, bx, by, half):
    """Metres from the marker centre to an axis aligned box. Negative if inside."""
    dx = abs(x - bx) - half
    dy = abs(y - by) - half
    if dx <= 0.0 and dy <= 0.0:
        return max(dx, dy)
    return math.hypot(max(dx, 0.0), max(dy, 0.0))


def test_seed_42_reproduces_positions_csv():
    assert generate_positions(42, shared()) == read_positions(POSITIONS)


def test_positions_inside_room_clear_of_obstacles_and_in_range():
    params = shared()
    box_half = float(params['box_size_m']) / 2.0
    boxes = [(float(params['box1_x']), float(params['box1_y'])),
             (float(params['box2_x']), float(params['box2_y']))]
    for row in read_positions(POSITIONS):
        x, y = row['x'], row['y']
        assert gap_to_wall(x, y, params) > 0.0
        assert gap_to_wall(x, y, params) >= 0.4
        for bx, by in boxes:
            assert gap_to_box(x, y, bx, by, box_half) >= 0.4
        assert 1.0 <= row['distance_m'] <= 2.5
        # x and y are stored to the millimetre, so the length of the stored point
        # can sit 1 mm outside the band the generator sampled.
        dist = math.hypot(x, y)
        assert 1.0 - 0.001 <= dist <= 2.5 + 0.001


def test_at_least_three_bearings_outside_camera_view():
    params = shared()
    half_fov = float(params['camera_hfov_deg']) / 2.0
    outside = [row for row in read_positions(POSITIONS)
               if abs(row['bearing_deg']) > half_fov]
    assert len(outside) >= 3


def test_occluded_rows_are_the_ones_blocked_by_a_box():
    params = shared()
    rows = read_positions(POSITIONS)
    occluded = [row['trial'] for row in rows if row['occluded'] == 1]
    blocked = [row['trial'] for row in rows
               if line_of_sight_blocked(row['x'], row['y'], params)]
    assert len(occluded) == 2
    assert occluded == blocked


def test_default_trials_dir_is_source_tree(monkeypatch):
    monkeypatch.delenv('BEACON_TRIALS_DIR', raising=False)
    source = os.path.join(PKG, 'trials')
    assert resolve_trials_dir() == source
    assert resolve_trials_dir('') == source
    monkeypatch.setenv('BEACON_TRIALS_DIR', '/tmp/beacon-trials-override')
    assert resolve_trials_dir() == '/tmp/beacon-trials-override'
    assert resolve_trials_dir('/tmp/beacon-trials-explicit') == '/tmp/beacon-trials-explicit'
