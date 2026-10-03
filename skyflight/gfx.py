# -*- coding: utf-8 -*-
"""
OpenGL 底层封装：着色器编译、网格上传、数学工具
"""
import ctypes
import math

import numpy as np
from OpenGL import GL


# ---------------------------------------------------------------- 数学
def perspective(fovy_deg, aspect, near, far):
    """透视投影。near 必须足够大，否则靠近相机的几何会退化"""
    near = max(float(near), 0.25)
    far = max(float(far), near + 1.0)
    f = 1.0 / math.tan(math.radians(fovy_deg) / 2.0)
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2.0 * far * near) / (near - far)
    m[3, 2] = -1.0
    return m


def look_at(eye, target, up):
    eye = np.asarray(eye, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    up = np.asarray(up, dtype=np.float64)
    f = target - eye
    n = np.linalg.norm(f)
    if n < 1e-9:
        f = np.array([0.0, 0.0, -1.0])
    else:
        f = f / n
    s = np.cross(f, up)
    ns = np.linalg.norm(s)
    if ns < 1e-9:
        s = np.array([1.0, 0.0, 0.0])
    else:
        s = s / ns
    u = np.cross(s, f)
    m = np.eye(4, dtype=np.float32)
    m[0, :3] = s
    m[1, :3] = u
    m[2, :3] = -f
    m[0, 3] = -np.dot(s, eye)
    m[1, 3] = -np.dot(u, eye)
    m[2, 3] = np.dot(f, eye)
    return m


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float64)


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float64)


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float64)


def euler_to_matrix(pitch, yaw, roll):
    """飞机姿态：先偏航(yaw) 再俯仰(pitch) 再滚转(roll)

    世界坐标：X 向东，Y 向上，Z 向南（右手系）
    机头默认朝 -Z（北）

    ============ 符号约定（必须和 flight.py 的速度公式一致）============
    本函数算出的机头方向，必须等于 flight.py 里的速度方向：
        fwd = ( sin yaw · cos pitch , sin pitch , -cos yaw · cos pitch )
    速度公式用的是 sin(yaw) 和 -cos(yaw)，所以这里要绕 **-yaw** 转。
    否则机身会朝向速度的反方向，表现就是"机头往左偏、人却在往右飞"。
    同理 roll 也取负号：绕 +Z 转正角会抬起右翼，取负后正的 roll
    才等于"右翼下沉（向右倾）"，与转弯方向 turn = -sin(roll)·g/V 一致。
    ==================================================================
    """
    return rot_y(-yaw) @ rot_x(pitch) @ rot_z(-roll)


# ---------------------------------------------------------------- 着色器
class Shader:
    def __init__(self, vs_src, fs_src, name='shader'):
        self.name = name
        self.program = GL.glCreateProgram()
        vs = self._compile(GL.GL_VERTEX_SHADER, vs_src, name + '.vert')
        fs = self._compile(GL.GL_FRAGMENT_SHADER, fs_src, name + '.frag')
        GL.glAttachShader(self.program, vs)
        GL.glAttachShader(self.program, fs)
        GL.glLinkProgram(self.program)
        if not GL.glGetProgramiv(self.program, GL.GL_LINK_STATUS):
            log = GL.glGetProgramInfoLog(self.program).decode(errors='replace')
            raise RuntimeError('%s 链接失败:\n%s' % (name, log))
        GL.glDeleteShader(vs)
        GL.glDeleteShader(fs)
        self._uniform_cache = {}

    @staticmethod
    def _compile(kind, src, label):
        sh = GL.glCreateShader(kind)
        GL.glShaderSource(sh, src)
        GL.glCompileShader(sh)
        if not GL.glGetShaderiv(sh, GL.GL_COMPILE_STATUS):
            log = GL.glGetShaderInfoLog(sh).decode(errors='replace')
            raise RuntimeError('%s 编译失败:\n%s' % (label, log))
        return sh

    def use(self):
        GL.glUseProgram(self.program)

    def loc(self, name):
        if name not in self._uniform_cache:
            self._uniform_cache[name] = GL.glGetUniformLocation(self.program, name)
        return self._uniform_cache[name]

    def set_mat4(self, name, m):
        # numpy 是行主序，OpenGL 默认按列主序读，所以必须转置
        GL.glUniformMatrix4fv(self.loc(name), 1, GL.GL_TRUE,
                              np.ascontiguousarray(m, dtype=np.float32))

    def read_mat4(self, name):
        """读回显卡上实际的矩阵（调试用）。

        注意：显卡按列主序存放，读回后 reshape 得到的是列主序矩阵，
        为了方便和 numpy 行主序比较，这里转置回行主序。
        """
        buf = (ctypes.c_float * 16)()
        GL.glGetUniformfv(self.program, self.loc(name), buf)
        return np.array(buf, dtype=np.float32).reshape(4, 4).T

    def set_mat3(self, name, m):
        GL.glUniformMatrix3fv(self.loc(name), 1, GL.GL_FALSE,
                              np.ascontiguousarray(m, dtype=np.float32))

    def set_vec3(self, name, v):
        GL.glUniform3f(self.loc(name), float(v[0]), float(v[1]), float(v[2]))

    def set_vec4(self, name, v):
        GL.glUniform4f(self.loc(name), float(v[0]), float(v[1]),
                       float(v[2]), float(v[3]))

    def set_float(self, name, x):
        GL.glUniform1f(self.loc(name), float(x))

    def set_int(self, name, x):
        GL.glUniform1i(self.loc(name), int(x))


