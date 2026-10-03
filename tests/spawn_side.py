# -*- coding: utf-8 -*-
"""侧视 + 追踪视角看飞机和跑道的关系（确认不再陷进地里）

侧视用正交投影放大，把轮胎和跑道面都拍清楚。
"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glfw
import numpy as np
from OpenGL import GL
from PIL import Image, ImageDraw

from skyflight import app as appmod, gfx, plane, terrain, i18n

OUT = r'C:\DEEPSEEK工作区\飞行模拟\shots'
i18n.set_lang(i18n.EN)

g = appmod.SkyFlightApp(aircraft_key='trainer')
g.init_gl()
c = g.craft
w, h = glfw.get_framebuffer_size(g.window)


def render_side(name, note, settle=True):
    """侧视正交：相机在飞机左边，正对跑道横截面"""
    if settle:
        for _ in range(300):
            g.update(1 / 60.0)
        # 再滑跑一会儿，看动起来是否还贴合
    surf = plane.surface_height(c.pos[0], c.pos[2],
                               float(terrain.height_at(c.pos[0], c.pos[2])))
    wheel = c.pos[1] - c.GEAR_HEIGHT
    span = 11.0
    proj = np.zeros((4, 4), dtype=np.float32)
    proj[0, 0] = 2.0 / (2 * span)                       # 左右 11 m
    proj[1, 1] = 2.0 / (2 * span * h / float(w))        # 上下按比例
    proj[2, 2] = -2.0 / 61.0
    proj[2, 3] = -60.0 / 61.0
    proj[3, 3] = 1.0
    cam = c.pos + np.array([-30.0, 2.0, 0.0])
    tgt = c.pos + np.array([0.0, -1.0, 0.0])
    VP = proj @ gfx.look_at(cam, tgt, np.array([0.0, 1.0, 0.0]))

    GL.glViewport(0, 0, w, h)
    GL.glClearColor(0.13, 0.18, 0.26, 1.0)
    GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
    sh = g.obj_shader
    sh.use()
    sh.set_mat4('uVP', VP)
    sh.set_vec3('uSunDir', (0.45, 0.75, 0.5))
    sh.set_vec3('uCamPos', cam)
    sh.set_vec3('uFogColor', g.fog_color)
    sh.set_float('uFogDensity', 0.0)

    def draw(mesh, m):
        sh.set_mat4('uModel', m)
        sh.set_mat3('uNormalMat', m[:3, :3])
        mesh.draw()

    # 沥青 + 标线（标线抬了 5mm，正常深度测试就行）
    m = np.eye(4, dtype=np.float32)
    m[1, 3] = 0.0
    draw(g.runway_mesh, m)
    draw(g.runway_paint_mesh, m)
    # 飞机 + 起落架
    R = gfx.euler_to_matrix(c.pitch, c.yaw, c.roll)
    pm = np.eye(4, dtype=np.float32)
    pm[:3, :3] = R.astype(np.float32)
    pm[:3, 3] = c.pos.astype(np.float32)
    draw(g.plane_mesh, pm)
    gv = max(0.02, c.gear)
    gl = np.array([[1, 0, 0, 0], [0, gv, 0, -0.55 * (1 - gv)],
                   [0, 0, 1, 0.30 + 0.70 * gv], [0, 0, 0, 1]], dtype=np.float32)
    draw(g.gear_mesh, pm @ gl)

    GL.glReadBuffer(GL.GL_BACK)
    d = GL.glReadPixels(0, 0, w, h, GL.GL_RGB, GL.GL_UNSIGNED_BYTE)
    a = np.frombuffer(d, dtype=np.uint8).reshape(h, w, 3)[::-1]
    img = Image.fromarray(a)
    dr = ImageDraw.Draw(img)
    dr.text((16, 14), note, fill=(255, 255, 90))
    dr.text((16, 34), 'runway top y=%.3f   wheel bottom y=%.3f   gap %+.4f m' % (
        surf, wheel, wheel - surf), fill=(255, 255, 90))
    img.save(os.path.join(OUT, name))
    print('  已存 %-28s 轮胎底 %.4f  跑道面 %.4f  间隙 %+.4f' % (
        name, wheel, surf, wheel - surf))


render_side('spawn-side-settled.png', 'SIDE VIEW (orthographic, 11 m wide) - settled')
glfw.terminate()
