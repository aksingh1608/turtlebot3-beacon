"""Controller node: turns the marker offset into velocity commands.

States: SEARCH, ALIGN, APPROACH, STOP, TIMEOUT. Every threshold and gain
comes from config/params.yaml.
"""

import math

import rclpy
from geometry_msgs.msg import Point, Twist
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.signals import SignalHandlerOptions
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String

from beacon.ros_util import (T, declare_typed, front_range, latched_qos, now_s,
                             read_params, zero_twist)

SPEC = {
    'control_hz': T.DOUBLE, 'qos_depth': T.INTEGER,
    'lost_timeout_s': T.DOUBLE, 'search_speed': T.DOUBLE,
    'center_tol': T.DOUBLE, 'k_ang': T.DOUBLE, 'max_ang': T.DOUBLE,
    'forward_speed': T.DOUBLE, 'approach_gain': T.DOUBLE,
    'stop_area': T.DOUBLE, 'stop_range_m': T.DOUBLE,
    'trial_timeout_s': T.DOUBLE, 'front_cone_deg': T.DOUBLE,
}


class ControllerNode(Node):

    def __init__(self):
        super().__init__('controller_node')
        declare_typed(self, SPEC)
        self.p = read_params(self, SPEC.keys())
        depth = int(self.p['qos_depth'])

        self.state = 'SEARCH'
        self.trial_id = 'none'
        self.trial_start_s = now_s(self)
        self.found = False
        self.offset = 0.0
        self.area_frac = 0.0
        self.last_seen_s = None
        self.front = math.inf

        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', depth)
        self.state_pub = self.create_publisher(String, '/beacon/state', depth)
        self.create_subscription(Point, '/beacon/target', self.on_target, depth)
        self.create_subscription(LaserScan, '/scan', self.on_scan, qos_profile_sensor_data)
        self.create_subscription(String, '/beacon/trial', self.on_trial, latched_qos())
        self.create_timer(1.0 / float(self.p['control_hz']), self.on_tick)
        self.get_logger().info('controller ready, state SEARCH')

    def on_target(self, msg):
        self.found = msg.z > 0.5
        if self.found:
            self.offset = msg.x
            self.area_frac = msg.y
            self.last_seen_s = now_s(self)

    def on_scan(self, msg):
        self.front = front_range(msg, float(self.p['front_cone_deg']))

    def on_trial(self, msg):
        if msg.data == self.trial_id and self.state not in ('STOP', 'TIMEOUT'):
            return
        self.trial_id = msg.data
        self.trial_start_s = now_s(self)
        self.found = False
        self.last_seen_s = None
        self.area_frac = 0.0
        self.offset = 0.0
        self.get_logger().info('trial %s started' % self.trial_id)
        self.set_state('SEARCH')

    def set_state(self, new_state):
        if new_state == self.state:
            return
        t = now_s(self) - self.trial_start_s
        self.get_logger().info('[%.2f s] %s -> %s (offset %+.3f, area %.4f, front %.2f m)' % (
            t, self.state, new_state, self.offset, self.area_frac, self.front))
        self.state = new_state

    def marker_recent(self, t):
        return self.last_seen_s is not None and (t - self.last_seen_s) < float(self.p['lost_timeout_s'])

    def on_tick(self):
        t = now_s(self)
        cmd = zero_twist()
        if self.state not in ('STOP', 'TIMEOUT'):
            elapsed = t - self.trial_start_s
            seen_now = self.found or self.marker_recent(t)
            if elapsed >= float(self.p['trial_timeout_s']):
                self.get_logger().error('trial %s failed: %.0f s without STOP' % (
                    self.trial_id, elapsed))
                self.set_state('TIMEOUT')
            elif (self.found and self.area_frac >= float(self.p['stop_area'])) or \
                    self.front <= float(self.p['stop_range_m']):
                self.set_state('STOP')
                self.get_logger().info('reached: area %.4f, front range %.2f m' % (
                    self.area_frac, self.front))
            elif not seen_now:
                self.set_state('SEARCH')
            elif abs(self.offset) > float(self.p['center_tol']):
                self.set_state('ALIGN')
            else:
                self.set_state('APPROACH')

        if self.state == 'SEARCH':
            cmd.angular.z = float(self.p['search_speed'])
        elif self.state == 'ALIGN':
            ang = -float(self.p['k_ang']) * self.offset
            lim = float(self.p['max_ang'])
            cmd.angular.z = max(-lim, min(lim, ang))
        elif self.state == 'APPROACH':
            cmd.linear.x = float(self.p['forward_speed'])
            cmd.angular.z = -float(self.p['k_ang']) * float(self.p['approach_gain']) * self.offset

        self.cmd_pub.publish(cmd)
        msg = String()
        msg.data = self.state
        self.state_pub.publish(msg)

    def publish_zero(self):
        self.cmd_pub.publish(zero_twist())


def main(args=None):
    # Handle SIGINT ourselves so the zero velocity below still goes out.
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = ControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.publish_zero()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
