# -*- coding: utf-8 -*-
"""
机型外观图 + 起落架收放对比图

输出：
  shots/aircraft-lineup.png    三种机型并排（斜后视）
  shots/gear-retract.png       起落架 放下 / 收起中途 / 收起 三张对比
"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glfw
import numpy as np
from OpenGL import GL
from PIL import Image, ImageDraw

from skyflight import app as appmod, gfx, plane, specs

OUT = r'C:\DEEPSEEK工作区\飞行模拟\shots'


def render(app, mesh_body, mesh_gear, R, pos, cam_off, tgt_off, w, h,
           proj_deg=42.0, gear=1.0, bg=(0.20, 0.26, 0.34)):
    """把机身+起落架画到离屏，返回 PIL 图"""
    cam = np.asarray(pos, dtype=np.float64) + np.asarray(cam_off, dtype=np.float64)
    tgt = np.asarray(pos, dtype=np.float64) + np.asarray(tgt_off, dtype=np.float64)
    proj = gfx.perspective(proj_deg, w / float(h), 0.3, 60000.0)
    VP = proj @ gfx.look_at(cam, tgt, np.array([0.0, 1.0, 0.0]))
    GL.glViewport(0, 0, w, h)
    GL.glClearColor(bg[0], bg[1], bg[2], 1.0)
    GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
    sh = app.obj_shader
    sh.use()
    sh.set_mat4('uVP', VP)
    sh.set_vec3('uSunDir', (0.42, 0.72, 0.55))
    sh.set_vec3('uCamPos', cam)
    sh.set_vec3('uFogColor', app.fog_color)
    sh.set_float('uFogDensity', 0.0)
    model = np.eye(4, dtype=np.float32)
    model[:3, :3] = np.asarray(R, dtype=np.float32)
    model[:3, 3] = np.asarray(pos, dtype=np.float32)
    sh.set_mat4('uModel', model)
    sh.set_mat3('uNormalMat', model[:3, :3])
    mesh_body.draw()
    if gear > 0.02:
        g = max(0.02, gear)
        gl = np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, g, 0.0, -0.55 * (1.0 - gear)],
            [0.0, 0.0, 1.0, 0.30 + 0.70 * gear],
            [0.0, 0.0, 0.0, 1.0],
        ], dtype=np.float32)
        gm = model @ gl
        sh.set_mat4('uModel', gm)
        sh.set_mat3('uNormalMat', gm[:3, :3])
        mesh_gear.draw()
    GL.glReadBuffer(GL.GL_BACK)
    d = GL.glReadPixels(0, 0, w, h, GL.GL_RGB, GL.GL_UNSIGNED_BYTE)
    a = np.frombuffer(d, dtype=np.uint8).reshape(h, w, 3)[::-1]
    return Image.fromarray(a)


def main():
    app = appmod.SkyFlightApp()
    app.init_gl()
    w, h = glfw.get_framebuffer_size(app.window)

    # ---------------- 三种机型并排
    tiles = []
    for sp in specs.CATALOG:
        body, gear = plane.build_plane(sp.key)
        R = gfx.euler_to_matrix(0.0, math.radians(35.0), 0.0)
        # 相机按机型大小缩放，保证画面里大小一致
        k = max(1.0, sp.fuse_len / 10.0)
        # 前侧上方视角：这样能看到机头、螺旋桨/进气口、发动机短舱
        fwd = R @ np.array([0.0, 0.0, -1.0])
        right = R @ np.array([1.0, 0.0, 0.0])
        cam_off = fwd * (15.0 * k) + right * (9.0 * k) + np.array([0.0, 5.5 * k, 0.0])
        img = render(app, body, gear, R, (0.0, 0.0, 0.0), cam_off,
                     fwd * (1.0 * k), w, h, gear=1.0)
        dr = ImageDraw.Draw(img)
        dr.text((16, 16), '%s  /  %s' % (sp.name, sp.name_en), fill=(255, 255, 90))
        dr.text((16, 36), 'span %.1f m  length %.1f m  mass %.0f kg  thrust %.0f N' % (
            sp.wing_span, sp.fuse_len, sp.mass, sp.max_thrust), fill=(210, 220, 235))
        dr.text((16, 56), 'gear %s' % ('retractable' if sp.gear_retract else 'fixed'),
                fill=(210, 220, 235))
        tiles.append(img)
        print('  已渲染 %s' % sp.name)

    tw, th = tiles[0].size
    sheet = Image.new('RGB', (tw, th * len(tiles)))
    for i, t in enumerate(tiles):
        sheet.paste(t, (0, i * th))
    sheet = sheet.resize((tw * 2 // 3, th * len(tiles) * 2 // 3))
    p1 = os.path.join(OUT, 'aircraft-lineup.png')
    sheet.save(p1)
    print('  机型并排图: %s' % p1)

    # ---------------- 起落架收放对比（用双发涡喷，起落架最明显）
    sp = specs.get('jet_heavy')
    body, gear = plane.build_plane(sp.key)
    R = gfx.euler_to_matrix(0.0, math.radians(28.0), 0.0)
    k = max(1.0, sp.fuse_len / 10.0)
    fwd = R @ np.array([0.0, 0.0, -1.0])
    right = R @ np.array([1.0, 0.0, 0.0])
    cam_off = fwd * (16.0 * k) + right * (11.0 * k) + np.array([0.0, 3.5 * k, 0.0])
    gtiles = []
    for gearv, label in ((1.0, 'GEAR DOWN  起落架放下'), (0.5, 'RETRACTING  收起中'),
                         (0.0, 'GEAR UP  起落架收起')):
        img = render(app, body, gear, R, (0.0, 0.0, 0.0), cam_off,
                     fwd * (1.0 * k), w, h, gear=gearv)
        dr = ImageDraw.Draw(img)
        dr.text((16, 16), label, fill=(255, 255, 90))
        gtiles.append(img)
    sheet2 = Image.new('RGB', (tw, th * len(gtiles)))
    for i, t in enumerate(gtiles):
        sheet2.paste(t, (0, i * th))
    sheet2 = sheet2.resize((tw * 2 // 3, th * len(gtiles) * 2 // 3))
    p2 = os.path.join(OUT, 'gear-retract.png')
    sheet2.save(p2)
    print('  起落架对比图: %s' % p2)

    glfw.terminate()


if __name__ == '__main__':
    main()
