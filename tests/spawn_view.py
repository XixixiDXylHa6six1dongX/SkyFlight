# -*- coding: utf-8 -*-
"""用游戏实际视角检查出生点的飞机是否看起来沉进跑道"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glfw
import numpy as np
from OpenGL import GL
from PIL import Image, ImageDraw

from skyflight import app as appmod, plane, terrain

OUT = r'C:\DEEPSEEK工作区\飞行模拟\shots'

g = appmod.SkyFlightApp()
g.init_gl()
c = g.craft
for _ in range(90):
    g.update(1 / 60.0)

surf = plane.surface_height(c.pos[0], c.pos[2], terrain.height_at(c.pos[0], c.pos[2]))
wheel = c.pos[1] - c.GEAR_HEIGHT
print('  机身 y=%.3f  轮胎底=%.3f  地面=%.3f  差=%+.4f' % (c.pos[1], wheel, surf, wheel - surf))
# 跑道标记最高的部件
print('  跑道中线/边线盒子 y=0.26 高0.06 -> 顶面 y=%.2f' % (0.26 + 0.03))
print('  跑道灯 y=0.55 高0.95     -> 顶面 y=%.2f' % (0.55 + 0.475))

shots = []
for mode, label in ((1, '追尾'), (0, '驾驶舱'), (2, '环绕')):
    g.camera.mode = mode
    # 复位相机
    fwd, right, up, R = c.basis()
    if mode == 0:
        g.camera.smooth = c.pos
    else:
        g.camera.smooth = c.pos - fwd * 30.0 + np.array([0.0, 9.0, 0.0])
    for _ in range(60):
        g.camera.update(c, {'dx': 0.0, 'dy': 0.0}, 1 / 60.0)
    g.draw()
    GL.glReadBuffer(GL.GL_BACK)
    w, h = glfw.get_framebuffer_size(g.window)
    d = GL.glReadPixels(0, 0, w, h, GL.GL_RGB, GL.GL_UNSIGNED_BYTE)
    a = np.frombuffer(d, dtype=np.uint8).reshape(h, w, 3)[::-1]
    img = Image.fromarray(a)
    dr = ImageDraw.Draw(img)
    dr.text((12, 12), '%s视角   轮胎底%.3f  跑道面%.3f  差%+.3f' % (
        label, wheel, surf, wheel - surf), fill=(255, 255, 60))
    p = os.path.join(OUT, 'Q3_%s视角.png' % label)
    img.save(p)
    shots.append(p)
    print('  已存 %s' % p)

glfw.terminate()
