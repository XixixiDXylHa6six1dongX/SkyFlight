# -*- coding: utf-8 -*-
"""
飞机模型

局部坐标：机头朝 -Z，右翼朝 +X，上为 +Y
全部用 gfx.box 拼，几何一定正确

每种机型返回 (机身网格, 起落架网格)：
  起落架单独成一个网格，收起时把它缩进去/藏起来
"""
import math

from . import gfx
from . import specs

# ---------------- 配色
BODY = (0.94, 0.94, 0.96)      # 机身白
BODY_GREY = (0.72, 0.74, 0.78)  # 军灰
ACCENT = (0.15, 0.35, 0.62)    # 蓝色涂装
ACCENT2 = (0.86, 0.22, 0.22)   # 红色条
DARK = (0.13, 0.13, 0.15)      # 起落架/进气口
GLASS = (0.40, 0.60, 0.78)     # 舱盖
GREY = (0.58, 0.60, 0.63)      # 机腹/金属
YELLOW = (0.95, 0.80, 0.25)
JET_DARK = (0.22, 0.24, 0.28)  # 喷口
NAVY = (0.10, 0.18, 0.34)
WHITE = (0.96, 0.96, 0.98)

# ---- 跑道尺寸（碰撞检测也要用，所以放在这里共享）
RUNWAY_LEN = 1400.0
RUNWAY_WID = 48.0
RUNWAY_TOP = 0.24     # 跑道面高度（沥青厚 0.24，铺在地面上）


# ==================================================================
#  机型 1：螺旋桨教练机（固定起落架）
# ==================================================================
def _build_trainer():
    v = []
    segs = [
        (-1.35, 0.60, 0.45, 0.45, 0.00, ACCENT),
        (-0.75, 0.65, 0.60, 0.60, 0.00, BODY),
        (0.15, 1.25, 0.78, 0.82, 0.00, BODY),
        (1.55, 1.55, 0.82, 0.88, 0.00, BODY),
        (3.05, 1.50, 0.76, 0.82, 0.02, BODY),
        (4.45, 1.30, 0.60, 0.66, 0.08, ACCENT),
        (5.45, 0.75, 0.42, 0.48, 0.14, ACCENT),
        (6.05, 0.45, 0.26, 0.30, 0.18, ACCENT),
    ]
    for zc, ln, wd, ht, yc, col in segs:
        v += gfx.box(0.0, yc, zc, wd, ht, ln, col)

    v += gfx.box(0.0, 0.05, 1.55, 0.86, 0.16, 2.20, ACCENT)
    v += gfx.box(0.0, -0.18, 1.55, 0.86, 0.08, 2.20, ACCENT2)

    wing_segs = [
        (1.55, 2.60, 2.10, 2.30, -0.02),
        (3.55, 1.40, 1.90, 2.55, 0.10),
        (4.90, 1.30, 1.60, 2.80, 0.22),
    ]
    for side in (1, -1):
        for cx, span, chord, zc, yc in wing_segs:
            v += gfx.box(side * cx, yc, zc, span, 0.20, chord, BODY)
            v += gfx.box(side * cx, yc, zc + chord / 2 - 0.12, span, 0.21, 0.22, ACCENT2)
        v += gfx.box(side * 5.55, 0.34, 2.80, 0.10, 0.55, 1.35, ACCENT)

    for side in (1, -1):
        v += gfx.box(side * 1.05, 0.22, 5.05, 1.95, 0.16, 1.05, BODY)
        v += gfx.box(side * 1.05, 0.22, 5.50, 1.95, 0.17, 0.18, ACCENT2)

    vt = [
        (5.05, 0.70, 0.14, 0.90, 2.35, 0.60),
        (5.45, 0.60, 0.14, 1.15, 2.20, 0.70),
        (5.95, 0.50, 0.14, 1.55, 2.05, 0.75),
        (6.35, 0.40, 0.13, 1.85, 1.95, 0.60),
    ]
    for zc, ln, wd, ht, yc, _ in vt:
        yc = yc / 2.0 + 0.22
        v += gfx.box(0.0, yc, zc, wd, ht, ln, ACCENT)

    v += gfx.box(0.0, 0.48, 0.30, 0.66, 0.26, 1.55, GLASS)
    v += gfx.box(0.0, 0.62, 0.30, 0.48, 0.10, 1.30, GLASS)
    v += gfx.box(0.0, 0.30, -0.50, 0.54, 0.20, 0.45, GLASS)

    # 发动机罩 + 三叶螺旋桨
    v += gfx.box(0.0, 0.00, -1.70, 0.50, 0.50, 0.30, DARK)
    v += gfx.box(0.0, 0.00, -1.90, 0.22, 0.22, 0.16, GREY)
    v += gfx.box(0.0, 0.95, -1.90, 0.10, 1.90, 0.06, DARK)
    v += gfx.box(-0.82, -0.42, -1.90, 1.64, 0.10, 0.06, DARK)
    v += gfx.box(0.82, -0.42, -1.90, 1.64, 0.10, 0.06, DARK)

    for side in (1, -1):
        v += gfx.box(side * 5.40, 0.10, 2.60, 0.12, 0.14, 0.14, YELLOW)

    # ---- 固定起落架
    gear = []
    gear += gfx.box(0.0, -0.62, -0.30, 0.10, 0.55, 0.10, DARK)
    gear += gfx.box(0.0, -0.92, -0.30, 0.20, 0.24, 0.20, DARK)
    for side in (1, -1):
        gear += gfx.box(side * 1.10, -0.62, 1.85, 0.10, 0.60, 0.10, DARK)
        gear += gfx.box(side * 1.10, -0.94, 1.85, 0.24, 0.26, 0.42, DARK)

    return gfx.Mesh(v), gfx.Mesh(gear)


