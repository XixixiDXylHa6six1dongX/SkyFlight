# -*- coding: utf-8 -*-
"""程序化地形：噪声高度场 + 双层网格（近处细、远处大范围）"""
import math

import numpy as np
from OpenGL import GL

from . import gfx


# ---------------------------------------------------------------- 噪声
_PERM = None


def _perm():
    global _PERM
    if _PERM is None:
        rng = np.random.RandomState(20261002)
        _PERM = rng.permutation(256).astype(np.int32)
    return _PERM


def _value_noise(ix, iy):
    """基于哈希的平滑值噪声（支持任意整数坐标）"""
    p = _perm()
    h = (p[(ix & 255)] + (iy & 255)) & 255
    return p[h] / 255.0


def _smooth(t):
    return t * t * (3.0 - 2.0 * t)


def fbm(x, y, octaves=5, lacunarity=2.0, gain=0.5):
    """分形噪声（向量化）"""
    total = np.zeros_like(x, dtype=np.float64)
    amp = 1.0
    freq = 1.0
    norm = 0.0
    for _ in range(octaves):
        xf = x * freq
        yf = y * freq
        ix = np.floor(xf).astype(np.int64)
        iy = np.floor(yf).astype(np.int64)
        fx = _smooth(xf - ix)
        fy = _smooth(yf - iy)
        n00 = _value_noise(ix, iy)
        n10 = _value_noise(ix + 1, iy)
        n01 = _value_noise(ix, iy + 1)
        n11 = _value_noise(ix + 1, iy + 1)
        nx0 = n00 + (n10 - n00) * fx
        nx1 = n01 + (n11 - n01) * fx
        total += amp * (nx0 + (nx1 - nx0) * fy)
        norm += amp
        amp *= gain
        freq *= lacunarity
    return total / norm


# ---------------------------------------------------------------- 高度场
TERRAIN_SCALE = 0.0060      # 山脉波长约 200~400 m
MOUNTAIN_HEIGHT = 1150.0
RUNWAY_LEN = 1400.0         # 跑道长（沿南北）
RUNWAY_WID = 90.0
FLAT_RADIUS = 1250.0        # 机场压平半径（要盖住整条跑道，否则跑道会插进山里）
WATER_LEVEL = 2.0
PLAIN_RADIUS = 2800.0       # 平原过渡带半径：这一圈压低成缓坡，避免"出机场就是高山"
PLAIN_FACTOR = 0.30         # 平原带高度保留比例


def height_at(x, z):
    """世界坐标 -> 地形高度（标量或数组）"""
    xa = np.asarray(x, dtype=np.float64)
    za = np.asarray(z, dtype=np.float64)

    n = fbm(xa * TERRAIN_SCALE, za * TERRAIN_SCALE, octaves=6)
    # 山脊感：把噪声抬成脊状
    ridge = 1.0 - np.abs(n * 2.0 - 1.0)
    n2 = fbm(xa * TERRAIN_SCALE * 3.1 + 17.3, za * TERRAIN_SCALE * 3.1 - 5.7, octaves=4)
    h = (n * 0.55 + ridge * 0.3 + n2 * 0.15)

    # 大尺度起伏
    big = fbm(xa * TERRAIN_SCALE * 0.22 + 100.0, za * TERRAIN_SCALE * 0.22 - 40.0, octaves=3)
    h = h * (0.45 + big * 1.3)

    h = (h - 0.30) * MOUNTAIN_HEIGHT
    h = np.maximum(h, -80.0)

    d = np.sqrt(xa * xa + za * za)

    # 机场附近压平
    inner = FLAT_RADIUS * 0.80
    outer = FLAT_RADIUS * 1.25
    if np.ndim(d) == 0:
        t = 0.0 if d < inner else min(1.0, (d - inner) / (outer - inner))
    else:
        t = np.clip((d - inner) / (outer - inner), 0.0, 1.0)
    t = t * t * (3.0 - 2.0 * t)
    h = h * t

    # 平原过渡带：机场外圈这一片压成缓坡，远处才起真山
    if np.ndim(d) == 0:
        tp = 0.0 if d < outer else min(1.0, (d - outer) / (PLAIN_RADIUS - outer))
        tp = tp * tp * (3.0 - 2.0 * tp)
    else:
        tp = np.clip((d - outer) / (PLAIN_RADIUS - outer), 0.0, 1.0)
        tp = tp * tp * (3.0 - 2.0 * tp)
    h = h * (PLAIN_FACTOR + (1.0 - PLAIN_FACTOR) * tp)

    # 湖盆：直接把坑内地形压到湖底，保证水面能露出来
    h = _apply_lakes(xa, za, h)

    return h


