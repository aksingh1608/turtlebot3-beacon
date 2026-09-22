"""Trial logger node: per tick CSV rows, a results row per trial, RViz path."""

import csv
import json
import math
import os
import time

import rclpy
from geometry_msgs.msg import Point, PoseStamped, Twist
from nav_msgs.msg import Odometry, Path
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.signals import SignalHandlerOptions
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String

from beacon.ros_util import (T, declare_typed, front_range, latched_qos, now_s,
                             read_params, yaw_from_quaternion)
from beacon.spawn_marker import resolve_trials_dir
from beacon.trial_rules import has_trial_id

SPEC = {
    'log_hz': T.DOUBLE, 'qos_depth': T.INTEGER, 'trials_dir': T.STRING,
    'path_max_poses': T.INTEGER, 'json_retry_s': T.DOUBLE, 'json_retries': T.INTEGER,
    'front_cone_deg': T.DOUBLE,
}

LOG_COLUMNS = ['t', 'x', 'y', 'yaw', 'state', 'offset', 'area_frac', 'found',
               'front_range', 'linear_cmd', 'angular_cmd']
RESULT_COLUMNS = ['trial', 'marker_x', 'marker_y', 'bearing_deg', 'occluded', 'first_seen_s',
                  'reached', 'time_to_reach_s', 'final_range_m', 'path_length_m',
                  'search_time_s', 'align_time_s', 'approach_time_s']


