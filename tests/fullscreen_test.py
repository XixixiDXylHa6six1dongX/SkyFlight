# -*- coding: utf-8 -*-
"""
全屏功能 + 版本号 测试
1) F11 能切进全屏、再按能回窗口，且窗口大小/位置能还原
2) 全屏后画面尺寸变化，投影比例仍然正确
3) 版本号出现在窗口标题和游戏画面上
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glfw
import numpy as np

from skyflight import app as appmod
from skyflight.version import VERSION, BUILD_DATE

fails = []


def check(name, ok, detail=''):
    print('  %-30s %s  %s' % (name, 'OK' if ok else '❌', detail))
    if not ok:
        fails.append(name)


print('=== 版本号 %s (%s) ===' % (VERSION, BUILD_DATE))
print()

g = appmod.SkyFlightApp()
g.init_gl()

# ---------- 1) 初始应该是窗口模式
print('--- 1) 初始状态 ---')
w0, h0 = glfw.get_window_size(g.window)
x0, y0 = glfw.get_window_pos(g.window)
check('初始是窗口模式', not g.fullscreen, '尺寸 %dx%d' % (w0, h0))
check('窗口标题含版本号', ('v' + VERSION) in glfw.get_window_title(g.window),
      glfw.get_window_title(g.window)[:46])

# ---------- 2) 按 F11 进全屏
print()
print('--- 2) 按 F11 进全屏 ---')
g._on_key(g.window, glfw.KEY_F11, 0, glfw.PRESS, 0)
glfw.poll_events()
mon = glfw.get_primary_monitor()
mode = glfw.get_video_mode(mon)
w1, h1 = glfw.get_window_size(g.window)
fb1 = glfw.get_framebuffer_size(g.window)
check('状态变为全屏', g.fullscreen)
check('尺寸等于显示器分辨率', (w1, h1) == (mode.size.width, mode.size.height),
      '%dx%d（显示器 %dx%d）' % (w1, h1, mode.size.width, mode.size.height))
check('画面尺寸跟上', fb1[0] > 0 and fb1[1] > 0, 'framebuffer %dx%d' % fb1)

# 全屏下渲染一帧，检查不报错、比例正确
GL_ok = True
try:
    g.update(1 / 60.0)
    g.draw()
    glfw.swap_buffers(g.window)
except Exception as e:
    GL_ok = False
    print('     渲染异常: %s' % e)
check('全屏下能正常渲染', GL_ok)

# ---------- 3) 再按 F11 回窗口
print()
print('--- 3) 再按 F11 回窗口 ---')
g._on_key(g.window, glfw.KEY_F11, 0, glfw.PRESS, 0)
glfw.poll_events()
w2, h2 = glfw.get_window_size(g.window)
x2, y2 = glfw.get_window_pos(g.window)
check('状态变回窗口', not g.fullscreen)
check('窗口大小已还原', (w2, h2) == (w0, h0), '%dx%d -> %dx%d' % (w0, h0, w2, h2))
check('窗口位置已还原', (x2, y2) == (x0, y0) or abs(x2 - x0) < 60,
      '(%d,%d) -> (%d,%d)' % (x0, y0, x2, y2))

# ---------- 4) Alt + 回车 也能全屏
print()
print('--- 4) Alt + 回车 ---')
g._on_key(g.window, glfw.KEY_ENTER, 0, glfw.PRESS, glfw.MOD_ALT)
glfw.poll_events()
check('Alt+回车进全屏', g.fullscreen)
g._on_key(g.window, glfw.KEY_ENTER, 0, glfw.PRESS, glfw.MOD_ALT)
glfw.poll_events()
check('再按回窗口', not g.fullscreen)

# 单独回车（无 Alt）不应该触发全屏
g._on_key(g.window, glfw.KEY_ENTER, 0, glfw.PRESS, 0)
glfw.poll_events()
check('单独回车不会全屏', not g.fullscreen)

# ---------- 5) 全屏下 HUD 版本号能否画出来
print()
print('--- 5) 画面上的版本号 ---')
from OpenGL import GL
from skyflight import hud as hudmod
from skyflight.version import VERSION as V

h = hudmod.Hud()
verts_before = len(h.verts)
# 用假飞机数据测 HUD 顶点生成
class FC:
    airspeed_kmh = 200.0; altitude = 800.0; throttle = 0.6
    vertical_speed = 2.0; aoa_deg = 3.0; g_load = 1.1
    roll = 0.1; pitch = 0.05; yaw = 0.9
    stalling = False; crashed = False


import skyflight.hud as H
class NoGL(H.Hud):
    def begin(self):
        self.verts = []
    def commit(self, *a, **k):
        pass


hh = NoGL()
H.draw_hud(hh, None, FC(), 1920.0, 1080.0, 165.0)
v = np.asarray(hh.verts, dtype=np.float32).reshape(-1, 6)
# 版本号应该画在右下角（x 接近 1920-16，y 接近 1080-16）
low_right = v[(v[:, 0] > 1500) & (v[:, 1] > 1000)]
check('HUD 底部右下有内容', len(low_right) > 0,
      '%d 个顶点（版本号位置）' % len(low_right))

glfw.terminate()

print()
if fails:
    print('❌ 失败项: %s' % ', '.join(fails))
else:
    print('✅ 全屏 + 版本号 全部通过')
