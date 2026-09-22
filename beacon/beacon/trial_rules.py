"""Trial bookkeeping rules with no ROS imports.

A results row is written only when a trial id has arrived.
TIMEOUT does not start counting until that same id has arrived.
The id "none" is the controller's value before the first trial.
"""

import os


def has_trial_id(trial_id):
    if trial_id is None:
        return False
    text = str(trial_id).strip()
    return text != '' and text != 'none'


def timeout_due(trial_id, elapsed_s, timeout_s):
    """True when this trial has run long enough to time out."""
    if not has_trial_id(trial_id):
        return False
    return float(elapsed_s) >= float(timeout_s)


def frame_filename(trial_id, state, sim_time_s):
    """Debug frame name: trial_<id>_<state>_<sim_time>.png."""
    return 'trial_%s_%s_%.2f.png' % (trial_id, state, float(sim_time_s))


def resolve_save_dir(save_dir, trials_dir):
    """Absolute folder for debug frames.

    An empty save_dir means <trials_dir>/frames.
    A relative save_dir is from the repo root, the parent of the beacon package.
    """
    if not save_dir:
        return os.path.join(trials_dir, 'frames')
    if os.path.isabs(save_dir):
        return save_dir
    package_root = os.path.dirname(os.path.abspath(trials_dir))
    repo_root = os.path.dirname(package_root)
    return os.path.join(repo_root, save_dir)