class TrialLoggerNode(Node):

    def __init__(self):
        super().__init__('trial_logger_node')
        declare_typed(self, SPEC)
        self.p = read_params(self, SPEC.keys())
        depth = int(self.p['qos_depth'])
        self.trials_dir = resolve_trials_dir(self.p['trials_dir'])
        self.logs_dir = os.path.join(self.trials_dir, 'logs')
        os.makedirs(self.logs_dir, exist_ok=True)

        self.trial_id = None
        self.marker = {}
        self.log_file = None
        self.log_writer = None
        self.reset_trial_stats()

        self.pose = None
        self.yaw = 0.0
        self.offset = 0.0
        self.area_frac = 0.0
        self.found = False
        self.state = 'SEARCH'
        self.front = math.inf
        self.linear_cmd = 0.0
        self.angular_cmd = 0.0

        self.path = Path()
        self.path_pub = self.create_publisher(Path, '/beacon/path', depth)
        self.create_subscription(Odometry, '/odom', self.on_odom, depth)
        self.create_subscription(Point, '/beacon/target', self.on_target, depth)
        self.create_subscription(String, '/beacon/state', self.on_state, depth)
        self.create_subscription(LaserScan, '/scan', self.on_scan, qos_profile_sensor_data)
        self.create_subscription(Twist, '/cmd_vel', self.on_cmd, depth)
        self.create_subscription(String, '/beacon/trial', self.on_trial, latched_qos())
        self.create_timer(1.0 / float(self.p['log_hz']), self.on_tick)
        self.get_logger().info('logging to %s' % self.logs_dir)

    def reset_trial_stats(self):
        self.trial_start_s = now_s(self)
        self.first_seen_s = None
        self.path_length = 0.0
        self.last_xy = None
        self.state_time = {'SEARCH': 0.0, 'ALIGN': 0.0, 'APPROACH': 0.0}
        self.state_since_s = self.trial_start_s
        self.finished = False

    def on_trial(self, msg):
        if not has_trial_id(msg.data):
            self.get_logger().warn('ignoring blank trial id')
            return
        if msg.data == self.trial_id and not self.finished:
            return
        self.close_log()
        self.trial_id = msg.data
        self.marker = self.read_current_trial(msg.data)
        self.reset_trial_stats()
        self.state = 'SEARCH'
        self.path = Path()
        self.path.header.frame_id = 'odom'
        path = os.path.join(self.logs_dir, 'trial_%s.csv' % self.trial_id)
        self.log_file = open(path, 'w', newline='')
        self.log_writer = csv.writer(self.log_file)
        self.log_writer.writerow(LOG_COLUMNS)
        self.get_logger().info('trial %s: logging to %s' % (self.trial_id, path))

    def read_current_trial(self, trial_id):
        """Marker position written by spawn_marker, retried briefly."""
        path = os.path.join(self.trials_dir, 'current_trial.json')
        for _ in range(int(self.p['json_retries'])):
            try:
                with open(path) as f:
                    info = json.load(f)
                if str(info.get('trial')) == str(trial_id):
                    return info
            except (OSError, ValueError):
                pass
            time.sleep(float(self.p['json_retry_s']))
        self.get_logger().warn('no current_trial.json for trial %s, marker columns left blank'
                               % trial_id)
        return {}

    def close_log(self):
        if self.log_file is not None:
            self.log_file.close()
            self.log_file = None
            self.log_writer = None

    def on_odom(self, msg):
        self.pose = msg.pose.pose
        self.yaw = yaw_from_quaternion(msg.pose.pose.orientation)

    def on_target(self, msg):
        self.found = msg.z > 0.5
        self.offset = msg.x
        self.area_frac = msg.y
        if self.found and self.first_seen_s is None:
            self.first_seen_s = now_s(self) - self.trial_start_s

    def on_scan(self, msg):
        self.front = front_range(msg, float(self.p['front_cone_deg']))

    def on_cmd(self, msg):
        self.linear_cmd = msg.linear.x
        self.angular_cmd = msg.angular.z

    def on_state(self, msg):
        if msg.data == self.state:
            return
        t = now_s(self)
        if self.state in self.state_time:
            self.state_time[self.state] += t - self.state_since_s
        self.state_since_s = t
        self.state = msg.data
        if self.state in ('STOP', 'TIMEOUT') and not self.finished:
            self.finished = True
            if has_trial_id(self.trial_id):
                self.write_result(t)
            else:
                self.get_logger().info('no trial id, results row skipped')

    def on_tick(self):
        if self.pose is None:
            return
        t = now_s(self)
        x = self.pose.position.x
        y = self.pose.position.y
        if self.last_xy is not None and not self.finished:
            self.path_length += math.hypot(x - self.last_xy[0], y - self.last_xy[1])
        self.last_xy = (x, y)

        ps = PoseStamped()
        ps.header.frame_id = 'odom'
        ps.header.stamp = self.get_clock().now().to_msg()
        ps.pose = self.pose
        self.path.header = ps.header
        self.path.poses.append(ps)
        if len(self.path.poses) > int(self.p['path_max_poses']):
            del self.path.poses[0]
        self.path_pub.publish(self.path)

        if self.log_writer is None or self.finished:
            return
        front = '' if math.isinf(self.front) else '%.3f' % self.front
        self.log_writer.writerow([
            '%.3f' % (t - self.trial_start_s), '%.4f' % x, '%.4f' % y, '%.4f' % self.yaw,
            self.state, '%.4f' % self.offset, '%.5f' % self.area_frac, int(self.found),
            front, '%.3f' % self.linear_cmd, '%.3f' % self.angular_cmd,
        ])
        self.log_file.flush()

    def write_result(self, t):
        if not has_trial_id(self.trial_id):
            self.get_logger().info('no trial id, results row skipped')
            return
        reached = self.state == 'STOP'
        elapsed = t - self.trial_start_s
        row = {
            'trial': self.trial_id,
            'marker_x': self.marker.get('x', ''),
            'marker_y': self.marker.get('y', ''),
            'bearing_deg': self.marker.get('bearing_deg', ''),
            'occluded': self.marker.get('occluded', ''),
            'first_seen_s': '' if self.first_seen_s is None else '%.2f' % self.first_seen_s,
            'reached': int(reached),
            'time_to_reach_s': '%.2f' % elapsed if reached else '',
            'final_range_m': '' if math.isinf(self.front) else '%.3f' % self.front,
            'path_length_m': '%.3f' % self.path_length,
            'search_time_s': '%.2f' % self.state_time['SEARCH'],
            'align_time_s': '%.2f' % self.state_time['ALIGN'],
            'approach_time_s': '%.2f' % self.state_time['APPROACH'],
        }
        path = os.path.join(self.trials_dir, 'results.csv')
        new = not os.path.exists(path)
        with open(path, 'a', newline='') as f:
            w = csv.DictWriter(f, fieldnames=RESULT_COLUMNS)
            if new:
                w.writeheader()
            w.writerow(row)
        self.close_log()
        self.get_logger().info('trial %s %s after %.1f s, row appended to %s' % (
            self.trial_id, 'reached' if reached else 'timed out', elapsed, path))


def main(args=None):
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = TrialLoggerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close_log()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
