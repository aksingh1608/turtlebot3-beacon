# Run Beacon with Docker

This is the way to run the simulation on a machine that does not have ROS 2 Humble installed. The image is Ubuntu 22.04 with Humble, Gazebo Classic, and the TurtleBot3 Waffle Pi packages. The repo is mounted into the container, so logs, figures, and screenshots land in this tree and stay owned by you.

## 1. Build the image

From the repo root. The first build downloads the Humble desktop image and the TurtleBot3 packages.

```
docker build -f docker/Dockerfile -t beacon:humble docker
```

Expect about 15 to 30 minutes the first time. Later builds are much shorter.

## 2. Start the container

From a desktop session, so Gazebo has a screen:

```
docker/run.sh
```

Add `--gpu` if you have an NVIDIA driver and want Gazebo to use it:

```
docker/run.sh --gpu
```

The prompt is inside the container. The repo is at `/ws/src/turtlebot3-beacon`. A second terminal on the host joins the same container with:

```
docker/exec.sh
```

## 3. Build the workspace

Inside the container:

```
cd /ws
colcon build --symlink-install --packages-select beacon
```

Expect about one minute. The entrypoint sources `/ws/install/setup.bash` on the next shell. Open a new shell with `docker/exec.sh`, or run `source /opt/beacon_env.sh` in this one.

## 4. Launch

```
cd /ws/src/turtlebot3-beacon
ros2 launch beacon sim.launch.py rviz:=true
```

Wait until the robot is visible. The first Gazebo window can take about a minute. The robot starts turning because the controller begins in SEARCH.

If the robot does not appear within 30 seconds, Gazebo was still starting. Spawn it by hand:

```
ros2 run gazebo_ros spawn_entity.py -entity waffle_pi -file /opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_waffle_pi/model.sdf -x 0.0 -y 0.0 -z 0.01
```

## 5. Run the trials and make the figures

In the second shell (`docker/exec.sh`):

```
cd /ws/src/turtlebot3-beacon
scripts/run_all_trials.sh
python3 scripts/analyze_trials.py
python3 scripts/pick_frames.py
```

`run_all_trials.sh` runs trials 1 to 10 and prints the results table. Figures land in `docs/figures`. Picked debug frames land in `docs/screenshots`. Take the manual screenshots on the host desktop while the windows are open. The list of moments is `docs/screenshot_list.md`.

Logs and `results.csv` land in `beacon/trials` inside the repo.

## 6. Settings to confirm in the sim

These values were chosen to match the Waffle Pi model. Check them once inside the container. Change `config/params.yaml` or the launch argument only if the command shows a different value.

| Setting | Current value | Command that confirms it | If it differs |
|---|---|---|---|
| Camera topic | `/camera/image_raw` | `ros2 topic list` after launch, and the camera plugin in the waffle_pi `model.sdf` | Relaunch with `image_topic:=/the/real/topic` |
| Camera horizontal field of view | `62.2` degrees | `grep -n horizontal_fov /opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_waffle_pi/model.sdf` (radians, multiply by 180/pi) | Edit `camera_hfov_deg` in `config/params.yaml` |
| Camera image size | used only as a check | `grep -n -E 'width|height' /opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_waffle_pi/model.sdf` | No parameter today. Record the size in the report |
| `/clock` with `use_sim_time` | `true` | `ros2 topic echo /clock --once` | Relaunch with `use_sim_time:=false` if `/clock` is missing |
| Scan `angle_min` | front cone uses the scan message | `ros2 topic echo /scan --once` and read `angle_min` | No edit if angle 0 is still straight ahead |
| `/spawn_entity`, `/delete_entity`, `/reset_world` | `init:=true`, `factory:=true` | `ros2 service list` | If a service is missing, the gzserver arguments in `launch/sim.launch.py` do not match this Gazebo |
| Trial 9 partly hidden | occluded row | Screenshot of `/beacon/debug_image` at the start of trial 9 | If the mask is empty while the cylinder is in view, lower `min_area_px` |

## 7. Humble already installed

Skip Docker when `ros2 pkg prefix turtlebot3_gazebo` prints a path and `echo "$ROS_DISTRO"` prints `humble`.

```
mkdir -p ~/ros2_ws/src
cp -a beacon ~/ros2_ws/src/beacon
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select beacon
source install/setup.bash
export TURTLEBOT3_MODEL=waffle_pi
export BEACON_WS="$HOME/ros2_ws"
ros2 launch beacon sim.launch.py rviz:=true
```

In a second terminal, source the same files, `cd` to this repo, and run `scripts/run_all_trials.sh`. The confirm commands in the table above are the same.
