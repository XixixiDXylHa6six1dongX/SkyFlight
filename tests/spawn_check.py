# -*- coding: utf-8 -*-
"""
停机检查：三种机型放到跑道上之后

要同时满足两件事：
  1. 出生瞬间轮胎底**高于**跑道面（留了离地间隙，不会看着陷进地里）
  2. 静置一会儿之后落到跑道上，轮胎底**正好**压在跑道面上

这一项特别重要 —— 用户报过三次"飞机卡进地里"。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glfw
import numpy as np
from skyflight import app as appmod, plane, terrain, specs

ok = True
print('  机型        停机高   出生间隙   落地后差值   结果')
for sp in specs.CATALOG:
    g = appmod.SkyFlightApp(aircraft_key=sp.key)
    g.init_gl()
    c = g.craft

    # 出生瞬间：刻意比跑道面高 SPAWN_CLEARANCE
    surf0 = plane.surface_height(c.pos[0], c.pos[2],
                                 float(terrain.height_at(c.pos[0], c.pos[2])))
    gap0 = (c.pos[1] - c.GEAR_HEIGHT) - surf0

    # 静置让它轻轻落到跑道上
    for _ in range(300):
        g.update(1 / 60.0)
        s = plane.surface_height(c.pos[0], c.pos[2],
                                 float(terrain.height_at(c.pos[0], c.pos[2])))
        if abs((c.pos[1] - c.GEAR_HEIGHT) - s) < 0.004:
            break
    surf = plane.surface_height(c.pos[0], c.pos[2],
                               float(terrain.height_at(c.pos[0], c.pos[2])))
    wheel = c.pos[1] - c.GEAR_HEIGHT
    diff = wheel - surf

    good = (gap0 > 0.05) and (abs(diff) < 0.01)
    if not good:
        ok = False
    print('  %-11s %7.2f %9.3f %12.4f   %s' % (
        sp.key, c.GEAR_HEIGHT, gap0, diff, 'OK' if good else 'FAIL'))

    # 起落架必须是放下的（停机状态要能滑跑）
    assert c.gear > 0.99, '%s 停机时起落架没收起' % sp.key
    # 不能是坠毁状态
    assert not c.crashed, '%s 从出生高度落下居然摔了' % sp.key
    glfw.terminate()

print()
print('  停机检查: %s' % ('全部通过' if ok else '有失败项'))
sys.exit(0 if ok else 1)
