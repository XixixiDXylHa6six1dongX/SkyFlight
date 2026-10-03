# -*- coding: utf-8 -*-
"""
转向行为实测：按 A / D 时飞机往哪边转、能不能改变航向
"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glfw
import numpy as np

from skyflight import app as appmod


def key(g, code, down):
    g._on_key(g.window, code, 0, glfw.PRESS if down else glfw.RELEASE, 0)


def fresh():
    g = appmod.SkyFlightApp()
    g.init_gl()
    c = g.craft
    c.pos = np.array([0.0, 900.0, 0.0])
    c.speed_val = 76.0
    c.vel = np.array([0.0, 0.0, -76.0])
    c.pitch = 0.01
    c.roll = 0.0
    c.yaw = 0.0
    c.alpha = 0.02
    c.on_ground = False
    g.throttle_cmd = 0.7
    for _ in range(30):
        g.update(1 / 60.0)
    return g


dt = 1 / 60.0

print('=== 按 D 键 4 秒 ===')
g = fresh()
c = g.craft
y0 = c.yaw
r0 = c.roll
key(g, glfw.KEY_D, True)
for i in range(240):
    g.update(dt)
    if (i + 1) % 60 == 0:
        print('  %d 秒: 倾角 %+7.1f°  航向 %+7.1f°  位置 x %+7.1f  z %+7.1f' % (
            (i + 1) // 60, math.degrees(c.roll), math.degrees(c.yaw),
            c.pos[0], c.pos[2]))
key(g, glfw.KEY_D, False)
print('  → 倾角 %.1f° (正=右倾)   航向变化 %.1f°   x 位移 %+.1f' % (
    math.degrees(c.roll), math.degrees(c.yaw - y0), c.pos[0]))
glfw.terminate()

print()
print('=== 按 A 键 4 秒 ===')
g = fresh()
c = g.craft
y0 = c.yaw
key(g, glfw.KEY_A, True)
for i in range(240):
    g.update(dt)
    if (i + 1) % 60 == 0:
        print('  %d 秒: 倾角 %+7.1f°  航向 %+7.1f°  位置 x %+7.1f  z %+7.1f' % (
            (i + 1) // 60, math.degrees(c.roll), math.degrees(c.yaw),
            c.pos[0], c.pos[2]))
key(g, glfw.KEY_A, False)
print('  → 倾角 %.1f° (正=右倾)   航向变化 %.1f°   x 位移 %+.1f' % (
    math.degrees(c.roll), math.degrees(c.yaw - y0), c.pos[0]))
glfw.terminate()

print()
print('=== 不按键（会不会自己偏）10 秒 ===')
g = fresh()
c = g.craft
y0 = c.yaw
r0 = c.roll
for i in range(600):
    g.update(dt)
    if (i + 1) % 120 == 0:
        print('  %d 秒: 倾角 %+7.2f°  航向 %+7.2f°  x %+7.1f' % (
            (i + 1) // 60, math.degrees(c.roll), math.degrees(c.yaw), c.pos[0]))
print('  → 10 秒漂移: 倾角 %+.2f°  航向 %+.2f°  x %+.1f' % (
    math.degrees(c.roll - r0), math.degrees(c.yaw - y0), c.pos[0]))
glfw.terminate()
