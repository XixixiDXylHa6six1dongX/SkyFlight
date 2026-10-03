# -*- coding: utf-8 -*-
"""
地景点缀：森林（实例化树）+ 湖泊水面 + 路边建筑

设计要点：
- 树的分布用"坐标哈希"决定，同一位置永远长同一棵树，不会闪烁
- 只在飞机附近一片范围内生成，飞出范围就重新生成（跟随飞机）
- 树用一次实例化绘制调用画完，几百棵也不掉帧
"""
import math

import numpy as np

from . import gfx, terrain


# ---------------------------------------------------------------- 随机（可复现）
def _hash01(ix, iz, salt=0.0):
    """由格子坐标得到 0~1 的稳定随机数（同一格子永远同值）"""
    v = math.sin(ix * 127.1 + iz * 311.7 + salt * 74.7) * 43758.5453
    return v - math.floor(v)


def _hash01_arr(ix, iz, salt=0.0):
    """同上，但支持 numpy 数组（向量化，快很多）"""
    ix = np.asarray(ix, dtype=np.float64)
    iz = np.asarray(iz, dtype=np.float64)
    v = np.sin(ix * 127.1 + iz * 311.7 + salt * 74.7) * 43758.5453
    return v - np.floor(v)


class TreeMesh:
    """一棵树：树干（方柱）+ 树冠（两级锥形）

    顶点数很少，靠实例化画很多棵。
    """

    def __init__(self):
        v = []
        trunk_col = (0.28, 0.20, 0.12)
        leaf_dark = (0.12, 0.30, 0.11)
        leaf_mid = (0.17, 0.39, 0.14)
        leaf_lite = (0.24, 0.48, 0.18)

        # 树干：高 3.4
        v += gfx.box(0.0, 1.7, 0.0, 0.42, 3.4, 0.42, trunk_col)
        # 三级树冠：底大顶小
        v += self._cone(0.0, 2.6, 0.0, 2.30, 3.4, 8, leaf_dark)
        v += self._cone(0.0, 4.8, 0.0, 1.60, 2.8, 8, leaf_mid)
        v += self._cone(0.0, 6.6, 0.0, 0.90, 2.0, 8, leaf_lite)
        self.mesh = gfx.Mesh(v)

    @staticmethod
    def _cone(cx, cy, cz, radius, height, segments, color):
        """圆锥（底面朝下，尖端朝上）"""
        r, g, b = color
        verts = []
        apex = (cx, cy + height, cz)
        for i in range(segments):
            a0 = 2 * math.pi * i / segments
            a1 = 2 * math.pi * (i + 1) / segments
            p0 = (cx + radius * math.cos(a0), cy, cz + radius * math.sin(a0))
            p1 = (cx + radius * math.cos(a1), cy, cz + radius * math.sin(a1))
            # 侧面
            for p in (p0, p1, apex):
                verts.extend([p[0], p[1], p[2], 0.0, 0.3, 0.0, r, g, b])
            # 底面（朝下，看不到但保持封闭）
            for p in (p1, p0, (cx, cy, cz)):
                verts.extend([p[0], p[1], p[2], 0.0, -1.0, 0.0, r * 0.7, g * 0.7, b * 0.7])
        return verts


