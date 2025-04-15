# Usage Guide

## Movement Controls

| Key(s)           | Action                    | Preview |
|------------------|----------------------------|---------|
| `W` / `S`        | Move forward / backward    | ![](gif/1-1.gif) |
| `A` / `D` or `←` / `→` | Rotate left / right view | ![](gif/1-2.gif) |
| `↑` / `↓`         | Look up / down             | ![](gif/1-3.gif) |

See [Agent Movement Configuration](../config_reference/config_reference.md#-agent-movement) for details of setting scale of the movement.


## Functional Controls

| Key      | Action                                                                 | Preview              |
|----------|------------------------------------------------------------------------|----------------------|
| `q`      | Exit the tool and save the recording                                    |                      |
| `m`      | Toggle top-down map view                                                | ![](gif/2-1.gif)     |
| `n`      | Select a point on the map and start navigation                          | ![](gif/2-2.gif)     |
| `e`      | Save all placed objects and generate `scene_config.json`               |                      |
| `space`  | Start or stop recording (toggle)                                        | ![](gif/2-4.gif)     |


### Scene Config Saving

The scene configuration (`scene_config.json`) stores user-placed object positions to enable future reproducibility. After arranging objects in the scene, press `e` to save their locations. This file can be reloaded later to restore the same arrangement.

Once saved, you will see this message in the terminal:

```bash
Configuration saved to ${output_path}/${dataset_name}/${scene_name}_X/scene_config.json
```

To reload, refer to the guide in [Scene Configuration](../config_reference/config_reference.md#-scene-configuration).


### Recording

The recording system captures both raw data and optionally a ROS2 bag, based on the config file.

> **Note:** To enable ROS bag recording, set `record_rosbag: true` in `habitat_data_collector.yaml`.
> 
> **Note:** Be sure to configure the output path properly in [Scene Output Settings](../config_reference/config_reference.md#-scene-output-settings).

When you press `space`, recording starts. A blinking red `REC` indicator appears in the bottom right corner. You will also see messages like:

```bash
Recording started
Start ROS bag recording: ${output_path}/${dataset_name}/${scene_name}_X/rosbag2
[INFO] [rosbag2_recorder]: Press SPACE for pausing/resuming
[INFO] [rosbag2_storage]: Opened database '.../rosbag2_0.db3' for READ_WRITE.
...
[INFO] [rosbag2_recorder]: Recording...
[INFO] [rosbag2_recorder]: Subscribed to topic '/camera/depth/image_raw'
[INFO] [rosbag2_recorder]: Subscribed to topic '/camera/rgb/image_raw'
[INFO] [rosbag2_recorder]: Subscribed to topic '/camera/pose'
[INFO] [rosbag2_recorder]: Subscribed to topic '/camera_info'
```

Press `space` again to stop recording:

```bash
Recording stopped
[INFO] [rosbag2_cpp]: Writing remaining messages from cache to the bag.
[INFO] [rosbag2_recorder]: Event publisher thread: Exiting
[INFO] [rosbag2_recorder]: Recording stopped
```

You may continue interacting with the simulation. To finalize and save the recording, press `q`. You will see:

```bash
Replay the recording and saving to disk...
Replaying and saving: 100%|██████████████████████████| 54/54 [00:05<00:00, 10.69it/s]
Replay and saving obs and pose completed in ${output_path}/${dataset_name}/${scene_name}_X
```

The following structure will appear in your output directory:

```
${output_path}/${dataset_name}/${scene_name}_X
├── camera_intrinsics.json
├── class_bbox.json
├── class_num.json
├── depth/
│   ├── 1744721112.0172191.png
│   └── ...
├── rgb/
│   ├── 1744721112.0172191.png
│   └── ...
├── pose.txt
└── rosbag2/
    ├── metadata.yaml
    └── rosbag2_0.db3
```

- `class_bbox.json`: Contains bounding boxes for each category.
- `class_num.json`: Tracks the number of each category present.
- `depth/`, `rgb/`: Image frames saved with timestamps.
- `pose.txt`: Stores camera poses as 4x4 transformation matrices.

<div align="center">
  <img src="gif/recording.gif" alt="Recording Example" width="80%"/>
  <p><em>Example: Recording process visualization</em></p>
</div>

## Object Interaction

| Key      | Action                                                                 | Preview |
|----------|------------------------------------------------------------------------|---------|
| `+`      | Randomly add an object on a placeable surface                          | ![](gif/3-1.gif) |
| `-`      | Randomly delete an object from the scene                               | ![](gif/3-2.gif) |
| `p`      | Add an object to the currently viewed placeable surface                | ![](gif/3-3.gif) |
| `g`      | Grab the nearest object                                                | ![](gif/3-4.gif) |
| `r`      | Place the currently grabbed object on the nearest placeable surface    | ![](gif/3-5.gif) |
