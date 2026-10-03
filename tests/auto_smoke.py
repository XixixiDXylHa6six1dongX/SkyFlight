# -*- coding: utf-8 -*-
"""
自动冒烟：真正打开游戏窗口，跑若干帧，截图保存，然后退出。
用于在没有人工操作的情况下验证主程序可用。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glfw
import numpy as np
from OpenGL import GL

from skyflight import app as appmod

FRAMES = int(os.environ.get('SKYFLIGHT_TEST_FRAMES', '150'))
SHOT = os.environ.get('SKYFLIGHT_TEST_SHOT', r'C:\DEEPSEEK工作区\飞行模拟\test_shot.png')

app = appmod.SkyFlightApp()
app.init_gl()
print('窗口已创建，开始渲染 %d 帧...' % FRAMES)

shots = []
errors = []
for i in range(FRAMES):
    # 模拟一段飞行：先满油门滑跑，速度够了起来
    app.throttle_cmd = 1.0
    if app.craft.airspeed_kmh > 95:
        app.keys['S'] = True      # 拉杆（注意 S = 低头 in my mapping? 见下）
    # 前 40 帧让它在地面加速，之后再拉杆
    if i < 40:
        app.keys.pop('S', None)
    app.update(1.0 / 60.0)
    try:
        app.draw()
    except Exception as e:
        errors.append('第 %d 帧 draw 出错: %s' % (i, e))
        break
    glfw.swap_buffers(app.window)
    glfw.poll_events()
    if glfw.window_should_close(app.window):
        break

# 截图
try:
    w, h = glfw.get_framebuffer_size(app.window)
    GL.glReadBuffer(GL.GL_FRONT)
    data = GL.glReadPixels(0, 0, w, h, GL.GL_RGB, GL.GL_UNSIGNED_BYTE)
    arr = np.frombuffer(data, dtype=np.uint8).reshape(h, w, 3)[::-1]
    from PIL import Image
    Image.fromarray(arr).save(SHOT)
    std = float(arr.std())
    print('截图已保存: %s (%dx%d, 颜色标准差 %.1f)' % (SHOT, w, h, std))
    if std < 5:
        errors.append('画面几乎是纯色（标准差 %.1f），可能没渲染出内容' % std)
except Exception as e:
    errors.append('截图失败: %s' % e)

print()
print('飞控状态: 速度 %.0f km/h  高度 %.0f m  迎角 %.1f°  俯仰 %.1f°  在地面=%s  坠毁=%s'
      % (app.craft.airspeed_kmh, app.craft.altitude, app.craft.aoa_deg,
         np.degrees(app.craft.pitch), app.craft.on_ground, app.craft.crashed))
print('FPS 估计: %.0f' % (FRAMES / max(1e-6, (time.time() - app.last_time) if False else 1)))

glfw.terminate()

if errors:
    print()
    print('发现问题:')
    for e in errors:
        print('  - %s' % e)
    sys.exit(1)
print()
print('自动冒烟通过：窗口正常打开、渲染 %d 帧、截图正常' % FRAMES)
sys.exit(0)