class Scenery:
    """跟随飞机的成片地景"""

    def __init__(self, radius=2600.0, cell=46.0):
        self.radius = float(radius)      # 生成范围半径
        self.cell = float(cell)          # 树的间距（越小越密）
        self.center = None
        self.tree = None                 # 懒加载（需要 GL 上下文）
        self.tree_count = 0
        self.houses = None
        self.houses_count = 0

    def _ensure_meshes(self):
        if self.tree is None:
            self.tree = TreeMesh()
        if self.houses is None:
            self.houses = gfx.Mesh(self._house_geometry())

    # ---------------------------------------------------------- 生成
    def _place_trees(self, cx, cz):
        """在半径内按格子撒树，返回实例数据（每行 8 个 float）

        关键：先把所有候选点算出来，再用一次性的向量化地形查询筛掉
        水里/太陡/太高的点。否则逐点查询地形会慢几十倍。
        """
        r = self.radius
        c = self.cell
        n = int(r / c)
        k = np.arange(-n, n + 1, dtype=np.int64)
        # 整体格子坐标（跟着世界坐标走，保证同一位置永远同一棵树）
        gi = np.floor(cx / c).astype(np.int64) + k
        gj = np.floor(cz / c).astype(np.int64) + k
        GI, GJ = np.meshgrid(gi, gj, indexing='ij')
        GI = GI.ravel()
        GJ = GJ.ravel()

        h1 = _hash01_arr(GI, GJ, 1.0)
        keep = h1 > 0.22
        GI, GJ = GI[keep], GJ[keep]
        if GI.size == 0:
            return np.zeros((0, 8), np.float32)

        h2 = _hash01_arr(GI, GJ, 2.0)
        h3 = _hash01_arr(GI, GJ, 3.0)
        h4 = _hash01_arr(GI, GJ, 4.0)
        x = (GI + h2) * c
        z = (GJ + h3) * c

        dx = x - cx
        dz = z - cz
        inside = dx * dx + dz * dz <= r * r
        # 跑道净空
        near_rw = (np.abs(x) < 110.0) & (np.abs(z) < terrain.RUNWAY_LEN * 0.60)
        # 机场核心区
        d_ap = np.sqrt(x * x + z * z)
        near_ap = d_ap < terrain.FLAT_RADIUS * 0.72
        keep = inside & ~near_rw & ~near_ap
        x, z, h4 = x[keep], z[keep], h4[keep]
        GI, GJ = GI[keep], GJ[keep]
        if x.size == 0:
            return np.zeros((0, 8), np.float32)

        # 向量化查地形（一次算完所有点）
        h = np.asarray(terrain.height_at(x, z), dtype=np.float64)
        # 用与地形网格尺度相当的步长估坡度
        step = max(18.0, c)
        hx = np.asarray(terrain.height_at(x + step, z), dtype=np.float64)
        hz = np.asarray(terrain.height_at(x, z + step), dtype=np.float64)
        slope = np.sqrt((hx - h) ** 2 + (hz - h) ** 2) / step

        good = (h > terrain.WATER_LEVEL + 3.0) & (h < 800.0) & (slope < 1.25)
        x, z, h, h4 = x[good], z[good], h[good], h4[good]
        GI, GJ = GI[good], GJ[good]
        if x.size == 0:
            return np.zeros((0, 8), np.float32)

        scale = 0.75 + h4 * 0.85
        yaw = _hash01_arr(GI, GJ, 5.0) * 6.283
        t = _hash01_arr(GI, GJ, 6.0)
        out = np.stack([
            x, h - 0.3, z, scale, yaw,
            0.80 + t * 0.35, 0.85 + t * 0.30, 0.75 + t * 0.35,
        ], axis=1)
        return out.astype(np.float32)

    def _place_houses(self, cx, cz):
        """跑道附近放几座小房子"""
        data = []
        # 沿着跑道两侧成排
        for k in range(-5, 6):
            for side in (-1, 1):
                for salt in range(2):
                    gi = k * 3 + side * 7 + salt * 2
                    gj = side * 5 + salt
                    x = gi * 52.0 + 40.0
                    z = gj * 60.0 + 120.0
                    if abs(x) < 90:
                        continue
                    h = float(terrain.height_at(x, z))
                    if h < terrain.WATER_LEVEL + 2:
                        continue
                    if float(terrain.slope_at(x, z)) > 0.7:
                        continue
                    s = 0.8 + _hash01(gi, gj, 7.0) * 0.6
                    yaw = _hash01(gi, gj, 8.0) * 6.283
                    t = _hash01(gi, gj, 9.0)
                    col = (0.55 + t * 0.3, 0.50 + t * 0.2, 0.45 + t * 0.15)
                    data.append((x, h, z, s, yaw, col[0], col[1], col[2]))
        return np.asarray(data, dtype=np.float32) if data else np.zeros((0, 8), np.float32)

    def update(self, center):
        """center = (x, z)。飞机走远了就重新生成"""
        if self.center is not None:
            dx = center[0] - self.center[0]
            dz = center[1] - self.center[1]
            if dx * dx + dz * dz < (self.radius * 0.45) ** 2:
                return False
        self.center = (float(center[0]), float(center[1]))
        cx, cz = self.center

        trees = self._place_trees(cx, cz)
        self.tree_count = trees.shape[0]

        houses = self._place_houses(cx, cz)
        self.houses_count = houses.shape[0]

        # 网格要 GL 上下文，所以延迟到真正要画的时候再建
        self._pending_trees = trees
        self._pending_houses = houses
        return True

    def upload(self):
        """把生成好但还没上传的实例数据传到显卡（需要 GL 上下文）"""
        if self.tree_count and getattr(self, '_pending_trees', None) is not None:
            self._ensure_meshes()
            self.tree.mesh.set_instances(self._pending_trees)
            self._pending_trees = None
        if self.houses_count and getattr(self, '_pending_houses', None) is not None:
            self._ensure_meshes()
            self.houses.set_instances(self._pending_houses)
            self._pending_houses = None

    @staticmethod
    def _house_geometry():
        """小房子：墙体 + 屋顶"""
        v = []
        v += gfx.box(0.0, 2.2, 0.0, 9.0, 4.4, 11.0, (0.86, 0.84, 0.80))
        # 屋顶用两级递减的盒子做出坡顶感
        v += gfx.box(0.0, 4.8, 0.0, 10.0, 0.8, 12.0, (0.55, 0.28, 0.22))
        v += gfx.box(0.0, 5.5, 0.0, 7.4, 0.8, 9.4, (0.60, 0.31, 0.24))
        v += gfx.box(0.0, 6.1, 0.0, 4.2, 0.7, 6.0, (0.66, 0.34, 0.26))
        # 门窗
        v += gfx.box(0.0, 1.4, -5.6, 1.8, 2.8, 0.3, (0.35, 0.28, 0.22))
        v += gfx.box(3.2, 2.6, -5.6, 2.0, 2.0, 0.3, (0.45, 0.62, 0.72))
        v += gfx.box(-3.2, 2.6, -5.6, 2.0, 2.0, 0.3, (0.45, 0.62, 0.72))
        return v

    # ---------------------------------------------------------- 绘制
    def draw_trees(self, shader):
        if self.tree_count and self.tree is not None:
            self.tree.mesh.draw_instanced()

    def draw_houses(self, shader):
        if self.houses_count and self.houses is not None:
            self.houses.draw_instanced()


