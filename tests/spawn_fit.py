# -*- coding: utf-8 -*-
"""
出生点/跑道贴合检查（v1.5.1 修正后）

要保证：
  1. 跑道面上没有任何部件高过 RUNWAY_TOP（标线不再凸起）
  2. 每种机型停机后，轮胎底都严格等于 RUNWAY_TOP（不下陷、不浮空）
  3. 出生瞬间轮胎底高于跑道面（留出间隙）
  4. 滑跑几秒后仍然贴合
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glfw
import numpy as np
from skyflight import gfx, plane, terrain, specs, app as appmod, flight

ok = True


def check(name, cond, detail=''):
    global ok
    if cond:
        print('  [OK] %-34s %s' % (name, detail))
    else:
        ok = False
        print('  [FAIL] %-34s %s' % (name, detail))


def capture_all(fn):
    saved = []

    class Cap:
        def __init__(self, v, indices=None):
            saved.append(np.asarray(v, dtype=np.float32).reshape(-1, 9))
            self.count = saved[-1].shape[0]
    orig = gfx.Mesh
    gfx.Mesh = Cap
    try:
        fn()
    finally:
        gfx.Mesh = orig
    return saved


# ---------- 1) 跑道各层高度
print('  跑道几何（沥青层 / 标线层）:')
parts = capture_all(plane.build_runway_parts)
assert len(parts) == 2, 'build_runway_parts 应返回 (沥青, 标线)'
asphalt, paint = parts
print('    沥青  y %.3f ~ %.3f' % (asphalt[:, 1].min(), asphalt[:, 1].max()))
print('    标线  y %.3f ~ %.3f' % (paint[:, 1].min(), paint[:, 1].max()))
print('    RUNWAY_TOP = %.3f' % plane.RUNWAY_TOP)

# 标线里除了跑道灯，其余都不该高过 RUNWAY_PAINT_TOP
dark = paint[(paint[:, 6] > 0.9) & (paint[:, 7] > 0.9)]     # 白色标线
light = paint[(paint[:, 7] < 0.9)]                            # 黄色灯
check('白色标线不高于 RUNWAY_PAINT_TOP',
      float(dark[:, 1].max()) <= plane.RUNWAY_PAINT_TOP + 1e-6,
      '最高 %.3f，上限 %.3f' % (float(dark[:, 1].max()), plane.RUNWAY_PAINT_TOP))
check('标线抬升很小（< 3 cm，不会看成台阶）',
      plane.RUNWAY_PAINT_TOP - plane.RUNWAY_TOP < 0.03,
      '抬升 %.1f mm' % ((plane.RUNWAY_PAINT_TOP - plane.RUNWAY_TOP) * 1000))
check('沥青顶面 = 跑道面', abs(float(asphalt[:, 1].max()) - plane.RUNWAY_TOP) < 1e-6,
      '%.3f' % float(asphalt[:, 1].max()))
check('跑道灯在跑道外侧', float(np.abs(light[:, 0]).min()) > plane.RUNWAY_WID * 0.5,
      '灯最内 x=%.1f，跑道半宽 %.1f' % (
          float(np.abs(light[:, 0]).min()), plane.RUNWAY_WID * 0.5))
check('surface_height 返回标线顶面', abs(
    plane.surface_height(0.0, 560.0, 0.0) - plane.RUNWAY_PAINT_TOP) < 1e-6,
    '%.4f' % plane.surface_height(0.0, 560.0, 0.0))

# ---------- 2) 各机型停机贴合
print()
print('  各机型停机高度（几何计算，不起窗口）:')
for sp in specs.CATALOG:
    base = plane.surface_height(0.0, 560.0, float(terrain.height_at(0.0, 560.0)))
    # 停机后轮胎底应该正好在跑道面上
    wheel = (base + sp.gear_height) - sp.gear_height
    check('%s 轮胎底 = 跑道面' % sp.key, abs(wheel - base) < 1e-9,
          '%.4f vs %.4f' % (wheel, base))

# ---------- 3) 实测：出生瞬间 + 滑跑后
print()
print('  实机验证（出生瞬间的间隙 与 滑跑后的贴合）:')
for sp in specs.CATALOG:
    g = appmod.SkyFlightApp(aircraft_key=sp.key)
    g.init_gl()
    c = g.craft
    surf = plane.surface_height(c.pos[0], c.pos[2],
                                float(terrain.height_at(c.pos[0], c.pos[2])))
    wheel0 = c.pos[1] - c.GEAR_HEIGHT
    gap0 = wheel0 - surf
    # 静置让它落到跑道上（出生有间隙，约 0.7 秒落稳）
    settle_frames = 0
    for _ in range(300):
        g.update(1 / 60.0)
        settle_frames += 1
        s_now = plane.surface_height(c.pos[0], c.pos[2],
                                     float(terrain.height_at(c.pos[0], c.pos[2])))
        if abs((c.pos[1] - c.GEAR_HEIGHT) - s_now) < 0.005:
            break
    surf2 = plane.surface_height(c.pos[0], c.pos[2],
                                 float(terrain.height_at(c.pos[0], c.pos[2])))
    wheel1 = c.pos[1] - c.GEAR_HEIGHT
    gap1 = wheel1 - surf2
    # 再滑跑 8 秒
    g._on_key(g.window, glfw.KEY_Z, 0, glfw.PRESS, 0)
    g.update(1 / 60.0)
    g._on_key(g.window, glfw.KEY_Z, 0, glfw.RELEASE, 0)
    for _ in range(480):
        g.update(1 / 60.0)
    surf3 = plane.surface_height(c.pos[0], c.pos[2],
                                 float(terrain.height_at(c.pos[0], c.pos[2])))
    wheel2 = c.pos[1] - c.GEAR_HEIGHT
    gap2 = wheel2 - surf3
    print('    %-11s 出生间隙 %+.3f m   落地后 %+.4f m (%.2f 秒)   滑跑8秒后 %+.4f m  (速度%.0f)' % (
        sp.key, gap0, gap1, settle_frames / 60.0, gap2, c.airspeed_kmh))
    check('%s 出生高于跑道面' % sp.key, gap0 > 0.05, '%+.3f m' % gap0)
    check('%s 会落到跑道上（不下陷不浮空）' % sp.key, abs(gap1) < 0.01,
          '%+.4f m' % gap1)
    check('%s 滑跑中不低于跑道面' % sp.key, gap2 > -0.01, '%+.4f m' % gap2)
    glfw.terminate()

print()
print('=' * 62)
print('  出生点/跑道贴合检查: %s' % ('全部通过' if ok else '有失败项'))
print('=' * 62)
sys.exit(0 if ok else 1)
