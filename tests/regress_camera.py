# -*- coding: utf-8 -*-
"""
yaw 约定修正后的全面回归

重点检查相机是否也被影响（相机也用 euler_to_matrix 算 basis）
"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glfw
import numpy as np
from OpenGL import GL
from PIL import Image

from skyflight import app as appmod, gfx


def key(g, code, down):
    g._on_key(g.window, code, 0, glfw.PRESS if down else glfw.RELEASE, 0)


OUT = r'C:\DEEPSEEK工作区\飞行模拟\shots'

g = appmod.SkyFlightApp()
g.init_gl()
c = g.craft
c.pos = np.array([0.0, 900.0, 0.0])
c.speed_val = 76.0
c.vel = np.array([0.0, 0.0, -76.0])
c.pitch = c.roll = c.yaw = 0.0
c.on_ground = False
g.throttle_cmd = 0.7
for _ in range(30):
    g.update(1 / 60.0)

print('=== 相机位置是否在飞机【后方】（追尾视角应如此）===')
print('%6s %10s %12s %10s %12s' % ('时刻', '航向°', '相机在前/后', '相机右偏', '相机上下'))
key(g, glfw.KEY_D, True)
for i in range(1, 301):
    g.update(1 / 60.0)
    if i % 60 == 0:
        fwd, right, up, R = c.basis()
        rel = g.camera.pos - c.pos
        front = float(np.dot(rel, fwd))
        side = float(np.dot(rel, right))
        vert = float(np.dot(rel, up))
        print('%6d %10.1f %12s %10.1f %12.1f' % (
            i // 60, math.degrees(c.yaw),
            '后方 ✅' if front < 0 else '前方 ❌', side, vert))
key(g, glfw.KEY_D, False)

print()
print('=== 相机看向的点是否在飞机前方 ===')
fwd, right, up, R = c.basis()
tgt_rel = g.camera.target - c.pos
print('  target 相对飞机: 前方投影 %+.1f  右偏 %+.1f  上 %+.1f' % (
    float(np.dot(tgt_rel, fwd)), float(np.dot(tgt_rel, right)),
    float(np.dot(tgt_rel, up))))
print('  → %s' % ('✅ 看向飞机前方' if np.dot(tgt_rel, fwd) > 0 else '❌ 看向飞机后方'))

print()
print('=== 机头方向 = 速度方向（最终确认）===')
v = c.vel / max(1e-6, np.linalg.norm(c.vel))
print('  机头 (%+.3f, %+.3f)   速度 (%+.3f, %+.3f)   点积 %+.3f' % (
    fwd[0], fwd[2], v[0], v[2], float(np.dot(fwd, v))))
print('  右翼世界高度 %+.2f   左翼 %+.2f  → %s' % (
    (R @ np.array([5.6, 0, 0]))[1], (R @ np.array([-5.6, 0, 0]))[1],
    '右翼低(右倾) ✅' if (R @ np.array([5.6, 0, 0]))[1] < (R @ np.array([-5.6, 0, 0]))[1]
    else '左翼低 ❌'))

print()
print('=== 罗盘读数是否合理（按 D 右转应往东 090 走）===')
print('  当前航向 %03d°  %s' % (
    int(math.degrees(c.yaw) % 360),
    '✅ 在东侧(右转正确)' if 0 < math.degrees(c.yaw) % 360 < 180 else '❌'))

glfw.terminate()
