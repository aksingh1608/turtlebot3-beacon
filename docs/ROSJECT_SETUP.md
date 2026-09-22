# ROSject setup

Create the ROSject on TheConstruct from the ROS 2 Humble template. Name it with a random string of 10 characters. This file calls that name ROSJECT_NAME_TBD. Use your string in the name field when you create the ROSject.

The simulation is Gazebo Classic 11 with the TurtleBot3 Waffle Pi. The package that you build is the `beacon` folder in this repo, the one that contains `package.xml` and `setup.py`.

## 1. Create the ROSject

1. Open TheConstruct and create a new ROSject.
2. Choose the ROS 2 Humble template.
3. Set the name to your 10 character string (ROSJECT_NAME_TBD in this file).
4. Open the ROSject desktop and a terminal.

## 2. Upload the package

The Humble template already has `~/ros2_ws`. Upload only the `beacon` folder into the workspace source tree:

```
mkdir -p ~/ros2_ws/src
```

Put the uploaded folder at `~/ros2_ws/src/beacon`. It must contain `package.xml`, `setup.py`, `launch`, `worlds`, `models`, `config`, `trials/positions.csv`, and `resource/beacon`.

Keep the rest of this repo on the ROSject as well, at `~/turtlebot3-beacon`. `scripts/` and `docs/` are not inside the package, and the trial scripts run from there.

Check the TurtleBot3 packages. If the next command prints a path, they are already installed:

```
source /opt/ros/humble/setup.bash
ros2 pkg prefix turtlebot3_gazebo
```

If that command fails, install the missing packages and source again:

```
sudo apt update
sudo apt install -y ros-humble-turtlebot3 ros-humble-turtlebot3-gazebo ros-humble-gazebo-ros ros-humble-cv-bridge
source /opt/ros/humble/setup.bash
```

## 3. Build and source

```
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
export TURTLEBOT3_MODEL=waffle_pi
```

A clean build prints `Summary: 1 package finished`. A setuptools warning about `setup.py install` is normal on Humble.

`--symlink-install` makes the installed files point back at `~/ros2_ws/src/beacon`. Trial logs then land in that source tree, not under `install/`.

Export `TURTLEBOT3_MODEL` in every new terminal. The TurtleBot3 launch files read it when they are imported. `sim.launch.py` also sets it to `waffle_pi` before those files load.

## 4. Launch

In the first terminal:

```
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
export TURTLEBOT3_MODEL=waffle_pi
ros2 launch beacon sim.launch.py rviz:=true
```

Wait until the robot is visible in Gazebo. The first load can take about a minute. The robot starts turning because the controller begins in SEARCH.

## 5. Confirm the topics

In a second terminal:

```
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 topic list
ros2 topic hz /camera/image_raw
```

`ros2 topic list` should include `/camera/image_raw`, `/scan`, `/odom`, `/clock`, `/cmd_vel`, and, after the nodes start, `/beacon/target`, `/beacon/state`, and `/beacon/debug_image`. `/beacon/trial` appears when a trial is spawned.

`ros2 topic hz /camera/image_raw` should print a rate. If the camera topic has another name, stop and relaunch with that name:

```
ros2 launch beacon sim.launch.py rviz:=true image_topic:=/the/topic/from/the/list
```

Also confirm the Gazebo services:

```
ros2 service list | grep -E 'spawn_entity|delete_entity|reset_world'
```

You should see `/spawn_entity`, `/delete_entity`, and `/reset_world`.

## 6. Run trial 1 and view the debug image

In the second terminal:

```
cd ~/turtlebot3-beacon
scripts/run_trial.sh 1
```

The script resets the world, spawns the red cylinder for row 1, and prints each state until STOP or TIMEOUT. Then it prints the `results.csv` row.

Watch the debug image with either of these:

```
ros2 run rqt_image_view rqt_image_view /beacon/debug_image
```

