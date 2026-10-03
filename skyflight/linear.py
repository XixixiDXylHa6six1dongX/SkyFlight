# -*- coding: utf-8 -*-
"""
线状地景：河流、公路

做法：沿着一条折线生成"贴地飘带"（ribbon）——
每段取左右两个点，高度取该处地形高度 + 抬升量，
这样飘带就完全贴着起伏的地面，不会悬空也不会插进山里。

河流额外处理：
  - 从高地出发，每一步朝"最低的邻居方向"流（真正顺坡而下）
  - 河床用比地形更低的高度（挖下去），所以看起来是水在沟里
"""
import math

import numpy as np

from . import gfx, terrain


def _terrain_h(x, z):
    return np.asarray(terrain.height_at(x, z), dtype=np.float64)


def trace_river(start_x, start_z, step=90.0, max_steps=90,
                min_height=terrain.WATER_LEVEL + 6.0):
    """从（start_x, start_z）往低处追踪一条河的路径

    每步在 8 个方向里挑最低的那个；如果走不动了（周围都比自己高）就停。
    返回 [(x, z, h), ...]，h 是地形高度。

    性能要点：8 个方向的高度**一次向量化查完**。
    一个方向查一次会让每条河慢好几倍（实测占总生成时间的 40%）。
    """
    x, z = float(start_x), float(start_z)
    h = float(terrain.height_at(x, z))
    if h < min_height:
        return []
    path = [(x, z, h)]
    # 8 个方向（顺序固定，保证可复现）
    dirs = np.asarray([
        (math.cos(a), math.sin(a))
        for a in (0, math.pi / 4, math.pi / 2, 3 * math.pi / 4,
                  math.pi, 5 * math.pi / 4, 3 * math.pi / 2, 7 * math.pi / 4)
    ], dtype=np.float64)
    for _ in range(max_steps):
        nx = x + dirs[:, 0] * step
        nz = z + dirs[:, 1] * step
        nh = np.asarray(terrain.height_at(nx, nz), dtype=np.float64)
        k = int(np.argmin(nh))
        best_h = float(nh[k])
        # 只往明显更低的地方走（避免原地打转）
        if best_h > h - step * 0.06:
            break                       # 太平或者已经上坡了，停下
        x, z, h = float(nx[k]), float(nz[k]), best_h
        path.append((x, z, h))
        if h <= terrain.WATER_LEVEL + 1.5:
            break                       # 入湖/入海
    return path if len(path) >= 4 else []


