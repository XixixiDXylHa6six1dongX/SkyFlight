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

from . import gfx, terrain, props, linear


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
    """针叶树：树干（方柱）+ 三级锥形树冠

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


class BroadleafTree:
    """阔叶树：树干 + 一大两小的球形树冠

    和针叶树混着放，树林看起来才有层次（只有锥形树会很单调）。
    """

    def __init__(self):
        v = []
        trunk = (0.32, 0.24, 0.15)
        c1 = (0.20, 0.42, 0.16)
        c2 = (0.26, 0.50, 0.19)
        c3 = (0.32, 0.56, 0.24)
        # 树干（略矮）
        v += gfx.box(0.0, 1.5, 0.0, 0.5, 3.0, 0.5, trunk)
        # 树冠：用低面数的"球"（八面体感），堆三层错位
        v += self._blob(0.0, 4.2, 0.0, 2.8, c1)
        v += self._blob(1.5, 5.4, 0.6, 2.0, c2)
        v += self._blob(-1.3, 5.2, -0.7, 1.8, c3)
        self.mesh = gfx.Mesh(v)

    @staticmethod
    def _blob(cx, cy, cz, r, color):
        """粗糙的球：正八面体（12 个三角形），够用而且顶点少"""
        r0, g0, b0 = color
        pts = [(cx + r, cy, cz), (cx - r, cy, cz),
               (cx, cy + r, cz), (cx, cy - r, cz),
               (cx, cy, cz + r), (cx, cy, cz - r)]
        tris = [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4),
                (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)]
        out = []
        for a, b_, c in tris:
            for i in (a, b_, c):
                p = pts[i]
                # 法线用指向球心的方向近似
                nx, ny, nz = p[0] - cx, p[1] - cy, p[2] - cz
                ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
                out.extend([p[0], p[1], p[2], nx / ln, ny / ln, nz / ln,
                            r0, g0, b0])
        return out


class Scenery:
    """跟随飞机的成片地景

    内容：
      - 针叶林 + 阔叶林混交（海拔越高针叶越多）
      - 村庄（成组放房子 / 谷仓 / 仓库 / 机库 / 教堂 / 水塔）
      - 山坡上的散石
      - 山脊上的风力发电机（叶轮会转）
    """

    def __init__(self, radius=2600.0, cell=46.0):
        self.radius = float(radius)      # 生成范围半径
        self.cell = float(cell)          # 树的间距（越小越密）
        # 树本身还要放大一点，否则从 100 m 以上看就是一层薄薄的绿点
        self.tree_scale = 1.35
        self.center = None
        self.conifer = None              # 懒加载（需要 GL 上下文）
        self.broadleaf = None
        self.conifer_count = 0
        self.broadleaf_count = 0
        self.props = {}                  # {名字: Props}
        self.ribbons = {}                # 河流 / 公路（每段一个网格）
        self.fields = {}                 # 农田色块（按颜色分组的网格）
        self.river_count = 0
        self.road_count = 0
        self.field_count = 0
        self.turbine = None              # 叶轮（单独画，会转）
        self.turbine_count = 0

    def _ensure_meshes(self):
        if self.conifer is None:
            self.conifer = TreeMesh()
        if self.broadleaf is None:
            self.broadleaf = BroadleafTree()
        if self.turbine is None:
            self.turbine = props.TurbineRotor()
        for name, builder in props.PROP_BUILDERS.items():
            if name not in self.props:
                self.props[name] = props.Props(name, builder)

    # ---------------------------------------------------------- 生成
    def _raw_cells(self, cx, cz, salt=None):
        """把半径内的格子坐标展开，并做稳定的哈希抽样

        返回 (x, z, GI, GJ, h2, h3) —— 位置已经加过抖动，
        但还没做地形筛选（筛选要一次性向量化做，见 _terrain_ok）。
        """
        r = self.radius
        c = self.cell
        n = int(r / c)
        k = np.arange(-n, n + 1, dtype=np.int64)
        gi = np.floor(cx / c).astype(np.int64) + k
        gj = np.floor(cz / c).astype(np.int64) + k
        GI, GJ = np.meshgrid(gi, gj, indexing='ij')
        GI = GI.ravel()
        GJ = GJ.ravel()
        return GI, GJ

    def _terrain_ok(self, x, z, c):
        """向量化地形筛选，返回 (ok, h, slope)"""
        step = max(18.0, c)
        h = np.asarray(terrain.height_at(x, z), dtype=np.float64)
        hx = np.asarray(terrain.height_at(x + step, z), dtype=np.float64)
        hz = np.asarray(terrain.height_at(x, z + step), dtype=np.float64)
        slope = np.sqrt((hx - h) ** 2 + (hz - h) ** 2) / step
        return h, slope

    @staticmethod
    def _runway_clearance(x, z, apron=110.0, airport=520.0):
        """跑道及机场核心区的净空判断（True = 不该放东西）

        airport 是"机场周边不长树"的半径。原来用 FLAT_RADIUS*0.72 = 900 m，
        结果从跑道上起飞时周围一大片光秃秃的草地很空。收窄到 520 m：
        既保住跑道进近面附近的开阔感，又让树林从机场边上就开始。
        """
        near_rw = (np.abs(x) < apron) & (np.abs(z) < terrain.RUNWAY_LEN * 0.60)
        d_ap = np.sqrt(x * x + z * z)
        near_ap = d_ap < airport
        return near_rw | near_ap

    def _place_forest(self, cx, cz):
        """针叶林 + 阔叶林。返回 (针叶实例, 阔叶实例)"""
        c = self.cell
        GI, GJ = self._raw_cells(cx, cz)

        h1 = _hash01_arr(GI, GJ, 1.0)
        keep = h1 > 0.20           # 留 80% 的格子当候选
        GI, GJ = GI[keep], GJ[keep]
        if GI.size == 0:
            return (np.zeros((0, 8), np.float32),) * 2

        h2 = _hash01_arr(GI, GJ, 2.0)
        h3 = _hash01_arr(GI, GJ, 3.0)
        h4 = _hash01_arr(GI, GJ, 4.0)
        x = (GI + h2) * c
        z = (GJ + h3) * c

        dx = x - cx
        dz = z - cz
        inside = dx * dx + dz * dz <= self.radius ** 2
        keep = inside & ~self._runway_clearance(x, z)
        x, z, h4 = x[keep], z[keep], h4[keep]
        GI, GJ = GI[keep], GJ[keep]
        if x.size == 0:
            return (np.zeros((0, 8), np.float32),) * 2

        h, slope = self._terrain_ok(x, z, c)
        # 树只长在水面以上、雪线以下、不太陡的坡上
        good = (h > terrain.WATER_LEVEL + 3.0) & (h < 820.0) & (slope < 1.25)
        x, z, h, slope, h4 = x[good], z[good], h[good], slope[good], h4[good]
        GI, GJ = GI[good], GJ[good]
        if x.size == 0:
            return (np.zeros((0, 8), np.float32),) * 2

        # 海拔越高针叶树越多（真实山地就是这样：低处阔叶、高处针叶）
        broad_frac = np.clip(0.62 - (h - terrain.WATER_LEVEL) / 1400.0, 0.05, 0.70)
        is_broad = _hash01_arr(GI, GJ, 10.0) < broad_frac

        # 成片而不是均匀撒点：用一个"大片噪声"决定这一带是不是林地，
        # 这样会出现成块的森林和开阔草地，比均匀分布自然得多。
        patch = (_hash01_arr(GI // 7, GJ // 7, 12.0) * 0.62
                 + _hash01_arr(GI // 2, GJ // 2, 13.0) * 0.38)
        forest_ok = patch > 0.30

        # 海拔越高树越稀（林线）
        thin = _hash01_arr(GI, GJ, 11.0)
        line_ok = thin > np.clip((h - 620.0) / 900.0, 0.0, 0.80)

        keep2 = forest_ok & line_ok
        x, z, h, h4 = x[keep2], z[keep2], h[keep2], h4[keep2]
        is_broad = is_broad[keep2]
        GI, GJ = GI[keep2], GJ[keep2]
        if x.size == 0:
            return (np.zeros((0, 8), np.float32),) * 2

        scale = (0.80 + h4 * 0.90) * self.tree_scale
        yaw = _hash01_arr(GI, GJ, 5.0) * 6.283
        t = _hash01_arr(GI, GJ, 6.0)

        def pack(mask):
            if not np.any(mask):
                return np.zeros((0, 8), np.float32)
            return np.stack([
                x[mask], h[mask] - 0.3, z[mask], scale[mask], yaw[mask],
                0.80 + t[mask] * 0.35, 0.85 + t[mask] * 0.30, 0.75 + t[mask] * 0.35,
            ], axis=1).astype(np.float32)

        return pack(~is_broad), pack(is_broad)

    def _place_village(self, cx, cz):
        """村庄：在跑道附近成组放建筑

        做法：先按较大间距选"村址"，再在每个村址周围放几座建筑。
        这样看起来是村子而不是随机撒房子。
        """
        out = {k: [] for k in props.PROP_BUILDERS}
        vc = 320.0                 # 村址间距
        r = self.radius
        n = int(r / vc)
        k = np.arange(-n, n + 1, dtype=np.int64)
        gi = np.floor(cx / vc).astype(np.int64) + k
        gj = np.floor(cz / vc).astype(np.int64) + k
        GI, GJ = np.meshgrid(gi, gj, indexing='ij')
        GI, GJ = GI.ravel(), GJ.ravel()

        # 40% 的格子当村址
        site = _hash01_arr(GI, GJ, 20.0) > 0.60
        GI, GJ = GI[site], GJ[site]
        if GI.size == 0:
            return out

        # 先把所有村址的位置算出来，然后**一次性**查地形和坡度。
        # 逐点查会慢很多（实测村庄占整个地景生成时间的 35%）。
        n_site = GI.size
        vx_all = (GI + 0.5 + (_hash01_arr(GI, GJ, 21.0) - 0.5) * 0.6) * vc
        vz_all = (GJ + 0.5 + (_hash01_arr(GI, GJ, 22.0) - 0.5) * 0.6) * vc
        ok_site = ((vx_all - cx) ** 2 + (vz_all - cz) ** 2 <= (r * 0.92) ** 2)
        ok_site &= ~self._runway_clearance(vx_all, vz_all)
        if not np.any(ok_site):
            return out
        hc_all = np.asarray(terrain.height_at(vx_all, vz_all), dtype=np.float64)
        ok_site &= (hc_all >= terrain.WATER_LEVEL + 4.0) & (hc_all <= 620.0)
        if not np.any(ok_site):
            return out
        # 坡度也一次算完（高度场差分）
        step = vc * 0.25
        hx_all = np.asarray(terrain.height_at(vx_all + step, vz_all),
                            dtype=np.float64)
        hz_all = np.asarray(terrain.height_at(vx_all, vz_all + step),
                            dtype=np.float64)
        slope_all = np.sqrt((hx_all - hc_all) ** 2
                            + (hz_all - hc_all) ** 2) / step
        ok_site &= slope_all <= 0.55

        sites = np.nonzero(ok_site)[0]
        for si in sites:
            gx, gz = int(GI[si]), int(GJ[si])
            vx, vz, hc = float(vx_all[si]), float(vz_all[si]), float(hc_all[si])

            # 一个村子 4~9 座建筑
            count = 4 + int(_hash01(gx, gz, 23.0) * 6)
            has_church = _hash01(gx, gz, 24.0) > 0.55
            # 建筑类型按权重抽
            kinds = ['house'] * 6 + ['barn'] * 2 + ['warehouse'] + ['water_tower']
            if has_church:
                kinds.append('church')
            # 同样把这一村的建筑位置一次算出来再批量查地形
            bs = []
            for b in range(count):
                a = _hash01(gx, gz, 30.0 + b) * 6.283
                dist = 22.0 + _hash01(gx, gz, 40.0 + b) * 68.0
                bs.append((vx + math.cos(a) * dist, vz + math.sin(a) * dist, b))
            if not bs:
                continue
            bx_all = np.asarray([q[0] for q in bs])
            bz_all = np.asarray([q[1] for q in bs])
            good = ~self._runway_clearance(bx_all, bz_all)
            hb_all = np.asarray(terrain.height_at(bx_all, bz_all),
                                dtype=np.float64)
            good &= hb_all >= terrain.WATER_LEVEL + 3.0
            hbx = np.asarray(terrain.height_at(bx_all + step, bz_all),
                             dtype=np.float64)
            hbz = np.asarray(terrain.height_at(bx_all, bz_all + step),
                             dtype=np.float64)
            sl = np.sqrt((hbx - hb_all) ** 2 + (hbz - hb_all) ** 2) / step
            good &= sl <= 0.6

            for k in np.nonzero(good)[0]:
                bx, bz, b = float(bx_all[k]), float(bz_all[k]), bs[k][2]
                hb = float(hb_all[k])
                pick = _hash01(gx, gz, 50.0 + b)
                if b == 0 and has_church:
                    kind = 'church'
                else:
                    kind = kinds[int(pick * len(kinds)) % len(kinds)]
                sc = 0.75 + _hash01(gx, gz, 60.0 + b) * 0.5
                yaw = _hash01(gx, gz, 70.0 + b) * 6.283
                t = _hash01(gx, gz, 80.0 + b)
                out[kind].append((bx, hb - 0.4, bz, sc, yaw,
                                  0.85 + t * 0.20, 0.85 + t * 0.18,
                                  0.85 + t * 0.16))
        return out

    def _place_rocks(self, cx, cz):
        """山坡上的散石：只在比较陡或者比较高的地方放"""
        c = 120.0
        GI, GJ = self._raw_cells(cx, cz)
        keep = _hash01_arr(GI, GJ, 90.0) > 0.86
        GI, GJ = GI[keep], GJ[keep]
        if GI.size == 0:
            return np.zeros((0, 8), np.float32)
        h2 = _hash01_arr(GI, GJ, 91.0)
        h3 = _hash01_arr(GI, GJ, 92.0)
        x = (GI + h2) * c
        z = (GJ + h3) * c
        dx, dz = x - cx, z - cz
        inside = dx * dx + dz * dz <= self.radius ** 2
        keep = inside & ~self._runway_clearance(x, z, apron=140.0)
        x, z, GI, GJ = x[keep], z[keep], GI[keep], GJ[keep]
        if x.size == 0:
            return np.zeros((0, 8), np.float32)
        h, slope = self._terrain_ok(x, z, c)
        # 陡坡或者高海拔才有石头
        good = (h > terrain.WATER_LEVEL + 1.0) & ((slope > 0.42) | (h > 620.0))
        x, z, h, GI, GJ = x[good], z[good], h[good], GI[good], GJ[good]
        if x.size == 0:
            return np.zeros((0, 8), np.float32)
        sc = 0.6 + _hash01_arr(GI, GJ, 93.0) * 1.4
        yaw = _hash01_arr(GI, GJ, 94.0) * 6.283
        t = _hash01_arr(GI, GJ, 95.0)
        return np.stack([
            x, h - 0.3, z, sc, yaw,
            0.80 + t * 0.25, 0.80 + t * 0.25, 0.80 + t * 0.25,
        ], axis=1).astype(np.float32)

    def _place_turbines(self, cx, cz):
        """风力发电机：立在山脊上相对平的地方，彼此拉开距离

        地形比较陡（坡度中位 1.4 左右），"又高又平"的点很稀少，
        所以采样格要密一点（260 m）、坡度阈值放宽到 0.5，
        否则一走一过可能一台都看不到。高的位置优先占。
        """
        c = 260.0
        GI, GJ = self._raw_cells(cx, cz)
        keep = _hash01_arr(GI, GJ, 100.0) > 0.62
        GI, GJ = GI[keep], GJ[keep]
        if GI.size == 0:
            return np.zeros((0, 8), np.float32)
        h2 = _hash01_arr(GI, GJ, 101.0)
        h3 = _hash01_arr(GI, GJ, 102.0)
        x = (GI + h2) * c
        z = (GJ + h3) * c
        dx, dz = x - cx, z - cz
        inside = dx * dx + dz * dz <= (self.radius * 0.95) ** 2
        keep = inside & ~self._runway_clearance(x, z, apron=260.0)
        x, z, GI, GJ = x[keep], z[keep], GI[keep], GJ[keep]
        if x.size == 0:
            return np.zeros((0, 8), np.float32)
        h, slope = self._terrain_ok(x, z, c)
        # 高处 + 相对平（山脊 / 台地）
        good = (h > 380.0) & (h < 1150.0) & (slope < 0.50)
        x, z, h, GI, GJ = x[good], z[good], h[good], GI[good], GJ[good]
        if x.size == 0:
            return np.zeros((0, 8), np.float32)
        # 越高的位置越先占（真实的电场先占山脊最好的位置）
        order = np.argsort(-h)
        x, z, h = x[order], z[order], h[order]
        sc_all = 0.85 + _hash01_arr(GI, GJ, 103.0)[order] * 0.45
        yaw_all = _hash01_arr(GI, GJ, 104.0)[order] * 6.283
        # 彼此至少隔开 200 m，最多 12 台
        pick = []
        for i in range(x.size):
            if len(pick) >= 12:
                break
            okp = True
            for j in pick:
                if (x[i] - x[j]) ** 2 + (z[i] - z[j]) ** 2 < 200.0 ** 2:
                    okp = False
                    break
            if okp:
                pick.append(i)
        if not pick:
            return np.zeros((0, 8), np.float32)
        idx = np.asarray(pick, dtype=np.int64)
        n = idx.size
        return np.stack([x[idx], h[idx] - 0.3, z[idx],
                         sc_all[idx], yaw_all[idx],
                         np.full(n, 0.92), np.full(n, 0.93), np.full(n, 0.94)],
                        axis=1).astype(np.float32)

    # ---------------------------------------------------------- 对外
    def update(self, center):
        """center = (x, z)。飞机走远了就重新生成"""
        if self.center is not None:
            dx = center[0] - self.center[0]
            dz = center[1] - self.center[1]
            if dx * dx + dz * dz < (self.radius * 0.45) ** 2:
                return False
        self.center = (float(center[0]), float(center[1]))
        cx, cz = self.center

        conifer, broad = self._place_forest(cx, cz)
        self.conifer_count = conifer.shape[0]
        self.broadleaf_count = broad.shape[0]
        self._pending_conifer = conifer
        self._pending_broad = broad

        village = self._place_village(cx, cz)
        self._pending_props = {}
        self.village_stats = {}
        for kind, rows in village.items():
            if rows:
                arr = np.asarray(rows, dtype=np.float32)
                self._pending_props[kind] = arr
                self.village_stats[kind] = arr.shape[0]
            else:
                self._pending_props[kind] = None
                self.village_stats[kind] = 0

        rocks = self._place_rocks(cx, cz)
        self._pending_props['rock'] = rocks if rocks.shape[0] else None
        self.village_stats['rock'] = rocks.shape[0]

        turb = self._place_turbines(cx, cz)
        self._pending_turbines = turb
        self.turbine_count = turb.shape[0]

        # 线状地景：河流 + 公路（贴地飘带）
        self._pending_rivers = self._make_rivers(cx, cz)
        self._pending_roads = self._make_roads(cx, cz)
        # 面状地景：农田色块
        self._pending_fields = self._make_fields(cx, cz)
        self.river_count = len(self._pending_rivers)
        self.road_count = len(self._pending_roads)
        self.field_count = len(self._pending_fields)

        return True

    # ---------------------------------------------------------- 河流 / 公路 / 农田
    def _make_rivers(self, cx, cz):
        """从附近的高地往下追几条河

        每条河从半径内比较高、比较平的地方出发，每隔一段取一个源头，
        然后顺坡而下直到入湖。用 < 400 m 的间距保证不会挤成一堆。
        """
        out = []
        r = self.radius
        step = 520.0
        n = int(r / step)
        k = np.arange(-n, n + 1, dtype=np.int64)
        gi = np.floor(cx / step).astype(np.int64) + k
        gj = np.floor(cz / step).astype(np.int64) + k
        GI, GJ = np.meshgrid(gi, gj, indexing='ij')
        GI, GJ = GI.ravel(), GJ.ravel()
        # 只有一部分格子做源头
        keep = _hash01_arr(GI, GJ, 200.0) > 0.55
        GI, GJ = GI[keep], GJ[keep]
        used = []
        for i in range(GI.size):
            x = (GI[i] + _hash01(GI[i], GJ[i], 201.0)) * step
            z = (GJ[i] + _hash01(GI[i], GJ[i], 202.0)) * step
            dx, dz = x - cx, z - cz
            if dx * dx + dz * dz > (r * 0.92) ** 2:
                continue
            # 源头之间至少隔开 500 m
            if any((x - ux) ** 2 + (z - uz) ** 2 < 500.0 ** 2 for ux, uz in used):
                continue
            path = linear.trace_river(x, z, step=80.0, max_steps=110)
            if len(path) < 5:
                continue
            used.append((x, z))
            v = linear.ribbon(
                path, width=26.0, y_offset=-0.55, wobble=4.0,
                seed=int(abs(GI[i] * 31 + GJ[i]) & 0x7FFFFFFF),
                color_a=(0.14, 0.30, 0.48), color_b=(0.20, 0.42, 0.60))
            if v:
                out.append(np.asarray(v, dtype=np.float32))
            if len(out) >= 4:
                break
        return out

    def _make_roads(self, cx, cz):
        """连接村庄的公路

        做法：拿半径内的村址两两配对（就近连），连成几条路。
        路比河窄、颜色偏灰，贴地抬高一点。
        """
        out = []
        r = self.radius
        vc = 320.0
        n = int(r / vc)
        k = np.arange(-n, n + 1, dtype=np.int64)
        gi = np.floor(cx / vc).astype(np.int64) + k
        gj = np.floor(cz / vc).astype(np.int64) + k
        GI, GJ = np.meshgrid(gi, gj, indexing='ij')
        GI, GJ = GI.ravel(), GJ.ravel()
        site = _hash01_arr(GI, GJ, 20.0) > 0.60
        GI, GJ = GI[site], GJ[site]
        if GI.size < 2:
            return out
        # 村址坐标
        nodes = []
        for i in range(GI.size):
            x = (GI[i] + 0.5 + (_hash01(GI[i], GJ[i], 21.0) - 0.5) * 0.6) * vc
            z = (GJ[i] + 0.5 + (_hash01(GI[i], GJ[i], 22.0) - 0.5) * 0.6) * vc
            dx, dz = x - cx, z - cz
            if dx * dx + dz * dz <= (r * 0.88) ** 2:
                nodes.append((x, z))
        if len(nodes) < 2:
            return out
        # 每个村连到最近的邻居（限制条数，避免画太多）
        made = 0
        for i, (x0, z0) in enumerate(nodes):
            best = None
            for j, (x1, z1) in enumerate(nodes):
                if i == j:
                    continue
                dd = (x1 - x0) ** 2 + (z1 - z0) ** 2
                if best is None or dd < best[0]:
                    best = (dd, x1, z1)
            if best is None:
                continue
            dd, x1, z1 = best
            if dd > 900.0 ** 2 or dd < 100.0 ** 2:
                continue
            dist = math.sqrt(dd)
            segs = max(3, int(dist / 120.0))
            path = []
            for s in range(segs + 1):
                t = s / float(segs)
                # 中间加一点弯曲，别是直线
                bend = math.sin(t * math.pi) * (_hash01(i, s, 210.0) - 0.5) * dist * 0.16
                px = x0 + (x1 - x0) * t
                pz = z0 + (z1 - z0) * t
                # 垂直于连线方向偏移
                ux, uz = (x1 - x0) / dist, (z1 - z0) / dist
                px += -uz * bend
                pz += ux * bend
                path.append((px, pz, float(terrain.height_at(px, pz))))
            v = linear.ribbon(path, width=9.0, y_offset=0.14, wobble=0.8,
                              seed=(i * 7919) & 0x7FFFFFFF, taper=False,
                              color_a=(0.42, 0.40, 0.37),
                              color_b=(0.46, 0.44, 0.41))
            if v:
                out.append(np.asarray(v, dtype=np.float32))
            made += 1
            if made >= 6:
                break
        return out

    def _make_fields(self, cx, cz):
        """农田：村庄周围的成片色块（不同颜色代表不同作物）"""
        patches = []
        r = self.radius
        vc = 320.0
        n = int(r / vc)
        k = np.arange(-n, n + 1, dtype=np.int64)
        gi = np.floor(cx / vc).astype(np.int64) + k
        gj = np.floor(cz / vc).astype(np.int64) + k
        GI, GJ = np.meshgrid(gi, gj, indexing='ij')
        GI, GJ = GI.ravel(), GJ.ravel()
        site = _hash01_arr(GI, GJ, 20.0) > 0.60
        GI, GJ = GI[site], GJ[site]
        # 几种作物颜色
        palette = [
            (0.42, 0.48, 0.20),      # 青苗
            (0.62, 0.55, 0.24),      # 成熟
            (0.36, 0.30, 0.20),      # 翻过的土
            (0.50, 0.52, 0.26),      # 黄绿
        ]
        for i in range(GI.size):
            gx, gz = int(GI[i]), int(GJ[i])
            vx = (gx + 0.5 + (_hash01(gx, gz, 21.0) - 0.5) * 0.6) * vc
            vz = (gz + 0.5 + (_hash01(gx, gz, 22.0) - 0.5) * 0.6) * vc
            dx, dz = vx - cx, vz - cz
            if dx * dx + dz * dz > (r * 0.85) ** 2:
                continue
            if bool(self._runway_clearance(np.array([vx]), np.array([vz]))[0]):
                continue
            hv = float(terrain.height_at(vx, vz))
            if hv < terrain.WATER_LEVEL + 4.0 or hv > 620.0:
                continue
            if float(terrain.slope_at(vx, vz)) > 0.45:
                continue
            # 把这一村的所有地块位置先算出来，再一次性查地形和坡度
            cnt = 3 + int(_hash01(gx, gz, 220.0) * 5)
            cand = []
            for b in range(cnt):
                px = vx + (_hash01(gx, gz, 230.0 + b) - 0.5) * 260.0
                pz = vz + (_hash01(gx, gz, 240.0 + b) - 0.5) * 260.0
                cand.append((px, pz, b))
            if not cand:
                continue
            pxs = np.asarray([c[0] for c in cand])
            pzs = np.asarray([c[1] for c in cand])
            phs = np.asarray(terrain.height_at(pxs, pzs), dtype=np.float64)
            stp = 60.0
            phx = np.asarray(terrain.height_at(pxs + stp, pzs), dtype=np.float64)
            phz = np.asarray(terrain.height_at(pxs, pzs + stp), dtype=np.float64)
            sls = np.sqrt((phx - phs) ** 2 + (phz - phs) ** 2) / stp
            good = (phs >= terrain.WATER_LEVEL + 3.0) & (sls <= 0.40)
            for k in np.nonzero(good)[0]:
                px, pz, b = float(pxs[k]), float(pzs[k]), cand[k][2]
                col = palette[int(_hash01(gx, gz, 250.0 + b) * len(palette))
                              % len(palette)]
                w = 40.0 + _hash01(gx, gz, 260.0 + b) * 70.0
                d = 40.0 + _hash01(gx, gz, 270.0 + b) * 70.0
                yaw = (_hash01(gx, gz, 280.0 + b) - 0.5) * 0.8
                patches.append((col, px, pz, w, d, yaw))
        return patches


    def upload(self):
        """把生成好但还没上传的实例数据传到显卡（需要 GL 上下文）"""
        pend = getattr(self, '_pending_conifer', None)
        if pend is not None and pend.shape[0]:
            self._ensure_meshes()
            self.conifer.mesh.set_instances(pend)
        self._pending_conifer = None

        pend = getattr(self, '_pending_broad', None)
        if pend is not None and pend.shape[0]:
            self._ensure_meshes()
            self.broadleaf.mesh.set_instances(pend)
        self._pending_broad = None

        for kind, arr in (getattr(self, '_pending_props', None) or {}).items():
            if arr is not None and arr.shape[0]:
                self._ensure_meshes()
                self.props[kind].set_instances(arr)
            elif kind in self.props:
                self.props[kind].count = 0
        self._pending_props = {}

        pend = getattr(self, '_pending_turbines', None)
        if pend is not None and pend.shape[0]:
            self._ensure_meshes()
            # 塔身用实例化画；叶轮记录实例数据，单独画（会转）
            self.props.setdefault('turbine_tower',
                                  props.Props('turbine_tower', props._turbine))
            self.props['turbine_tower'].set_instances(pend)
            rotor_data = pend.copy()
            rotor_data[:, 1] += 22.6 * pend[:, 3]    # 叶轮装在塔顶
            self.turbine.set_instances(rotor_data)
        self._pending_turbines = None

        # 河流 / 公路：每段单独一个网格（飘带已经按地形采样过高度了）
        for attr, key in (('_pending_rivers', 'rivers'),
                          ('_pending_roads', 'roads')):
            parts = getattr(self, attr, None) or []
            for i, arr in enumerate(parts):
                name = '%s_%d' % (key, i)
                if name not in self.ribbons:
                    self.ribbons[name] = gfx.Mesh(arr)
                else:
                    self.ribbons[name] = gfx.Mesh(arr)
            setattr(self, attr, None)

        # 农田：所有色块合成一个网格（按颜色分组，减少 draw call）
        patches = getattr(self, '_pending_fields', None) or []
        by_color = {}
        for (col, px, pz, w, d, yaw) in patches:
            by_color.setdefault(col, []).append((px, pz, w, d, yaw))
        for col, items in by_color.items():
            fp = linear.FlatPatch(col)
            for (px, pz, w, d, yaw) in items:
                fp.add(px, pz, w, d, yaw)
            verts = fp.build()
            if verts.size:
                key = 'field_%d_%d_%d' % (int(col[0] * 99), int(col[1] * 99),
                                          int(col[2] * 99))
                self.fields[key] = gfx.Mesh(verts)
        self._pending_fields = None

    def update_animation(self, dt):
        """每帧推进动画（风机叶轮转动）"""
        if self.turbine is not None:
            self.turbine.update(dt)

    @staticmethod
    def _house_geometry():
        """兼容老调用：小房子几何"""
        return props._house()

    # ---------------------------------------------------------- 绘制
    def draw_trees(self, shader):
        if self.conifer_count and self.conifer is not None:
            self.conifer.mesh.draw_instanced()
        if self.broadleaf_count and self.broadleaf is not None:
            self.broadleaf.mesh.draw_instanced()

    def draw_houses(self, shader):
        """画所有建筑（保留旧名字，内部画全部道具）"""
        self.draw_props(shader)

    def draw_props(self, shader):
        for kind, p in self.props.items():
            if kind == 'turbine_tower':
                continue
            p.draw(shader)
        # 河流 / 公路 / 农田：平面网格，正常画
        for mesh in self.ribbons.values():
            shader.set_mat4('uModel', np.eye(4, dtype=np.float32))
            shader.set_mat3('uNormalMat', np.eye(3, dtype=np.float32))
            mesh.draw()
        for mesh in self.fields.values():
            shader.set_mat4('uModel', np.eye(4, dtype=np.float32))
            shader.set_mat3('uNormalMat', np.eye(3, dtype=np.float32))
            mesh.draw()

    def draw_turbines(self, shader):
        p = self.props.get('turbine_tower')
        if p is not None:
            p.draw(shader)
        if self.turbine is not None:
            self.turbine.draw(shader)

    def total_props(self):
        return sum(p.count for k, p in self.props.items() if k != 'turbine_tower')


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
