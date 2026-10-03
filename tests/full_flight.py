# -*- coding: utf-8 -*-
"""
完整飞行实测：起飞 -> 爬升 -> 巡航 -> 转弯 -> 降落
全程只用"按键"，验证玩家能真的完整飞一圈
"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glfw
import numpy as np

from skyflight import app as appmod


def k(g, code, down):
    g._on_key(g.window, code, 0, glfw.PRESS if down else glfw.RELEASE, 0)


g = appmod.SkyFlightApp()
g.init_gl()
dt = 1 / 60.0
c = g.craft


def step(n=1):
    for _ in range(n):
        g.update(dt)


def log(tag):
    print('  %-14s 高度 %5.0f m  速度 %4.0f km/h  俯仰 %+5.1f°  倾角 %+5.1f°  迎角 %+5.1f°  %s' % (
        tag, c.altitude, c.airspeed_kmh, math.degrees(c.pitch),
        math.degrees(c.roll), c.aoa_deg, '' if not c.crashed else '✖坠毁'))


results = []

# ============ 1. 起飞
print('=== 1) 起飞 ===')
log('出生')
k(g, glfw.KEY_Z, True); step(); k(g, glfw.KEY_Z, False)
t = 0
while c.airspeed_kmh < 100 and t < 2400:
    step(); t += 1
print('  滑跑 %.1f 秒到 %.0f km/h' % (t * dt, c.airspeed_kmh))
# 抬前轮
k(g, glfw.KEY_S, True)
t = 0
while math.degrees(c.pitch) < 12.0 and t < 600:
    step(); t += 1
print('  抬前轮 %.1f 秒到 %.1f°' % (t * dt, math.degrees(c.pitch)))
# 保持到离地
t = 0
while c.altitude < 15.0 and t < 1200:
    step(); t += 1
    if math.degrees(c.pitch) < 8:
        k(g, glfw.KEY_S, True)
    else:
        k(g, glfw.KEY_S, False)
k(g, glfw.KEY_S, False)
lifted = c.altitude >= 15.0 and not c.crashed
results.append(('起飞离地', lifted, '高度 %.0f m' % c.altitude))
log('离地')

# ============ 2. 爬升到 800 m
print()
print('=== 2) 爬升到 800 m ===')
k(g, glfw.KEY_SHIFT if False else glfw.KEY_Z, True); step(); k(g, glfw.KEY_Z, False)
t = 0
while c.altitude < 800.0 and t < 60 * 180:
    step(); t += 1
    pd = math.degrees(c.pitch)
    if pd < 9.0:
        k(g, glfw.KEY_S, True); k(g, glfw.KEY_W, False)
    elif pd > 13.0:
        k(g, glfw.KEY_S, False); k(g, glfw.KEY_W, True)
    else:
        k(g, glfw.KEY_S, False); k(g, glfw.KEY_W, False)
k(g, glfw.KEY_S, False); k(g, glfw.KEY_W, False)
climbed = c.altitude >= 790.0 and not c.crashed
results.append(('爬升到 800m', climbed, '%.0f m，用时 %.0f 秒' % (c.altitude, t * dt)))
log('爬到 800m')

# ============ 3. 巡航保持（比例控制）
print()
print('=== 3) 巡航保持 20 秒 ===')
errs = []
for i in range(1200):
    dh = 800.0 - c.altitude
    want = max(-6.0, min(8.0, dh * 0.10))
    pd = math.degrees(c.pitch)
    if pd < want - 1.0:
        k(g, glfw.KEY_S, True); k(g, glfw.KEY_W, False)
    elif pd > want + 1.0:
        k(g, glfw.KEY_S, False); k(g, glfw.KEY_W, True)
    else:
        k(g, glfw.KEY_S, False); k(g, glfw.KEY_W, False)
    step()
    errs.append(abs(c.altitude - 800.0))
    if c.crashed:
        break
k(g, glfw.KEY_S, False); k(g, glfw.KEY_W, False)
hold_ok = (not c.crashed) and np.mean(errs) < 60
results.append(('巡航保持', hold_ok, '平均误差 %.0f m，最大 %.0f m' % (
    np.mean(errs), np.max(errs))))
log('巡航')

# ============ 4. 转弯（航向角会在 ±180° 循环，必须逐帧累加）
print()
print('=== 4) 右转一圈 ===')
k(g, glfw.KEY_D, True)
t = 0
turned = 0.0
prev = c.yaw
while t < 60 * 60:
    step(); t += 1
    d = c.yaw - prev
    if d > math.pi:
        d -= 2 * math.pi
    elif d < -math.pi:
        d += 2 * math.pi
    turned += abs(d)
    prev = c.yaw
    if t <= 5 or t % 600 == 0:
        print('    t=%4d  yaw=%+8.2f°  d=%+.4f°  turned=%.1f°  倾角=%+.1f°  坠毁=%s' % (
            t, math.degrees(c.yaw), math.degrees(d), math.degrees(turned),
            math.degrees(c.roll), c.crashed))
    if c.crashed or math.degrees(turned) > 350:
        break
k(g, glfw.KEY_D, False)
step(180)
turn_ok = (not c.crashed) and math.degrees(turned) > 340
results.append(('转弯一周', turn_ok, '转过 %.0f°，用时 %.1f 秒，松杆后倾角 %.1f°' % (
    math.degrees(turned), t * dt, math.degrees(c.roll))))
log('转完')

# ============ 5. 下降 + 降落
print()
print('=== 5) 下降回机场 ===')
# 先降低功率，下降
k(g, glfw.KEY_LEFT_CONTROL, True)
t = 0
while g.throttle_cmd > 0.20 and t < 60 * 10:
    step(); t += 1
k(g, glfw.KEY_LEFT_CONTROL, False)
print('  油门收到 %.0f%%' % (g.throttle_cmd * 100))
k(g, glfw.KEY_F, True); step(); k(g, glfw.KEY_F, False)
print('  放襟翼')

# 下降到 300 m
t = 0
while c.altitude > 300.0 and t < 60 * 200:
    step(); t += 1
    if math.degrees(c.pitch) > -3.0:
        k(g, glfw.KEY_W, True); k(g, glfw.KEY_S, False)
    else:
        k(g, glfw.KEY_W, False)
k(g, glfw.KEY_W, False)
log('降到 300m')

print()
print('=== 结果汇总 ===')
npass = 0
for name, ok, detail in results:
    print('  %-14s %s  %s' % (name, '✅' if ok else '❌', detail))
    if ok:
        npass += 1
print()
print('  通过 %d/%d' % (npass, len(results)))
print('  最终: %s' % c.status())

# 截图
from OpenGL import GL
from PIL import Image
GL.glViewport(0, 0, *glfw.get_framebuffer_size(g.window))
g.draw()
glfw.swap_buffers(g.window); glfw.poll_events()
GL.glReadBuffer(GL.GL_FRONT)
w, h = glfw.get_framebuffer_size(g.window)
d = GL.glReadPixels(0, 0, w, h, GL.GL_RGB, GL.GL_UNSIGNED_BYTE)
a = np.frombuffer(d, dtype=np.uint8).reshape(h, w, 3)[::-1]
Image.fromarray(a).save(r'C:\DEEPSEEK工作区\飞行模拟\shots\飞行中.png')
print('  截图已保存')
glfw.terminate()
