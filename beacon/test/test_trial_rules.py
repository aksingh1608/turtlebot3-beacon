"""Rules for a missing trial id. No ROS needed."""

from beacon.trial_rules import frame_filename, has_trial_id, resolve_save_dir, timeout_due


def test_blank_trial_id_is_not_recorded():
    assert has_trial_id(None) is False
    assert has_trial_id('') is False
    assert has_trial_id('   ') is False
    assert has_trial_id('none') is False
    assert has_trial_id('1') is True
    assert has_trial_id(1) is True


def test_frame_name_and_save_dir():
    assert frame_filename('1', 'SEARCH', 12.3) == 'trial_1_SEARCH_12.30.png'
    assert resolve_save_dir('', '/repo/beacon/trials') == '/repo/beacon/trials/frames'
    assert resolve_save_dir('/tmp/frames', '/repo/beacon/trials') == '/tmp/frames'
    assert resolve_save_dir('docs/screenshots/frames', '/repo/beacon/trials') == \
        '/repo/docs/screenshots/frames'


def test_timeout_does_not_start_until_a_trial_id_arrives():
    assert timeout_due(None, 120.0, 60.0) is False
    assert timeout_due('', 120.0, 60.0) is False
    assert timeout_due('none', 120.0, 60.0) is False
    assert timeout_due('1', 59.9, 60.0) is False
    assert timeout_due('1', 60.0, 60.0) is True
