"""Spawn the red marker for one trial and announce the trial id.

Usage (inside the container, or on a Humble install):
    ros2 run beacon spawn_marker --trial 3
    ros2 run beacon spawn_marker --x 1.5 --y -0.8
    ros2 run beacon spawn_marker --random-seed 7
    ros2 run beacon spawn_marker --write-positions --seed 42

The position generator is a plain function so it also runs without ROS.
ROS imports happen inside main() for that reason.
"""

import argparse
import csv
import json
import math
import os
import random
import sys
import time

import yaml

POSITIONS_COLUMNS = ['trial', 'x', 'y', 'distance_m', 'bearing_deg', 'occluded']


def find_share_dir():
    """Package share directory when installed, else the source tree."""
    try:
        from ament_index_python.packages import get_package_share_directory
        return get_package_share_directory('beacon')
    except Exception:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_shared_params(share_dir=None):
    share_dir = share_dir or find_share_dir()
    path = os.path.join(share_dir, 'config', 'params.yaml')
    with open(path, 'r') as f:
        data = yaml.safe_load(f)
    return data['beacon_shared']['ros__parameters']


def source_package_root():
    """Package directory in the source tree, the folder that holds trials/.

    realpath follows a symlink install back to the checkout. A plain copy
    under an install prefix is matched to <workspace>/src/beacon when that
    checkout exists.
    """
    here = os.path.realpath(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    marker = os.path.join('trials', 'positions.csv')
    if os.path.isfile(os.path.join(root, marker)):
        return root
    parts = here.split(os.sep)
    if 'install' in parts:
        workspace = os.sep.join(parts[:parts.index('install')]) or os.sep
        src = os.path.join(workspace, 'src', 'beacon')
        if os.path.isfile(os.path.join(src, marker)):
            return src
    return root


def resolve_trials_dir(explicit=''):
    """Where positions.csv, logs and results live.

    Order: explicit argument, BEACON_TRIALS_DIR, then trials/ in the source tree.
    """
    if explicit:
        return os.path.abspath(os.path.expanduser(explicit))
    env = os.environ.get('BEACON_TRIALS_DIR', '')
    if env:
        return os.path.abspath(os.path.expanduser(env))
    return os.path.join(source_package_root(), 'trials')


def wrap_deg(a):
    """Wrap an angle in degrees to [-180, 180)."""
    return (a + 180.0) % 360.0 - 180.0


def box_centres(shared):
    return [(float(shared['box1_x']), float(shared['box1_y'])),
            (float(shared['box2_x']), float(shared['box2_y']))]


def clear_of_walls(x, y, shared):
    limit = (float(shared['room_size_m']) / 2.0 - float(shared['wall_thickness_m']) / 2.0
             - float(shared['clearance_m']) - float(shared['marker_radius_m']))
    return abs(x) <= limit and abs(y) <= limit


def clear_of_boxes(x, y, shared):
    need = (float(shared['box_size_m']) / 2.0 + float(shared['clearance_m'])
            + float(shared['marker_radius_m']))
    return all(max(abs(x - bx), abs(y - by)) >= need for bx, by in box_centres(shared))


def box_half_angle_deg(dist, shared):
    """Angular half width of a box seen from the origin at distance dist."""
    return math.degrees(math.atan2(float(shared['box_size_m']) / 2.0, dist))


def line_of_sight_blocked(x, y, shared):
    """True if a box sits between the origin and the marker."""
    dist = math.hypot(x, y)
    bearing = math.degrees(math.atan2(y, x))
    marker_half = math.degrees(math.atan2(float(shared['marker_radius_m']), dist))
    for bx, by in box_centres(shared):
        bdist = math.hypot(bx, by)
        if bdist >= dist:
            continue
        bbearing = math.degrees(math.atan2(by, bx))
        diff = abs(wrap_deg(bearing - bbearing))
        # Use the diagonal half size so any box orientation is covered.
        half = math.degrees(math.atan2(float(shared['box_size_m']) / 2.0 * math.sqrt(2.0), bdist))
        if diff < half + marker_half:
            return True
    return False


def position_ok(x, y, shared):
    return clear_of_walls(x, y, shared) and clear_of_boxes(x, y, shared)


def generate_positions(seed, shared, n=None, occluded=None):
    """Return a list of trial dicts for positions.csv.

    Free trials are spread over 360 degrees with one bearing bin per trial.
    Occluded trials sit behind a box so the box hides about half the marker
    from the start pose.
    """
    n = int(shared['n_trials']) if n is None else int(n)
    occluded = int(shared['occluded_trials']) if occluded is None else int(occluded)
    free = n - occluded
    rng = random.Random(seed)
    dmin = float(shared['dist_min_m'])
    dmax = float(shared['dist_max_m'])
    rows = []
    bin_width = 360.0 / free
    for i in range(free):
        for _ in range(10000):
            bearing = wrap_deg(i * bin_width + rng.uniform(0.0, bin_width))
            dist = rng.uniform(dmin, dmax)
            x = dist * math.cos(math.radians(bearing))
            y = dist * math.sin(math.radians(bearing))
            if position_ok(x, y, shared) and not line_of_sight_blocked(x, y, shared):
                break
        else:
            raise RuntimeError('could not place free trial %d' % (i + 1))
        rows.append(_row(len(rows) + 1, x, y, 0))
    boxes = box_centres(shared)
    for j in range(occluded):
        bx, by = boxes[j % len(boxes)]
        bdist = math.hypot(bx, by)
        bbearing = math.degrees(math.atan2(by, bx))
        for _ in range(10000):
            side = rng.choice((-1.0, 1.0))
            bearing = wrap_deg(bbearing + side * box_half_angle_deg(bdist, shared))
            dist = bdist + rng.uniform(float(shared['occlusion_extra_dist_min_m']),
                                       float(shared['occlusion_extra_dist_max_m']))
            dist = min(dist, dmax)
            x = dist * math.cos(math.radians(bearing))
            y = dist * math.sin(math.radians(bearing))
            if (dmin <= dist <= dmax and position_ok(x, y, shared)
                    and line_of_sight_blocked(x, y, shared)):
                break
        else:
            raise RuntimeError('could not place occluded trial %d' % (j + 1))
        rows.append(_row(len(rows) + 1, x, y, 1))
    return rows


def _row(trial, x, y, occluded):
    return {
        'trial': trial,
        'x': round(x, 3),
        'y': round(y, 3),
        'distance_m': round(math.hypot(x, y), 3),
        'bearing_deg': round(math.degrees(math.atan2(y, x)), 1),
        'occluded': int(occluded),
    }


def write_positions(rows, path):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=POSITIONS_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def read_positions(path):
    with open(path, newline='') as f:
        return [{
            'trial': int(r['trial']),
            'x': float(r['x']),
            'y': float(r['y']),
            'distance_m': float(r['distance_m']),
            'bearing_deg': float(r['bearing_deg']),
            'occluded': int(r['occluded']),
        } for r in csv.DictReader(f)]


def describe(rows, shared):
    half_fov = float(shared['camera_hfov_deg']) / 2.0
    lines = []
    for r in rows:
        view = 'in view' if abs(r['bearing_deg']) <= half_fov else 'out of view'
        occ = ', occluded' if r['occluded'] else ''
        lines.append('trial %2d  x %+6.3f  y %+6.3f  dist %.3f  bearing %+7.1f  %s%s' % (
            r['trial'], r['x'], r['y'], r['distance_m'], r['bearing_deg'], view, occ))
    return '\n'.join(lines)


def parse_args(argv):
    ap = argparse.ArgumentParser(description='Spawn the Beacon red marker for one trial.')
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--trial', type=int, help='row from positions.csv')
    g.add_argument('--random-seed', type=int, help='one random position from this seed')
    g.add_argument('--write-positions', action='store_true',
                   help='regenerate positions.csv and exit (no ROS needed)')
    ap.add_argument('--x', type=float, help='marker x in metres')
    ap.add_argument('--y', type=float, help='marker y in metres')
    ap.add_argument('--seed', type=int, default=None, help='seed for --write-positions')
    ap.add_argument('--trials-dir', default='', help='folder holding positions.csv and logs')
    ap.add_argument('--no-reset', action='store_true', help='skip the /reset_world call')
    return ap.parse_args(argv)


def choose_position(args, shared, trials_dir):
    """Return (trial_id, row) for the requested position."""
    if args.trial is not None:
        rows = read_positions(os.path.join(trials_dir, 'positions.csv'))
        match = [r for r in rows if r['trial'] == args.trial]
        if not match:
            raise SystemExit('trial %d is not in positions.csv' % args.trial)
        return str(args.trial), match[0]
    if args.x is not None and args.y is not None:
        row = _row(0, args.x, args.y, int(line_of_sight_blocked(args.x, args.y, shared)))
        return 'xy_%.2f_%.2f' % (args.x, args.y), row
    if args.random_seed is not None:
        rng = random.Random(args.random_seed)
        for _ in range(10000):
            bearing = rng.uniform(-180.0, 180.0)
            dist = rng.uniform(float(shared['dist_min_m']), float(shared['dist_max_m']))
            x = dist * math.cos(math.radians(bearing))
            y = dist * math.sin(math.radians(bearing))
            if position_ok(x, y, shared):
                break
        row = _row(0, x, y, int(line_of_sight_blocked(x, y, shared)))
        return 'seed%d' % args.random_seed, row
    raise SystemExit('give --trial N, or --x X --y Y, or --random-seed S')


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    share = find_share_dir()
    shared = load_shared_params(share)
    trials_dir = resolve_trials_dir(args.trials_dir)

    if args.write_positions:
        seed = int(shared['default_seed']) if args.seed is None else args.seed
        rows = generate_positions(seed, shared)
        path = os.path.join(trials_dir, 'positions.csv')
        write_positions(rows, path)
        print('wrote %s with seed %d' % (path, seed))
        print(describe(rows, shared))
        return 0

    trial_id, row = choose_position(args, shared, trials_dir)

    # ROS imports live here so the generator above works without ROS.
    import rclpy
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
    from std_msgs.msg import String
    from std_srvs.srv import Empty
    from gazebo_msgs.srv import DeleteEntity, SpawnEntity

    timeout = float(shared['service_timeout_s'])
    entity = str(shared['marker_entity_name'])
    rclpy.init()
    node = rclpy.create_node('spawn_marker')

    def call(client, request, label):
        if not client.wait_for_service(timeout_sec=timeout):
            node.get_logger().error('%s service not available after %.0f s' % (label, timeout))
            return None
        future = client.call_async(request)
        rclpy.spin_until_future_complete(node, future, timeout_sec=timeout)
        if not future.done():
            node.get_logger().error('%s call timed out' % label)
            return None
        return future.result()

    if not args.no_reset:
        call(node.create_client(Empty, '/reset_world'), Empty.Request(), '/reset_world')

    delete_req = DeleteEntity.Request()
    delete_req.name = entity
    res = call(node.create_client(DeleteEntity, '/delete_entity'), delete_req, '/delete_entity')
    if res is not None and not res.success:
        node.get_logger().info('no existing %s to delete' % entity)

    with open(os.path.join(share, 'models', 'red_marker', 'model.sdf'), 'r') as f:
        xml = f.read()
    spawn_req = SpawnEntity.Request()
    spawn_req.name = entity
    spawn_req.xml = xml
    spawn_req.initial_pose.position.x = float(row['x'])
    spawn_req.initial_pose.position.y = float(row['y'])
    spawn_req.initial_pose.position.z = 0.0
    spawn_req.initial_pose.orientation.w = 1.0
    res = call(node.create_client(SpawnEntity, '/spawn_entity'), spawn_req, '/spawn_entity')
    if res is None or not res.success:
        node.get_logger().error('spawn failed: %s' % (res.status_message if res else 'no reply'))
        node.destroy_node()
        rclpy.shutdown()
        return 1

    os.makedirs(trials_dir, exist_ok=True)
    info = dict(row)
    info['trial'] = trial_id
    info['written_at'] = time.time()
    with open(os.path.join(trials_dir, 'current_trial.json'), 'w') as f:
        json.dump(info, f, indent=2)

    qos = QoSProfile(depth=1, history=HistoryPolicy.KEEP_LAST,
                     reliability=ReliabilityPolicy.RELIABLE,
                     durability=DurabilityPolicy.TRANSIENT_LOCAL)
    pub = node.create_publisher(String, '/beacon/trial', qos)
    msg = String()
    msg.data = trial_id
    pub.publish(msg)
    # Keep the latched publisher alive long enough for the nodes to receive it.
    end = time.time() + float(shared['spawn_settle_s'])
    while time.time() < end:
        rclpy.spin_once(node, timeout_sec=0.1)
        pub.publish(msg)

    print('trial %s: marker at x=%.3f y=%.3f, distance %.3f m, bearing %.1f deg, occluded %d' % (
        trial_id, row['x'], row['y'], row['distance_m'], row['bearing_deg'], row['occluded']))
    node.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
