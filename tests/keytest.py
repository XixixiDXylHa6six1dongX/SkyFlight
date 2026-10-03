# -*- coding: utf-8 -*-
"""
键位实测：模拟真实按键，检查游戏是否真的响应
直接调用游戏的按键回调 + 跑 update，观察飞控状态变化
"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glfw
import numpy as np

from skyflight import app as appmod
from skyflight.app import key_name


def press(g, code):
    g._on_key(g.window, code, 0, glfw.PRESS, 0)


def release(g, code):
    g._on_key(g.window, code, 0, glfw.RELEASE, 0)


def hold(g, code, secs=1.0, dt=1 / 60.0):
    press(g, code)
    for _ in range(int(secs / dt)):
        g.update(dt)
    release(g, code)


print('=== 1) 按键名解析（这是之前坏掉的地方）===')
codes = [
    ('W', glfw.KEY_W), ('A', glfw.KEY_A), ('S', glfw.KEY_S), ('D', glfw.KEY_D),
    ('Q', glfw.KEY_Q), ('E', glfw.KEY_E), ('F', glfw.KEY_F), ('B', glfw.KEY_B),
    ('M', glfw.KEY_M), ('P', glfw.KEY_P), ('R', glfw.KEY_R), ('C', glfw.KEY_C),
    ('Z', glfw.KEY_Z), ('X', glfw.KEY_X), ('H', glfw.KEY_H),
    ('UP', glfw.KEY_UP), ('DOWN', glfw.KEY_DOWN),
    ('LEFT', glfw.KEY_LEFT), ('RIGHT', glfw.KEY_RIGHT),
    ('LEFT_SHIFT', glfw.KEY_LEFT_SHIFT), ('RIGHT_SHIFT', glfw.KEY_RIGHT_SHIFT),
    ('LEFT_CONTROL', glfw.KEY_LEFT_CONTROL), ('RIGHT_CONTROL', glfw.KEY_RIGHT_CONTROL),
    ('ESCAPE', glfw.KEY_ESCAPE),
]
bad = [x for x in codes if key_name(x[1]) != x[0]]
for want, code in codes:
    got = key_name(code)
    print('  %-14s -> %-14s %s' % (want, got, '' if got == want else '❌'))
print()
print('  解析失败: %d 个' % len(bad))

# ---------- 启动游戏实例
g = appmod.SkyFlightApp()
g.init_gl()
g.craft.reset((0.0, 120.0, 900.0))
dt = 1 / 60.0

print()
print('=== 2) 俯仰键（S / ↓ = 拉杆抬头，W / ↑ = 推杆低头）===')
for label, code, want in (('S 拉杆抬头', glfw.KEY_S, 1),
                          ('DOWN 拉杆抬头', glfw.KEY_DOWN, 1),
                          ('W 推杆低头', glfw.KEY_W, -1),
                          ('UP 推杆低头', glfw.KEY_UP, -1)):
    g.controls.pitch = 0.0
    hold(g, code, 0.4, dt)
    d = g.controls.pitch
    ok = (d > 0.5) if want > 0 else (d < -0.5)
    print('  %-16s pitch = %+.2f  %s' % (label, d, 'OK' if ok else '❌ 无响应'))

print()
print('=== 3) 滚转键 ===')
for label, code in (('D 右滚', glfw.KEY_D), ('RIGHT 右滚', glfw.KEY_RIGHT),
                    ('A 左滚', glfw.KEY_A), ('LEFT 左滚', glfw.KEY_LEFT)):
    g.controls.roll = 0.0
    hold(g, code, 0.4, dt)
    d = g.controls.roll
    ok = (d > 0.5) if '右' in label else (d < -0.5)
    print('  %-12s roll = %+.2f  %s' % (label, d, 'OK' if ok else '❌ 无响应'))

print()
print('=== 4) 方向舵 ===')
for label, code in (('E 右舵', glfw.KEY_E), ('Q 左舵', glfw.KEY_Q)):
    g.controls.yaw = 0.0
    hold(g, code, 0.4, dt)
    d = g.controls.yaw
    ok = (d > 0.5) if '右' in label else (d < -0.5)
    print('  %-10s yaw = %+.2f  %s' % (label, d, 'OK' if ok else '❌ 无响应'))

print()
print('=== 5) 油门（之前完全失效）===')
g.throttle_cmd = 0.0
hold(g, glfw.KEY_LEFT_SHIFT, 1.0, dt)
t1 = g.throttle_cmd
print('  LEFT_SHIFT 1 秒後 throttle = %.2f  %s' % (t1, 'OK' if t1 > 0.3 else '❌ 无响应'))
hold(g, glfw.KEY_LEFT_CONTROL, 0.6, dt)
t2 = g.throttle_cmd
print('  LEFT_CONTROL 0.6 秒後 throttle = %.2f  %s' % (t2, 'OK' if t2 < t1 - 0.2 else '❌ 无响应'))
press(g, glfw.KEY_Z); g.update(dt); release(g, glfw.KEY_Z)
print('  Z 满油门 throttle = %.2f  %s' % (g.throttle_cmd, 'OK' if g.throttle_cmd > 0.99 else '❌'))
press(g, glfw.KEY_X); g.update(dt); release(g, glfw.KEY_X)
print('  X 收油门 throttle = %.2f  %s' % (g.throttle_cmd, 'OK' if g.throttle_cmd < 0.01 else '❌'))

print()
print('=== 6) 功能键 ===')
m0 = g.camera.mode
press(g, glfw.KEY_C); g.update(dt); release(g, glfw.KEY_C)
print('  C 切视角 %d -> %d  %s' % (m0, g.camera.mode, 'OK' if g.camera.mode != m0 else '❌'))
p0 = g.paused
press(g, glfw.KEY_P); g.update(dt); release(g, glfw.KEY_P)
print('  P 暂停 %s -> %s  %s' % (p0, g.paused, 'OK' if g.paused != p0 else '❌'))
press(g, glfw.KEY_P); g.update(dt); release(g, glfw.KEY_P)
f0 = g.controls.flaps
press(g, glfw.KEY_F); g.update(dt); release(g, glfw.KEY_F)
print('  F 襟翼 %.0f -> %.0f  %s' % (f0, g.controls.flaps, 'OK' if g.controls.flaps != f0 else '❌'))
b0 = g.controls.brakes
press(g, glfw.KEY_B); g.update(dt)
print('  B 刹车 = %.0f  %s' % (g.controls.brakes, 'OK' if g.controls.brakes > 0.5 else '❌'))
release(g, glfw.KEY_B)
m0 = g.controls.mouse_mode
press(g, glfw.KEY_M); g.update(dt); release(g, glfw.KEY_M)
print('  M 鼠标操纵 %s -> %s  %s' % (m0, g.controls.mouse_mode,
      'OK' if g.controls.mouse_mode != m0 else '❌'))
press(g, glfw.KEY_M); g.update(dt); release(g, glfw.KEY_M)
g.craft.pos = np.array([0.0, 300.0, 0.0])
g.craft.speed_val = 80.0
p0 = g.craft.pos.copy()
press(g, glfw.KEY_R); g.update(dt); release(g, glfw.KEY_R)
moved = np.linalg.norm(g.craft.pos - p0) > 100
print('  R 重来 位置重置 %s  %s' % (moved, 'OK' if moved else '❌'))

print()
print('=== 7) 长按（方向键会产生 REPEAT 事件）===')
g.controls.pitch = 0.0
g._on_key(g.window, glfw.KEY_DOWN, 0, glfw.PRESS, 0)
g._on_key(g.window, glfw.KEY_DOWN, 0, glfw.REPEAT, 0)
for _ in range(30):
    g.update(dt)
print('  长按 DOWN 後 pitch = %+.2f  %s' % (g.controls.pitch,
      'OK' if g.controls.pitch > 0.5 else '❌'))
g._on_key(g.window, glfw.KEY_DOWN, 0, glfw.RELEASE, 0)

# ---------- 汇总
print()
print('=== 按键状态表（当前按下的键）===')
held = [k for k, v in g.keys.items() if v]
print('  按下的键: %s' % (held if held else '（无）'))
print('  记录过的键名共 %d 个: %s' % (len(g.keys), sorted(set(g.keys))))

glfw.terminate()