# ================================================================ 水面
class Water:
    """湖/海的水面：一整块大平面固定在水位高度

    做法：一个以飞机为中心的大圆盘画在水位高度上。
    地形高于水面的地方会把水挡住（有深度测试），所以只有真正低洼处
    才露出水来 —— 这样天然无缝，也不会出现"一块一块"的方格缝隙。
    """

    def __init__(self, radius=16000.0, segments=64):
        self.radius = float(radius)
        self.segments = int(segments)
        self.center = None
        self.mesh = None
        self.count = 0

    def update(self, center):
        # 整片水面跟着飞机走，几乎不需要重建
        if self.center is None:
            self.center = (float(center[0]), float(center[1]))
            self._build()
            return True
        return False

    def _build(self):
        """用环形四边形条带铺水面。

        不要用"从圆心发散"的扇形三角：那样相邻三角形在天上斜看时
        会出现细缝（两三角形共边但采样不一致）。用四边形条带更稳。
        """
        seg = self.segments
        r = self.radius
        y = terrain.WATER_LEVEL
        col = (0.24, 0.47, 0.63)      # 偏亮的蓝，和绿地拉开差别
        v = []
        cx, cz = self.center
        rings = [0.0, 0.10, 0.25, 0.45, 0.7, 1.0]
        radii = [r * t for t in rings]
        for ri in range(len(radii) - 1):
            r0, r1 = radii[ri], radii[ri + 1]
            for i in range(seg):
                a0 = 2 * math.pi * i / seg
                a1 = 2 * math.pi * (i + 1) / seg
                c0, s0 = math.cos(a0), math.sin(a0)
                c1, s1 = math.cos(a1), math.sin(a1)
                p00 = (cx + r0 * c0, y, cz + r0 * s0)
                p10 = (cx + r1 * c0, y, cz + r1 * s0)
                p11 = (cx + r1 * c1, y, cz + r1 * s1)
                p01 = (cx + r0 * c1, y, cz + r0 * s1)
                for p in (p00, p10, p11, p00, p11, p01):
                    v.extend([p[0], p[1], p[2], 0.0, 1.0, 0.0,
                              col[0], col[1], col[2]])
        self.mesh = gfx.Mesh(np.asarray(v, dtype=np.float32).reshape(-1))
        self.count = len(v) // 9

    def upload(self):
        pass

    def draw(self, shader):
        if self.mesh is None or self.count == 0:
            return
        shader.set_mat4('uModel', np.eye(4, dtype=np.float32))
        shader.set_mat3('uNormalMat', np.eye(3, dtype=np.float32))
        self.mesh.draw()
