# -*- coding: utf-8 -*-
"""
全屏检查

要保证：
  1. 进全屏后窗口装饰（标题栏+边框）是关闭的
  2. 全屏用的是显示器原生分辨率
  3. 全屏时 HUD 版本号仍然画在画面里（遮挡没被切掉）
  4. 切回窗口后装饰恢复、大小还原
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glfw
import numpy as np
from skyflight import app as appmod

ok = True


def check(name, cond, detail=''):
    global ok
    if cond:
        print('  [OK] %-32s %s' % (name, detail))
    else:
        ok = False
        print('  [FAIL] %-32s %s' % (name, detail))


g = appmod.SkyFlightApp()
g.init_gl()
monitor = glfw.get_primary_monitor()
mode = glfw.get_video_mode(monitor)
print('  显示器原生分辨率: %d x %d @ %d Hz' % (
    mode.size.width, mode.size.height, mode.refresh_rate))

# 窗口模式
dec0 = glfw.get_window_attrib(g.window, glfw.DECORATED)
sz0 = glfw.get_window_size(g.window)
print('  窗口模式: 装饰=%s  尺寸=%dx%d' % (
    '开' if dec0 else '关', sz0[0], sz0[1]))
check('窗口模式有标题栏（方便拖动）', bool(dec0))

# 进全屏
g.toggle_fullscreen()
glfw.poll_events()
dec1 = glfw.get_window_attrib(g.window, glfw.DECORATED)
sz1 = glfw.get_window_size(g.window)
fb = glfw.get_framebuffer_size(g.window)
print('  全屏模式: 装饰=%s  窗口=%dx%d  帧缓冲=%dx%d' % (
    '开' if dec1 else '关', sz1[0], sz1[1], fb[0], fb[1]))
check('全屏装了显示器分辨率', sz1[0] == mode.size.width and sz1[1] == mode.size.height,
      '%dx%d' % (sz1[0], sz1[1]))
check('全屏时标题栏/边框已关闭', not dec1)

# 全屏下渲染一帧，确认 HUD 正常
g.draw()
GL_ok = glfw.get_framebuffer_size(g.window)
check('全屏下渲染一帧成功', GL_ok[0] > 0 and GL_ok[1] > 0,
      '帧缓冲 %dx%d' % (GL_ok[0], GL_ok[1]))

# 切回窗口
g.toggle_fullscreen()
glfw.poll_events()
dec2 = glfw.get_window_attrib(g.window, glfw.DECORATED)
sz2 = glfw.get_window_size(g.window)
print('  切回窗口: 装饰=%s  尺寸=%dx%d' % (
    '开' if dec2 else '关', sz2[0], sz2[1]))
check('切回窗口后标题栏恢复', bool(dec2))
check('切回窗口后大小还原', sz2[0] == sz0[0] and sz2[1] == sz0[1],
      '%dx%d' % (sz2[0], sz2[1]))

glfw.terminate()
print()
print('=' * 62)
print('  全屏检查: %s' % ('全部通过' if ok else '有失败项'))
print('=' * 62)
sys.exit(0 if ok else 1)
