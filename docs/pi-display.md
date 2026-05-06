# Pi Display Configuration

The Pi display settings live in the `display` section of the YAML config and are editable from the Settings tab at `/config`.

Related pages: [Dashboard Guide](dashboard.md), [Settings](dashboard-settings.md), [Manual State](dashboard-manual-state.md), [YAML Editor](dashboard-yaml.md).

## Display Fields

```yaml
display:
  pi_enabled: true
  width: 800
  height: 480
  fullscreen: true
  framebuffer: /dev/fb0
  background_color: "#000000"
  show_detail: true
  scale_mode: contain
```

| Field | Meaning |
| --- | --- |
| `pi_enabled` | Enables or disables the Pi renderer. If false, `renderer.py` exits without opening the display. |
| `width` | Pygame display width. Use the physical display width for best results. |
| `height` | Pygame display height. Use the physical display height for best results. |
| `fullscreen` | Opens pygame fullscreen when true. |
| `framebuffer` | Device path for framebuffer fallback, usually `/dev/fb0`. |
| `background_color` | Letterbox fill color for `contain` mode. |
| `show_detail` | Draws detail text near the bottom of the Pi display when true. |
| `scale_mode` | Controls frame fitting: `contain`, `cover`, or `stretch`. |

## Matching Web And Pi

The web display and Pi renderer read the same state file and asset folders. To keep them visually aligned:

- Use the same `avatar.asset_dir` for both.
- Use the same `avatar.state_file` for monitor, web preview, and Pi renderer.
- Keep `display.scale_mode` set to `contain` unless you intentionally want cropping or stretching.
- Set `display.width` and `display.height` to match the Pi display.
- Generate sprites with a canvas size that matches the target display, commonly `800x480`.

The root web page uses the full browser window and applies the configured scale mode. The Pi renderer uses the configured dimensions and scale mode.

## Scale Modes

Use `contain` for most avatar displays. It preserves the whole frame and avoids distortion.

Use `cover` when the display must be filled edge-to-edge and cropping is acceptable.

Use `stretch` only when exact edge-to-edge fill matters more than preserving proportions.

## Running On A Pi

Run the monitor and Pi renderer separately:

```bash
python monitor.py --config /etc/pi-avatar/avatar.yaml
python renderer.py --config /etc/pi-avatar/avatar.yaml
```

For systemd installs:

```bash
sudo ./scripts/install-pi.sh
sudo systemctl restart pi-avatar-monitor pi-avatar-renderer
```

If you change the config from the dashboard, restart services that are already running if they need to pick up display or rule changes.

## Disabling Hardware Output

Set `display.pi_enabled` to false when you want to use the web display without opening the Pi display:

```yaml
display:
  pi_enabled: false
```

Manual state and web preview still work. The Pi renderer simply exits.
