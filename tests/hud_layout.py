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

# ---------- 关键回归：draw() 必须真的把 HUD 画出来
# 这里的教训：加新绘制代码时很容易把 draw() 末尾的仪表盘那段覆盖掉，
# 而且**不会报任何错** —— 界面就那么安静地消失了（v1.6.0 真实发生过）。
print()
print('  draw() 是否真的调用了仪表盘（防止再次被覆盖）:')
import inspect
g = appmod.SkyFlightApp()
g.init_gl()

# 用 AST 静态检查：draw 函数体里必须出现 draw_hud 调用
import ast
import textwrap
src = inspect.getsource(type(g).draw)
tree = ast.parse(textwrap.dedent(src))
found_call = False
for node in ast.walk(tree):
    if isinstance(node, ast.Call):
        f = node.func
        name = ''
        if isinstance(f, ast.Attribute):
            name = f.attr
        elif isinstance(f, ast.Name):
            name = f.id
        if name == 'draw_hud':
            found_call = True
check('draw() 源码里有 draw_hud 调用', found_call)

# 运行时检查：画一帧之后，画面上必须出现 HUD 的深色面板像素
g.draw()
GL.glReadBuffer(GL.GL_BACK)
w, h = glfw.get_framebuffer_size(g.window)
d = GL.glReadPixels(0, 0, w, h, GL.GL_RGB, GL.GL_UNSIGNED_BYTE)
a = np.frombuffer(d, dtype=np.uint8).reshape(h, w, 3)[::-1]
panel = a[h - 150:h - 40, 10:240]          # 左下角空速面板区域
dark = int(((panel[:, :, 0] < 70) & (panel[:, :, 1] < 80)
            & (panel[:, :, 2] < 90)).sum())
print('     左下角面板区域深色像素 = %d' % dark)
check('画面左下角真的画出了面板', dark > 2000, '%d 个像素' % dark)
check('show_hud 没有被意外关掉', bool(g.show_hud))


def panel_dark():
    """画一帧，返回左下角面板区域的深色像素数"""
    g.draw()
    GL.glReadBuffer(GL.GL_BACK)
    d = GL.glReadPixels(0, 0, w, h, GL.GL_RGB, GL.GL_UNSIGNED_BYTE)
    a = np.frombuffer(d, dtype=np.uint8).reshape(h, w, 3)[::-1]
    reg = a[h - 150:h - 40, 10:240]
    return int(((reg[:, :, 0] < 70) & (reg[:, :, 1] < 80)
                & (reg[:, :, 2] < 90)).sum())


# ---------- 关键回归 2：有粒子的时候 HUD 也必须还在
# 真实教训：曾经有一段重复的 draw_hud 被误放进 _draw_particles() 里。
# 平时 _draw_particles 没粒子就直接 return，所以看不出问题；
# 一旦坠毁产生粒子，那段代码就会执行，却拿不到 fb_w / fb_h → NameError
# → 被 except 吞掉并 show_hud = False → 仪表盘永久消失。
print()
print('  有粒子时（坠毁场景）仪表盘是否还在:')
g.craft.pos = np.array([0.0, 120.0, 200.0])
g.craft.pitch = -0.6
g.craft.speed_val = 90.0
g.craft.vel = np.array([5.0, -25.0, -80.0])
g.craft.on_ground = False
g.craft.crashed = False
g.throttle_cmd = 0.6
for _ in range(300):
    g.update(1 / 60.0)
    if g.craft.crashed:
        break
check('确实坠毁并产生了粒子', bool(g.craft.crashed) and g.particles.count() > 0,
      '粒子 %d 个' % g.particles.count())

dark2 = panel_dark()
check('坠毁时 HUD 没有被关掉', bool(g.show_hud))
check('坠毁时面板仍然画出来', dark2 > 2000, '%d 个像素' % dark2)

# 按 R 重来之后也要还在
g._on_key(g.window, glfw.KEY_R, 0, glfw.PRESS, 0)
g.update(1 / 60.0)
g._on_key(g.window, glfw.KEY_R, 0, glfw.RELEASE, 0)
for _ in range(150):
    g.update(1 / 60.0)
dark3 = panel_dark()
check('按 R 重来后 HUD 还在', bool(g.show_hud) and dark3 > 2000,
      '深色像素 %d' % dark3)

glfw.terminate()

print()
print('  HUD 排版检查: %s' % ('全部通过' if ok else '有失败项'))
sys.exit(0 if ok else 1)
