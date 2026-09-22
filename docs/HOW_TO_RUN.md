# How to run Beacon

Written for a shell inside the Beacon container. Build and start that container with [DOCKER_SETUP.md](DOCKER_SETUP.md). Lines marked CONFIRM IN SIM need one check against the installed Waffle Pi model. The commands that do the check are in that same file.

Inside the container the repo is `/ws/src/turtlebot3-beacon` and the workspace is `/ws`.

## 1. The package is already mounted

`beacon` is the folder that holds `package.xml` and `setup.py`. In the container it is `/ws/src/turtlebot3-beacon/beacon`. `scripts/` and `docs/` stay next to it in the repo.

## 2. Build

```
cd /ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select beacon
source install/setup.bash
```

A clean build prints `Summary: 1 package finished`. Warnings from setuptools about `setup.py install` are normal on Humble.

## 3. Pick the robot model

```
export TURTLEBOT3_MODEL=waffle_pi
```

The launch file also sets this, but the TurtleBot3 launch files read it at import time, so export it in every terminal you use.

## 4. Launch the simulation

```
ros2 launch beacon sim.launch.py rviz:=true
```

This starts Gazebo with `worlds/beacon_room.world`, spawns the Waffle Pi at the origin, starts `detector_node`, `controller_node` and `trial_logger_node` with `config/params.yaml`, and opens RViz with `config/beacon.rviz`. The robot starts turning at once because the controller begins in SEARCH.

Launch arguments:

| Argument | Default | Meaning |
|---|---|---|
| world | beacon_room | or turtlebot3_world |
| x_pose, y_pose | 0.0, 0.0 | robot start pose |
| rviz | false | open RViz |
| trial | none | spawn this trial from positions.csv after `spawn_delay` seconds |
| spawn_delay | 10.0 | wait for Gazebo before the first spawn |
| image_topic | /camera/image_raw | camera topic the detector reads |
| trials_dir | empty | where logs land, see step 6 |
| use_sim_time | true | nodes use the Gazebo clock. CONFIRM IN SIM that `/clock` is published |

Gazebo can take a minute to load the first time. Wait until the robot is visible before running a trial.

## 5. Confirm the camera topic

In a second terminal:

```
source /opt/beacon_env.sh
ros2 topic list
ros2 topic hz /camera/image_raw
```

Checked in this image: the camera publishes on `/camera/image_raw`, the field of view is 62.2 degrees, and the image is 640 by 480. If a later install shows a different topic name, restart with:

```
ros2 launch beacon sim.launch.py rviz:=true image_topic:=/your/topic/name
```

The detector logs `detection rate NN% (a of b frames)` once a second. If it prints `no frames received yet` the topic name is wrong.

## 6. Run one trial

In the second terminal:

```
cd /ws/src/turtlebot3-beacon
scripts/run_trial.sh 1
```

The script calls `ros2 run beacon spawn_marker --trial 1`, which resets the world, spawns the red cylinder at row 1 of `trials/positions.csv`, and publishes the trial id. It then prints each state change and the row that lands in `results.csv`.

You can also do it by hand:

```
ros2 run beacon spawn_marker --trial 1
ros2 topic echo /beacon/state
```

Watch the debug image with either of these:

```
ros2 run rqt_image_view rqt_image_view /beacon/debug_image
```

or the DebugImage panel in RViz. The left half is the camera frame with the contour, centroid, bounding box, centre line and the shaded centre band. The right half is the red mask. The top strip shows the state, offset, area fraction and fps. The bottom bar shows the offset from -1 to +1.

Where the logs land: by default in the source tree, in the trials folder of the beacon package:

```
/ws/src/turtlebot3-beacon/beacon/trials
```

so `logs/trial_1.csv`, `results.csv` and `current_trial.json` sit next to `positions.csv`. This is the package source, not the install prefix. To send them somewhere else, set this in every terminal before launching:

```
export BEACON_TRIALS_DIR=/path/you/choose
```

The launch argument `trials_dir:=` does the same for the nodes.

## 7. Run all ten trials and make the figures

```
scripts/run_all_trials.sh
python3 scripts/analyze_trials.py
```

If you set `BEACON_TRIALS_DIR`, the script reads it and you can drop the flag. Figures land in `docs/figures`. The script prints the success rate, mean and max time to reach, and mean final range. `results.csv` keeps every run. If you repeat a trial, the last row for that trial number is the one plotted.

To regenerate the trial positions with another seed (no ROS needed):

```
python3 -c "import sys; sys.path.insert(0, 'beacon'); from beacon.spawn_marker import main; main(['--write-positions', '--seed', '7', '--trials-dir', 'beacon/trials'])"
```

## 8. Screenshots for the report

Save them in `docs/screenshots`. Suggested set:

* `gazebo_room.png`: the Gazebo window with the room, both boxes, the robot and a marker.
* `rviz_overview.png`: RViz with the LaserScan, robot model, path and debug image panel.
* `debug_search.png`, `debug_align.png`, `debug_approach.png`, `debug_stop.png`: one debug image per state. The detector writes a PNG on every state change into `docs/screenshots/frames`. `python3 scripts/pick_frames.py` copies one frame of trial 1 for each state into `docs/screenshots`.
* `terminal_reached.png`: the controller terminal showing the `reached:` line and the run_trial.sh output with the results row.

Take screenshots on the host desktop. `docs/screenshot_list.md` lists each one. For the debug image, `rqt_image_view` has a save button.

## 9. Troubleshooting

**No image.** `ros2 topic hz /camera/image_raw` shows nothing. Check `ros2 topic list` for the real camera topic and pass `image_topic:=`. Make sure `TURTLEBOT3_MODEL=waffle_pi`; burger has no camera.

**Red not detected.** The detector logs `detection rate 0%` while the marker is in view. Open the debug image and look at the mask. Edit `config/params.yaml` under `detector_node`: raise `h_high1` or lower `h_low2` to widen the red bands, lower `s_min` if the cylinder looks washed out, lower `v_min` if it looks dark, and lower `min_area_px` when the marker is far away. Restart the nodes after every change: `ros2 launch beacon nodes.launch.py` when Gazebo is already up.

**Robot spins forever.** It never leaves SEARCH. Either the marker is not detected (see above) or it is hidden behind a box for the whole turn, which is by design for the two occluded trials at the start but should end after the robot moves. Check that `/beacon/target` shows `z: 1.0` while the marker is in view. If it does and the robot still spins, `lost_timeout_s` may be too short for the frame rate.

**Robot hits the marker.** Raise `stop_area` (it stops earlier when the marker fills more of the frame) or raise `stop_range_m` (it stops earlier on the LiDAR). Check that `/scan` publishes and that `front_range` in the trial log is not empty. CONFIRM IN SIM that the LDS scan starts at angle 0 straight ahead; the front cone code handles any `angle_min`, but the value should be checked once.

**Nodes print nothing and the controller never ticks.** With `use_sim_time:=true` the nodes wait for `/clock`. If Gazebo is paused or `/clock` is missing, relaunch with `use_sim_time:=false`.

**Stop is latched.** After STOP or TIMEOUT the controller waits for the next trial id. Run `spawn_marker` again to start a new trial.
