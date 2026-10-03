# -*- coding: utf-8 -*-
"""
地景检查

要求：
  1. 针叶林和阔叶林都要有（混交林）
  2. 村庄里要有多种建筑（房子/谷仓/仓库/教堂/水塔）
  3. 山坡上要有石头
  4. 合适的地方要有风力发电机，叶轮能转
  5. 水里、跑道上、机场核心区不能长东西
  6. 生成速度不能太慢（飞行中重新生成不能卡顿）
  7. 同一个位置每次生成结果一致（不会闪烁）
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from skyflight import scenery, terrain, props

ok = True


def check(name, cond, detail=''):
    global ok
    if cond:
        print('  [OK] %-30s %s' % (name, detail))
    else:
        ok = False
        print('  [FAIL] %-30s %s' % (name, detail))


sc = scenery.Scenery(radius=2600.0, cell=52.0)

# ---------- 1) 多地点生成
print('  多个位置的生成结果:')
t_total = 0.0
worst = 0.0
found_turbines = 0
found_kinds = set()
for cx, cz in ((0, 0), (3000, 2000), (-4000, 5000), (6000, -3000),
               (1200, -5000), (-2500, -2500), (8000, 3000)):
    sc.center = None
    t0 = time.time()
    sc.update((float(cx), float(cz)))
    dt = time.time() - t0
    t_total += dt
    worst = max(worst, dt)
    turb = sc.turbine_count
    if turb:
        found_turbines += turb
    kinds = {k: v for k, v in sc.village_stats.items() if v}
    found_kinds.update(kinds)
    print('     (%6d,%6d) %.3fs  针叶%4d 阔叶%4d 风机%2d  建筑 %s' % (
        cx, cz, dt, sc.conifer_count, sc.broadleaf_count, turb,
        ','.join('%s%d' % (k[:4], v) for k, v in sorted(kinds.items())) or '-'))

check('生成速度（平均 < 0.35 s）', t_total / 7 < 0.35, '平均 %.3f s，最慢 %.3f s' % (
    t_total / 7, worst))
check('混合林（针叶 + 阔叶都有）', sc.conifer_count > 0 and sc.broadleaf_count > 0,
      '最近一次 针叶%d 阔叶%d' % (sc.conifer_count, sc.broadleaf_count))
check('风力发电机能生成', found_turbines > 0, '7 个位置共 %d 台' % found_turbines)
check('村庄建筑种类丰富（>=4 种）', len(found_kinds) >= 4,
      '出现过: %s' % ', '.join(sorted(found_kinds)))

# ---------- 2) 一致性（同一位置两次生成应完全相同）
print()
print('  生成一致性（同一位置两次应完全一致，否则飞过会闪烁）:')
sc.center = None
sc.update((1234.0, -567.0))
a_con, a_broad = sc.conifer_count, sc.broadleaf_count
a_stats = dict(sc.village_stats)
sc.center = None
sc.update((1234.0, -567.0))
b_con, b_broad = sc.conifer_count, sc.broadleaf_count
b_stats = dict(sc.village_stats)
check('针叶树一致', a_con == b_con, '%d vs %d' % (a_con, b_con))
check('阔叶树一致', a_broad == b_broad, '%d vs %d' % (a_broad, b_broad))
check('建筑一致', a_stats == b_stats, '%s' % ('相同' if a_stats == b_stats else
                                            '%s vs %s' % (a_stats, b_stats)))

# ---------- 3) 不该有东西的地方
print()
print('  净空检查（跑道 / 机场核心区 / 水里）:')
sc.center = None
sc.update((0.0, 0.0))


def gather_points():
    """把当前生成的所有实例坐标收集起来"""
    pts = []
    for data in (getattr(sc, '_pending_conifer', None),
                 getattr(sc, '_pending_broad', None)):
        if data is not None and len(data):
            pts.append(np.stack([data[:, 0], data[:, 2]], axis=1))
    for arr in (getattr(sc, '_pending_props', None) or {}).values():
        if arr is not None and len(arr):
            pts.append(np.stack([arr[:, 0], arr[:, 2]], axis=1))
    tur = getattr(sc, '_pending_turbines', None)
    if tur is not None and len(tur):
        pts.append(np.stack([tur[:, 0], tur[:, 2]], axis=1))
    return np.concatenate(pts, axis=0) if pts else np.zeros((0, 2))


P = gather_points()
print('     实例总数 %d' % P.shape[0])
near_rw = (np.abs(P[:, 0]) < 110.0) & (np.abs(P[:, 1]) < terrain.RUNWAY_LEN * 0.60)
check('跑道范围内没有东西', int(near_rw.sum()) == 0, '%d 个越界' % int(near_rw.sum()))

d_ap = np.sqrt(P[:, 0] ** 2 + P[:, 1] ** 2)
core = d_ap < 520.0
check('机场核心区没有东西', int(core.sum()) == 0, '%d 个越界' % int(core.sum()))

hw = np.asarray(terrain.height_at(P[:, 0], P[:, 1]))
in_water = hw < terrain.WATER_LEVEL + 1.0
check('水里没有东西', int(in_water.sum()) == 0, '%d 个泡在水里' % int(in_water.sum()))

# ---------- 4) 道具几何
print()
print('  道具几何:')
for name, fn in props.PROP_BUILDERS.items():
    v = fn()
    a = np.asarray(v, dtype=np.float32).reshape(-1, 9)
    h = float(a[:, 1].max() - a[:, 1].min())
    print('     %-12s 顶点 %4d  高 %5.1f m' % (name, a.shape[0], h))
    check('  %s 几何合理' % name, a.shape[0] >= 36 and h > 0.5,
          '顶点 %d 高 %.1f' % (a.shape[0], h))

rt = props._turbine_rotor()
ra = np.asarray(rt, dtype=np.float32).reshape(-1, 9)
check('风机叶轮几何（三片叶）', ra.shape[0] >= 36, '顶点 %d' % ra.shape[0])

# ---------- 5) 叶轮旋转（不起窗口，用一个假网格绕开 GL 上下文）
print()
print('  风机叶轮旋转:')


class _FakeMesh:
    def draw(self):
        pass


rot = props.TurbineRotor()
rot.mesh = _FakeMesh()          # 直接塞一个假网格，就不用建 GL 资源了
rot.instances = np.array([[0.0, 100.0, 0.0, 1.0, 0.0, 1.0, 1.0, 1.0]],
                         dtype=np.float32)
a0 = rot.angle
for _ in range(60):
    rot.update(1 / 60.0)
check('叶轮会转', rot.angle > a0, '1 秒转过 %.1f°' % np.degrees(rot.angle - a0))

# 转满一圈应该回到 0 附近（取模正确）
rot.angle = 0.0
for _ in range(int(2 * np.pi / rot.rate * 60) + 2):
    rot.update(1 / 60.0)
check('角度取模正确（< 2π）', 0.0 <= rot.angle < 2 * np.pi, 'angle=%.3f' % rot.angle)

print()
print('=' * 62)
print('  地景检查: %s' % ('全部通过' if ok else '有失败项'))
print('=' * 62)
sys.exit(0 if ok else 1)