# ---------------------------------------------------------------- 网格
class Mesh:
    """带位置/法线/颜色的静态网格"""

    def __init__(self, vertices, indices=None):
        v = np.asarray(vertices, dtype=np.float32).reshape(-1, 9)
        self.count = v.shape[0]
        self.vao = GL.glGenVertexArrays(1)
        GL.glBindVertexArray(self.vao)
        self.vbo = GL.glGenBuffers(1)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, v.nbytes, v, GL.GL_STATIC_DRAW)
        stride = 9 * 4
        GL.glEnableVertexAttribArray(0)
        GL.glVertexAttribPointer(0, 3, GL.GL_FLOAT, GL.GL_FALSE, stride,
                                 ctypes.c_void_p(0))
        GL.glEnableVertexAttribArray(1)
        GL.glVertexAttribPointer(1, 3, GL.GL_FLOAT, GL.GL_FALSE, stride,
                                 ctypes.c_void_p(12))
        GL.glEnableVertexAttribArray(2)
        GL.glVertexAttribPointer(2, 3, GL.GL_FLOAT, GL.GL_FALSE, stride,
                                 ctypes.c_void_p(24))
        self.ebo = None
        if indices is not None:
            idx = np.asarray(indices, dtype=np.uint32).reshape(-1)
            self.count = idx.size
            self.ebo = GL.glGenBuffers(1)
            GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, self.ebo)
            GL.glBufferData(GL.GL_ELEMENT_ARRAY_BUFFER, idx.nbytes, idx,
                            GL.GL_STATIC_DRAW)
        GL.glBindVertexArray(0)

    def draw(self):
        GL.glBindVertexArray(self.vao)
        if self.ebo is not None:
            GL.glDrawElements(GL.GL_TRIANGLES, self.count, GL.GL_UNSIGNED_INT, None)
        else:
            GL.glDrawArrays(GL.GL_TRIANGLES, 0, self.count)

    # ---------------------------------------------------------- 实例化
    def set_instances(self, data):
        """上传实例数据。每行 8 个 float：位置(3) + 缩放(1) + 偏航(1) + 颜色(3)

        用一次绘制调用画出成百上千个副本（森林、礁石、成片建筑都靠它）。
        """
        arr = np.asarray(data, dtype=np.float32).reshape(-1, 8)
        self.instance_count = arr.shape[0]
        if self.instance_count == 0:
            return
        if getattr(self, 'inst_vbo', None) is None:
            self.inst_vbo = GL.glGenBuffers(1)
        GL.glBindVertexArray(self.vao)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.inst_vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, arr.nbytes, arr, GL.GL_STATIC_DRAW)
        stride = 8 * 4
        # location 3 = 位置, 4 = 缩放, 5 = 偏航, 6 = 颜色
        GL.glEnableVertexAttribArray(3)
        GL.glVertexAttribPointer(3, 3, GL.GL_FLOAT, GL.GL_FALSE, stride, ctypes.c_void_p(0))
        GL.glVertexAttribDivisor(3, 1)
        GL.glEnableVertexAttribArray(4)
        GL.glVertexAttribPointer(4, 1, GL.GL_FLOAT, GL.GL_FALSE, stride, ctypes.c_void_p(12))
        GL.glVertexAttribDivisor(4, 1)
        GL.glEnableVertexAttribArray(5)
        GL.glVertexAttribPointer(5, 1, GL.GL_FLOAT, GL.GL_FALSE, stride, ctypes.c_void_p(16))
        GL.glVertexAttribDivisor(5, 1)
        GL.glEnableVertexAttribArray(6)
        GL.glVertexAttribPointer(6, 3, GL.GL_FLOAT, GL.GL_FALSE, stride, ctypes.c_void_p(20))
        GL.glVertexAttribDivisor(6, 1)
        GL.glBindVertexArray(0)

    def draw_instanced(self):
        n = getattr(self, 'instance_count', 0)
        if n == 0:
            return
        GL.glBindVertexArray(self.vao)
        if self.ebo is not None:
            GL.glDrawElementsInstanced(GL.GL_TRIANGLES, self.count,
                                       GL.GL_UNSIGNED_INT, None, n)
        else:
            GL.glDrawArraysInstanced(GL.GL_TRIANGLES, 0, self.count, n)