# ==================================================================
#  机型 2：轻型涡喷教练机（单发、后掠翼、可收起落架）
# ==================================================================
def _build_jet_light():
    v = []
    # 机身：细长，机头尖
    segs = [
        (-3.60, 0.90, 0.30, 0.30, 0.00, ACCENT2),   # 机头尖
        (-3.00, 0.60, 0.46, 0.44, 0.00, BODY),
        (-2.30, 0.80, 0.62, 0.60, 0.00, BODY),
        (-1.20, 1.40, 0.78, 0.76, 0.00, BODY),
        (0.40, 1.80, 0.84, 0.82, 0.00, BODY),
        (2.20, 1.80, 0.82, 0.82, 0.00, BODY),
        (4.00, 1.60, 0.74, 0.78, 0.02, BODY),
        (5.60, 1.40, 0.62, 0.68, 0.06, ACCENT),
    ]
    for zc, ln, wd, ht, yc, col in segs:
        v += gfx.box(0.0, yc, zc, wd, ht, ln, col)

    # 蓝色腰线
    v += gfx.box(0.0, 0.06, 0.60, 0.86, 0.18, 4.60, ACCENT)
    v += gfx.box(0.0, -0.20, 0.60, 0.86, 0.09, 4.60, ACCENT2)

    # 后掠主翼（用多段向后的 box 拼出后掠）
    # 外段中心 4.95 + 半宽 0.40 = 翼尖 x 5.35 -> 翼展 10.7 m
    ws = [
        (0.95, 1.90, 2.60, 0.95, -0.04),
        (2.60, 1.70, 2.30, 1.65, 0.06),
        (3.95, 1.30, 1.90, 2.30, 0.14),
        (4.95, 0.80, 1.50, 2.85, 0.20),
    ]
    for side in (1, -1):
        for cx, span, chord, zc, yc in ws:
            v += gfx.box(side * cx, yc, zc, span, 0.18, chord, BODY)
            v += gfx.box(side * cx, yc + 0.01, zc + chord / 2 - 0.12, span, 0.19, 0.22, ACCENT2)
        # 翼下导弹挂架（贴在机翼下面，不超出翼尖）
        v += gfx.box(side * 3.60, -0.24, 2.60, 0.22, 0.22, 2.40, GREY)
        v += gfx.box(side * 3.60, -0.24, 1.30, 0.16, 0.16, 0.50, ACCENT2)

    # 单发：机身两侧进气口
    for side in (1, -1):
        v += gfx.box(side * 0.62, -0.06, 0.60, 0.40, 0.52, 1.60, DARK)

    # 尾喷口
    v += gfx.box(0.0, 0.06, 6.30, 0.66, 0.62, 0.30, JET_DARK)
    v += gfx.box(0.0, 0.06, 6.46, 0.50, 0.46, 0.14, (0.55, 0.28, 0.12))

    # 后掠平尾 + 垂尾
    for side in (1, -1):
        v += gfx.box(side * 1.15, 0.24, 5.90, 2.10, 0.14, 1.10, BODY)
        v += gfx.box(side * 1.15, 0.25, 6.35, 2.10, 0.15, 0.20, ACCENT2)
    vt = [
        (5.50, 1.00, 0.13, 0.90, 0.85, 0.60),
        (6.00, 0.90, 0.13, 1.30, 0.75, 0.80),
        (6.45, 0.70, 0.12, 1.75, 0.70, 0.75),
    ]
    for zc, ln, wd, ht, yoff, _ in vt:
        v += gfx.box(0.0, yoff + ht / 2, zc, wd, ht, ln, ACCENT)

    # 座舱盖（低矮细长）
    v += gfx.box(0.0, 0.46, -1.40, 0.58, 0.22, 1.90, GLASS)
    v += gfx.box(0.0, 0.54, -1.05, 0.46, 0.10, 1.40, GLASS)

    for side in (1, -1):
        v += gfx.box(side * 4.60, 0.06, 3.10, 0.12, 0.12, 0.12, YELLOW)

    # ---- 可收放起落架（前三点、单轮）
    gear = []
    gear += gfx.box(0.0, -0.72, -2.20, 0.10, 0.60, 0.10, DARK)
    gear += gfx.box(0.0, -1.16, -2.20, 0.18, 0.26, 0.20, DARK)
    for side in (1, -1):
        gear += gfx.box(side * 0.78, -0.72, 1.10, 0.10, 0.70, 0.10, DARK)
        gear += gfx.box(side * 0.78, -1.20, 1.10, 0.22, 0.28, 0.40, DARK)

    return gfx.Mesh(v), gfx.Mesh(gear)


