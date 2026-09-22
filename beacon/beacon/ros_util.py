"""Small helpers shared by the Beacon nodes."""

import math

from geometry_msgs.msg import Twist
from rclpy.parameter import Parameter
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

STATES = ('SEARCH', 'ALIGN', 'APPROACH', 'STOP', 'TIMEOUT')

# Parameter types, keyed by the names used in config/params.yaml.
T = Parameter.Type


def declare_typed(node, spec):
    """Declare parameters with a type and no default.

    The values must come from config/params.yaml or a launch override.
    A missing value raises ParameterUninitializedException on first read,
    which is the intended failure: nodes carry no tunables of their own.
    """
    for name, ptype in spec.items():
        node.declare_parameter(name, ptype)


def read_params(node, names):
    return {name: node.get_parameter(name).value for name in names}


def latched_qos():
    """QoS for /beacon/trial: late subscribers still get the last id."""
    return QoSProfile(depth=1, history=HistoryPolicy.KEEP_LAST,
                      reliability=ReliabilityPolicy.RELIABLE,
                      durability=DurabilityPolicy.TRANSIENT_LOCAL)


def now_s(node):
    return node.get_clock().now().nanoseconds * 1e-9


def zero_twist():
    return Twist()


def yaw_from_quaternion(q):
    siny = 2.0 * (q.w * q.z + q.x * q.y)
    cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny, cosy)


def front_range(scan, cone_deg):
    """Smallest valid range within cone_deg of straight ahead.

    Returns math.inf when no beam in the cone carries a valid value.
    Inf, nan, zero and values outside [range_min, range_max] are ignored.
    """
    cone = math.radians(cone_deg)
    best = math.inf
    angle = scan.angle_min
    for r in scan.ranges:
        a = math.atan2(math.sin(angle), math.cos(angle))
        angle += scan.angle_increment
        if abs(a) > cone:
            continue
        if not math.isfinite(r) or r <= 0.0 or r < scan.range_min or r > scan.range_max:
            continue
        if r < best:
            best = r
    return best
