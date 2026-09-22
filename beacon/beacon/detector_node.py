"""Detector node: camera frames in, marker target and debug image out."""

import os
import time
from collections import deque

import cv2
import rclpy
from cv_bridge import CvBridge
from geometry_msgs.msg import Point
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.signals import SignalHandlerOptions
from sensor_msgs.msg import Image
from std_msgs.msg import String

from beacon.ros_util import T, declare_typed, latched_qos, now_s, read_params
from beacon.spawn_marker import resolve_trials_dir
from beacon.vision import detect_marker, draw_debug

VISION_SPEC = {
    'h_low1': T.INTEGER, 'h_high1': T.INTEGER, 'h_low2': T.INTEGER, 'h_high2': T.INTEGER,
    's_min': T.INTEGER, 'v_min': T.INTEGER,
    'morph_kernel': T.INTEGER, 'min_area_px': T.INTEGER,
    'center_tol': T.DOUBLE,
    'debug_top_px': T.INTEGER, 'debug_bottom_px': T.INTEGER, 'debug_margin_px': T.INTEGER,
    'debug_font_scale': T.DOUBLE, 'debug_font_thickness': T.INTEGER,
    'debug_line_px': T.INTEGER, 'debug_dot_px': T.INTEGER, 'debug_band_alpha': T.DOUBLE,
    'debug_color_contour': T.INTEGER_ARRAY, 'debug_color_centroid': T.INTEGER_ARRAY,
    'debug_color_bbox': T.INTEGER_ARRAY, 'debug_color_centre_line': T.INTEGER_ARRAY,
    'debug_color_band': T.INTEGER_ARRAY, 'debug_color_text': T.INTEGER_ARRAY,
    'debug_color_strip': T.INTEGER_ARRAY, 'debug_color_bar': T.INTEGER_ARRAY,
    'debug_color_bar_marker': T.INTEGER_ARRAY,
}

NODE_SPEC = {
    'image_topic': T.STRING, 'qos_depth': T.INTEGER,
    'log_period_s': T.DOUBLE, 'fps_window': T.INTEGER,
    'save_frames': T.BOOL, 'save_dir': T.STRING, 'save_period_s': T.DOUBLE,
    'trials_dir': T.STRING,
}


class DetectorNode(Node):

    def __init__(self):
        super().__init__('detector_node')
        declare_typed(self, VISION_SPEC)
        declare_typed(self, NODE_SPEC)
        self.p = read_params(self, VISION_SPEC.keys())
        cfg = read_params(self, NODE_SPEC.keys())
        depth = int(cfg['qos_depth'])

        self.bridge = CvBridge()
        self.state = 'NONE'
        self.trial_id = 'none'
        self.frames = 0
        self.hits = 0
        self.stamps = deque(maxlen=int(cfg['fps_window']))
        self.save_frames = bool(cfg['save_frames'])
        self.save_period_s = float(cfg['save_period_s'])
        self.save_dir = cfg['save_dir'] or os.path.join(resolve_trials_dir(cfg['trials_dir']), 'frames')
        self.save_next = False
        self.last_save_s = -1.0
        if self.save_frames:
            os.makedirs(self.save_dir, exist_ok=True)

        self.target_pub = self.create_publisher(Point, '/beacon/target', depth)
        self.debug_pub = self.create_publisher(Image, '/beacon/debug_image', depth)
        self.create_subscription(Image, cfg['image_topic'], self.on_image, qos_profile_sensor_data)
        self.create_subscription(String, '/beacon/state', self.on_state, depth)
        self.create_subscription(String, '/beacon/trial', self.on_trial, latched_qos())
        self.create_timer(float(cfg['log_period_s']), self.on_log_timer)
        self.get_logger().info('detector listening on %s' % cfg['image_topic'])

    def on_state(self, msg):
        if msg.data != self.state:
            self.state = msg.data
            self.save_next = True

    def on_trial(self, msg):
        self.trial_id = msg.data

    def on_image(self, msg):
        try:
            bgr = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:
            self.get_logger().warn('image conversion failed: %s' % e)
            return
        det = detect_marker(bgr, self.p)
        self.frames += 1
        if det['found']:
            self.hits += 1

        target = Point()
        target.x = float(det['offset'])
        target.y = float(det['area_frac'])
        target.z = 1.0 if det['found'] else 0.0
        self.target_pub.publish(target)

        self.stamps.append(time.monotonic())
        fps = 0.0
        if len(self.stamps) > 1:
            span = self.stamps[-1] - self.stamps[0]
            if span > 0.0:
                fps = (len(self.stamps) - 1) / span

        debug = draw_debug(bgr, det, self.state, fps, self.p)
        out = self.bridge.cv2_to_imgmsg(debug, encoding='bgr8')
        out.header = msg.header
        self.debug_pub.publish(out)

        if self.save_frames:
            self.maybe_save(debug)

    def maybe_save(self, debug):
        t = now_s(self)
        periodic = self.state == 'APPROACH' and (t - self.last_save_s) >= self.save_period_s
        if not (self.save_next or periodic):
            return
        name = 'trial%s_%08.2fs_%s.png' % (self.trial_id, t, self.state)
        cv2.imwrite(os.path.join(self.save_dir, name), debug)
        self.save_next = False
        self.last_save_s = t

    def on_log_timer(self):
        if self.frames == 0:
            self.get_logger().info('no frames received yet')
            return
        rate = 100.0 * self.hits / self.frames
        self.get_logger().info('detection rate %.0f%% (%d of %d frames), state %s' % (
            rate, self.hits, self.frames, self.state))
        self.frames = 0
        self.hits = 0


def main(args=None):
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = DetectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
