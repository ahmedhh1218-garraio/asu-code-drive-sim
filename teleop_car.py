#!/usr/bin/env python3
"""PlayStation / generic gamepad teleop for the simulated car.

Reads a connected gamepad via ``pygame`` and publishes Gazebo ``/cmd_vel``
twists. Falls back to keyboard control (terminal) when no joystick or pygame is
available. Useful for generating demonstration data in simulation.
"""

import argparse
import logging
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("teleop")

LINEAR_SPEED = 0.3
ANGULAR_SPEED = 1.2


class GzPublisher:
    """Publish Twist messages to /cmd_vel; no-op stub when transport missing."""

    def __init__(self):
        try:
            from gz.transport13 import Node  # type: ignore
            from gz.msgs10.twist_pb2 import Twist  # type: ignore

            self._Twist = Twist
            self._node = Node()
            self._pub = self._node.advertise("/cmd_vel", Twist)
            log.info("Publishing to /cmd_vel via gz.transport.")
        except Exception as exc:  # pragma: no cover - optional dependency
            log.warning("gz.transport unavailable (%s). Commands will be logged only.", exc)
            self._pub = None

    def publish(self, linear, angular):
        if self._pub:
            msg = self._Twist()
            msg.linear.x = linear
            msg.angular.z = angular
            self._pub.publish(msg)
        else:
            log.debug("cmd_vel linear=%.2f angular=%.2f", linear, angular)


def run_gamepad(pub):
    import pygame

    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        log.warning("No joystick detected; switching to keyboard mode.")
        return False

    js = pygame.joystick.Joystick(0)
    js.init()
    log.info("Using joystick: %s", js.get_name())

    clock = pygame.time.Clock()
    try:
        while True:
            pygame.event.pump()
            # Left stick Y -> forward/back, right stick X -> turn.
            forward = -js.get_axis(1)
            turn = -js.get_axis(3) if js.get_numaxes() > 3 else -js.get_axis(2)
            deadzone = 0.1
            forward = 0.0 if abs(forward) < deadzone else forward
            turn = 0.0 if abs(turn) < deadzone else turn
            pub.publish(forward * LINEAR_SPEED, turn * ANGULAR_SPEED)
            clock.tick(20)
    except KeyboardInterrupt:
        pub.publish(0.0, 0.0)
    return True


def run_keyboard(pub):
    log.info("Keyboard teleop: w/s = fwd/back, a/d = left/right, space = stop, q = quit")
    mapping = {
        "w": (LINEAR_SPEED, 0.0),
        "s": (-LINEAR_SPEED, 0.0),
        "a": (0.0, ANGULAR_SPEED),
        "d": (0.0, -ANGULAR_SPEED),
        " ": (0.0, 0.0),
    }
    while True:
        try:
            key = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if key == "q":
            break
        linear, angular = mapping.get(key[:1] if key else " ", (0.0, 0.0))
        pub.publish(linear, angular)
        time.sleep(0.05)
    pub.publish(0.0, 0.0)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Gamepad/keyboard teleop for sim car")
    parser.add_argument("--keyboard", action="store_true", help="Force keyboard mode")
    args = parser.parse_args(argv)

    pub = GzPublisher()
    if args.keyboard:
        run_keyboard(pub)
        return
    try:
        if not run_gamepad(pub):
            run_keyboard(pub)
    except ImportError:
        log.warning("pygame not installed; using keyboard mode.")
        run_keyboard(pub)


if __name__ == "__main__":
    sys.exit(main())