def ribbon(path, width, y_offset=0.35, wobble=0.0, seed=0,
           color_a=(0.16, 0.34, 0.52), color_b=(0.22, 0.44, 0.62),
           taper=True, closed_start=False):
    """沿折线生成贴地飘带顶点

    path      [(x, z, h), ...] 折线（h 是地形高度）
    width     带宽（米）
    y_offset  离地高度（路面抬高一点；河流给负值挖下去）
    wobble    边缘随机摆动幅度（让河流看起来自然）
    color_a/b 两端的颜色（渐变，看起来有层次）
    taper     两端收窄（河流/公路的尽头不会突然断成一条横线）
    """
    if len(path) < 2:
        return []
    rng = np.random.default_rng(int(abs(seed)) & 0x7FFFFFFF)
    pts = np.asarray([(p[0], p[1], p[2]) for p in path], dtype=np.float64)
    n = len(pts)
    ca = np.asarray(color_a, dtype=np.float64)
    cb = np.asarray(color_b, dtype=np.float64)

    # ---- 先把两侧所有角点的坐标算出来，地形高度**一次查完**
    # （逐点查是之前的性能瓶颈：每条河要几十次单独查询）
    seg = n - 1
    axs = np.empty(seg, dtype=np.float64)
    azs = np.empty(seg, dtype=np.float64)
    bxs = np.empty(seg, dtype=np.float64)
    bzs = np.empty(seg, dtype=np.float64)
    cxs = np.empty(seg, dtype=np.float64)
    czs = np.empty(seg, dtype=np.float64)
    dxs = np.empty(seg, dtype=np.float64)
    dzs = np.empty(seg, dtype=np.float64)
    cols = np.empty((seg, 3), dtype=np.float64)
    for i in range(seg):
        p0, p1 = pts[i], pts[i + 1]
        dx, dz = p1[0] - p0[0], p1[1] - p0[1]
        ln = math.hypot(dx, dz) or 1.0
        nx, nz = -dz / ln, dx / ln
        t0 = i / float(max(1, n - 1))
        t1 = (i + 1) / float(max(1, n - 1))
        w0 = width
        w1 = width
        if taper:
            w0 *= 0.45 + 0.55 * min(1.0, min(t0, 1.0 - t0) * 4.0)
            w1 *= 0.45 + 0.55 * min(1.0, min(t1, 1.0 - t1) * 4.0)
        if wobble > 0.0:
            w0 += rng.normal(0.0, wobble)
            w1 += rng.normal(0.0, wobble)
        w0 = max(1.0, w0)
        w1 = max(1.0, w1)
        axs[i], azs[i] = p0[0] + nx * w0 * 0.5, p0[1] + nz * w0 * 0.5
        bxs[i], bzs[i] = p0[0] - nx * w0 * 0.5, p0[1] - nz * w0 * 0.5
        cxs[i], czs[i] = p1[0] + nx * w1 * 0.5, p1[1] + nz * w1 * 0.5
        dxs[i], dzs[i] = p1[0] - nx * w1 * 0.5, p1[1] - nz * w1 * 0.5
        tm = 0.5 * (t0 + t1)
        cols[i] = ca * (1.0 - tm) + cb * tm

    # 一次查完 4 组角点
    ha = _terrain_h(axs, azs) + y_offset
    hb = _terrain_h(bxs, bzs) + y_offset
    hc = _terrain_h(cxs, czs) + y_offset
    hd = _terrain_h(dxs, dzs) + y_offset

    verts = []
    for i in range(seg):
        col = cols[i]
        col = np.clip(col, 0.0, 1.0)

        def v(x, y, z):
            return [x, y, z, 0.0, 1.0, 0.0, col[0], col[1], col[2]]

        # 两个三角形
        verts += v(axs[i], ha[i], azs[i])
        verts += v(bxs[i], hb[i], bzs[i])
        verts += v(dxs[i], hd[i], dzs[i])
        verts += v(axs[i], ha[i], azs[i])
        verts += v(dxs[i], hd[i], dzs[i])
        verts += v(cxs[i], hc[i], czs[i])
    return verts


class FlatPatch:
    """贴地色块（农田、空地）：给定中心 + 尺寸 + 朝向，采地形高度贴上去

    多个地块先攒起来，最后一次性做成网格，避免很多次小 draw call。
    """

    def __init__(self, color, lift=0.12):
        self.color = color
        self.lift = float(lift)
        self.patch_list = []

    def add(self, x, z, w, d, yaw=0.0):
        self.patch_list.append((float(x), float(z), float(w), float(d), float(yaw)))

    def __len__(self):
        return len(self.patch_list)

    def build(self):
        """把所有地块做成一个网格"""
        if not self.patch_list:
            return np.zeros(0, dtype=np.float32)
        # 一次性采样所有角点的地形高度（向量化，快很多）
        xs_all = []
        zs_all = []
        for (x, z, w, d, yaw) in self.patch_list:
            c, s = math.cos(yaw), math.sin(yaw)
            hw, hd = w * 0.5, d * 0.5
            for (px, pz) in ((-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)):
                xs_all.append(x + px * c - pz * s)
                zs_all.append(z + px * s + pz * c)
        hs = _terrain_h(np.asarray(xs_all), np.asarray(zs_all))

        verts = []
        r, g, b = self.color
        for i, (x, z, w, d, yaw) in enumerate(self.patch_list):
            c, s = math.cos(yaw), math.sin(yaw)
            hw, hd = w * 0.5, d * 0.5
            corners = []
            for k, (px, pz) in enumerate(((-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd))):
                corners.append((x + px * c - pz * s,
                                hs[i * 4 + k] + self.lift,
                                z + px * s + pz * c))
            # 颜色加一点随机深浅，看起来不像塑料板
            t = 0.90 + 0.20 * ((i * 2654435761) % 1000) / 1000.0
            rr, gg, bb = r * t, g * t, b * t
            for idx in (0, 1, 2, 0, 2, 3):
                px, py, pz = corners[idx]
                verts.extend([px, py, pz, 0.0, 1.0, 0.0, rr, gg, bb])
        return np.asarray(verts, dtype=np.float32)