# ---------------------------------------------------------------- 几何构造
def box(cx, cy, cz, sx, sy, sz, color):
    """轴对齐长方体"""
    hx, hy, hz = sx / 2.0, sy / 2.0, sz / 2.0
    x0, x1 = cx - hx, cx + hx
    y0, y1 = cy - hy, cy + hy
    z0, z1 = cz - hz, cz + hz
    r, g, b = color
    verts = []
    faces = [
        ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (0, 0, 1)),
        ((x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (0, 0, -1)),
        ((x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (1, 0, 0)),
        ((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0), (-1, 0, 0)),
        ((x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0), (0, 1, 0)),
        ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (0, -1, 0)),
    ]
    for p0, p1, p2, p3, n in faces:
        for p in (p0, p1, p2, p0, p2, p3):
            verts.extend([p[0], p[1], p[2], n[0], n[1], n[2], r, g, b])
    return verts


def quad(p0, p1, p2, p3, color, normal=None):
    """四边形，双面"""
    if normal is None:
        a = np.array(p1, dtype=np.float64) - np.array(p0, dtype=np.float64)
        b = np.array(p3, dtype=np.float64) - np.array(p0, dtype=np.float64)
        n = np.cross(a, b)
        ln = np.linalg.norm(n)
        n = n / ln if ln > 1e-9 else np.array([0.0, 1.0, 0.0])
    else:
        n = np.asarray(normal, dtype=np.float64)
    r, g, b = color
    verts = []
    for p in (p0, p1, p2, p0, p2, p3):
        verts.extend([p[0], p[1], p[2], n[0], n[1], n[2], r, g, b])
    return verts


def disc(cx, cy, cz, radius, segments, color, axis='y'):
    """圆盘（用于机头、螺旋桨盘）"""
    r, g, b = color
    verts = []
    for i in range(segments):
        a0 = 2 * math.pi * i / segments
        a1 = 2 * math.pi * (i + 1) / segments
        if axis == 'z':
            p0 = (cx, cy, cz)
            p1 = (cx + radius * math.cos(a0), cy + radius * math.sin(a0), cz)
            p2 = (cx + radius * math.cos(a1), cy + radius * math.sin(a1), cz)
            n = (0, 0, 1)
        else:
            p0 = (cx, cy, cz)
            p1 = (cx + radius * math.cos(a0), cy, cz + radius * math.sin(a0))
            p2 = (cx + radius * math.cos(a1), cy, cz + radius * math.sin(a1))
            n = (0, 1, 0)
        for p in (p0, p1, p2):
            verts.extend([p[0], p[1], p[2], n[0], n[1], n[2], r, g, b])
    return verts
