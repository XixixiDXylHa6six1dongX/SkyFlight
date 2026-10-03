# -*- coding: utf-8 -*-
"""
修复后验证 + Q2 / Q3 排查

Q1: 机头方向和飞行方向是否一致（数值 + 画面）
Q2: 反向操作时速度怎么变
Q3: 出生点渲染是否沉进跑道
"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glfw
import numpy as np
from OpenGL import GL
from PIL import Image

from skyflight import app as appmod, plane, terrain

OUT = r'C:\DEEPSEEK工作区\飞行模拟\shots'


def key(g, code, down):
    g._on_key(g.window, code, 0, glfw.PRESS if down else glfw.RELEASE, 0)


# ============================================================ Q1
print('=' * 70)
print('Q1 机头 / 飞行方向一致性')
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
print('  按 D，逐秒看机头 vs 速度：')
for i in range(1, 361):
    g.update(1 / 60.0)
    if i % 60 == 0:
        fwd, right, up, R = c.basis()
        v = c.vel / max(1e-6, np.linalg.norm(c.vel))
        yaw_deg = math.degrees(c.yaw)
        d = float(np.dot(fwd, v))
        print('    %d 秒: 航向%+7.1f°  机头(%+.3f,%+.3f) 速度(%+.3f,%+.3f) 夹角点积%+.3f %s' % (
            i // 60, yaw_deg, fwd[0], fwd[2], v[0], v[2], d,
            '✅' if d > 0.95 else '❌'))
key(g, glfw.KEY_D, False)
glfw.terminate()

# ============================================================ Q2
print()
print('=' * 70)
print('Q2 反向操作时的速度变化')
print('=' * 70)
for label, keys in (('收油门(X) + 拉杆抬头(S)', [glfw.KEY_X, glfw.KEY_S]),
                    ('收油门(X) + 推杆低头(W)', [glfw.KEY_X, glfw.KEY_W]),
                    ('满油门(Z) + 推杆低头(W)', [glfw.KEY_Z, glfw.KEY_W]),
                    ('满油门(Z) + 拉杆抬头(S)', [glfw.KEY_Z, glfw.KEY_S])):
    g = appmod.SkyFlightApp()
    g.init_gl()
    c = g.craft
    c.pos = np.array([0.0, 1500.0, 0.0])
    c.speed_val = 76.0
    c.vel = np.array([0.0, 0.0, -76.0])
    c.pitch = c.roll = c.yaw = 0.0
    c.on_ground = False
    g.throttle_cmd = 0.7
    for _ in range(30):
        g.update(1 / 60.0)
    spd0 = c.airspeed_kmh
    for k in keys:
        key(g, k, True)
    for _ in range(300):
        g.update(1 / 60.0)
    for k in keys:
        key(g, k, False)
    print('  %-24s 速度 %4.0f -> %4.0f km/h  %s   油门%.0f%%  俯仰%+6.1f°  迎角%+5.1f°' % (
        label, spd0, c.airspeed_kmh,
        '↑变快' if c.airspeed_kmh > spd0 + 3 else ('↓变慢' if c.airspeed_kmh < spd0 - 3 else '→基本不变'),
        c.throttle * 100, math.degrees(c.pitch), c.aoa_deg))
    glfw.terminate()

# ============================================================ Q3
print()
print('=' * 70)
print('Q3 出生点渲染检查')
print('=' * 70)
g = appmod.SkyFlightApp()
g.init_gl()
c = g.craft
for _ in range(60):
    g.update(1 / 60.0)
surf = plane.surface_height(c.pos[0], c.pos[2], terrain.height_at(c.pos[0], c.pos[2]))
print('  机身原点 y=%.3f   地面=%.3f   轮胎底 y=%.3f   相对 %+.3f' % (
    c.pos[1], surf, c.pos[1] - c.GEAR_HEIGHT, c.pos[1] - c.GEAR_HEIGHT - surf))

# 用侧视正交相机拍一张，看清轮胎和跑道的关系
w, h = glfw.get_framebuffer_size(g.window)
proj = np.zeros((4, 4), dtype=np.float32)
span = 14.0
proj[0, 0] = 2.0 / (2 * span)
proj[1, 1] = 2.0 / (2 * span * h / float(w))
proj[2, 2] = -2.0 / 199.0
proj[2, 3] = -201.0 / 199.0
proj[3, 3] = 1.0
cam = c.pos + np.array([-40.0, 1.5, 0.0])
tgt = c.pos + np.array([0.0, 0.0, 1.0])
from skyflight import gfx
VP = proj @ gfx.look_at(cam, tgt, np.array([0.0, 1.0, 0.0]))

GL.glViewport(0, 0, w, h)
GL.glClearColor(0.16, 0.22, 0.32, 1)
GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
g.obj_shader.use()
g.obj_shader.set_mat4('uVP', VP)
g.obj_shader.set_vec3('uSunDir', (0.45, 0.75, 0.5))
g.obj_shader.set_vec3('uCamPos', cam)
g.obj_shader.set_vec3('uFogColor', g.fog_color)
g.obj_shader.set_float('uFogDensity', 0.0)
for mesh, pos, nm in ((g.runway_mesh, (0.0, 0.0, 0.0), '跑道'),
                      (g.plane_mesh, c.pos, '飞机')):
    m = np.eye(4, dtype=np.float32)
    if nm == '飞机':
        R = gfx.euler_to_matrix(c.pitch, c.yaw, c.roll)
        m[:3, :3] = R.astype(np.float32)
    m[:3, 3] = np.asarray(pos, dtype=np.float32)
    g.obj_shader.set_mat4('uModel', m)
    g.obj_shader.set_mat3('uNormalMat', m[:3, :3])
    mesh.draw()
GL.glReadBuffer(GL.GL_BACK)
d = GL.glReadPixels(0, 0, w, h, GL.GL_RGB, GL.GL_UNSIGNED_BYTE)
a = np.frombuffer(d, dtype=np.uint8).reshape(h, w, 3)[::-1]
img = Image.fromarray(a)
from PIL import ImageDraw
dr = ImageDraw.Draw(img)
dr.text((12, 12), '侧视正交：跑道面 y=0.24  轮胎底 y=%.3f  差 %+.3f' % (
    c.pos[1] - c.GEAR_HEIGHT, c.pos[1] - c.GEAR_HEIGHT - surf), fill=(255, 255, 60))
img.save(os.path.join(OUT, 'Q3_起落架侧视.png'))
print('  侧视截图已保存: Q3_起落架侧视.png')
glfw.terminate()
