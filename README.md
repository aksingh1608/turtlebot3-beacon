# Beacon

Beacon is a vision guided TurtleBot3 simulation. A Waffle Pi in Gazebo Classic looks for a red cylinder with its camera, turns until the cylinder sits in the centre of the frame, drives towards it and stops in front of it. Ten scripted trials place the marker at different distances and bearings, two of them partly hidden behind a box, and a logger records every run for analysis.

ROSject name: ROSJECT_NAME_TBD

## Assignment mapping

| Part | What Beacon does | Where |
|---|---|---|
| Setup | Custom 6 m by 6 m room with two boxes, Waffle Pi spawned at the origin, one launch file | `worlds/beacon_room.world`, `launch/sim.launch.py` |
| Sensor | Camera frames from `/camera/image_raw`, LiDAR from `/scan`, odometry from `/odom` | `detector_node.py`, `controller_node.py`, `trial_logger_node.py` |
| Detection | HSV threshold with two red hue bands, morphology, largest contour, normalised horizontal offset | `beacon/vision.py`, tested by `test/test_vision.py` |
| Navigation | Five state controller: SEARCH, ALIGN, APPROACH, STOP, TIMEOUT, with a LiDAR safety stop | `controller_node.py` |

## Architecture

![architecture](docs/architecture.svg)

![state machine](docs/state_machine.svg)

## States

| State | Condition | Command |
|---|---|---|
| SEARCH | no marker seen for `lost_timeout_s` | turn in place at `search_speed` |
| ALIGN | marker seen and abs(offset) > `center_tol` | angular = clip(-k_ang * offset, -max_ang, max_ang), no forward motion |
| APPROACH | marker seen and abs(offset) <= `center_tol` | linear = `forward_speed`, angular = -k_ang * approach_gain * offset |
| STOP | area_frac >= `stop_area` or front range <= `stop_range_m` | zero velocity, latched until the next trial id |
| TIMEOUT | `trial_timeout_s` passed without STOP | zero velocity, failure logged, latched |

Offset is (cx - W/2) / (W/2), so it runs from -1 at the left edge to +1 at the right edge. The front range is the smallest valid `/scan` range within `front_cone_deg` of straight ahead. Every node publishes zero velocity when it shuts down.

## Parameters

All of them live in `beacon/config/params.yaml`.

| Parameter | Default | Used by | Meaning |
|---|---|---|---|
| image_topic | /camera/image_raw | detector | camera topic |
| h_low1, h_high1 | 0, 10 | detector | first red hue band (OpenCV 0 to 179) |
| h_low2, h_high2 | 170, 179 | detector | second red hue band |
| s_min, v_min | 120, 70 | detector | saturation and value floors |
| morph_kernel | 5 | detector | open then close kernel size in pixels |
| min_area_px | 150 | detector | smallest contour accepted |
| center_tol | 0.10 | controller, detector | centre band half width in offset units |
| control_hz | 10.0 | controller | command rate |
| lost_timeout_s | 1.0 | controller | seconds without the marker before SEARCH |
| search_speed | 0.3 | controller | SEARCH turn rate in rad/s |
| k_ang | 1.0 | controller | ALIGN gain |
| max_ang | 0.8 | controller | ALIGN angular limit in rad/s |
| forward_speed | 0.15 | controller | APPROACH speed in m/s |
| approach_gain | 0.5 | controller | fraction of k_ang used while driving |
| stop_area | 0.12 | controller | area fraction that triggers STOP |
| stop_range_m | 0.35 | controller | LiDAR range that triggers STOP |
| trial_timeout_s | 60.0 | controller | failure deadline |
| front_cone_deg | 15.0 | controller, logger | half angle of the front LiDAR cone |
| log_hz | 10.0 | logger | log row rate |
| save_frames, save_dir | false, empty | detector | write debug PNGs on state changes |
| box1_x, box1_y, box2_x, box2_y | 1.0, 0.8, -1.2, -0.9 | spawn_marker, analysis | occlusion box centres |
| dist_min_m, dist_max_m | 1.0, 2.5 | spawn_marker | marker distance range |
| clearance_m | 0.4 | spawn_marker | minimum gap to walls and boxes |
| default_seed | 42 | spawn_marker | seed for positions.csv |

## Topics

| Topic | Type | Direction |
|---|---|---|
| /camera/image_raw | sensor_msgs/Image | Gazebo to detector |
| /scan | sensor_msgs/LaserScan | Gazebo to controller and logger |
| /odom | nav_msgs/Odometry | Gazebo to logger |
| /cmd_vel | geometry_msgs/Twist | controller to Gazebo |
| /beacon/target | geometry_msgs/Point | detector to controller and logger. x offset, y area fraction, z 1.0 when found |
| /beacon/debug_image | sensor_msgs/Image | detector to RViz or rqt_image_view |
| /beacon/state | std_msgs/String | controller to everyone |
| /beacon/trial | std_msgs/String, transient local | spawn_marker to controller and logger |
| /beacon/path | nav_msgs/Path | logger to RViz |
| /reset_world, /delete_entity, /spawn_entity | services | spawn_marker to Gazebo |

## Run it

```
cd ~/ros2_ws && colcon build --symlink-install && source install/setup.bash && export TURTLEBOT3_MODEL=waffle_pi
ros2 launch beacon sim.launch.py rviz:=true
scripts/run_trial.sh 1
```

Full instructions, including the camera topic check and troubleshooting, are in [docs/HOW_TO_RUN.md](docs/HOW_TO_RUN.md).

## Trials

`beacon/trials/positions.csv` holds ten marker positions drawn with seed 42: distances from 1.0 to 2.5 m, bearings spread around the full circle so eight trials start with the marker out of view, and two trials (9 and 10) with the marker half hidden behind a box. `scripts/run_trial.sh N` runs one trial and prints its `results.csv` row. The protocol, the success rule and the column definitions are in [docs/trial_protocol.md](docs/trial_protocol.md).

## Figures

`python3 scripts/analyze_trials.py` reads `results.csv` and the per trial logs and writes to `docs/figures`:

* `paths_topdown.png`: room, boxes, markers and every robot path.
* `time_to_reach.png`: time to STOP per trial, failures marked.
* `state_timeline.png`: SEARCH, ALIGN, APPROACH and STOP segments per trial.
* `offset_vs_time.png`: the horizontal offset of every trial with the centre band shaded.
* `results_table.png`: the results table as an image.

It also prints the success rate, the mean and max time to reach, and the mean final range.

## Tests

```
pip install -r requirements-dev.txt
cd beacon && python3 -m pytest test -v
```

The vision tests use synthetic images and need no ROS.

## Layout

```
beacon/            ROS 2 package (ament_python): nodes, launch, world, model, config, trials, tests
scripts/           run_trial.sh and analyze_trials.py
docs/              HOW_TO_RUN.md, trial_protocol.md, diagrams, figures, screenshots
```