# 湖泊：(中心 x, 中心 z, 半径, 湖底高度)
# 湖底要明显低于水位（拉开距离避免水面和湖底打架），飞起来容易看到。
_LAKES = [
    (2100.0, 1500.0, 900.0, -78.0),
    (-2200.0, 2000.0, 1000.0, -80.0),
    (2800.0, -1700.0, 820.0, -76.0),
    (-1400.0, -2600.0, 950.0, -80.0),
    (3600.0, 3000.0, 1250.0, -80.0),
    (-3400.0, -1000.0, 880.0, -78.0),
]


def _apply_lakes(xa, za, h):
    """把湖的位置压成湖底：坑心用湖底高度，往外平滑过渡回原地形"""
    xa = np.asarray(xa, dtype=np.float64)
    za = np.asarray(za, dtype=np.float64)
    h = np.array(h, dtype=np.float64, copy=True)
    for lx, lz, lr, bed in _LAKES:
        d = np.sqrt((xa - lx) ** 2 + (za - lz) ** 2)
        if np.ndim(d) == 0:
            if d <= lr * 0.62:
                t = 1.0
            elif d >= lr:
                t = 0.0
            else:
                t = _smooth((lr - d) / (lr * 0.38))
        else:
            t = np.clip((lr - d) / (lr * 0.38), 0.0, 1.0)
            t = _smooth(t)
        h = h * (1.0 - t) + bed * t
    return h


def slope_at(x, z, step=12.0):
    """用有限差分估算坡度（0=平地，越大越陡）"""
    hx = height_at(x + step, z) - height_at(x - step, z)
    hz = height_at(x, z + step) - height_at(x, z - step)
    return np.sqrt(hx * hx + hz * hz) / (2.0 * step)


def _color_for(h, slope, water=0.0):
    """按高度和坡度上色：草地 -> 干草 -> 岩石 -> 雪"""
    grass = np.array([0.24, 0.43, 0.17])
    grass2 = np.array([0.28, 0.46, 0.19])
    dry = np.array([0.44, 0.45, 0.24])
    rock = np.array([0.40, 0.36, 0.32])
    rock2 = np.array([0.50, 0.47, 0.44])
    snow = np.array([0.95, 0.96, 0.98])
    sand = np.array([0.78, 0.72, 0.52])
    seabed = np.array([0.13, 0.26, 0.24])

    hh = np.asarray(h, dtype=np.float64)

    # 0~550 m 草地
    t1 = np.clip(hh / 550.0, 0.0, 1.0)[..., None]
    col = grass * (1 - t1) + grass2 * t1
    # 550~950 m 过渡到干草
    t2 = np.clip((hh - 550.0) / 400.0, 0.0, 1.0)[..., None]
    col = col * (1 - t2) + dry * t2
    # 950~1250 m 岩石
    t3 = np.clip((hh - 950.0) / 300.0, 0.0, 1.0)[..., None]
    col = col * (1 - t3) + rock * t3
    # 1250~1700 m 高山裸岩
    t4 = np.clip((hh - 1250.0) / 450.0, 0.0, 1.0)[..., None]
    col = col * (1 - t4) + rock2 * t4
    # 1700 m 以上积雪
    t5 = np.clip((hh - 1700.0) / 350.0, 0.0, 1.0)[..., None]
    col = col * (1 - t5) + snow * t5

    # 陡坡露岩
    s = np.clip((slope - 0.55) / 0.45, 0.0, 1.0)[..., None]
    col = col * (1 - s) + rock * s

    # 水下是深色水底
    under = np.clip((WATER_LEVEL - hh) / 30.0, 0.0, 1.0)[..., None]
    col = col * (1 - under) + seabed * under

    # 沙滩只出现在水位以上 3 米内的窄带（用高度直接算，别用宽泛的 water）
    band = np.clip((3.0 - (hh - WATER_LEVEL)) / 3.0, 0.0, 1.0)[..., None]
    band = band * (1.0 - under)
    col = col * (1 - band * 0.9) + sand * (band * 0.9)
    return np.clip(col, 0.0, 1.0)


