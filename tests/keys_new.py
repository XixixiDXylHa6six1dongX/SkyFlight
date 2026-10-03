# -*- coding: utf-8 -*-
"""
新按键验证：G（起落架收放）和 V（换机型）

不起窗口，只检查代码路径和状态机是否连起来。
"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from skyflight import flight, specs

ok = True


def check(name, cond, detail=''):
    global ok
    if cond:
        print('  [OK] %s %s' % (name, detail))
    else:
        ok = False
        print('  [FAIL] %s %s' % (name, detail))


# ---------- 代码路径
src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'skyflight', 'app.py'), encoding='utf-8').read()
print('  app.py 中的按键处理:')
for label, needle in (("G 收起落架", "n == 'G'"),
                      ("V 换机型", "n == 'V'"),
                      ("L 切换语言", "n == 'L'"),
                      ("N 音效开关", "n == 'N'"),
                      ("调用 toggle_sound", "self.toggle_sound()"),
                      ("调用 toggle_language", "self.toggle_language()"),
                      ("调用 toggle_gear", "self.craft.toggle_gear()"),
                      ("调用 next_aircraft", "self.next_aircraft()"),
                      ("绘制起落架网格", "self.gear_mesh.draw()"),
                      ("绘制粒子", "self._draw_particles"),
                      ("更新特效", "self._update_effects"),
                      ("按机型建模型", "plane.build_plane(self.aircraft_key)")):
    check(label, needle in src)

# ---------- 状态机
print()
print('  起落架状态机:')
for key in ('jet_light', 'jet_heavy'):
    a = flight.Aircraft(aircraft_key=key)
    a.on_ground = False
    a.speed_val = 100.0
    a.gear = 1.0
    ok1, msg1 = a.toggle_gear()
    check('%s 空中按 G 能收' % key, ok1 and a.gear_up_locked, msg1)
    a.gear = 0.0
    ok2, msg2 = a.toggle_gear()
    check('%s 收起状态按 G 能放' % key, ok2 and a.gear_down_locked, msg2)

a = flight.Aircraft(aircraft_key='trainer')
r, msg = a.toggle_gear()
check('螺旋桨机按 G 无效', r is False and a.gear > 0.99, msg)

# 地面上收不起来
a = flight.Aircraft(aircraft_key='jet_light')
a.gear = 1.0
a.on_ground = True
a.speed_val = 50.0
okg, msg = a.toggle_gear()
check('地面上收不起来', (not okg) and a.gear > 0.99, '%s / gear=%.2f' % (msg, a.gear))

# 低速收不起来
a = flight.Aircraft(aircraft_key='jet_light')
a.gear = 1.0
a.on_ground = False
a.speed_val = 3.0
okg, msg = a.toggle_gear()
check('速度太低收不起来', (not okg) and a.gear > 0.99, '%s / gear=%.2f' % (msg, a.gear))

# 但"放下"在任何时候都允许
a = flight.Aircraft(aircraft_key='jet_light')
a.gear = 0.0
a.on_ground = True
a.speed_val = 1.0
okg, msg = a.toggle_gear()
check('地面上也能放下起落架', okg and a.gear_down_locked, msg)

# 状态机跑起来：空中收轮后 gear 会真的变成 0
a = flight.Aircraft(aircraft_key='jet_light')
a.on_ground = False
a.speed_val = 120.0
a.gear = 1.0
a.toggle_gear()
for _ in range(200):
    a.update(1 / 60.0, {'throttle': 0.7}, lambda x, z: 0.0)
check('空中收轮动画跑完', a.gear < 0.01, 'gear=%.2f' % a.gear)

print()
print('  按键检查: %s' % ('全部通过' if ok else '有失败项'))
sys.exit(0 if ok else 1)
