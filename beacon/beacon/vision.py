"""Pure image processing for the Beacon marker detector.

No ROS imports live here so the functions run under plain pytest.
All thresholds and colours arrive in the parameter dict `p`, which the
detector node fills from config/params.yaml.
"""

import cv2
import numpy as np

# Fixed OpenCV ranges, not tunables.
HSV_MAX = 255
FONT = cv2.FONT_HERSHEY_SIMPLEX


def empty_detection(mask=None):
    """The dict returned when no marker is accepted."""
    return {
        'found': False,
        'cx': None,
        'cy': None,
        'area_frac': 0.0,
        'offset': 0.0,
        'bbox': None,
        'mask': mask,
        'contour': None,
    }


def red_mask(bgr, p):
    """Binary mask of red pixels using two hue bands and morphology."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    s_min = int(p['s_min'])
    v_min = int(p['v_min'])
    low1 = np.array([int(p['h_low1']), s_min, v_min], dtype=np.uint8)
    high1 = np.array([int(p['h_high1']), HSV_MAX, HSV_MAX], dtype=np.uint8)
    low2 = np.array([int(p['h_low2']), s_min, v_min], dtype=np.uint8)
    high2 = np.array([int(p['h_high2']), HSV_MAX, HSV_MAX], dtype=np.uint8)
    mask = cv2.bitwise_or(cv2.inRange(hsv, low1, high1), cv2.inRange(hsv, low2, high2))
    k = int(p['morph_kernel'])
    if k > 1:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask


def detect_marker(bgr, p):
    """Find the largest red blob in a BGR image.

    Returns a dict with keys found, cx, cy, area_frac, offset, bbox, mask
    and contour. offset is (cx - W/2) / (W/2), so it lies in [-1, 1] and is
    positive when the marker sits to the right of the image centre.
    """
    height, width = bgr.shape[:2]
    mask = red_mask(bgr, p)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    det = empty_detection(mask)
    if not contours:
        return det
    best = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(best)
    if area < float(p['min_area_px']):
        return det
    moments = cv2.moments(best)
    if moments['m00'] <= 0.0:
        return det
    cx = moments['m10'] / moments['m00']
    cy = moments['m01'] / moments['m00']
    half_w = width / 2.0
    offset = float(np.clip((cx - half_w) / half_w, -1.0, 1.0))
    x, y, w, h = cv2.boundingRect(best)
    det.update({
        'found': True,
        'cx': float(cx),
        'cy': float(cy),
        'area_frac': float(area) / float(width * height),
        'offset': offset,
        'bbox': (int(x), int(y), int(w), int(h)),
        'contour': best,
    })
    return det


def debug_image_shape(frame_shape, p):
    """Shape of the image draw_debug returns for a frame of frame_shape."""
    height, width = frame_shape[:2]
    return (int(p['debug_top_px']) + height + int(p['debug_bottom_px']), 2 * width, 3)


def _color(p, key):
    return tuple(int(c) for c in p[key])


def draw_debug(bgr, det, state, fps, p):
    """Compose the debug view.

    Left half: the camera frame with contour, centroid, bounding box, the
    vertical centre line and the shaded centre tolerance band.
    Right half: the binary mask.
    Top strip: state, offset, area fraction and fps.
    Bottom strip: a horizontal bar from -1 to 1 with the current offset.
    """
    height, width = bgr.shape[:2]
    top = int(p['debug_top_px'])
    bottom = int(p['debug_bottom_px'])
    margin = int(p['debug_margin_px'])
    scale = float(p['debug_font_scale'])
    thick = int(p['debug_font_thickness'])
    line_px = int(p['debug_line_px'])
    dot_px = int(p['debug_dot_px'])
    alpha = float(p['debug_band_alpha'])

    out = np.zeros(debug_image_shape(bgr.shape, p), dtype=np.uint8)
    out[:] = _color(p, 'debug_color_strip')

    # Left half: frame with overlays.
    left = bgr.copy()
    half_w = width / 2.0
    tol_px = int(round(float(p['center_tol']) * half_w))
    band = left.copy()
    cv2.rectangle(band, (int(half_w) - tol_px, 0), (int(half_w) + tol_px, height - 1),
                  _color(p, 'debug_color_band'), -1)
    left = cv2.addWeighted(band, alpha, left, 1.0 - alpha, 0.0)
    cv2.line(left, (int(half_w), 0), (int(half_w), height - 1),
             _color(p, 'debug_color_centre_line'), 1)
    if det is not None and det.get('found'):
        if det.get('contour') is not None:
            cv2.drawContours(left, [det['contour']], -1, _color(p, 'debug_color_contour'), line_px)
        x, y, w, h = det['bbox']
        cv2.rectangle(left, (x, y), (x + w, y + h), _color(p, 'debug_color_bbox'), line_px)
        cv2.circle(left, (int(round(det['cx'])), int(round(det['cy']))), dot_px,
                   _color(p, 'debug_color_centroid'), -1)
    out[top:top + height, 0:width] = left

    # Right half: the mask.
    mask = det['mask'] if det is not None and det.get('mask') is not None else None
    if mask is None:
        mask = np.zeros((height, width), dtype=np.uint8)
    out[top:top + height, width:2 * width] = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)

    # Top strip text.
    found = bool(det is not None and det.get('found'))
    offset = float(det['offset']) if found else 0.0
    area_frac = float(det['area_frac']) if found else 0.0
    text = '%s   offset %+.3f   area %.4f   fps %.1f   %s' % (
        state, offset, area_frac, float(fps), 'marker' if found else 'no marker')
    text_y = top - margin // 2
    cv2.putText(out, text, (margin, text_y), FONT, scale, _color(p, 'debug_color_text'),
                thick, cv2.LINE_AA)

    # Bottom strip offset bar.
    bar_y = top + height + bottom // 2
    x0 = margin
    x1 = 2 * width - margin
    bar_color = _color(p, 'debug_color_bar')
    cv2.line(out, (x0, bar_y), (x1, bar_y), bar_color, line_px)
    mid = (x0 + x1) // 2
    half_len = (x1 - x0) / 2.0
    tol_bar = int(round(float(p['center_tol']) * half_len))
    tick = bottom // 4
    for x in (x0, mid, x1):
        cv2.line(out, (x, bar_y - tick), (x, bar_y + tick), bar_color, 1)
    cv2.rectangle(out, (mid - tol_bar, bar_y - tick), (mid + tol_bar, bar_y + tick),
                  _color(p, 'debug_color_band'), -1)
    cv2.line(out, (x0, bar_y), (x1, bar_y), bar_color, line_px)
    if found:
        mx = int(round(mid + offset * half_len))
        cv2.circle(out, (mx, bar_y), dot_px + 1, _color(p, 'debug_color_bar_marker'), -1)
    cv2.putText(out, '-1', (x0, bar_y - tick - 2), FONT, scale * 0.8, bar_color, thick, cv2.LINE_AA)
    cv2.putText(out, '+1', (x1 - 2 * margin, bar_y - tick - 2), FONT, scale * 0.8, bar_color,
                thick, cv2.LINE_AA)
    return out
