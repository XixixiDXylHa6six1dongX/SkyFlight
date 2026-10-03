# -*- coding: utf-8 -*-
"""左右对照图：按 D / 按 A / 不按，三张图并排，直接看哪边机翼低

相机固定在飞机正后方偏上，画面上方=北(机头原方向)，画面右=东(飞机右侧)
"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glfw
import numpy as np
from OpenGL import GL
from PIL import Image, ImageDraw

from skyflight import app as appmod, gfx, plane

OUT = r'C:\DEEPSEEK工作区\飞行模拟\shots'


def colored_plane():
    saved = []

    class Cap:
        def __init__(self, verts, indices=None):
            saved.append(np.asarray(verts, dtype=np.float32).reshape(-1, 9))
            self.count = saved[-1].shape[0]

    orig = gfx.Mesh
    gfx.Mesh = Cap
    try:
        plane.build_plane()
    finally:
        gfx.Mesh = orig
    V = np.concatenate(saved, axis=0).copy()
    x = V[:, 0]
    wing = (np.abs(x) > 1.2) & (V[:, 1] > -0.6) & (V[:, 1] < 0.8)
    V[wing & (x > 0), 6:9] = (1.0, 0.0, 0.0)     # 模型 +X 红
    V[wing & (x < 0), 6:9] = (0.05, 0.15, 1.0)   # 模型 -X 蓝
    return gfx.Mesh(V.reshape(-1))


g = appmod.SkyFlightApp()
g.init_gl()
mesh = colored_plane()
c = g.craft
w, h = glfw.get_framebuffer_size(g.window)
proj = gfx.perspective(48.0, w / float(h), 0.5, 42000.0)

tiles = []
for tag, key in (('不按键', None), ('按D', glfw.KEY_D), ('按A', glfw.KEY_A)):
    c.pos = np.array([0.0, 900.0, 0.0])
    c.speed_val = 76.0
    c.vel = np.array([0.0, 0.0, -76.0])
    c.pitch = c.roll = c.yaw = 0.0
    c.on_ground = False
    g.throttle_cmd = 0.7
    for _ in range(30):
        g.update(1 / 60.0)
    # 复位到起点、正北
    c.pos = np.array([0.0, 900.0, 0.0])
    c.yaw = 0.0
    c.roll = 0.0
    c.vel = np.array([0.0, 0.0, -76.0])
    if key:
        g._on_key(g.window, key, 0, glfw.PRESS, 0)
    for _ in range(150):
        g.update(1 / 60.0)

    fwd, right, up, R = c.basis()
    cam = c.pos - fwd * 30.0 + np.array([0.0, 6.0, 0.0])
    tgt = c.pos + fwd * 60.0
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
    m = np.eye(4, dtype=np.float32)
    m[:3, :3] = R.astype(np.float32)
    m[:3, 3] = c.pos.astype(np.float32)
    g.obj_shader.set_mat4('uModel', m)
    g.obj_shader.set_mat3('uNormalMat', m[:3, :3])
    mesh.draw()

    GL.glReadBuffer(GL.GL_BACK)
    d = GL.glReadPixels(0, 0, w, h, GL.GL_RGB, GL.GL_UNSIGNED_BYTE)
    a = np.frombuffer(d, dtype=np.uint8).reshape(h, w, 3)[::-1]
    img = Image.fromarray(a)
    dr = ImageDraw.Draw(img)
    ry_world = (R @ np.array([5.6, 0, 0]))[1]
    ly_world = (R @ np.array([-5.6, 0, 0]))[1]
    dr.text((16, 16), '%s   倾角 %+.1f°   航向 %+.1f°' % (
        tag, math.degrees(c.roll), math.degrees(c.yaw)), fill=(255, 255, 60))
    dr.text((16, 38), '右翼(红)高度 %+.1f   左翼(蓝)高度 %+.1f  → %s更低' % (
        ry_world, ly_world, '右翼(红)' if ry_world < ly_world else '左翼(蓝)'),
        fill=(255, 255, 60))
    # 小色块图例
    dr.rectangle([16, 62, 44, 82], fill=(255, 0, 0))
    dr.text((50, 66), '= 右翼', fill=(255, 255, 255))
    dr.rectangle([130, 62, 158, 82], fill=(10, 40, 255))
    dr.text((164, 66), '= 左翼', fill=(255, 255, 255))
    tiles.append(img)
    print('  %s: 右翼(红) %+.1f   左翼(蓝) %+.1f  → %s更低' % (
        tag, ry_world, ly_world, '右翼(红)' if ry_world < ly_world else '左翼(蓝)'))
    if key:
        g._on_key(g.window, key, 0, glfw.RELEASE, 0)

# 拼成一张
tw, th = tiles[0].size
sheet = Image.new('RGB', (tw, th * 3), (0, 0, 0))
for i, t in enumerate(tiles):
    sheet.paste(t, (0, i * th))
sheet = sheet.resize((tw // 2, th * 3 // 2))
sheet.save(os.path.join(OUT, '转向对照.png'))
print()
print('  对照图已保存: 转向对照.png')
glfw.terminate()
