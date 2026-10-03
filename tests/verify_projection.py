# -*- coding: utf-8 -*-
"""
投影管线验证（修正版）
立方体放在相机正前方 10 m（不是原点！），验证渲染尺寸是否符合数学预期
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glfw
import numpy as np
from OpenGL import GL
from PIL import Image

from skyflight import gfx

OUT = r'C:\DEEPSEEK工作区\飞行模拟\shots'
os.makedirs(OUT, exist_ok=True)

W, H = 1000, 600
FOV = 60.0
CUBE = 1.4
DIST = 10.0

glfw.init()
for a, b in ((glfw.CONTEXT_VERSION_MAJOR, 3), (glfw.CONTEXT_VERSION_MINOR, 3),
             (glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE),
             (glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)):
    glfw.window_hint(a, b)
win = glfw.create_window(W, H, 'proj', None, None)
glfw.make_context_current(win)
glfw.swap_interval(0)
GL.glEnable(GL.GL_DEPTH_TEST)
GL.glDisable(GL.GL_CULL_FACE)

VS = """#version 330 core
layout(location=0) in vec3 aPos;
uniform mat4 uVP; uniform mat4 uModel;
void main() { gl_Position = uVP * uModel * vec4(aPos, 1.0); }"""
FS = """#version 330 core
out vec4 C;
void main() { C = vec4(1.0, 0.25, 0.2, 1.0); }"""
sh = gfx.Shader(VS, FS, 'proj')
mesh = gfx.Mesh(gfx.box(0.0, 0.0, 0.0, CUBE, CUBE, CUBE, (1, 0.25, 0.2)))

GL.glViewport(0, 0, W, H)
GL.glClearColor(0.10, 0.13, 0.19, 1)
GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)

aspect = W / float(H)
proj = gfx.perspective(FOV, aspect, 0.1, 500.0)
view = gfx.look_at(np.array([0.0, 0.0, 0.0]), np.array([0.0, 0.0, -DIST]),
                   np.array([0.0, 1.0, 0.0]))
VP = proj @ view

# 关键：把立方体平移到相机前方 10 m
m = np.eye(4, dtype=np.float32)
m[:3, 3] = np.array([0.0, 0.0, -DIST], dtype=np.float32)

sh.use()
sh.set_mat4('uVP', VP)
sh.set_mat4('uModel', m)
mesh.draw()
err = GL.glGetError()

glfw.swap_buffers(win)
glfw.poll_events()
GL.glReadBuffer(GL.GL_FRONT)
d = GL.glReadPixels(0, 0, W, H, GL.GL_RGB, GL.GL_UNSIGNED_BYTE)
arr = np.frombuffer(d, dtype=np.uint8).reshape(H, W, 3)[::-1]
Image.fromarray(arr).save(os.path.join(OUT, 'PROJ_cube.png'))

bg = np.array([26, 33, 48])
mask = (np.abs(arr.astype(int) - bg).sum(axis=2) > 40)
print('=== 立方体投影验证（放在相机正前方 %.0f m）===' % DIST)
print('  GL 错误: %d' % err)
if mask.sum():
    ys, xs = np.where(mask)
    aw, ah = xs.max() - xs.min(), ys.max() - ys.min()
    print('  实际渲染: 宽 %d px 高 %d px  (中心 x %.0f, y %.0f)' % (
        aw, ah, (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2))
else:
    aw = ah = 0
    print('  ❌ 没渲染出来')

vis_h = 2 * DIST * math.tan(math.radians(FOV) / 2)
vis_w = vis_h * aspect
exp_w = CUBE / vis_w * W
exp_h = CUBE / vis_h * H
print('  数学预期: 宽 %.0f px 高 %.0f px' % (exp_w, exp_h))
print()
if aw:
    print('  实际/预期 = %.2f 倍' % (aw / exp_w))
    print('  ✅ 投影管线正常' if abs(aw / exp_w - 1.0) < 0.3 else '  ❌ 投影管线异常')
glfw.terminate()