# ==================================================================
#  机型 3：双发涡喷公务机（大、四轮主起落架）
# ==================================================================
def _build_jet_heavy():
    v = []
    segs = [
        (-7.40, 1.20, 0.44, 0.44, 0.00, ACCENT2),
        (-6.40, 1.00, 0.70, 0.68, 0.00, BODY),
        (-5.20, 1.40, 1.00, 0.98, 0.00, BODY),
        (-3.60, 1.80, 1.30, 1.26, 0.00, BODY),
        (-1.40, 2.60, 1.42, 1.38, 0.00, BODY),
        (1.60, 3.20, 1.40, 1.36, 0.00, BODY),
        (4.40, 2.40, 1.26, 1.22, 0.02, BODY),
        (6.60, 1.80, 1.02, 1.00, 0.08, ACCENT),
        (8.10, 1.20, 0.72, 0.74, 0.14, ACCENT),
    ]
    for zc, ln, wd, ht, yc, col in segs:
        v += gfx.box(0.0, yc, zc, wd, ht, ln, col)

    # 腰线
    v += gfx.box(0.0, 0.10, 0.00, 1.44, 0.26, 12.00, ACCENT)
    v += gfx.box(0.0, -0.34, 0.00, 1.44, 0.12, 12.00, ACCENT2)

    # 大展弦比后掠翼
    # 外段中心 6.90 + 半宽 0.90 = 翼尖 x 7.80 -> 翼展 15.6 m
    ws = [
        (1.15, 2.30, 4.60, 1.20, -0.06),
        (3.30, 2.00, 4.00, 2.10, 0.06),
        (5.15, 1.70, 3.20, 3.10, 0.18),
        (6.55, 1.10, 2.40, 4.20, 0.28),
        (6.90, 0.90, 1.80, 5.20, 0.34),
    ]
    for side in (1, -1):
        for cx, span, chord, zc, yc in ws:
            v += gfx.box(side * cx, yc, zc, span, 0.26, chord, BODY)
            v += gfx.box(side * cx, yc + 0.02, zc + chord / 2 - 0.16, span, 0.27, 0.30, ACCENT2)
        # 翼尖小翼
        v += gfx.box(side * 7.75, 0.55, 5.40, 0.16, 0.95, 2.20, ACCENT)

    # 双发：翼吊发动机短舱 + 尾喷口
    for side in (1, -1):
        v += gfx.box(side * 3.60, -0.30, 0.60, 1.40, 1.20, 4.40, BODY_GREY)
        v += gfx.box(side * 3.60, -0.30, -1.80, 1.25, 1.05, 0.50, DARK)
        v += gfx.box(side * 3.60, -0.30, 2.95, 1.00, 0.85, 0.40, JET_DARK)
        v += gfx.box(side * 3.60, -0.30, 3.10, 0.80, 0.65, 0.20, (0.55, 0.28, 0.12))

    # 平尾 + 大垂尾（T 型）
    for side in (1, -1):
        v += gfx.box(side * 2.30, 0.30, 7.40, 4.20, 0.24, 2.20, BODY)
        v += gfx.box(side * 2.30, 0.32, 8.20, 4.20, 0.25, 0.30, ACCENT2)
    v += gfx.box(0.0, 2.40, 7.60, 0.30, 3.60, 2.60, ACCENT)
    v += gfx.box(0.0, 4.30, 7.90, 0.26, 1.00, 2.00, ACCENT)
    v += gfx.box(0.0, 0.64, 8.60, 4.30, 0.30, 1.40, BODY)   # T 型平尾

    # 座舱玻璃带
    v += gfx.box(0.0, 0.86, -5.00, 1.16, 0.44, 2.60, GLASS)
    for side in (1, -1):
        v += gfx.box(side * 0.62, 0.86, -3.20, 0.14, 0.42, 2.20, GLASS)
        v += gfx.box(side * 0.62, 0.86, -0.60, 0.14, 0.42, 2.00, GLASS)

    for side in (1, -1):
        v += gfx.box(side * 7.70, 0.06, 4.60, 0.16, 0.16, 0.16, YELLOW)

    # ---- 可收放起落架（前双轮 + 主四轮）
    gear = []
    gear += gfx.box(0.0, -1.00, -5.20, 0.12, 0.70, 0.12, DARK)
    for side in (1, -1):
        gear += gfx.box(side * 0.26, -1.42, -5.20, 0.20, 0.28, 0.24, DARK)
    for side in (1, -1):
        gear += gfx.box(side * 1.60, -1.00, 0.60, 0.12, 0.70, 0.12, DARK)
        gear += gfx.box(side * 1.60, -1.46, 0.10, 0.24, 0.32, 0.46, DARK)
        gear += gfx.box(side * 1.60, -1.46, 1.10, 0.24, 0.32, 0.46, DARK)

    return gfx.Mesh(v), gfx.Mesh(gear)


