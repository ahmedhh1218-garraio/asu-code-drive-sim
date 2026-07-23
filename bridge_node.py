#!/usr/bin/env python3
"""QEMU <-> Gazebo bridge node.

Exposes a TCP server speaking the newline-delimited JSON protocol used by
``app/sim_bridge_client.py``. Motion commands are translated into Gazebo
``/cmd_vel`` twist messages, and sensor requests are answered with the latest
ray-sensor distances published on ``car/sensors/*``.

The bridge gracefully degrades when the Gazebo Python transport (``gz.transport``)
is not installed: it then serves synthetic sensor data so the protocol and the
QEMU side can still be tested.
"""

import argparse
import json
import logging
import math
import socketserver
import threading

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("bridge")

SENSOR_NAMES = ["front", "front_left", "front_right"]
MAX_DISTANCE_CM = 200.0

# Linear/angular speeds applied for each discrete action.
LINEAR_SPEED = 0.3  # m/s
ANGULAR_SPEED = 1.2  # rad/s

# IMU normalisation constants. These mirror app/config.py so the simulated IMU
# lands in the same roughly [-1, 1] range the hardware MPU6050 produces.
GRAVITY = 9.80665            # m/s^2
IMU_ACCEL_RANGE_G = 2.0      # +/- 2 g maps to [-1, 1]
IMU_GYRO_RANGE_DPS = 250.0   # +/- 250 deg/s maps to [-1, 1]
IMU_ZEROS = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # [ax, ay, az, gx, gy, gz]


class GazeboLink:
    """Thin wrapper around gz.transport. Falls back to a stub when missing."""

    def __init__(self):
        self._distances = {name: MAX_DISTANCE_CM for name in SENSOR_NAMES}
        self._imu = list(IMU_ZEROS)
        self._lock = threading.Lock()
        self._node = None
        self._cmd_pub = None
        self._connect()

    def _connect(self):
        try:
            from gz.transport13 import Node  # type: ignore
            from gz.msgs10.twist_pb2 import Twist  # type: ignore
            from gz.msgs10.laserscan_pb2 import LaserScan  # type: ignore
            from gz.msgs10.imu_pb2 import IMU as ImuMsg  # type: ignore

            self._Twist = Twist
            self._node = Node()
            self._cmd_pub = self._node.advertise("/cmd_vel", Twist)

            for name in SENSOR_NAMES:
                topic = f"/car/sensors/{name}"
                self._node.subscribe(LaserScan, topic, self._make_cb(name))
            self._node.subscribe(ImuMsg, "/car/imu", self._imu_cb)
            log.info("Connected to Gazebo transport.")
        except Exception as exc:  # pragma: no cover - optional dependency
            log.warning("Gazebo transport unavailable (%s). Using stub sensors.", exc)
            self._node = None

    def _make_cb(self, name):
        def _cb(msg):
            ranges = [r for r in msg.ranges if not math.isinf(r) and not math.isnan(r)]
            distance = min(ranges) if ranges else MAX_DISTANCE_CM / 100.0
            with self._lock:
                self._distances[name] = min(distance * 100.0, MAX_DISTANCE_CM)

        return _cb

    def _imu_cb(self, msg):
        """Normalise a Gazebo IMU message into [ax, ay, az, gx, gy, gz]."""

        def _clamp(value):
            return max(-1.0, min(1.0, value))

        accel = [
            _clamp(msg.linear_acceleration.x / GRAVITY / IMU_ACCEL_RANGE_G),
            _clamp(msg.linear_acceleration.y / GRAVITY / IMU_ACCEL_RANGE_G),
            _clamp(msg.linear_acceleration.z / GRAVITY / IMU_ACCEL_RANGE_G),
        ]
        gyro = [
            _clamp(math.degrees(msg.angular_velocity.x) / IMU_GYRO_RANGE_DPS),
            _clamp(math.degrees(msg.angular_velocity.y) / IMU_GYRO_RANGE_DPS),
            _clamp(math.degrees(msg.angular_velocity.z) / IMU_GYRO_RANGE_DPS),
        ]
        with self._lock:
            self._imu = accel + gyro

    # -- API ----------------------------------------------------------------
    def send_motion(self, action, speed):
        scale = max(0.0, min(speed, 100)) / 100.0
        linear, angular = 0.0, 0.0
        if action == "forward":
            linear = LINEAR_SPEED * scale
        elif action == "backward":
            linear = -LINEAR_SPEED * scale
        elif action == "left":
            angular = ANGULAR_SPEED * scale
        elif action == "right":
            angular = -ANGULAR_SPEED * scale

        if self._node and self._cmd_pub:
            msg = self._Twist()
            msg.linear.x = linear
            msg.angular.z = angular
            self._cmd_pub.publish(msg)

    def distances_cm(self):
        with self._lock:
            return dict(self._distances)

    def imu_normalized(self):
        with self._lock:
            return list(self._imu)


class BridgeHandler(socketserver.StreamRequestHandler):
    def handle(self):
        link = self.server.gazebo
        log.info("Client connected: %s", self.client_address)
        for raw in self.rfile:
            line = raw.decode("utf-8").strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue

            if msg.get("type") == "motion":
                link.send_motion(msg.get("action", "stop"), msg.get("speed", 0))
                self._reply({"ok": True})
            elif msg.get("type") == "sensors":
                self._reply({"distances": link.distances_cm()})
            elif msg.get("type") == "imu":
                self._reply({"imu": link.imu_normalized()})
            else:
                self._reply({"error": "unknown message type"})
        log.info("Client disconnected: %s", self.client_address)

    def _reply(self, payload):
        self.wfile.write((json.dumps(payload) + "\n").encode("utf-8"))
        self.wfile.flush()


class BridgeServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main(argv=None):
    parser = argparse.ArgumentParser(description="QEMU <-> Gazebo bridge")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args(argv)

    gazebo = GazeboLink()
    server = BridgeServer((args.host, args.port), BridgeHandler)
    server.gazebo = gazebo
    log.info("Bridge listening on %s:%d", args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down bridge.")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
