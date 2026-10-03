# -*- coding: utf-8 -*-
"""
停机检查：三种机型放到跑道上之后，轮胎底必须正好压在跑道面上

这一项特别重要——之前的"飞机卡进跑道"就是停机高度算错导致的。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glfw
import numpy as np
from skyflight import app as appmod, plane, terrain, specs

ok = True
print('  机型        停机高   轮胎底   跑道面    差值   结果')
for sp in specs.CATALOG:
    g = appmod.SkyFlightApp(aircraft_key=sp.key)
    g.init_gl()
    c = g.craft
    for _ in range(30):
        g.update(1 / 60.0)
    surf = plane.surface_height(c.pos[0], c.pos[2],
                               terrain.height_at(c.pos[0], c.pos[2]))
    wheel = c.pos[1] - c.GEAR_HEIGHT
    diff = wheel - surf
    good = abs(diff) < 0.02
    if not good:
        ok = False
    print('  %-11s %7.2f %8.3f %8.3f %+7.3f   %s' % (
        sp.key, c.GEAR_HEIGHT, wheel, surf, diff, 'OK' if good else 'FAIL'))
    # 还要确认起落架是放下的（停机状态必须能滑跑）
    assert c.gear > 0.99, '%s 停机时起落架没收起' % sp.key
    glfw.terminate()

print()
print('  停机检查: %s' % ('全部通过' if ok else '有失败项'))
sys.exit(0 if ok else 1)
