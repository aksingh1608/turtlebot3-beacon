"""Unit tests for beacon.vision. No ROS needed: run with pytest."""

import math

import cv2
import numpy as np

from beacon.vision import debug_image_shape, detect_marker, draw_debug

W, H = 640, 480

# Same values as config/params.yaml detector_node section.
PARAMS = {
    'h_low1': 0, 'h_high1': 10, 'h_low2': 170, 'h_high2': 179,
    's_min': 120, 'v_min': 70,
    'morph_kernel': 5,
    'min_area_px': 150,
    'center_tol': 0.10,
    'debug_top_px': 40, 'debug_bottom_px': 40, 'debug_margin_px': 12,
    'debug_font_scale': 0.55, 'debug_font_thickness': 1,
    'debug_line_px': 2, 'debug_dot_px': 5, 'debug_band_alpha': 0.35,
    'debug_color_contour': [0, 255, 0],
    'debug_color_centroid': [0, 255, 255],
    'debug_color_bbox': [255, 200, 0],
    'debug_color_centre_line': [255, 255, 255],
    'debug_color_band': [120, 120, 120],
    'debug_color_text': [255, 255, 255],
    'debug_color_strip': [30, 30, 30],
    'debug_color_bar': [200, 200, 200],
    'debug_color_bar_marker': [0, 0, 255],
}

RED = (0, 0, 255)
GREY = (90, 90, 90)


def blank():
    img = np.zeros((H, W, 3), dtype=np.uint8)
    img[:] = GREY
    return img


def disc(img, cx, cy, r, color=RED):
    cv2.circle(img, (cx, cy), r, color, -1)
    return img


def test_red_disc_found_with_known_offset_and_area():
    cx, cy, r = 400, 240, 40
    det = detect_marker(disc(blank(), cx, cy, r), PARAMS)
    assert det['found'] is True
    expected_offset = (cx - W / 2) / (W / 2)
    assert abs(det['offset'] - expected_offset) < 0.02
    expected_area = math.pi * r * r / (W * H)
    assert abs(det['area_frac'] - expected_area) / expected_area < 0.10
    assert abs(det['cx'] - cx) < 2 and abs(det['cy'] - cy) < 2
    x, y, w, h = det['bbox']
    assert x <= cx <= x + w and y <= cy <= y + h


def test_offset_sign_left_centre_right():
    left = detect_marker(disc(blank(), 100, 240, 30), PARAMS)
    centre = detect_marker(disc(blank(), 320, 240, 30), PARAMS)
    right = detect_marker(disc(blank(), 540, 240, 30), PARAMS)
    assert left['offset'] < -0.5
    assert abs(centre['offset']) < 0.02
    assert right['offset'] > 0.5


def test_no_red_not_found():
    img = blank()
    disc(img, 320, 240, 50, color=(255, 0, 0))
    disc(img, 100, 100, 50, color=(0, 255, 0))
    det = detect_marker(img, PARAMS)
    assert det['found'] is False
    assert det['offset'] == 0.0
    assert det['area_frac'] == 0.0


def test_small_speck_rejected():
    # A 5 px radius disc is about 79 px of area, below min_area_px.
    det = detect_marker(disc(blank(), 320, 240, 5), PARAMS)
    assert det['found'] is False


def test_larger_of_two_blobs_wins():
    img = blank()
    disc(img, 120, 240, 20)
    disc(img, 500, 240, 45)
    det = detect_marker(img, PARAMS)
    assert det['found'] is True
    assert det['offset'] > 0.4
    assert abs(det['cx'] - 500) < 2


def test_dark_red_hue_band_wraps():
    # Hue near 179 also counts as red.
    hsv = np.zeros((H, W, 3), dtype=np.uint8)
    hsv[:] = (60, 40, 120)
    cv2.circle(hsv, (320, 240), 40, (176, 200, 200), -1)
    det = detect_marker(cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR), PARAMS)
    assert det['found'] is True


def test_draw_debug_size_and_type():
    img = disc(blank(), 400, 240, 40)
    det = detect_marker(img, PARAMS)
    out = draw_debug(img, det, 'ALIGN', 12.3, PARAMS)
    assert out.shape == debug_image_shape(img.shape, PARAMS)
    assert out.shape == (H + 80, 2 * W, 3)
    assert out.dtype == np.uint8
    # Also works with no detection at all.
    out2 = draw_debug(blank(), None, 'SEARCH', 0.0, PARAMS)
    assert out2.shape == (H + 80, 2 * W, 3)