def _build_patch_arrays(center, size, cells):
    """生成一块地形的顶点和索引（顶点用局部坐标，中心在原点）"""
    n = cells + 1
    half = size / 2.0
    xs = np.linspace(-half, half, n, dtype=np.float64)
    zs = np.linspace(-half, half, n, dtype=np.float64)
    gx, gz = np.meshgrid(xs, zs, indexing='ij')
    wx = gx + center[0]
    wz = gz + center[1]

    h = height_at(wx, wz)

    step = size / cells
    hx = height_at(wx + step, wz)
    hz = height_at(wx, wz + step)
    nx = -(hx - h) / step
    nz = -(hz - h) / step
    ny = np.ones_like(h)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / ln, ny / ln, nz / ln

    slope = 1.0 - ny
    water = np.clip((WATER_LEVEL + 6.0 - h) / 12.0, 0.0, 1.0)
    col = _color_for(h, slope, water)

    verts = np.stack([gx, h, gz, nx, ny, nz, col[..., 0], col[..., 1],
                      col[..., 2]], axis=-1).reshape(-1, 9).astype(np.float32)

    idx = []
    for i in range(cells):
        for j in range(cells):
            a = i * n + j
            b = a + 1
            d = a + n
            e = d + 1
            idx.extend([a, d, b, b, d, e])
    idx = np.asarray(idx, dtype=np.uint32)
    return verts, idx


class TerrainPatch:
    """一块地形网格。center 是它当前覆盖的世界中心（x, z）"""

    def __init__(self, size, cells, name='terrain'):
        self.size = float(size)
        self.cells = int(cells)
        self.name = name
        self.center = None
        self.vao = None
        self.vbo = None
        self.ebo = None
        self.count = 0
        self.rebuilds = 0

    def update(self, center):
        """center = (x, z)。走出半个块才重建，避免频繁重建"""
        threshold = self.size * 0.5
        if self.center is not None:
            dx = center[0] - self.center[0]
            dz = center[1] - self.center[1]
            if dx * dx + dz * dz < threshold * threshold:
                return False
        self.center = (float(center[0]), float(center[1]))
        verts, idx = _build_patch_arrays(self.center, self.size, self.cells)
        self.count = idx.size
        if self.vao is None:
            self.vao = GL.glGenVertexArrays(1)
            self.vbo = GL.glGenBuffers(1)
            self.ebo = GL.glGenBuffers(1)
        GL.glBindVertexArray(self.vao)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, verts.nbytes, verts, GL.GL_DYNAMIC_DRAW)
        stride = 9 * 4
        import ctypes as _ct
        GL.glEnableVertexAttribArray(0)
        GL.glVertexAttribPointer(0, 3, GL.GL_FLOAT, GL.GL_FALSE, stride, _ct.c_void_p(0))
        GL.glEnableVertexAttribArray(1)
        GL.glVertexAttribPointer(1, 3, GL.GL_FLOAT, GL.GL_FALSE, stride, _ct.c_void_p(12))
        GL.glEnableVertexAttribArray(2)
        GL.glVertexAttribPointer(2, 3, GL.GL_FLOAT, GL.GL_FALSE, stride, _ct.c_void_p(24))
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        GL.glBufferData(GL.GL_ELEMENT_ARRAY_BUFFER, idx.nbytes, idx, GL.GL_DYNAMIC_DRAW)
        GL.glBindVertexArray(0)
        self.rebuilds += 1
        return True

    def draw(self, shader):
        if self.center is None or self.count == 0:
            return
        m = np.eye(4, dtype=np.float32)
        m[0, 3] = self.center[0]
        m[2, 3] = self.center[1]
        shader.set_mat4('uModel', m)
        shader.set_mat3('uNormalMat', np.eye(3, dtype=np.float32))
        GL.glBindVertexArray(self.vao)
        GL.glDrawElements(GL.GL_TRIANGLES, self.count, GL.GL_UNSIGNED_INT, None)


class Terrain:
    """双层地形：近处细节层 + 远处大范围层"""

    def __init__(self, near_size=2400.0, near_cells=60,
                 far_size=17000.0, far_cells=34):
        self.near = TerrainPatch(near_size, near_cells, 'terrain-near')
        self.far = TerrainPatch(far_size, far_cells, 'terrain-far')

    def update(self, center):
        a = self.near.update(center)
        b = self.far.update(center)
        return a or b

    def draw(self, shader):
        # 先画远处（粗糙），再画近处（细节）盖上去
        self.far.draw(shader)
        self.near.draw(shader)

    @property
    def center(self):
        return self.near.center

    @property
    def count(self):
        return self.near.count + self.far.count
