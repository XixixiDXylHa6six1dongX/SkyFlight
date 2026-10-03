# -*- coding: utf-8 -*-
"""
终极对照：同一组顶点
  模式1：直接当 NDC 画（不过矩阵）
  模式2：经过 uVP 变换
两者应该一样大。如果模式2更大 -> 矩阵变换有问题
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glfw
import numpy as np
from OpenGL import GL

from skyflight import gfx

W, H = 1000, 600

glfw.init()
for a, b in ((glfw.CONTEXT_VERSION_MAJOR, 3), (glfw.CONTEXT_VERSION_MINOR, 3),
             (glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE),
             (glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)):
    glfw.window_hint(a, b)
win = glfw.create_window(W, H, 'x', None, None)
glfw.make_context_current(win)
glfw.show_window(win)
glfw.poll_events()
GL.glDisable(GL.GL_DEPTH_TEST)
GL.glDisable(GL.GL_CULL_FACE)

VS = """#version 330 core
layout(location=0) in vec3 aPos;
uniform mat4 uVP;
uniform int uPassthrough;
void main(){
    if (uPassthrough == 1) { gl_Position = vec4(aPos, 1.0); }
    else { gl_Position = uVP * vec4(aPos, 1.0); }
}
"""
FS = """#version 330 core
out vec4 C;
void main(){ C = vec4(1.0, 0.25, 0.2, 1.0); }
"""
sh = gfx.Shader(VS, FS, 't')

# 三角形：NDC x ∈ [-0.2, 0.2]（宽 0.4 -> 画面 20%）
tri = np.zeros((3, 9), dtype=np.float32)
tri[0, 0:3] = [-0.2, -0.1, 0.0]
tri[1, 0:3] = [0.2, -0.1, 0.0]
tri[2, 0:3] = [0.0, 0.1, 0.0]
tri[:, 3:6] = [0.0, 0.0, 1.0]
tri[:, 6:9] = [1.0, 0.25, 0.2]
mesh = gfx.Mesh(tri.reshape(-1))

# 正交投影：世界 -10~10 -> NDC -1~1，所以 proj[0][0] = 0.1
proj = np.zeros((4, 4), dtype=np.float32)
proj[0, 0] = 1.0 / 10.0
proj[1, 1] = 1.0 / (10.0 * H / float(W))
proj[2, 2] = -2.0 / 499.0
proj[2, 3] = -501.0 / 499.0
proj[3, 3] = 1.0
view = gfx.look_at(np.array([0.0, 0.0, 60.0]), np.array([0.0, 0.0, 0.0]),
                   np.array([0.0, 1.0, 0.0]))
VP = proj @ view
print('proj[0][0] = %.4f' % proj[0, 0])
print('VP[0][0]   = %.4f' % VP[0, 0])
print('view 是否只有平移: %s' % np.allclose(view[:3, :3], np.eye(3)))
print()


def run(tag, passthrough):
    GL.glViewport(0, 0, W, H)
    GL.glClearColor(0.1, 0.13, 0.19, 1)
    GL.glClear(GL.GL_COLOR_BUFFER_BIT)
    sh.use()
    sh.set_mat4('uVP', VP)
    sh.set_int('uPassthrough', passthrough)
    mesh.draw()
    glfw.swap_buffers(win)
    glfw.poll_events()
    GL.glReadBuffer(GL.GL_FRONT)
    d = GL.glReadPixels(0, 0, W, H, GL.GL_RGB, GL.GL_UNSIGNED_BYTE)
    a = np.frombuffer(d, dtype=np.uint8).reshape(H, W, 3)[::-1]
    bg = np.array([26, 33, 48])
    m = (np.abs(a.astype(int) - bg).sum(axis=2) > 30)
    ys, xs = np.where(m)
    if len(xs):
        print('  %-24s 宽 %4d px   x %d~%d' % (tag, xs.max() - xs.min(), xs.min(), xs.max()))
        return xs.max() - xs.min()
    print('  %-24s 没渲染' % tag)
    return 0


print('三角形 NDC 宽 0.4  ->  预期屏幕宽 %.0f px' % (0.4 / 2 * W))
w1 = run('模式1_直接NDC', 1)
w2 = run('模式2_经过uVP', 0)
print()
print('模式2 / 模式1 = %.3f' % (w2 / max(w1, 1)))
if w1 and abs(w2 / w1 - 1.0) > 0.2:
    print('  ❌ 经过 uVP 后尺寸变了 -> 矩阵或变换有问题')
else:
    print('  ✅ 两者一致 -> 变换正常')
glfw.terminate()
