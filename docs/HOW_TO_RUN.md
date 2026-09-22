# How to run Beacon

Written for a fresh terminal inside a TheConstruct ROSject (ROS 2 Humble, Gazebo Classic 11, TurtleBot3 packages installed). Lines marked CONFIRM IN ROSJECT were written without a Humble machine at hand and need one check on the real system.

## 1. Create the workspace and copy the package

```
mkdir -p ~/ros2_ws/src
cp -r beacon ~/ros2_ws/src/beacon
```

`beacon` is the folder in this repo that holds `package.xml` and `setup.py`. Only that folder goes into the workspace. The `scripts` and `docs` folders stay in the repo.

## 2. Build

```
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
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
| use_sim_time | true | nodes use the Gazebo clock. CONFIRM IN ROSJECT that `/clock` is published |

Gazebo in a ROSject can take a minute to load the first time. Wait until the robot is visible before running a trial.

## 5. Confirm the camera topic

In a second terminal:

```
source ~/ros2_ws/install/setup.bash
ros2 topic list
ros2 topic hz /camera/image_raw
```

CONFIRM IN ROSJECT: the Waffle Pi camera in turtlebot3_gazebo publishes on `/camera/image_raw`. If the list shows a different name (for example `/camera/image_raw/compressed` only, or a namespaced topic), restart with:

```
ros2 launch beacon sim.launch.py rviz:=true image_topic:=/your/topic/name
```

The detector logs `detection rate NN% (a of b frames)` once a second. If it prints `no frames received yet` the topic name is wrong.

## 6. Run one trial

In the second terminal:

```
cd ~/turtlebot3-beacon        # the repo folder, where scripts/ lives
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

Where the logs land: by default in the source tree, in the trials folder of the beacon package you copied into the workspace:

```
~/ros2_ws/src/beacon/trials
```

so `logs/trial_1.csv`, `results.csv` and `current_trial.json` sit next to `positions.csv`. This is the package source, not the install prefix. To send them somewhere else, set this in every terminal before launching:

```
export BEACON_TRIALS_DIR=/path/you/choose
```

The launch argument `trials_dir:=` does the same for the nodes.

## 7. Run all ten trials and make the figures

```
for n in $(seq 1 10); do scripts/run_trial.sh "$n"; done
python3 scripts/analyze_trials.py --trials-dir ~/ros2_ws/src/beacon/trials
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
* `debug_search.png`, `debug_align.png`, `debug_approach.png`, `debug_stop.png`: the debug image in each state. Set `save_frames: true` in `params.yaml` to have the detector write a PNG on every state change into `<trials_dir>/frames`.
* `terminal_reached.png`: the controller terminal showing the `reached:` line and the run_trial.sh output with the results row.

In the ROSject use the desktop screenshot tool, or `gnome-screenshot` if present. For the debug image, `rqt_image_view` has a save button.

## 9. Troubleshooting

**No image.** `ros2 topic hz /camera/image_raw` shows nothing. Check `ros2 topic list` for the real camera topic and pass `image_topic:=`. Make sure `TURTLEBOT3_MODEL=waffle_pi`; burger has no camera.

**Red not detected.** The detector logs `detection rate 0%` while the marker is in view. Open the debug image and look at the mask. Edit `config/params.yaml` under `detector_node`: raise `h_high1` or lower `h_low2` to widen the red bands, lower `s_min` if the cylinder looks washed out, lower `v_min` if it looks dark, and lower `min_area_px` when the marker is far away. Restart the nodes after every change: `ros2 launch beacon nodes.launch.py` when Gazebo is already up.

**Robot spins forever.** It never leaves SEARCH. Either the marker is not detected (see above) or it is hidden behind a box for the whole turn, which is by design for the two occluded trials at the start but should end after the robot moves. Check that `/beacon/target` shows `z: 1.0` while the marker is in view. If it does and the robot still spins, `lost_timeout_s` may be too short for the frame rate.

**Robot hits the marker.** Raise `stop_area` (it stops earlier when the marker fills more of the frame) or raise `stop_range_m` (it stops earlier on the LiDAR). Check that `/scan` publishes and that `front_range` in the trial log is not empty. CONFIRM IN ROSJECT that the LDS scan starts at angle 0 straight ahead; the front cone code handles any `angle_min`, but the value should be checked once.

**Nodes print nothing and the controller never ticks.** With `use_sim_time:=true` the nodes wait for `/clock`. If Gazebo is paused or `/clock` is missing, relaunch with `use_sim_time:=false`.

**Stop is latched.** After STOP or TIMEOUT the controller waits for the next trial id. Run `spawn_marker` again to start a new trial.