or the DebugImage panel in RViz. The left half is the camera frame. The right half is the red mask.

## 7. Run all ten trials and the analysis

Leave the simulation running. In the repo terminal:

```
cd ~/turtlebot3-beacon
for n in $(seq 1 10); do scripts/run_trial.sh "$n"; done
python3 scripts/analyze_trials.py --trials-dir ~/ros2_ws/src/beacon/trials
```

Trial 9 is the first occluded run. Save a screenshot of the debug image at the start of that trial. The check is whether the visible half of the cylinder still produces a mask.

## 8. Where every output lands

| Output | Path |
|---|---|
| Per trial log | `~/ros2_ws/src/beacon/trials/logs/trial_N.csv` |
| Results table | `~/ros2_ws/src/beacon/trials/results.csv` |
| Marker pose for the current trial | `~/ros2_ws/src/beacon/trials/current_trial.json` |
| Debug frames, only if `save_frames` is true | `~/ros2_ws/src/beacon/trials/frames/` |
| Analysis figures | `~/turtlebot3-beacon/docs/figures/` (`paths_topdown.png`, `time_to_reach.png`, `state_timeline.png`, `offset_vs_time.png`, `results_table.png`) |

`current_trial.json` is runtime state. `logs/` and `results.csv` are meant to be kept. Copy `logs/` and `results.csv` from `~/ros2_ws/src/beacon/trials` back to `beacon/trials` in the repo if you want them in git. The figures are already in the repo tree.

To send logs somewhere else, export `BEACON_TRIALS_DIR` in every terminal before you launch and before you run the scripts. The launch argument `trials_dir:=` does the same for the nodes.

## 9. Settings to confirm on the ROSject

These were written without a Humble machine. Check each one. Change it only if the ROSject disagrees.

| Setting | Current value | Where | How to check | How to change it if it differs |
|---|---|---|---|---|
| Camera topic | `/camera/image_raw` | `config/params.yaml` `image_topic`, launch argument `image_topic` | `ros2 topic list` after launch. Also open the waffle_pi `model.sdf` in `turtlebot3_gazebo` and read the camera plugin topic. | Relaunch with `image_topic:=/the/real/topic`. |
| Camera horizontal field of view | `62.2` degrees | `config/params.yaml` `beacon_shared` `camera_hfov_deg` | In that same `model.sdf`, read the camera `horizontal_fov`. Gazebo stores it in radians. Multiply by 180/pi. | Edit `camera_hfov_deg` and restart the nodes. This value only affects which trials count as starting out of view. |
| `use_sim_time` and `/clock` | `true` | launch argument `use_sim_time` | `ros2 topic echo /clock`. The nodes do not tick if this is true and `/clock` is missing. | Relaunch with `use_sim_time:=false`. |
| Scan `angle_min` | front cone uses the scan message, so any `angle_min` is valid | `front_range` in `beacon/ros_util.py` | `ros2 topic echo /scan --once` and read `angle_min`. Straight ahead should be angle 0. | No edit if `angle_min` is not 0. The cone is measured from angle 0 after wrapping. If angle 0 is not straight ahead on the robot, say so in the report. |
| gzserver `init` and `factory` | `init:=true`, `factory:=true` | `launch/sim.launch.py`, noted again in `worlds/beacon_room.world` | `ros2 service list` includes `/reset_world`, `/spawn_entity`, and `/delete_entity`. | If those services are missing, open `gazebo_ros/launch/gzserver.launch.py` and use the argument names that load `libgazebo_ros_init.so` and `libgazebo_ros_factory.so`. |
| Trial 9 partly hidden | occluded row, about half the cylinder behind box 1 | `docs/trial_protocol.md`, `trials/positions.csv` row 9 | Screenshot of `/beacon/debug_image` at the start of trial 9. The mask should show the visible part. | If the mask is empty while the cylinder is clearly in view, lower `min_area_px` in `config/params.yaml` and restart the nodes. |
