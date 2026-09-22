"""Trial bookkeeping rules with no ROS imports.

A results row is written only when a trial id has arrived.
TIMEOUT does not start counting until that same id has arrived.
The id "none" is the controller's value before the first trial.
"""


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
