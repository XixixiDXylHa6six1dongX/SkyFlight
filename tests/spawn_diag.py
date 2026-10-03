# -*- coding: utf-8 -*-
"""精确测量：飞机模型的最低点，以及它在跑道上的实际位置"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glfw
import numpy as np

from skyflight import gfx, plane, terrain, app as appmod

# ---------- 干净的模型捕获（只抓一次 build_plane，且只抓第一个 Mesh）
captured = []


class Cap:
    def __init__(self, verts, indices=None):
        v = np.asarray(verts, dtype=np.float32).reshape(-1, 9)
        captured.append(v)
        self.count = v.shape[0]


orig = gfx.Mesh
gfx.Mesh = Cap
try:
    plane.build_plane()
finally:
    gfx.Mesh = orig

assert len(captured) == 1, '应该只捕获 1 个网格，实际 %d 个' % len(captured)
V = captured[0]
P = V[:, 0:3]
print('=== 飞机模型（局部坐标）===')
print('  顶点数 %d' % P.shape[0])
print('  X 右翼+ / 左翼-  : %7.2f ~ %7.2f' % (P[:, 0].min(), P[:, 0].max()))
print('  Y 上+ / 下-      : %7.2f ~ %7.2f' % (P[:, 1].min(), P[:, 1].max()))
print('  Z 前- / 后+      : %7.2f ~ %7.2f' % (P[:, 2].min(), P[:, 2].max()))

# 按颜色区分起飞落架（DARK 深色）
col = V[:, 6:9]
dark = (col[:, 0] < 0.2) & (col[:, 1] < 0.2) & (col[:, 2] < 0.2)
if dark.any():
    print('  深色（起落架）最低点 Y = %.2f' % P[dark, 1].min())
print()

# ---------- 翻转后的世界坐标
for name, d in (('只翻 X（当前代码）', np.diag([-1.0, 1.0, 1.0])),
                ('翻 X + 翻 Y', np.diag([-1.0, -1.0, 1.0]))):
    Q = (d @ P.T).T
    print('%s:' % name)
    print('    世界 X %7.2f ~ %7.2f   世界 Y %7.2f ~ %7.2f   世界 Z %7.2f ~ %7.2f' % (
        Q[:, 0].min(), Q[:, 0].max(), Q[:, 1].min(), Q[:, 1].max(),
        Q[:, 2].min(), Q[:, 2].max()))
    print('    → 机头在世界 Z 最小端: %s' % ('是' if Q[:,2].min() < 0 else '否'))
    print('    → 最低点（起落架）世界 Y = %.2f' % Q[:, 1].min())
print()

# ---------- 跑道
print('=== 跑道 ===')
print('  RUNWAY_LEN = %.0f  RUNWAY_WID = %.0f  RUNWAY_TOP = %.2f' % (
    plane.RUNWAY_LEN, plane.RUNWAY_WID, plane.RUNWAY_TOP))
print()

# ---------- 实际游戏状态
g = appmod.SkyFlightApp()
g.init_gl()
c = g.craft
gh = plane.surface_height(c.pos[0], c.pos[2], terrain.height_at(c.pos[0], c.pos[2]))
print('=== 游戏里的出生状态 ===')
print('  机身原点 y = %.3f' % c.pos[1])
print('  地面高度   = %.3f  (跑道面 %.2f)' % (gh, plane.RUNWAY_TOP))
print('  模型最低点相对机身原点 = %.3f' % P[:, 1].min())
print('  所以轮胎底世界 y = %.3f' % (c.pos[1] + P[:, 1].min()))
print('  轮胎底相对跑道面 = %+.3f m' % (c.pos[1] + P[:, 1].min() - plane.RUNWAY_TOP))
print()
print('  要让轮胎正好落在跑道面，机身原点应该在 y = %.3f' % (plane.RUNWAY_TOP - P[:, 1].min()))
print('  当前是 %.3f，差 %.3f m' % (c.pos[1], (plane.RUNWAY_TOP - P[:, 1].min()) - c.pos[1]))

# 启动油门看看
g._on_key(g.window, glfw.KEY_Z, 0, glfw.PRESS, 0)
g.update(1 / 60.0)
g._on_key(g.window, glfw.KEY_Z, 0, glfw.RELEASE, 0)
for _ in range(120):
    g.update(1 / 60.0)
print()
print('=== 启动油门 2 秒后 ===')
print('  机身原点 y = %.3f   轮胎底 = %.3f   相对跑道 %+.3f  %s' % (
    c.pos[1], c.pos[1] + P[:, 1].min(), c.pos[1] + P[:, 1].min() - plane.RUNWAY_TOP,
    '✅ 正常' if c.pos[1] + P[:, 1].min() >= plane.RUNWAY_TOP - 0.05 else '❌ 陷入'))
glfw.terminate()
