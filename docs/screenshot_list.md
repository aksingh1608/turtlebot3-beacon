# Screenshots to take by hand

Save these on the host desktop into `docs/screenshots`. The four debug images are copied later by `python3 scripts/pick_frames.py`. Do not take those by hand unless the picker reports a missing state.

The simulation is already running (`ros2 launch beacon sim.launch.py rviz:=true`). Commands below are in the second shell from `docker/exec.sh`.

| File | When | What to capture |
|---|---|---|
| `gazebo_room.png` | Just after `scripts/run_trial.sh 1` prints the marker position, before the robot has driven far | The Gazebo window: room, both boxes, robot, red cylinder |
| `rviz_overview.png` | While the second shell prints `state: APPROACH` | RViz with LaserScan, the robot model, and Path ticked |
| `topic_list.png` | After the nodes are up, before or during trial 1 | The terminal showing `ros2 topic list` |
| `camera_hz.png` | Same shell, after the topic list | The terminal showing `ros2 topic hz /camera/image_raw` with a rate |
| `terminal_reached.png` | When the controller prints `reached:` and `run_trial.sh` prints the results row | That terminal |
| `results_table.png` | After `scripts/run_all_trials.sh` finishes | The terminal showing the final results table |

Commands for the two terminal pictures:

```
ros2 topic list
ros2 topic hz /camera/image_raw
```

In RViz, tick LaserScan, RobotModel, Path, and DebugImage before the APPROACH shot.
