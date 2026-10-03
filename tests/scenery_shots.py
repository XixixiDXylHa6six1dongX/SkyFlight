# -*- coding: utf-8 -*-
"""拍新地景的实际画面：村庄、风机、混交林"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glfw
import numpy as np
from OpenGL import GL
from PIL import Image, ImageDraw

from skyflight import app as appmod, scenery, terrain, i18n

OUT = r'C:\DEEPSEEK工作区\飞行模拟\shots'
i18n.set_lang(i18n.EN)

# 先找出有风机和村庄的位置
probe = scenery.Scenery(radius=2600.0, cell=52.0)
best_turb = None
best_village = None
for cx in range(-6000, 8001, 1000):
    for cz in range(-6000, 8001, 1000):
        probe.center = None
        probe.update((float(cx), float(cz)))
        if probe.turbine_count >= 6 and best_turb is None:
            best_turb = (cx, cz, probe.turbine_count)
        houses = probe.village_stats.get('house', 0)
        if houses >= 25 and best_village is None:
            best_village = (cx, cz, houses)
    if best_turb and best_village:
        break

print('  风机最多的位置: %s' % (best_turb,))
print('  房子最多的位置: %s' % (best_village,))

g = appmod.SkyFlightApp()
g.init_gl()
c = g.craft


def shot(cx, cz, alt, pitch, yaw_deg, name, note):
    c.pos = np.array([float(cx), float(alt), float(cz)])
    yaw = math.radians(yaw_deg)
    c.yaw = yaw
    c.pitch = pitch
    c.roll = 0.0
    c.speed_val = 80.0
    c.vel = np.array([math.sin(yaw) * 80, 0.0, -math.cos(yaw) * 80])
    c.on_ground = False
    g.throttle_cmd = 0.7
    for _ in range(150):
        g.update(1 / 60.0)
    g.draw()
    GL.glReadBuffer(GL.GL_BACK)
    w, h = glfw.get_framebuffer_size(g.window)
    d = GL.glReadPixels(0, 0, w, h, GL.GL_RGB, GL.GL_UNSIGNED_BYTE)
    a = np.frombuffer(d, dtype=np.uint8).reshape(h, w, 3)[::-1]
    img = Image.fromarray(a)
    ImageDraw.Draw(img).text((620, 700), note, fill=(255, 255, 90))
    p = os.path.join(OUT, name)
    img.save(p)
    print('  已存 %s  (树 %d+%d, 风机 %d, 建筑 %d)' % (
        name, g.scenery.conifer_count, g.scenery.broadleaf_count,
        g.scenery.turbine_count, g.scenery.total_props()))


if best_turb:
    # 相机放低、贴近风电场，斜着看过去
    shot(best_turb[0], best_turb[1] - 700, 460, -0.10, 0,
         'scenery-windfarm.png', 'wind farm on the ridge')
shot(0, 0, 330, -0.14, 30, 'scenery-village.png', 'village + mixed forest')
shot(-900, 900, 240, -0.04, 200, 'scenery-rocks.png', 'rocks on steep slopes')

# 中文界面同一位置
i18n.set_lang(i18n.ZH)
shot(0, 0, 330, -0.14, 30, 'scenery-zh.png', '')

glfw.terminate()
