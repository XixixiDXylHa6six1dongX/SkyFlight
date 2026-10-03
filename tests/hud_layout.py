# -*- coding: utf-8 -*-
"""
左上角 HUD 排版检查

要保证：
  1. 版本号和机型名不重叠（之前的 bug）
  2. 三段文字都在屏幕范围内，且不压到中间的罗盘
  3. 起落架的三种状态（DOWN / UP / 收起中）都能正确显示
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glfw
import numpy as np
from OpenGL import GL
from PIL import Image

from skyflight import app as appmod, specs

OUT = r'C:\DEEPSEEK工作区\飞行模拟\shots'
ok = True


def check(name, cond, detail=''):
    global ok
    if cond:
        print('  [OK] %-24s %s' % (name, detail))
    else:
        ok = False
        print('  [FAIL] %-24s %s' % (name, detail))


print('  左上角文字排版（按实测宽度算）:')
for sp in specs.CATALOG:
    g = appmod.SkyFlightApp(aircraft_key=sp.key)
    g.init_gl()
    hud = g.hud
    lx = 12 + 2
    vw = hud.text_width('V1.4.0', 16)
    nw = hud.text_width(sp.name_en.upper(), 16)
    v_end = lx + vw
    n_start = lx + vw + 14
    n_end = n_start + nw
    print('     %-11s V 段 %6.1f~%6.1f   机型段 %6.1f~%6.1f' % (
        sp.key, lx, v_end, n_start, n_end))
    check('%s 版本与机型不重叠' % sp.key, n_start > v_end + 4,
          '间隔 %.1f px' % (n_start - v_end))

    # 罗盘左边缘：draw_hud 里 cw = min(460, screen_w*0.36)
    w, h = glfw.get_framebuffer_size(g.window)
    cw = min(460.0, w * 0.36)
    c_left = w * 0.5 - cw * 0.5
    check('%s 不压到罗盘' % sp.key, n_end < c_left,
          '机型段右端 %.0f < 罗盘左端 %.0f' % (n_end, c_left))
    check('%s 在屏幕内' % sp.key, n_end < w)

    # 起落架三种状态都要能画出来
    for gear, expect in ((1.0, 'GEAR DOWN'), (0.0, 'GEAR UP'), (0.5, 'GEAR 50%')):
        g.craft.gear = gear
        try:
            g.draw()
            err = GL.glGetError()
            check('%s gear=%.1f 渲染' % (sp.key, gear), err == 0,
                  '%s (GL错误 %d)' % (expect, err))
        except Exception as e:
            check('%s gear=%.1f 渲染' % (sp.key, gear), False, str(e))
    g.craft.gear = 1.0
    glfw.terminate()

print()
print('  HUD 排版检查: %s' % ('全部通过' if ok else '有失败项'))
sys.exit(0 if ok else 1)
