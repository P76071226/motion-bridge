# Phone Orientation Dashboard

Stream real-time phone orientation data from Android (Termux) to your laptop and visualize it with a 3D axes diagram and live readouts.

## Setup

### Laptop

```bash
cd ~/phone_controller
uv sync
uv run python server.py
```

The server will start two services:
- **HTTP Dashboard**: http://localhost:8080 (open in browser)
- **WebSocket Server**: ws://localhost:8765 (for phone + browser connections)
- **Air Mouse Client**: optional macOS pointer controller, started separately

### Phone (Android + Termux)

1. **Install Termux:API**
   - Install the Termux:API app from F-Droid (not Play Store)
   - Install the Termux app from F-Droid

2. **Set up Termux**
   ```bash
   pkg update && pkg install termux-api python
   pip install websockets
   ```

3. **Copy `phone_client.py` to Termux** and run it:
   ```bash
   python phone_client.py --server 192.168.x.x
   ```
   Replace `192.168.x.x` with your laptop's local IP on the same WiFi network.

## Usage

1. Open the dashboard in a browser: http://<laptop-ip>:8080
2. Status shows "Waiting..." (red dot)
3. Run `phone_client.py` on the phone
4. Status changes to "Connected" (green dot)
5. Tilt the phone — the 3D axes rotate in real-time

The right panel shows:
- **Alpha (Yaw)**: rotation around Z axis (0–360°)
- **Beta (Pitch)**: rotation around X axis (-90 to +90°)
- **Gamma (Roll)**: rotation around Y axis (-90 to +90°)
- **Quaternion**: raw x, y, z, w values

## Air Mouse (macOS)

The optional air mouse client turns phone orientation into relative macOS pointer
movement. It is movement-only in this first version; use your normal mouse or
trackpad for clicks.

Start the server and phone client first, then run:

```bash
uv run python air_mouse.py --server ws://localhost:8765/
```

Hold the phone still when the client connects. After a short stable window, that
pose becomes neutral. Tilting left/right moves the cursor horizontally; tilting
forward/back moves it vertically. Return to the neutral pose to stop movement.
Press `Ctrl+C` to stop the air mouse client. Restart it to recenter.

macOS may require permission before a terminal-launched process can control the
pointer. If movement is blocked, open **System Settings → Privacy & Security**
and allow your terminal app under **Accessibility** and **Input Monitoring**.

Tuning options:

```bash
uv run python air_mouse.py \
  --server ws://localhost:8765/ \
  --sensitivity 80 \
  --deadzone 0.03 \
  --smoothing 0.25 \
  --max-speed 35
```

- `--sensitivity`: cursor speed per radian of phone movement
- `--deadzone`: neutral-zone size in radians to suppress jitter
- `--smoothing`: cursor smoothing, from `0.0` immediate to higher values
- `--max-speed`: maximum cursor pixels per sensor update

## Data Format

Phone → Server → Browser (JSON over WebSocket):

```json
{
  "type": "orientation",
  "quaternion": {
    "x": 0.12,
    "y": 0.34,
    "z": 0.05,
    "w": 0.93
  }
}
```

The server also emits a normalized controller message after each orientation
update so other apps can consume phone tilt without doing quaternion math:

```json
{
  "type": "controller",
  "axes": {
    "yaw": 0.0,
    "pitch": 0.0,
    "roll": 0.0
  },
  "quaternion": {
    "x": 0.12,
    "y": 0.34,
    "z": 0.05,
    "w": 0.93
  }
}
```

Axis values are normalized to `-1.0` through `1.0`. Apps can connect to
`ws://<laptop-ip>:8765/` and listen for `type: "controller"` messages.

## Architecture

```
Phone (Termux)
  termux-sensor (reads device orientation)
    → phone_client.py (sends quaternion)
      → server.py (WS relay)
        → dashboard (browser, Three.js visualization)
```

## Troubleshooting

**Phone can't connect**: Ensure phone and laptop are on the same WiFi. Check the laptop's IP with `ipconfig` (Windows) or `ifconfig` (Mac/Linux) and update the `--server` argument.

**Dashboard shows "Disconnected"**: Check that `phone_client.py` is running. Monitor the server logs for errors.

**Axes don't rotate**: Ensure Termux:API is properly installed and the phone has motion sensor permissions.

## Future Enhancements

- Add accelerometer data
- Add gyroscope data
- Add air mouse click controls
- Log data to file
- Record/playback sessions
