# -*- coding: utf-8 -*-
"""无头冒烟测试：不开真窗口，检查着色器/网格/物理是否正常"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from skyflight import gfx, shaders, terrain, flight, plane, scenery, specs

ok = True


def check(name, fn):
    global ok
    try:
        fn()
        print('  [OK] %s' % name)
    except Exception as e:
        ok = False
        import traceback
        print('  [FAIL] %s' % name)
        print('     %s' % e)
        traceback.print_exc()


GH = lambda x, z: terrain.height_at(x, z)
FLAT = lambda x, z: 0.0


# ---------- 1) 地形
def t_terrain():
    h = terrain.height_at(0.0, 0.0)
    assert abs(h) < 5.0, '机场高度应接近 0，实际 %s' % h
    hs = [terrain.height_at(x, z) for x, z in
          [(3000, 0), (-4000, 5000), (12000, -8000), (500, 500), (40000, 40000)]]
    assert all(-300 < v < 2500 for v in hs), '高度异常: %s' % hs
    print('     机场=%.2f m，采样=%s' % (h, ['%.0f' % v for v in hs]))


check('地形高度场', t_terrain)


# ---------- 2) 平飞稳定性（最关键）
def t_level_flight():
    a = flight.Aircraft(pos=(0.0, 800.0, 0.0))
    a.throttle = 0.62
    a.vel = np.array([0.0, 0.0, -78.0])
    hist = []
    for i in range(60 * 20):     # 20 秒
        a.update(1 / 60.0, {'pitch': 0.0, 'roll': 0.0, 'yaw': 0.0,
                            'flaps': 0.0, 'throttle': 0.62}, FLAT)
        if i % (60 * 5) == 0:
            hist.append((i / 60.0, a.aoa_deg, math.degrees(a.pitch),
                         a.airspeed_kmh, a.altitude, a.vertical_speed))
    print('     时间  迎角    俯仰    速度     高度    升降率')
    for t, ao, pi, sp, al, vs in hist:
        print('     %4.0fs %6.1f° %6.1f° %6.0f   %7.0f  %6.1f' %
              (t, ao, pi, sp, al, vs))
    assert abs(a.aoa_deg) < 45, '迎角失控: %.1f°' % a.aoa_deg
    assert abs(math.degrees(a.pitch)) < 45, '俯仰失控: %.1f°' % math.degrees(a.pitch)
    assert not any(math.isnan(x) for x in np.concatenate([a.pos, a.vel])), 'NaN'
    assert 40 < a.airspeed_kmh < 500, '速度异常: %.0f' % a.airspeed_kmh


check('平飞稳定性（无输入 20 秒）', t_level_flight)


# ---------- 3) 操纵响应
def t_controls():
    # 拉杆应抬头
    a = flight.Aircraft(pos=(0.0, 1500.0, 0.0))
    a.throttle = 0.7
    a.vel = np.array([0.0, 0.0, -80.0])
    p0 = math.degrees(a.pitch)
    for i in range(60 * 3):
        a.update(1 / 60.0, {'pitch': 1.0, 'roll': 0.0, 'yaw': 0.0,
                            'flaps': 0.0, 'throttle': 0.7}, FLAT)
    p1 = math.degrees(a.pitch)
    print('     拉杆 3 秒：俯仰 %.1f° -> %.1f°  迎角 %.1f°' % (p0, p1, a.aoa_deg))
    assert p1 > p0 + 5, '拉杆没有抬头：%.1f -> %.1f' % (p0, p1)

    # 推杆应低头
    b = flight.Aircraft(pos=(0.0, 1500.0, 0.0))
    b.throttle = 0.7
    b.vel = np.array([0.0, 0.0, -80.0])
    q0 = math.degrees(b.pitch)
    for i in range(60 * 3):
        b.update(1 / 60.0, {'pitch': -1.0, 'roll': 0.0, 'yaw': 0.0,
                            'flaps': 0.0, 'throttle': 0.7}, FLAT)
    q1 = math.degrees(b.pitch)
    print('     推杆 3 秒：俯仰 %.1f° -> %.1f°' % (q0, q1))
    assert q1 < q0 - 5, '推杆没有低头'

    # 右滚
    c = flight.Aircraft(pos=(0.0, 1500.0, 0.0))
    c.throttle = 0.7
    c.vel = np.array([0.0, 0.0, -80.0])
    for i in range(60 * 2):
        c.update(1 / 60.0, {'pitch': 0.0, 'roll': 1.0, 'yaw': 0.0,
                            'flaps': 0.0, 'throttle': 0.7}, FLAT)
    print('     右滚 2 秒：滚转 %.1f°（正=右翼下沉）' % math.degrees(c.roll))
    assert c.roll > math.radians(10), '没有右滚：%.1f°' % math.degrees(c.roll)


check('操纵响应（俯仰/滚转）', t_controls)


# ---------- 4) 失速
def t_stall():
    a = flight.Aircraft(pos=(0.0, 3000.0, 0.0))
    a.throttle = 0.0
    a.vel = np.array([0.0, 0.0, -55.0])
    stall_seen = False
    max_aoa = 0.0
    for i in range(60 * 25):
        a.update(1 / 60.0, {'pitch': 1.0, 'roll': 0.0, 'yaw': 0.0,
                            'flaps': 0.0, 'throttle': 0.0}, FLAT)
        max_aoa = max(max_aoa, a.aoa_deg)
        if a.stalling:
            stall_seen = True
    print('     收油门死拉杆：最大迎角 %.1f°  触发失速=%s  末速 %.0f km/h'
          % (max_aoa, stall_seen, a.airspeed_kmh))
    assert stall_seen, '没能触发失速'


check('失速行为', t_stall)


# ---------- 5) 起飞能力（地面加速能不能离地）
def t_takeoff():
    a = flight.Aircraft(pos=(0.0, 1.0, 1200.0))
    a.vel = np.array([0.0, 0.0, 0.0])
    a.throttle = 1.0
    lifted = False
    for i in range(60 * 30):
        ctrl = {'pitch': 0.55 if a.airspeed_kmh > 70 else 0.0,
                'roll': 0.0, 'yaw': 0.0, 'flaps': 0.5, 'throttle': 1.0}
        a.update(1 / 60.0, ctrl, GH)
        if a.altitude > 6.0:
            lifted = True
            break
    print('     起飞测试：%s，用时 %.1f s，离地高度 %.1f m，速度 %.0f km/h'
          % ('成功离地' if lifted else '没能离地', i / 60.0, a.altitude, a.airspeed_kmh))
    assert lifted, '满油门 30 秒没能起飞'


check('起飞能力', t_takeoff)


# ---------- 6) 几何
def t_mesh_build():
    # 这里只验证顶点数据，不需要 GL 上下文，所以临时替换 gfx.Mesh
    def capture_all(builder):
        """返回本次构建里每个网格的顶点数组（顺序对应创建的先后）"""
        saved = []

        class _Capture:
            def __init__(self, vertices, indices=None):
                a = np.asarray(vertices, dtype=np.float32).reshape(-1, 9)
                saved.append(a)
                self.count = a.shape[0]

        orig = gfx.Mesh
        gfx.Mesh = _Capture
        try:
            builder()
        finally:
            gfx.Mesh = orig
        return saved

    def capture(builder):
        """只取第一个网格（兼容老写法）"""
        return capture_all(builder)[0]

    # 三种机型都检查：返回 [机身, 起落架] 两个网格
    # 注意用 capture 包起来 —— 真正的 build_plane 会创建 GL 网格，需要上下文
    for sp in specs.CATALOG:
        meshes = capture_all(lambda k=sp.key: plane.build_plane(k))
        assert len(meshes) == 2, '%s 应该返回 (机身, 起落架) 两个网格' % sp.key
        v, gv = meshes[0], meshes[1]
        print('     [%s] %s 机身顶点 %d 个，起落架 %d 个' % (
            sp.key, sp.name, v.shape[0], gv.shape[0]))
        assert v.shape[0] > 300, '%s 机身顶点太少: %d' % (sp.key, v.shape[0])
        span = float(v[:, 0].max() - v[:, 0].min())
        length = float(v[:, 2].max() - v[:, 2].min())
        print('           翼展 %.2f m（配置 %.1f），机长 %.2f m（配置 %.1f）' % (
            span, sp.wing_span, length, sp.fuse_len))
        assert abs(span - sp.wing_span) < 2.0, '%s 翼展不对: %.2f' % (sp.key, span)
        assert abs(length - sp.fuse_len) < 3.0, '%s 机长不对: %.2f' % (sp.key, length)
        assert gv.shape[0] >= 60, '%s 起落架顶点太少: %d' % (sp.key, gv.shape[0])
        # 起落架最低点必须和 specs 里声明的 gear_height 一致
        gmin = float(gv[:, 1].min())
        print('           起落架最低点 y=%+.2f（配置 -%.2f）' % (gmin, sp.gear_height))
        assert abs(gmin + sp.gear_height) < 0.06, (
            '%s 起落架高度和 specs 不一致：模型 %.2f vs 配置 %.2f'
            % (sp.key, gmin, sp.gear_height))
        sh = capture(lambda k=sp.key: plane.build_shadow(k))
        assert sh.shape[0] >= 36, '%s 阴影顶点太少' % sp.key

    v = capture(lambda: plane.build_plane('trainer')[0])
    for name, fn in (('跑道', plane.build_runway), ('塔台', plane.build_tower),
                     ('机库', plane.build_hangar)):
        w = capture(fn)
        print('     %s顶点 %d 个' % (name, w.shape[0]))
        assert w.shape[0] >= 36, '%s 顶点太少' % name


check('几何构造', t_mesh_build)


# ---------- 7) OpenGL 真渲染一帧
def t_gl():
    import glfw
    from OpenGL import GL

    if not glfw.init():
        raise RuntimeError('glfw init 失败')
    glfw.window_hint(glfw.VISIBLE, False)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)
    win = glfw.create_window(640, 400, 'smoke', None, None)
    if not win:
        raise RuntimeError('创建窗口失败')
    glfw.make_context_current(win)
    print('     OpenGL %s / %s' % (GL.glGetString(GL.GL_VERSION).decode(),
                                   GL.glGetString(GL.GL_RENDERER).decode()))

    sky = gfx.Shader(shaders.SKY_VS, shaders.SKY_FS, 'sky')
    obj = gfx.Shader(shaders.OBJ_VS, shaders.OBJ_FS, 'obj')
    ter = gfx.Shader(shaders.TERRAIN_VS, shaders.TERRAIN_FS, 'terrain')
    inst = gfx.Shader(shaders.INST_VS, shaders.INST_FS, 'inst')
    wat = gfx.Shader(shaders.INST_VS, shaders.WATER_FS, 'water')
    print('     五个着色器全部编译通过（天空/物体/地形/实例化/水面）')

    pm = plane.build_plane()[0]
    rm = plane.build_runway()
    tm = plane.build_tower()
    tp = terrain.Terrain()
    tp.update((0.0, 0.0))
    print('     双层地形生成成功（近 %d + 远 %d 索引）'
          % (tp.near.count, tp.far.count))

    sc = scenery.Scenery(radius=1600.0, cell=52.0)
    sc.update((0.0, 0.0))
    print('     地景生成：针叶树 %d 棵，阔叶树 %d 棵' % (
        sc.conifer_count, sc.broadleaf_count))
    print('     村庄建筑：%s' % {k: v for k, v in sc.village_stats.items() if v})
    print('     山顶风机：%d 台' % sc.turbine_count)
    sc.upload()
    # 道具网格都要能建成
    n_props = sc.total_props()
    print('     道具实例合计：%d 个' % n_props)
    assert sc.conifer_count + sc.broadleaf_count > 200, '树太少'
    assert n_props > 0, '一个道具都没生成'
    wt = scenery.Water(radius=6000.0, segments=48)
    wt.update((0.0, 0.0))
    wt.upload()
    print('     水面：%d 个三角形' % wt.count)

    GL.glEnable(GL.GL_DEPTH_TEST)
    GL.glViewport(0, 0, 640, 400)
    GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)

    craft = flight.Aircraft(pos=(0.0, 120.0, 900.0))
    cam = np.array([0.0, 128.0, 918.0])
    proj = gfx.perspective(62.0, 1.6, 0.6, 42000.0)
    view = gfx.look_at(cam, craft.pos, (0, 1, 0))
    VP = proj @ view

    # 天空
    GL.glDisable(GL.GL_DEPTH_TEST)
    sky.use()
    sky.set_mat4('uInvVP', np.linalg.inv(VP))
    sky.set_vec3('uCamPos', cam)
    sky.set_vec3('uSunDir', (0.4, 0.6, 0.6))
    sky.set_float('uTime', 1.0)
    sky.set_float('uCloudCover', 0.5)
    GL.glEnable(GL.GL_DEPTH_TEST)

    # 地形
    ter.use()
    ter.set_mat4('uVP', VP)
    ter.set_vec3('uSunDir', (0.4, 0.6, 0.6))
    ter.set_vec3('uCamPos', cam)
    ter.set_vec3('uFogColor', (0.7, 0.78, 0.88))
    ter.set_float('uFogDensity', 0.00007)
    GL.glDisable(GL.GL_CULL_FACE)
    tp.draw(ter)
    GL.glEnable(GL.GL_CULL_FACE)

    # 水面
    wat.use()
    wat.set_mat4('uVP', VP)
    wat.set_vec3('uSunDir', (0.4, 0.6, 0.6))
    wat.set_vec3('uCamPos', cam)
    wat.set_vec3('uFogColor', (0.7, 0.78, 0.88))
    wat.set_float('uFogDensity', 0.00007)
    GL.glEnable(GL.GL_BLEND)
    GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
    GL.glDepthMask(GL.GL_FALSE)
    wt.draw(wat)
    GL.glDepthMask(GL.GL_TRUE)
    GL.glDisable(GL.GL_BLEND)

    # 森林 + 房屋
    inst.use()
    inst.set_mat4('uVP', VP)
    inst.set_vec3('uSunDir', (0.4, 0.6, 0.6))
    inst.set_vec3('uCamPos', cam)
    inst.set_vec3('uFogColor', (0.7, 0.78, 0.88))
    inst.set_float('uFogDensity', 0.00007)
    sc.draw_trees(inst)
    sc.draw_houses(inst)

    # 飞机
    obj.use()
    obj.set_mat4('uVP', VP)
    obj.set_vec3('uSunDir', (0.4, 0.6, 0.6))
    obj.set_vec3('uCamPos', cam)
    obj.set_vec3('uFogColor', (0.7, 0.78, 0.88))
    obj.set_float('uFogDensity', 0.00007)
    m = np.eye(4, dtype=np.float32)
    m[:3, 3] = craft.pos.astype(np.float32)
    obj.set_mat4('uModel', m)
    obj.set_mat3('uNormalMat', np.eye(3, dtype=np.float32))
    pm.draw()
    rm.draw()
    tm.draw()

    err = GL.glGetError()
    if err != 0:
        raise RuntimeError('OpenGL 错误码 %s' % err)
    # 读回像素，确认真的画了东西（不是全黑/全白）
    px = GL.glReadPixels(0, 0, 640, 400, GL.GL_RGB, GL.GL_UNSIGNED_BYTE)
    arr = np.frombuffer(px, dtype=np.uint8).reshape(-1, 3)
    print('     渲染一帧成功（无 GL 错误）')
    print('     画面颜色：均值=%s  最小=%s  最大=%s'
          % (arr.mean(axis=0).round(1), arr.min(axis=0), arr.max(axis=0)))
    assert arr.std() > 8, '画面几乎是纯色，可能没渲染出东西'

    glfw.destroy_window(win)
    glfw.terminate()


check('OpenGL 渲染', t_gl)

print()
print('=' * 62)
print('  冒烟测试: %s' % ('全部通过' if ok else '有失败项'))
print('=' * 62)
sys.exit(0 if ok else 1)
