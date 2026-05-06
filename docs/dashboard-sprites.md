# Sprite Import

The Sprite Import tab turns a background image plus a spritesheet or sprite page into renderer-ready PNG frames under `assets/<state>/`. It uses the same processing model as `source-assets/manifest.example.json` and `process_assets.py`, but gives you previews before writing final assets.

Related pages: [Dashboard Guide](dashboard.md), [Settings](dashboard-settings.md), [Manual State](dashboard-manual-state.md), [YAML Editor](dashboard-yaml.md).

## Outputs

Uploads are stored under:

```text
source-assets/uploads/
```

Processed frames are written under the configured asset directory:

```text
<avatar.asset_dir>/<state>/00.png
<avatar.asset_dir>/<state>/01.png
<avatar.asset_dir>/<state>/02.png
```

For local development, that is usually `assets/<state>/`.

## Controls

| Control | Meaning |
| --- | --- |
| Background image | Base image resized to the configured canvas size. Each output frame is composited on top of this image. |
| Spritesheet or sprite page | Source image containing one or more sprite frames. |
| State | Name of the state folder to write, such as `idle` or `working`. This should match an entry in `avatar.states`. |
| Mode | `grid` for evenly spaced frames, or `frames` for explicit rectangles. |
| Canvas width | Output frame width. |
| Canvas height | Output frame height. |
| Frame width | Grid mode frame width. |
| Frame height | Grid mode frame height. |
| Columns | Grid mode number of columns in the spritesheet. |
| Frame count | Grid mode number of frames to extract. |
| Position X | X coordinate where the extracted sprite is placed on the background canvas. |
| Position Y | Y coordinate where the extracted sprite is placed on the background canvas. |
| Scale | Multiplier applied to each extracted sprite before compositing. |
| Explicit frames JSON | Frames mode rectangle list. Each rectangle has `x`, `y`, `w`, and `h`. |
| Preview Frames | Processes into a temporary directory and displays the output without changing assets. |
| Process Assets | Replaces the selected state's PNG frames in the configured asset directory. |
| Restore Default State | Replaces the selected state's PNG frames with the generated default placeholders. |

## Grid Mode

Use grid mode when frames are evenly sized and arranged left-to-right, row-by-row.

Grid extraction uses:

- `frame_width`
- `frame_height`
- `columns`
- `frame_count`

For frame index `0`, extraction starts at `x=0`, `y=0`. For later frames, the dashboard calculates the row and column from the index.

Example:

```json
{
  "mode": "grid",
  "frame_width": 128,
  "frame_height": 128,
  "columns": 8,
  "frame_count": 8,
  "position": {"x": 336, "y": 176},
  "scale": 2
}
```

## Explicit Frames Mode

Use frames mode when the sprites are irregularly sized or not arranged in a clean grid.

Each rectangle is relative to the top-left corner of the uploaded spritesheet:

```json
[
  {"x": 0, "y": 0, "w": 120, "h": 140},
  {"x": 128, "y": 0, "w": 132, "h": 144}
]
```

The rectangles are extracted in order and saved as `00.png`, `01.png`, and so on.

## Recommended Import Workflow

1. Confirm the state exists in `avatar.states` on the [Settings](dashboard-settings.md) page.
2. Upload the background image and spritesheet.
3. Set the canvas size to match your intended display, usually `800` by `480`.
4. Choose `grid` or `frames`.
5. Adjust frame dimensions, position, and scale.
6. Click Preview Frames.
7. Repeat until the previews look right.
8. Click Process Assets. This removes older PNG frames for that state before writing the new set.
9. Use [Manual State](dashboard-manual-state.md) to check the animation.

## Troubleshooting

- If preview fails with a bounds error, one or more frame rectangles extend outside the spritesheet.
- If the sprite is too small or too large, adjust `Scale`.
- If the sprite is in the wrong place, adjust `Position X` and `Position Y`.
- If the animation has missing or unexpected frames, check `Frame count` or the explicit frame list.
- If the main display does not show the processed frames, confirm that `avatar.asset_dir` points at the same output directory.
- If you want the generated placeholder art back for a state, select that state and click Restore Default State.
