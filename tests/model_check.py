# -*- coding: utf-8 -*-
"""模型检查：尺寸、命名、以及正交多视角预览"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from skyflight import gfx, plane

saved = {}


class FM:
    def __init__(self, vertices, indices=None):
        saved['v'] = np.asarray(vertices, dtype=np.float32).reshape(-1, 9)
        self.count = saved['v'].shape[0]


o = gfx.Mesh
gfx.Mesh = FM
plane.build_plane()
m = saved['v']
gfx.Mesh = o

P = m[:, 0:3]
print('=== 飞机模型尺寸 ===')
print('  翼展 X: %7.2f ~ %7.2f   = %.2f m' % (P[:, 0].min(), P[:, 0].max(), np.ptp(P[:, 0])))
print('  高度 Y: %7.2f ~ %7.2f   = %.2f m' % (P[:, 1].min(), P[:, 1].max(), np.ptp(P[:, 1])))
print('  长度 Z: %7.2f ~ %7.2f   = %.2f m' % (P[:, 2].min(), P[:, 2].max(), np.ptp(P[:, 2])))
print('  三角形数: %d' % (m.shape[0] // 3))
ok = True
if not (9.0 < np.ptp(P[:, 0]) < 14.0):
    print('  ❌ 翼展不在 9~14 m'); ok = False
if not (1.5 < np.ptp(P[:, 1]) < 5.0):
    print('  ❌ 高度不在 1.5~5 m'); ok = False
if not (7.0 < np.ptp(P[:, 2]) < 13.0):
    print('  ❌ 长度不在 7~13 m'); ok = False
if P[:, 2].min() > -0.5:
    print('  ❌ 机头不在前方(-Z)'); ok = False
print('  尺寸检查: %s' % ('通过' if ok else '失败'))

# 渲染多视角
import glfw
from OpenGL import GL
from PIL import Image
from skyflight import shaders

OUT = r'C:\DEEPSEEK工作区\飞行模拟\shots'
os.makedirs(OUT, exist_ok=True)
W, H = 1100, 700
glfw.init()
for h_, v_ in ((glfw.CONTEXT_VERSION_MAJOR, 3), (glfw.CONTEXT_VERSION_MINOR, 3),
               (glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE),
               (glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)):
    glfw.window_hint(h_, v_)
win = glfw.create_window(W, H, 'modelcheck', None, None)
glfw.make_context_current(win)
GL.glEnable(GL.GL_DEPTH_TEST)
GL.glEnable(GL.GL_CULL_FACE)
sh = gfx.Shader(shaders.OBJ_VS, shaders.OBJ_FS, 'obj')
mesh = plane.build_plane()


def ortho(l, r, b, t, n, f):
    mm = np.zeros((4, 4), dtype=np.float32)
    mm[0, 0] = 2 / (r - l); mm[1, 1] = 2 / (t - b); mm[2, 2] = -2 / (f - n)
    mm[0, 3] = -(r + l) / (r - l); mm[1, 3] = -(t + b) / (t - b)
    mm[2, 3] = -(f + n) / (f - n); mm[3, 3] = 1
    return mm


def render(name, eye_off, span=7.5, tgt=(0.0, 0.3, 2.4)):
    GL.glViewport(0, 0, W, H)
    GL.glClearColor(0.12, 0.16, 0.23, 1)
    GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
    eye = np.array(eye_off, dtype=float)
    t = np.array(tgt, dtype=float)
    proj = ortho(-span, span, -span * H / float(W), span * H / float(W), 0.1, 500.0)
    view = gfx.look_at(eye, t, np.array([0.0, 1.0, 0.0]))
    VP = proj @ view
    sh.use()
    sh.set_mat4('uVP', VP)
    sh.set_vec3('uSunDir', (0.45, 0.70, 0.55))
    sh.set_vec3('uCamPos', eye)
    sh.set_vec3('uFogColor', (0.7, 0.78, 0.88))
    sh.set_float('uFogDensity', 0.0)
    mm = np.eye(4, dtype=np.float32)
    flip = np.eye(4, dtype=np.float32)
    flip[0, 0] = -1.0
    mm = mm @ flip
    sh.set_mat4('uModel', mm)
    sh.set_mat3('uNormalMat', mm[:3, :3])
    mesh.draw()
    glfw.swap_buffers(win)
    glfw.poll_events()
    GL.glReadBuffer(GL.GL_FRONT)
    d = GL.glReadPixels(0, 0, W, H, GL.GL_RGB, GL.GL_UNSIGNED_BYTE)
    a = np.frombuffer(d, dtype=np.uint8).reshape(H, W, 3)[::-1]
    Image.fromarray(a).save(os.path.join(OUT, 'Y_' + name + '.png'))
    bg = np.array([31, 41, 59])
    nb = int((np.abs(a.astype(int) - bg).sum(axis=2) > 28).sum())
    print('  Y_%-16s 飞机像素 %6d (%.1f%%)' % (name, nb, nb * 100.0 / (W * H)))


render('侧视', (-120, 3, 2.4))
render('顶视', (0, 120, 2.4))
render('后视', (0, 4, 120))
render('前视', (0, 4, -120))
render('斜视', (-80, 55, -55))
glfw.terminate()
