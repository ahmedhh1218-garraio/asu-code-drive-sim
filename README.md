# ASU Code & Drive — Simulation Environment

Gazebo simulation and the **QEMU ↔ Gazebo bridge** for the ASU Code & Drive
Embedded Linux course. This lets students drive and test the car in a virtual
maze — no physical hardware required — while running the same application code
they would run on the real Raspberry Pi / BeagleBone build.

## What's inside

| Path | Purpose |
|------|---------|
| `bridge_node.py` | TCP bridge server. Translates the car app's JSON motion/sensor protocol into Gazebo `/cmd_vel` twists, ray-sensor distances and IMU readings. Falls back to synthetic sensors when Gazebo transport is missing. |
| `teleop_car.py` | Gamepad / keyboard teleop that publishes `/cmd_vel` twists — used to generate demonstration data in simulation. |
| `launch_sim.sh` | Launches the Gazebo maze world with the car model. |
| `launch_full_stack.sh` | Starts the bridge node and teleop node together. |
| `worlds/maze.sdf` | The maze world the car drives through. |
| `models/car/` | The car model (`model.sdf`, `model.config`). |
| `qemu_client/sim_bridge_client.py` | Client used by the car application **inside QEMU** to talk to the bridge over TCP. |

## How the pieces connect

```
┌─────────────────────┐        TCP (JSON)        ┌──────────────────┐      gz.transport      ┌──────────┐
│  Car app (in QEMU)  │  ───────────────────▶    │   bridge_node    │  ───────────────────▶  │  Gazebo  │
│  sim_bridge_client  │  ◀───────────────────    │  (this repo)     │  ◀───────────────────  │  (maze)  │
└─────────────────────┘   motion / sensors       └──────────────────┘   /cmd_vel · sensors   └──────────┘
```

- The app sends `{"type":"motion","action":...}`, `{"type":"sensors"}` and
  `{"type":"imu"}` messages.
- The bridge converts motion into Gazebo twist messages and returns ray-sensor
  distances (in centimetres) and 6-axis IMU features (normalised).
- If `gz.transport` is not installed, the bridge serves **synthetic** sensor data
  so the protocol and the QEMU side can still be tested end to end.

## Sensor suite

The simulated car mirrors the physical hardware:

- **Three ultrasonic-style distance sensors** — `front`, `front_left` and
  `front_right` (modelled as single-ray lidars aimed forward and ~±45°).
- **A 6-axis IMU** — 3-axis accelerometer + 3-axis gyroscope
  (`ax, ay, az, gx, gy, gz`), published on `car/imu` and returned normalised to
  roughly `[-1, 1]`.

## Requirements

- Python 3.10+
- [Gazebo](https://gazebosim.org) (Garden or Harmonic) — provides `gz sim`
- Optional: `python3-gz-transport` bindings for real sensor/motion data
- Optional: `pygame` for gamepad teleop

## Quick start

1. Launch the simulation world:
   ```bash
   ./launch_sim.sh
   ```
2. In a second terminal, start the bridge + teleop:
   ```bash
   ./launch_full_stack.sh
   ```
3. Boot your QEMU car image (the one you built during the sessions) and
   connect it to the bridge — see below.

## Connect your QEMU car to the sim

The car image you built in the course already runs in **simulation mode**
(`CAR_SIM=1`), so on boot the app tries to reach the bridge over TCP. You just
need the app to point at the host running this repo. The correct address
depends on how you launch QEMU:

| QEMU network mode | How you launched it | `SIM_BRIDGE_HOST` to use |
|-------------------|---------------------|--------------------------|
| **User-mode (SLIRP)** — the default | `runqemu qemuarm64` | `10.0.2.2` (already the default) |
| **TAP / bridged** | `runqemu qemuarm64 ... slirp`-disabled, guest gets `192.168.7.2` | `192.168.7.1` (the host end of the tap link) |

1. On the **host**, start the world and bridge (two terminals):
   ```bash
   ./launch_sim.sh          # terminal 1 — Gazebo maze
   ./launch_full_stack.sh   # terminal 2 — bridge (port 9000) + teleop
   ```
2. **Boot QEMU.** If you use the default `runqemu` (SLIRP), nothing else is
   needed — the app reaches the host at `10.0.2.2:9000` automatically.
3. If you use **tap** networking, tell the app the host address before it
   starts (inside the guest):
   ```bash
   export SIM_BRIDGE_HOST=192.168.7.1
   export SIM_BRIDGE_PORT=9000
   # then start the car app (or restart the car-training service)
   ```
4. **Watch Gazebo.** As the app (teleop, or your trained model) sends motion
   commands, the car drives through the maze and the ray sensors feed live
   distances back to the app. That's your visual test.

### Quick check it's connected

- The bridge terminal logs `motion` / `sensors` messages when the app is talking to it.
- If the car doesn't move: confirm the host/port match your QEMU network mode,
  and that port `9000` isn't blocked by a firewall.

### No QEMU? Run it all on your laptop

You can also see the car drive without QEMU — run the car app directly on the
host with `CAR_SIM=1` pointing at `127.0.0.1`. Same bridge, same Gazebo window,
much faster iteration while experimenting.

## Notes

- The bridge port can be overridden with `SIM_BRIDGE_PORT` (default `9000`).
- `launch_sim.sh` sets `GZ_SIM_RESOURCE_PATH` so Gazebo can find the local car model.
- If Gazebo transport bindings aren't installed, the bridge serves **synthetic**
  sensor data so the protocol still works end to end (you just won't see physics).