# ==================================================================
_BUILDERS = {
    'trainer': _build_trainer,
    'jet_light': _build_jet_light,
    'jet_heavy': _build_jet_heavy,
}


def build_plane(key=None):
    """按机型返回 (机身网格, 起落架网格)

    key 省略时用 specs.DEFAULT（螺旋桨教练机），
    这样老代码 build_plane() 仍然能拿到机身网格。
    """
    sp = specs.get(key) if key else specs.DEFAULT
    fn = _BUILDERS.get(sp.key, _build_trainer)
    return fn()


def build_plane_body(key=None):
    return build_plane(key)[0]


def build_shadow(key=None):
    """飞机的地面阴影：按机型轮廓做一个扁平暗色多边形

    平铺在地面上（y 很小），随机身偏航一起转，让飞机看起来是"停在地上"。
    """
    sp = specs.get(key) if key else specs.DEFAULT
    col = (0.06, 0.07, 0.09)
    v = []
    body_len = sp.fuse_len
    span = sp.wing_span
    if sp.key == 'jet_heavy':
        v += gfx.box(0.0, 0.0, 0.5, 1.6, 0.012, body_len, col)
        v += gfx.box(0.0, 0.0, 2.6, span, 0.012, 4.0, col)
        v += gfx.box(0.0, 0.0, 7.6, 5.0, 0.012, 2.4, col)
    elif sp.key == 'jet_light':
        v += gfx.box(0.0, 0.0, 1.0, 1.0, 0.012, body_len, col)
        v += gfx.box(0.0, 0.0, 2.0, span, 0.012, 2.8, col)
        v += gfx.box(0.0, 0.0, 6.2, 3.2, 0.012, 1.6, col)
    else:
        v += gfx.box(0.0, 0.0, 2.4, 1.5, 0.012, 9.0, col)
        v += gfx.box(0.0, 0.0, 2.6, span, 0.012, 3.0, col)
        v += gfx.box(0.0, 0.0, 5.3, 4.2, 0.012, 1.4, col)
    return gfx.Mesh(v)


def build_runway():
    """跑道沥青层（返回单个网格，兼容老调用）"""
    return gfx.Mesh(_runway_asphalt())


def build_runway_parts():
    """返回 (沥青网格, 标线网格)

    拆成两个网格是为了绘制时分别处理：
      沥青正常画；标线**关掉深度测试**再画，这样标线和沥青同高度也不会
      z-fighting（闪烁），而飞机随后照常画，轮胎压在标线之上。
    """
    return gfx.Mesh(_runway_asphalt()), gfx.Mesh(_runway_paint())


