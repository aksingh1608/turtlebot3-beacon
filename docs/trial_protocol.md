# Trial protocol

Ten trials come from `generate_positions` in `beacon/beacon/spawn_marker.py` with seed 42 and the geometry in `config/params.yaml`. The robot starts at the origin facing +x. The marker is a red cylinder, radius 0.075 m, height 0.3 m. Every marker is inside the room, 1.0 to 2.5 m from the start, and at least 0.4 m clear of every wall and box.

## The ten trials

Bearing is measured from the robot's initial heading, positive to the left. The Waffle Pi camera sees about 62 degrees, so anything beyond 31 degrees starts out of view.

| Trial | x (m) | y (m) | Distance (m) | Bearing (deg) | Starts | Tests |
|---|---|---|---|---|---|---|
| 1 | 1.732 | 0.300 | 1.758 | 9.8 | in view, near centre | direct approach with a small ALIGN step |
| 2 | 0.493 | 1.749 | 1.817 | 74.2 | out of view, left | SEARCH turning left finds it early |
| 3 | -0.325 | 1.856 | 1.884 | 99.9 | out of view, left | quarter turn search |
| 4 | -0.998 | 0.151 | 1.010 | 171.4 | behind, closest | half turn then a short approach |
| 5 | -1.142 | -0.083 | 1.145 | -175.8 | behind | longest search, short approach |
| 6 | -0.228 | -1.892 | 1.906 | -96.9 | out of view, right | search passes the far walls first |
| 7 | 1.241 | -1.688 | 2.095 | -53.7 | out of view, right | search almost a full turn |
| 8 | 2.298 | -0.876 | 2.460 | -20.9 | in view, edge of frame | largest ALIGN correction, longest drive |
| 9 | 1.421 | 1.552 | 2.104 | 47.5 | out of view, half hidden by box 1 | detection of a partly hidden marker |
| 10 | -1.784 | -1.751 | 2.500 | -135.5 | out of view, half hidden by box 2 | occlusion plus the longest distance |

Trials 9 and 10 sit on the ray through the edge of a box seen from the origin, so about half the cylinder is hidden at the start. Whether the visible half exceeds `min_area_px` from 2.1 to 2.5 m is the point of those trials. CONFIRM IN SIM with a screenshot of the debug image at the start of trial 9.

## Running a trial

1. Gazebo and the three nodes are up (`ros2 launch beacon sim.launch.py`).
2. `scripts/run_trial.sh N` resets the world, deletes any old marker, spawns the marker for row N, publishes the trial id on `/beacon/trial` and waits for STOP or TIMEOUT.
3. The controller resets to SEARCH when the trial id arrives. The logger opens `logs/trial_N.csv` and starts a new path.
4. On STOP or TIMEOUT the logger appends one row to `results.csv`.

Run every trial once in order. Repeat a trial only if something outside the system went wrong (Gazebo crashed, the spawn failed). The last row per trial number counts.

## Success

A trial succeeds when the controller enters STOP within `trial_timeout_s` (60 s). STOP means the marker filled at least `stop_area` (12 percent) of the frame or the LiDAR saw an object within `stop_range_m` (0.35 m) in the front cone. A trial fails when the timeout fires first; the row shows `reached = 0` and an empty `time_to_reach_s`.

Secondary checks per trial, all from the log row:

* `first_seen_s` is short for trials 1 and 8, and longer for the trials that start behind the robot.
* `final_range_m` is below about 0.7 m, showing the robot stopped close to the marker and not at a wall or box.
* `path_length_m` is close to the marker distance for the in view trials; SEARCH adds no path length because the robot turns in place.

## Columns of results.csv

| Column | Meaning |
|---|---|
| trial | trial id (the row number of positions.csv, or `xy_...` and `seedN` for ad hoc runs) |
| marker_x, marker_y | marker position in the world frame, from current_trial.json |
| bearing_deg | marker bearing from the start pose |
| occluded | 1 when a box hides part of the marker at the start |
| first_seen_s | seconds from trial start to the first frame with the marker found |
| reached | 1 for STOP, 0 for TIMEOUT |
| time_to_reach_s | seconds from trial start to STOP, empty on failure |
| final_range_m | LiDAR front range at the end, empty if every beam in the cone was invalid |
| path_length_m | distance travelled, integrated from odom at log_hz |
| search_time_s, align_time_s, approach_time_s | seconds spent in each state |

## Columns of logs/trial_N.csv

One row per tick at `log_hz` (10 Hz): `t` (seconds since trial start), `x`, `y`, `yaw` from odom, `state`, `offset`, `area_frac`, `found` from the detector, `front_range` from the scan, and `linear_cmd`, `angular_cmd` from the last `/cmd_vel`.
