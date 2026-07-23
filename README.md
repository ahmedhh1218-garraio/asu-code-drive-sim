# ASU Code & Drive — Simulation Environment

Gazebo simulation and the **QEMU ↔ Gazebo bridge** for the ASU Code & Drive
Embedded Linux course. This lets students drive and test the car in a virtual
maze — no physical hardware required — while running the same application code
they would run on the real Raspberry Pi / BeagleBone build.

## What's inside

| Path | Purpose |
|------|---------|
| `bridge_node.py` | TCP bridge server. Translates the car app's JSON motion/sensor protocol into Gazebo `/cmd_vel` twists and ray-sensor distances. Falls back to synthetic sensors when Gazebo transport is missing. |
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

- The app sends `{"type":"motion","action":...}` and `{"type":"sensors"}` messages.
- The bridge converts motion into Gazebo twist messages and returns ray-sensor
  distances (in centimetres).
- If `gz.transport` is not installed, the bridge serves **synthetic** sensor data
  so the protocol and the QEMU side can still be tested end to end.

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
3. From the car application (inside QEMU or on a laptop), point
   `SIM_BRIDGE_HOST` / `SIM_BRIDGE_PORT` at the machine running the bridge
   (default port `9000`) and use `qemu_client/sim_bridge_client.py`.

## Notes

- The bridge port can be overridden with `SIM_BRIDGE_PORT` (default `9000`).
- `launch_sim.sh` sets `GZ_SIM_RESOURCE_PATH` so Gazebo can find the local car model.