def _runway_asphalt():
    """沥青板：从地面铺到 RUNWAY_TOP"""
    return gfx.box(0.0, RUNWAY_TOP * 0.5, 0.0, RUNWAY_WID, RUNWAY_TOP, RUNWAY_LEN,
                   (0.20, 0.20, 0.22))


def _runway_paint():
    """跑道标线：中线虚线 + 两侧边线 + 两端编号 + 跑道灯

    标线一律画在 RUNWAY_TOP **同一高度**（零厚度薄片），所以轮胎底
    停在 RUNWAY_TOP 就是"正好压在最上层"，不会陷进去。
    跑道灯立在跑道两侧之外，飞机滑跑不会撞到。
    """
    v = []
    L = RUNWAY_LEN
    W = RUNWAY_WID
    # 标线贴在沥青面上：抬 5 mm 让它在深度上明确压过沥青（否则同高度会
    # z-fighting 闪烁），又远低于轮胎底，所以不会挡住飞机。
    PAINT_LIFT = 0.005
    paint_y = RUNWAY_TOP - PAINT_LIFT * 0.5      # 顶面 = RUNWAY_TOP + 5mm
    paint_h = PAINT_LIFT + 0.004
    WHITE = (0.93, 0.93, 0.88)

    # 中线虚线
    n = 24
    for i in range(n):
        z = -L / 2 + (i + 0.5) * (L / n)
        v += gfx.box(0.0, paint_y, z, 1.7, paint_h, L / n * 0.48, WHITE)
    # 两侧边线
    for side in (1, -1):
        v += gfx.box(side * (W / 2 - 1.3), paint_y, 0.0, 1.0, paint_h, L, WHITE)
    # 两端跑道编号
    for side in (1, -1):
        for k in range(4):
            v += gfx.box(side * (7.0 - k * 4.6), paint_y, -L / 2 + 30.0,
                         2.2, paint_h, 12.0, WHITE)
    # 跑道灯（立杆 + 灯头），在跑道外侧
    for i in range(0, 27):
        z = -L / 2 + i * (L / 26)
        for side in (1, -1):
            v += gfx.box(side * (W / 2 + 2.2), RUNWAY_TOP + 0.31, z, 0.75, 0.95, 0.75,
                         (0.98, 0.86, 0.30))
    return v


# 跑道面上最高的地方（标线顶面）。停机时轮胎底停在这之上。
RUNWAY_PAINT_TOP = RUNWAY_TOP + 0.005 + 0.004 * 0.5


def surface_height(x, z, terrain_h):
    """实际可落脚的地面高度 = 地形和跑道里更高的那个。

    碰撞检测必须用它，否则飞机会沉进跑道里。
    注意返回的是**跑道面上最高的那一层**（含标线），
    这样轮胎底不会插进标线里。
    terrain_h 是地形高度（由调用方传进来，避免循环依赖）。
    """
    if abs(x) <= RUNWAY_WID * 0.5 and abs(z) <= RUNWAY_LEN * 0.5:
        return max(float(terrain_h), RUNWAY_PAINT_TOP)
    return float(terrain_h)


def build_tower():
    """塔台"""
    v = []
    v += gfx.box(0.0, 9.0, 0.0, 7.0, 18.0, 7.0, (0.82, 0.82, 0.80))
    v += gfx.box(0.0, 19.5, 0.0, 11.0, 3.0, 11.0, (0.36, 0.43, 0.52))
    v += gfx.box(0.0, 21.2, 0.0, 11.6, 0.5, 11.6, (0.30, 0.33, 0.38))
    v += gfx.box(0.0, 22.5, 0.0, 1.1, 2.6, 1.1, (0.86, 0.30, 0.25))
    for side in (1, -1):
        v += gfx.box(side * 5.55, 19.5, 0.0, 0.2, 2.2, 10.2, (0.30, 0.55, 0.70))
        v += gfx.box(0.0, 19.5, side * 5.55, 10.2, 2.2, 0.2, (0.30, 0.55, 0.70))
    return gfx.Mesh(v)


def build_hangar():
    """机库，给地面加点东西"""
    v = []
    v += gfx.box(0.0, 3.5, 0.0, 26.0, 7.0, 18.0, (0.72, 0.73, 0.75))
    v += gfx.box(0.0, 7.4, 0.0, 27.0, 0.9, 19.0, (0.45, 0.48, 0.52))
    v += gfx.box(0.0, 3.0, -9.1, 16.0, 5.4, 0.3, (0.38, 0.40, 0.44))
    return gfx.Mesh(v)
