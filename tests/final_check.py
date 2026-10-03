# -*- coding: utf-8 -*-
"""
最终验证：正交投影 + 已知尺寸方块
用独立文件运行，排除内联脚本转义问题
"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glfw
import numpy as np
from OpenGL import GL
from PIL import Image

from skyflight import gfx

OUT = r'C:\DEEPSEEK工作区\飞行模拟\shots'
W, H = 1000, 600
SPAN = 10.0
CUBE_W, CUBE_H, CUBE_D = 4.0, 2.0, 2.0

glfw.init()
for a, b in ((glfw.CONTEXT_VERSION_MAJOR, 3), (glfw.CONTEXT_VERSION_MINOR, 3),
             (glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE),
             (glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)):
    glfw.window_hint(a, b)
win = glfw.create_window(W, H, 'final', None, None)
glfw.make_context_current(win)
glfw.show_window(win)
glfw.poll_events()
GL.glDisable(GL.GL_DEPTH_TEST)
GL.glDisable(GL.GL_CULL_FACE)

VS = """#version 330 core
layout(location=0) in vec3 aPos;
layout(location=1) in vec3 aNormal;
layout(location=2) in vec3 aColor;
uniform mat4 uVP;
uniform mat4 uModel;
void main() { gl_Position = uVP * uModel * vec4(aPos, 1.0); }
"""
FS = """#version 330 core
out vec4 C;
void main() { C = vec4(0.9, 0.25, 0.22, 1.0); }
"""
sh = gfx.Shader(VS, FS, 'final')

# 正交投影：世界 x∈[-SPAN, SPAN] 映射到屏幕宽
aspect = W / float(H)
proj = np.zeros((4, 4), dtype=np.float32)
proj[0, 0] = 2.0 / (2 * SPAN)
proj[1, 1] = 2.0 / (2 * SPAN * H / float(W))
proj[2, 2] = -2.0 / 499.0
proj[2, 3] = -(501.0) / 499.0
proj[3, 3] = 1.0
view = gfx.look_at(np.array([0.0, 0.0, 60.0]), np.array([0.0, 0.0, 0.0]),
                   np.array([0.0, 1.0, 0.0]))
VP = proj @ view

PX_PER_UNIT = W / (2.0 * SPAN)
print('正交半宽 %.1f  ->  1 世界单位 = %.1f 像素' % (SPAN, PX_PER_UNIT))
print('proj[0][0] = %.4f (应为 %.4f)' % (proj[0, 0], 1.0 / SPAN))
print('proj[1][1] = %.4f (应为 %.4f)' % (proj[1, 1], 1.0 / (SPAN * H / float(W))))
print('方块世界尺寸: %.1f x %.1f x %.1f' % (CUBE_W, CUBE_H, CUBE_D))
print('预期屏幕尺寸: 宽 %.0f px, 高 %.0f px' % (CUBE_W * PX_PER_UNIT, CUBE_H * PX_PER_UNIT))
print()

# 直接构造顶点（不用 gfx.box，排除 box 的问题）
hw, hh, hd = CUBE_W / 2, CUBE_H / 2, CUBE_D / 2
raw = np.array([
    -hw, -hh, -hd, 0, 0, -1, 0.9, 0.25, 0.22,
    hw, -hh, -hd, 0, 0, -1, 0.9, 0.25, 0.22,
    hw, hh, -hd, 0, 0, -1, 0.9, 0.25, 0.22,
    -hw, -hh, -hd, 0, 0, -1, 0.9, 0.25, 0.22,
    hw, hh, -hd, 0, 0, -1, 0.9, 0.25, 0.22,
    -hw, hh, -hd, 0, 0, -1, 0.9, 0.25, 0.22,
], dtype=np.float32)
print('手工构造的正面三角形顶点 x: %.2f ~ %.2f' % (raw.reshape(-1, 9)[:, 0].min(),
                                              raw.reshape(-1, 9)[:, 0].max()))
mesh_manual = gfx.Mesh(raw)

mesh_box = gfx.Mesh(gfx.box(0, 0, 0, CUBE_W, CUBE_H, CUBE_D, (0.9, 0.25, 0.22)))
print('gfx.box 顶点数 %d, 手工顶点数 %d' % (mesh_box.count, mesh_manual.count))
print()


def render(mesh, tag):
    GL.glViewport(0, 0, W, H)
    GL.glClearColor(0.10, 0.13, 0.19, 1)
    GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
    sh.use()
    sh.set_mat4('uVP', VP)
    sh.set_mat4('uModel', np.eye(4, dtype=np.float32))
    mesh.draw()
    glfw.swap_buffers(win)
    glfw.poll_events()
    GL.glReadBuffer(GL.GL_FRONT)
    d = GL.glReadPixels(0, 0, W, H, GL.GL_RGB, GL.GL_UNSIGNED_BYTE)
    a = np.frombuffer(d, dtype=np.uint8).reshape(H, W, 3)[::-1]
    Image.fromarray(a).save(os.path.join(OUT, tag + '.png'))
    bg = np.array([26, 33, 48])
    mask = (np.abs(a.astype(int) - bg).sum(axis=2) > 30)
    ys, xs = np.where(mask)
    if len(xs):
        aw, ah = xs.max() - xs.min(), ys.max() - ys.min()
        print('  %-20s 宽 %4d px (预期 %.0f)  高 %4d px (预期 %.0f)  比值 %.2f' % (
            tag, aw, CUBE_W * PX_PER_UNIT, ah, CUBE_H * PX_PER_UNIT,
            aw / (CUBE_W * PX_PER_UNIT)))
    else:
        print('  %-20s 没渲染' % tag)


render(mesh_manual, 'F1_手工正面')
render(mesh_box, 'F2_gfxbox')

glfw.terminate()
