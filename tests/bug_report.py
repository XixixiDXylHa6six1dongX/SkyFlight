# -*- coding: utf-8 -*-
"""
三个问题的诊断

Q1: 按 D 时右翼下压、往右飞，但机头往左偏？
Q2: 往与运动方向相反的方向推，速度还往原方向增加？
Q3: 出生点飞机卡进跑道？
"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glfw
import numpy as np

from skyflight import app as appmod, plane, terrain


def key(g, code, down):
    g._on_key(g.window, code, 0, glfw.PRESS if down else glfw.RELEASE, 0)


print('=' * 70)
print('Q3: 出生点 / 起落架')
print('=' * 70)
g = appmod.SkyFlightApp()
g.init_gl()
c = g.craft
surf = plane.surface_height(c.pos[0], c.pos[2], terrain.height_at(c.pos[0], c.pos[2]))
print('  出生: 机身原点 y=%.3f  地面(含跑道) y=%.3f  轮胎底 y=%.3f' % (
    c.pos[1], surf, c.pos[1] - c.GEAR_HEIGHT))
print('  轮胎底相对地面 = %+.3f m  %s' % (
    c.pos[1] - c.GEAR_HEIGHT - surf,
    '✅ 贴地' if abs(c.pos[1] - c.GEAR_HEIGHT - surf) < 0.05 else '❌'))
print()
print('  按 Z 满油门后逐秒:')
key(g, glfw.KEY_Z, True)
g.update(1 / 60.0)
key(g, glfw.KEY_Z, False)
for i in range(1, 481):
    g.update(1 / 60.0)
    if i % 60 == 0:
        s = plane.surface_height(c.pos[0], c.pos[2], terrain.height_at(c.pos[0], c.pos[2]))
        wheel = c.pos[1] - c.GEAR_HEIGHT
        print('    %2d 秒: 原点 y=%.3f  轮胎底=%.3f  地面=%.3f  相对=%+.3f  速度=%.0f  %s' % (
            i // 60, c.pos[1], wheel, s, wheel - s, c.airspeed_kmh,
            '❌ 陷进去' if wheel < s - 0.05 else '✅'))
glfw.terminate()

print()
print('=' * 70)
print('Q1: 按 D 时 机头方向 / 运动方向 / 机翼')
print('=' * 70)
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
key(g, glfw.KEY_D, True)
print('  %4s %9s %9s %10s %10s %10s %10s' % (
    '秒', '倾角°', '航向°', '机头X', '机头Z', '速度X', '速度Z'))
for i in range(1, 361):
    g.update(1 / 60.0)
    if i % 60 == 0:
        fwd, right, up, R = c.basis()
        v = c.vel / max(1e-6, np.linalg.norm(c.vel))
        print('  %4d %9.1f %9.1f %10.3f %10.3f %10.3f %10.3f' % (
            i // 60, math.degrees(c.roll), math.degrees(c.yaw),
            fwd[0], fwd[2], v[0], v[2]))
key(g, glfw.KEY_D, False)
fwd, right, up, R = c.basis()
v = c.vel / max(1e-6, np.linalg.norm(c.vel))
dot = float(np.dot(fwd, v))
print()
print('  机头方向 · 速度方向 = %+.3f  (1.0=完全一致, -1.0=完全相反)' % dot)
print('  → %s' % ('✅ 机头和运动方向一致' if dot > 0.9 else
                  ('❌ 机头和运动方向相反！' if dot < -0.5 else '⚠ 有偏差')))
print('  右翼世界高度 %+.2f  左翼 %+.2f' % (
    (R @ np.array([5.6, 0, 0]))[1], (R @ np.array([-5.6, 0, 0]))[1]))
glfw.terminate()

print()
print('=' * 70)
print('Q2: 反向推进 / 速度方向')
print('=' * 70)
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
print('  初始: yaw=%.1f°  速度=%.0f km/h  速度方向 X%+.2f Z%+.2f' % (
    math.degrees(c.yaw), c.airspeed_kmh,
    c.vel[0] / max(1, np.linalg.norm(c.vel)),
    c.vel[2] / max(1, np.linalg.norm(c.vel))))
print()
print('  按 S（拉杆抬头）+ 满油门，看速度大小和方向怎么变:')
key(g, glfw.KEY_Z, True)
g.update(1 / 60.0)
key(g, glfw.KEY_Z, False)
key(g, glfw.KEY_S, True)
for i in range(1, 481):
    g.update(1 / 60.0)
    if i % 60 == 0:
        v = c.vel / max(1e-6, np.linalg.norm(c.vel))
        fwd, right, up, R = c.basis()
        print('    %2d 秒: 速度=%4.0f km/h  机头X%+.2f Z%+.2f  速度X%+.2f Z%+.2f  α=%+.1f°' % (
            i // 60, c.airspeed_kmh, fwd[0], fwd[2], v[0], v[2], c.aoa_deg))
key(g, glfw.KEY_S, False)
glfw.terminate()
