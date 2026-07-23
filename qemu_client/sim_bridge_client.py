"""Simulation bridge client.

Connects the car application (running inside QEMU or on a laptop) to the Gazebo
simulation bridge over TCP. Motor commands are sent up; sensor distances are
requested on demand. A newline-delimited JSON protocol keeps the bridge simple.
"""

import json
import logging
import socket
import threading

import config

log = logging.getLogger(__name__)


class SimBridgeClient:
    """TCP client speaking the newline-delimited JSON bridge protocol."""

    def __init__(self, host=config.SIM_BRIDGE_HOST, port=config.SIM_BRIDGE_PORT):
        self.host = host
        self.port = port
        self._sock = None
        self._lock = threading.Lock()
        self._last_distances = {
            name: config.MAX_DISTANCE_CM for name in config.SENSOR_NAMES
        }
        self._last_imu = [0.0] * len(config.IMU_FEATURE_NAMES)
        self._connect()

    def _connect(self):
        try:
            self._sock = socket.create_connection((self.host, self.port), timeout=2.0)
            self._sock_file = self._sock.makefile("r")
            log.info("Connected to sim bridge %s:%s", self.host, self.port)
        except OSError as exc:
            log.error("Sim bridge connection failed: %s", exc)
            self._sock = None

    def _send(self, message):
        if self._sock is None:
            self._connect()
        if self._sock is None:
            return None
        try:
            with self._lock:
                self._sock.sendall((json.dumps(message) + "\n").encode("utf-8"))
                line = self._sock_file.readline()
            if not line:
                return None
            return json.loads(line)
        except (OSError, ValueError) as exc:
            log.error("Sim bridge I/O error: %s", exc)
            self._sock = None
            return None

    # -- public API ---------------------------------------------------------
    def send_motion(self, action, speed):
        """Send a motion command to the simulated car."""
        self._send({"type": "motion", "action": action, "speed": speed})

    def get_distances_cm(self):
        """Request the latest simulated sensor distances (centimetres)."""
        reply = self._send({"type": "sensors"})
        if reply and "distances" in reply:
            self._last_distances = {
                name: float(reply["distances"].get(name, config.MAX_DISTANCE_CM))
                for name in config.SENSOR_NAMES
            }
        return dict(self._last_distances)

    def get_imu(self):
        """Request the latest simulated IMU features ``[ax,ay,az,gx,gy,gz]``."""
        reply = self._send({"type": "imu"})
        if reply and "imu" in reply:
            values = reply["imu"]
            if isinstance(values, list) and len(values) == len(config.IMU_FEATURE_NAMES):
                self._last_imu = [float(v) for v in values]
        return list(self._last_imu)

    def close(self):
        if self._sock:
            try:
                self._sock.close()
            except OSError:  # pragma: no cover
                pass
            self._sock = None


_client = None


def get_sim_client():
    global _client
    if _client is None:
        _client = SimBridgeClient()
    return _client
