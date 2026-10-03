# -*- coding: utf-8 -*-
"""
SkyFlight 主程序
运行：python -m skyflight
"""
import math
import sys
import time

import glfw
import numpy as np
from OpenGL import GL

from . import (gfx, shaders, sky, terrain, flight, plane, scenery, specs,
               i18n, sound as soundmod, particles as particlesmod,
               hud as hudmod)
from .version import VERSION, BUILD_DATE


WINDOW_W, WINDOW_H = 1280, 760
APP_NAME = 'SkyFlight 飞行模拟器'

# 飞机模型最低点（起落架轮胎底）在局部坐标的 Y 值。
# 机身原点离地高度 = WHEEL_DROP
WHEEL_DROP = 1.07

# 出生点：停在跑道中段偏南，机头朝北（-Z）。
# 放在 z=+560 而不是跑道最南端(700)：
#   1) 留出足够滑跑距离
#   2) 追尾相机朝前看 26 m，这样前方能看见长长的跑道，视野自然
SPAWN_ON_RUNWAY = True
RUNWAY_START = (0.0, 0.0, 560.0)

# 出生时给轮胎留的离地间隙（米）。
# 停机时轮胎底 = 地面高度 + 这个值，所以飞机是"停在跑道面之上一点点"，
# 一眼能看出轮胎和跑道之间有缝，不会像陷进地里。
SPAWN_CLEARANCE = 0.25


def ground_at(x, z):
    """飞机能落脚的地面高度（含跑道面和上面的标线）"""
    return plane.surface_height(x, z, terrain.height_at(x, z))


def spawn_position(spec=None):
    """返回出生位置：轮胎底 = 地面 + SPAWN_CLEARANCE

    注意不要再写"地面 + gear_height"这种刚好贴地的算法 ——
    刚好贴地时轮胎会插进跑道标线（标线是凸起的），看着就是陷进地里。
    """
    x, _, z = RUNWAY_START
    sp = spec if spec is not None else specs.DEFAULT
    ground = ground_at(x, z)
    # 模型最低点（轮胎底）在局部坐标 -gear_height，所以机身原点 = 轮胎底 + gear_height
    wheel_bottom = ground + SPAWN_CLEARANCE
    return np.array([x, wheel_bottom + sp.gear_height, z], dtype=np.float64)

# ---------------------------------------------------------------- 按键名表
# 注意：glfw.get_key_name() 对方向键、Shift、Ctrl、Esc 等"特殊键"返回 None，
# 只靠它会导致这些键完全失效。所以这里用键码自己查表。
KEY_NAMES = {
    glfw.KEY_SPACE: 'SPACE',
    glfw.KEY_ESCAPE: 'ESCAPE',
    glfw.KEY_ENTER: 'ENTER',
    glfw.KEY_TAB: 'TAB',
    glfw.KEY_BACKSPACE: 'BACKSPACE',
    glfw.KEY_UP: 'UP',
    glfw.KEY_DOWN: 'DOWN',
    glfw.KEY_LEFT: 'LEFT',
    glfw.KEY_RIGHT: 'RIGHT',
    glfw.KEY_LEFT_SHIFT: 'LEFT_SHIFT',
    glfw.KEY_RIGHT_SHIFT: 'RIGHT_SHIFT',
    glfw.KEY_LEFT_CONTROL: 'LEFT_CONTROL',
    glfw.KEY_RIGHT_CONTROL: 'RIGHT_CONTROL',
    glfw.KEY_LEFT_ALT: 'LEFT_ALT',
    glfw.KEY_RIGHT_ALT: 'RIGHT_ALT',
    glfw.KEY_INSERT: 'INSERT',
    glfw.KEY_DELETE: 'DELETE',
    glfw.KEY_HOME: 'HOME',
    glfw.KEY_END: 'END',
    glfw.KEY_PAGE_UP: 'PAGE_UP',
    glfw.KEY_PAGE_DOWN: 'PAGE_DOWN',
    glfw.KEY_KP_0: 'KP_0', glfw.KEY_KP_1: 'KP_1', glfw.KEY_KP_2: 'KP_2',
    glfw.KEY_KP_3: 'KP_3', glfw.KEY_KP_4: 'KP_4', glfw.KEY_KP_5: 'KP_5',
    glfw.KEY_KP_6: 'KP_6', glfw.KEY_KP_7: 'KP_7', glfw.KEY_KP_8: 'KP_8',
    glfw.KEY_KP_9: 'KP_9',
}
# 字母和数字键（A-Z / 0-9）也直接建表，避免依赖 get_key_name
for _c in range(ord('A'), ord('Z') + 1):
    KEY_NAMES[getattr(glfw, 'KEY_%s' % chr(_c))] = chr(_c)
for _d in range(0, 10):
    KEY_NAMES[getattr(glfw, 'KEY_%d' % _d)] = str(_d)
    KEY_NAMES[getattr(glfw, 'KEY_KP_%d' % _d)] = 'KP_%d' % _d


def key_name(key, scancode=0):
    """把 GLFW 键码转成名字。优先查自己的表，兜底用 glfw.get_key_name()。"""
    n = KEY_NAMES.get(key)
    if n:
        return n
    try:
        s = glfw.get_key_name(key, scancode)
        return s.upper() if s else None
    except Exception:
        return None

# ---------------------------------------------------------------- 相机
class Camera:
    def __init__(self):
        self.mode = 1          # 0 驾驶舱, 1 追尾, 2 环绕
        self.pos = np.array([0.0, 135.0, 915.0])
        self.target = np.array([0.0, 120.0, 900.0])
        self.orbit_yaw = 0.6
        self.orbit_pitch = 0.25
        self.orbit_dist = 24.0
        self.smooth = np.array([0.0, 135.0, 915.0])

    def update(self, craft, mouse, dt):
        if self.mode == 0:
            # 驾驶舱视角
            fwd, right, up, R = craft.basis()
            eye = craft.pos + R @ np.array([0.0, 0.62, 0.55])
            look = eye + fwd * 12.0 + up * 0.4
            self.pos = eye
            self.target = look
        elif self.mode == 1:
            # 追尾：相机拉远，避免近距离透视畸变把飞机拉变形
            fwd, right, up, R = craft.basis()
            back = 26.0 + craft.speed * 0.10
            up_off = 7.5
            desired = craft.pos - fwd * back + np.array([0.0, up_off, 0.0])
            k = min(1.0, dt * 4.5)
            self.smooth = self.smooth + (desired - self.smooth) * k
            self.pos = self.smooth
            self.target = craft.pos + fwd * 26.0 + np.array([0.0, 1.5, 0.0])
        else:
            # 环绕：鼠标拖动控制
            self.orbit_yaw += mouse.get('dx', 0.0) * 0.01
            self.orbit_pitch += mouse.get('dy', 0.0) * 0.01
            self.orbit_pitch = max(-0.2, min(1.35, self.orbit_pitch))
            d = self.orbit_dist + craft.speed * 0.03
            cp = math.cos(self.orbit_pitch)
            off = np.array([
                math.sin(self.orbit_yaw) * cp * d,
                math.sin(self.orbit_pitch) * d + 1.5,
                math.cos(self.orbit_yaw) * cp * d,
            ])
            self.pos = craft.pos + off
            self.target = craft.pos

        # 防止相机钻进地面（地面高度要含跑道面）
        gh = ground_at(self.pos[0], self.pos[2])
        if self.pos[1] < gh + 2.2:
            self.pos[1] = gh + 2.2


# ---------------------------------------------------------------- 主程序
class SkyFlightApp:
    def __init__(self, aircraft_key=None):
        self.window = None
        self.keys = {}
        self.mouse = {'dx': 0.0, 'dy': 0.0, 'x': 0.0, 'y': 0.0, 'left': False, 'right': False}
        self.aircraft_key = aircraft_key or specs.DEFAULT.key
        self.craft = flight.Aircraft(aircraft_key=self.aircraft_key)
        self.camera = Camera()
        # 出生在跑道上（停住，需要自己加油门滑跑起飞）
        if SPAWN_ON_RUNWAY:
            self._place_on_runway()
        self.controls = flight.Controls()
        self.gear_key_prev = False
        self.time = 0.0
        self.paused = False
        self.show_help = True
        self.last_time = time.time()
        self.fps = 0.0
        self.frame_count = 0
        self.fps_timer = 0.0
        self.title_timer = 0.0
        self.terrain_patch = None
        self.plane_mesh = None
        self.gear_mesh = None
        self.runway_mesh = None
        self.runway_paint_mesh = None
        self.tower_mesh = None
        self.sky_shader = None
        self.obj_shader = None
        self.terrain_shader = None
        self.sky_quad = None
        self.throttle_cmd = 0.0
        self.sun_dir = np.array([0.42, 0.62, 0.66])
        self.sun_dir = self.sun_dir / np.linalg.norm(self.sun_dir)
        self.fog_density = 0.00026
        self.fog_color = np.array([0.68, 0.76, 0.88])
        self.cloud_cover = 0.52
        # 全屏状态
        self.fullscreen = False
        self.window_rect = None      # 进全屏前的窗口位置和大小
        # 启动时可加 --fullscreen 直接全屏
        self.start_fullscreen = '--fullscreen' in sys.argv or '-f' in sys.argv
        # 启动时可加 --aircraft=jet_light 直接选机型
        for a in sys.argv[1:]:
            if a.startswith('--aircraft='):
                self.aircraft_key = specs.get(a.split('=', 1)[1]).key
                self.craft = flight.Aircraft(aircraft_key=self.aircraft_key)
                if SPAWN_ON_RUNWAY:
                    self._place_on_runway()

        # ---- 音效（--no-sound / -q 关闭；打不开设备也会自动静音）
        self.sound_on = not ('--no-sound' in sys.argv or '-q' in sys.argv)
        self.sound = soundmod.SilentSound()

        # ---- 粒子特效（爆炸、扬尘、轮胎烟、凝结尾）
        self.particles = None
        self.contrail_timer = 0.0
        self.touchdown_prev = True
        self.hit_cooldown = 0.0
        self.crash_smoke_timer = 0.0
        self.particle_shader = None

    # ------------------------------------------------ 机型 / 停机
    def _place_on_runway(self):
        """把飞机放到跑道上，并按当前机型的起落架高度确定停机高度

        轮胎底 = 地面 + SPAWN_CLEARANCE（留一点离地间隙，不插进标线里）
        """
        sp = self.craft.spec
        x, _, z = RUNWAY_START
        ground = ground_at(x, z)
        p0 = np.array([x, ground + SPAWN_CLEARANCE + sp.gear_height, z],
                      dtype=np.float64)
        c = self.craft
        c.pos = p0.copy()
        c.pitch = c.roll = c.yaw = 0.0
        c.p = c.q = c.r = 0.0
        c.alpha = math.radians(2.0)
        c.aoa_deg = 2.0
        c.stalling = False
        c.crashed = False
        c.crash_timer = 0.0
        c.gear = 1.0            # 停机时一定放下
        c.gear_up_locked = False
        c.gear_down_locked = False
        # 关键：先标成"还没接地"。
        # 出生点故意比跑道面高 SPAWN_CLEARANCE，如果这里就写 on_ground=True，
        # 物理的地面吸附（只在空中生效）不会把它压下来，飞机就会一直悬在
        # 跑道上方 25 cm —— 看着像浮空。标成未接地后它会在 0.2 秒内
        # 自己轻轻落到跑道上，之后就正常贴地滑跑。
        # 25 cm 的自由落体速度约 2.2 m/s，远低于 19 m/s 的坠毁阈值，不会摔。
        c.on_ground = False
        c.vel = np.zeros(3)
        c.speed_val = 0.0
        c.throttle = 0.0
        c.alpha = math.radians(2.0)
        c.pitch = 0.0
        c.roll = 0.0
        self.camera.pos = p0 + np.array([0.0, 6.0, 30.0])
        self.camera.target = p0 + np.array([0.0, 1.0, -20.0])
        self.camera.smooth = self.camera.pos.copy()
        return p0

    def set_aircraft(self, key):
        """换机型：重建模型和飞行参数，回到跑道上"""
        if key == self.aircraft_key:
            return
        self.aircraft_key = key
        self.craft = flight.Aircraft(aircraft_key=key)
        self.plane_mesh, self.gear_mesh = plane.build_plane(key)
        self.shadow_mesh = plane.build_shadow(key)
        self._place_on_runway()
        print('  [aircraft] %s' % (i18n.t('msg.aircraft') % (
            self.craft.spec.name, self.craft.spec.name_en)))

    def next_aircraft(self):
        self.set_aircraft(specs.next_key(self.aircraft_key))

    # ------------------------------------------------ 初始化
    def init_gl(self):
        if not glfw.init():
            raise RuntimeError('GLFW 初始化失败')
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)
        glfw.window_hint(glfw.SAMPLES, 4)
        self.window = glfw.create_window(WINDOW_W, WINDOW_H,
                                         '%s  v%s' % (APP_NAME, VERSION),
                                         None, None)
        if not self.window:
            raise RuntimeError('创建窗口失败（可能显卡不支持 OpenGL 3.3）')
        glfw.make_context_current(self.window)
        glfw.swap_interval(1)

        glfw.set_key_callback(self.window, self._on_key)
        glfw.set_mouse_button_callback(self.window, self._on_mouse_button)
        glfw.set_cursor_pos_callback(self.window, self._on_mouse_move)

        # 启动参数 --fullscreen / -f 时直接进全屏
        if self.start_fullscreen:
            self.toggle_fullscreen()

        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_CULL_FACE)
        GL.glCullFace(GL.GL_BACK)
        GL.glEnable(GL.GL_MULTISAMPLE)
        GL.glClearColor(0.55, 0.70, 0.88, 1.0)

        self.sky_shader = gfx.Shader(sky.SKY_VS, sky.SKY_FS, 'sky')
        self.obj_shader = gfx.Shader(shaders.OBJ_VS, shaders.OBJ_FS, 'obj')
        self.terrain_shader = gfx.Shader(shaders.TERRAIN_VS, shaders.TERRAIN_FS, 'terrain')
        self.inst_shader = gfx.Shader(shaders.INST_VS, shaders.INST_FS, 'inst')
        self.water_shader = gfx.Shader(shaders.WATER_VS, shaders.WATER_FS, 'water')
        # 粒子用专门的 billboard 着色器（方片要展开到相机平面里）
        self.particle_shader = gfx.Shader(shaders.PARTICLE_VS, shaders.PARTICLE_FS,
                                         'particle')
        # 粒子池（爆炸/扬尘/烟）
        self.particles = particlesmod.Particles()
        # 音效：GL 就绪后再启动（避免拖慢窗口创建）
        if self.sound_on:
            self.sound = soundmod.Sound()
            if self.sound.ready:
                print('  [音效] 已启动（%d Hz 混音）' % soundmod.RATE)
            else:
                print('  [音效] 不可用，已静音：%s' % (self.sound.error or '未知'))
        self.hud_shader = hudmod.make_hud_shader()
        self.hud = hudmod.Hud()
        self.show_hud = True
        self.show_scenery = True

        self.plane_mesh, self.gear_mesh = plane.build_plane(self.aircraft_key)
        self.shadow_mesh = plane.build_shadow(self.aircraft_key)
        self.runway_mesh, self.runway_paint_mesh = plane.build_runway_parts()
        self.tower_mesh = plane.build_tower()
        # 双层地形：近处细、远处大范围
        self.terrain_patch = terrain.Terrain()
        # 成片地景：森林 + 湖面 + 路边房屋
        self.scenery = scenery.Scenery(radius=2600.0, cell=40.0)
        self.water = scenery.Water(radius=16000.0, segments=72)
        self.scenery_pending = True      # 首帧立即生成一次

        # 全屏四边形
        quad = np.array([
            -1, -1, 0, 1, -1, 0, 1, 1, 0,
            -1, -1, 0, 1, 1, 0, -1, 1, 0,
        ], dtype=np.float32)
        verts = np.zeros((6, 9), dtype=np.float32)
        verts[:, 0:3] = quad.reshape(6, 3)
        self.sky_quad = gfx.Mesh(verts.reshape(-1))

    # ------------------------------------------------ 全屏
    def toggle_fullscreen(self):
        """在窗口和全屏之间切换

        全屏时显式关掉窗口装饰（标题栏 + 边框），保证看不到那圈窗口条子。
        只靠 set_window_monitor 在部分 Windows 版本上仍会残留一条标题栏。
        """
        monitor = glfw.get_primary_monitor()
        if monitor is None:
            return
        if self.fullscreen:
            # 回到窗口模式：先恢复装饰和大小，再还原位置
            glfw.set_window_attrib(self.window, glfw.DECORATED, True)
            glfw.set_window_monitor(self.window, None, 100, 80, WINDOW_W, WINDOW_H, 0)
            if self.window_rect is not None:
                x, y, w, h = self.window_rect
                glfw.set_window_pos(self.window, x, y)
                glfw.set_window_size(self.window, w, h)
            self.fullscreen = False
        else:
            # 记住当前窗口位置和大小
            try:
                x, y = glfw.get_window_pos(self.window)
                w, h = glfw.get_window_size(self.window)
                self.window_rect = (int(x), int(y), int(w), int(h))
            except Exception:
                self.window_rect = None
            # 用显示器原生分辨率进全屏（最清晰，不拉伸）
            mode = glfw.get_video_mode(monitor)
            glfw.set_window_monitor(self.window, monitor, 0, 0,
                                   mode.size.width, mode.size.height,
                                   mode.refresh_rate)
            # 关键：再明确关掉装饰，确保标题栏/边框彻底消失
            glfw.set_window_attrib(self.window, glfw.DECORATED, False)
            self.fullscreen = True
        # 全屏切换会改变画面尺寸，重新读取一次，避免第一帧比例不对
        glfw.poll_events()

    def _on_key(self, win, key, scancode, action, mods):
        name = key_name(key, scancode)
        if action == glfw.PRESS:
            if name:
                self.keys[name] = True
            self._on_key_press(key, name, mods)
        elif action == glfw.RELEASE:
            if name:
                self.keys[name] = False
        elif action == glfw.REPEAT:
            # 长按方向键等，保持按下状态
            if name:
                self.keys[name] = True

    def _on_key_press(self, key, name, mods=0):
        n = (name or '').upper()
        # 全屏：F11，或 Alt + 回车
        if key == glfw.KEY_F11:
            self.toggle_fullscreen()
            return
        if key in (glfw.KEY_ENTER, glfw.KEY_KP_ENTER) and (mods & glfw.MOD_ALT):
            self.toggle_fullscreen()
            return
        if n == 'C':
            self.camera.mode = (self.camera.mode + 1) % 3
        elif n == 'V':
            # 换机型
            self.next_aircraft()
        elif n == 'L':
            # 中英文界面切换
            self.toggle_language()
        elif n == 'N':
            # 音效开关
            self.toggle_sound()
        elif n == 'G':
            # 收起落架 / 放起落架（安全检查放在 Aircraft.toggle_gear 里）
            # toggle_gear 返回的是 i18n 键，这里再翻译成当前语言
            accepted, msg_key = self.craft.toggle_gear()
            print('  [gear] %s' % i18n.t(msg_key))
        elif n == 'R':
            # 重来：回到跑道起点，停住
            if SPAWN_ON_RUNWAY:
                self._place_on_runway()
                self.controls.flaps = 0.0
            else:
                self.craft.reset((0.0, 120.0, 900.0))
                self.camera.smooth = self.craft.pos + np.array([0.0, 15.0, 16.0])
        elif n == 'P':
            self.paused = not self.paused
        elif n == 'H':
            self.show_help = not self.show_help
        elif n == 'M':
            self.controls.mouse_mode = not self.controls.mouse_mode
            if self.controls.mouse_mode and self.camera.mode != 2:
                glfw.set_input_mode(self.window, glfw.CURSOR,
                                    glfw.CURSOR_DISABLED)
            else:
                glfw.set_input_mode(self.window, glfw.CURSOR, glfw.CURSOR_NORMAL)
        elif n == 'F':
            self.controls.flaps = 0.0 if self.controls.flaps > 0.5 else 1.0
        elif n in ('ESCAPE', 'ESC'):
            # 如果鼠标被锁定，先解锁
            if glfw.get_input_mode(self.window, glfw.CURSOR) == glfw.CURSOR_DISABLED:
                glfw.set_input_mode(self.window, glfw.CURSOR, glfw.CURSOR_NORMAL)
                self.controls.mouse_mode = False
            else:
                glfw.set_window_should_close(self.window, True)

    def _on_mouse_button(self, win, button, action, mods):
        state = action == glfw.PRESS
        if button == glfw.MOUSE_BUTTON_LEFT:
            self.mouse['left'] = state
        elif button == glfw.MOUSE_BUTTON_RIGHT:
            self.mouse['right'] = state

    def _on_mouse_move(self, win, x, y):
        self.mouse['dx'] += x - self.mouse['x']
        self.mouse['dy'] += y - self.mouse['y']
        self.mouse['x'] = x
        self.mouse['y'] = y

    # ------------------------------------------------ 每帧逻辑
    def update(self, dt):
        self.time += dt

        # 油门
        if self.keys.get('Z'):
            self.throttle_cmd = 1.0
        if self.keys.get('X'):
            self.throttle_cmd = 0.0
        if self.keys.get('LEFT_SHIFT') or self.keys.get('RIGHT_SHIFT'):
            self.throttle_cmd = min(1.0, self.throttle_cmd + 0.75 * dt)
        if self.keys.get('LEFT_CONTROL') or self.keys.get('RIGHT_CONTROL'):
            self.throttle_cmd = max(0.0, self.throttle_cmd - 0.95 * dt)

        ctrl = self.controls.update(self.keys, dt, self.mouse)
        act = ctrl.as_dict(throttle=self.throttle_cmd)

        if not self.paused:
            # 碰撞检测用"地面高度"（含跑道面），否则飞机会沉进跑道
            self.craft.update(dt, act, ground_at)

        # 相机
        self.camera.update(self.craft, self.mouse, dt)
        self.mouse['dx'] = 0.0
        self.mouse['dy'] = 0.0

        # 地形/地景跟随飞机
        cx, cz = self.craft.pos[0], self.craft.pos[2]
        self.terrain_patch.update((cx, cz))
        if self.show_scenery:
            self.scenery.update((cx, cz))
            self.water.update((cx, cz))
            # 生成好的实例数据在这里上传到显卡（必须在 GL 上下文里）
            self.scenery.upload()
            self.water.upload()
            # 风机叶轮转动等动画
            self.scenery.update_animation(dt)

        # ---------------- 特效 + 音效
        self._update_effects(dt)

    def _effect_events(self):
        """检测"该放特效/音效"的事件（坠毁、接地、擦地）"""
        c = self.craft
        # 坠毁：只触发一次
        if c.crashed and not getattr(self, '_was_crashed', False):
            self._was_crashed = True
            if self.particles is not None:
                # 爆炸放在机身高度（不是地面），看起来更像空中炸开
                self.particles.explosion(
                    (c.pos[0], c.pos[1] + 0.5, c.pos[2]), scale=1.0)
            self.sound.explosion()
        if not c.crashed:
            self._was_crashed = False

        # 接地：从"空中"变成"贴地"的那一刻
        was_air = not self.touchdown_prev
        if c.on_ground and was_air and not c.crashed:
            strength = min(1.6, 0.5 + abs(c.vertical_speed) * 0.06)
            if self.particles is not None:
                gh = ground_at(c.pos[0], c.pos[2])
                self.particles.dust((c.pos[0], gh + 0.3, c.pos[2]), strength)
            self.sound.touchdown(strength)
        self.touchdown_prev = bool(c.on_ground)

        # 擦地 / 撞地（贴地但角度不对）
        self.hit_cooldown = max(0.0, self.hit_cooldown - 1.0 / 60.0)
        if (c.on_ground and not c.crashed and self.hit_cooldown <= 0.0
                and (abs(c.roll) > 0.32 or abs(c.pitch) > 0.30)
                and c.airspeed_kmh > 40.0):
            self.hit_cooldown = 0.5
            self.sound.hit()
            if self.particles is not None:
                gh = ground_at(c.pos[0], c.pos[2])
                self.particles.dust((c.pos[0], gh + 0.2, c.pos[2]), 0.8, n=14)

    def _update_effects(self, dt):
        """推进粒子 + 把当前飞行状态喂给音效"""
        c = self.craft
        self._effect_events()

        # ---- 尾迹：高空凝结尾 / 轮胎烟 / 坠毁后冒烟
        if self.particles is not None:
            fwd, right, up, R = c.basis()
            vel = c.vel.copy()
            # 高空凝结尾（900 m 以上、速度够快）
            if (not c.crashed and not c.on_ground and c.altitude > 900.0
                    and c.airspeed_kmh > 120.0):
                self.contrail_timer += dt
                if self.contrail_timer >= 0.06:
                    self.contrail_timer = 0.0
                    for side in (-1.0, 1.0):
                        p = c.pos + right * (side * 7.0) - fwd * 1.0
                        self.particles.contrail(tuple(p), vel, 1.0, n=1)
            else:
                self.contrail_timer = 0.0
            # 轮胎烟（重刹 / 高速贴地）
            if (c.on_ground and not c.crashed
                    and c.airspeed_kmh > 60.0
                    and getattr(c, 'airbrake', 0.0) > 0.5):
                for side in (-1.0, 1.0):
                    p = c.pos + right * (side * 1.1) - fwd * 1.8
                    p[1] = ground_at(p[0], p[2]) + 0.15
                    self.particles.smoke_trail(tuple(p), vel, 1.0, n=2)
            # 坠毁后持续冒黑烟
            if c.crashed:
                self.crash_smoke_timer += dt
                if self.crash_smoke_timer >= 0.08:
                    self.crash_smoke_timer = 0.0
                    if self.time - c.crash_timer < 6.0 or c.crash_timer < 6.0:
                        self.particles.smoke_trail(
                            tuple(c.pos + np.array([0.0, 1.0, 0.0])),
                            np.zeros(3), 1.0, n=3, dark=True)
            self.particles.update(dt if not self.paused else 0.0)

        # ---- 音效状态
        spd_frac = min(1.5, c.airspeed_kmh / 300.0)
        self.sound.set_state(
            throttle=c.throttle,
            speed_frac=spd_frac,
            kind=c.spec.kind,
            on_ground=c.on_ground,
            brakes=getattr(c, 'airbrake', 0.0),
            stalled=c.stalling,
            paused=self.paused,
        )

    def draw(self):
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)

        # 用真实画面尺寸（窗口可缩放、可全屏，不能用常量）
        fb_w, fb_h = glfw.get_framebuffer_size(self.window)
        if fb_w < 1 or fb_h < 1:
            fb_w, fb_h = WINDOW_W, WINDOW_H
        # 视口必须每帧设置，否则切换全屏/缩放窗口后画面只占一角
        GL.glViewport(0, 0, fb_w, fb_h)
        aspect = fb_w / float(fb_h)
        fov = 62.0 if self.camera.mode != 0 else 72.0
        proj = gfx.perspective(fov, aspect, 0.6, 42000.0)
        view = gfx.look_at(self.camera.pos, self.camera.target,
                           np.array([0.0, 1.0, 0.0]))
        VP = proj @ view

        # ---------- 天空（最先画，不写深度）
        eye = np.asarray(self.camera.pos, dtype=np.float64)
        tgt = np.asarray(self.camera.target, dtype=np.float64)
        fwd = tgt - eye
        n = np.linalg.norm(fwd)
        fwd = fwd / n if n > 1e-9 else np.array([0.0, 0.0, -1.0])
        world_up = np.array([0.0, 1.0, 0.0])
        rgt = np.cross(fwd, world_up)
        nr = np.linalg.norm(rgt)
        rgt = rgt / nr if nr > 1e-9 else np.array([1.0, 0.0, 0.0])
        upv = np.cross(rgt, fwd)

        GL.glDepthMask(GL.GL_FALSE)
        self.sky_shader.use()
        self.sky_shader.set_vec3('uRight', rgt)
        self.sky_shader.set_vec3('uUp', upv)
        self.sky_shader.set_vec3('uFwd', fwd)
        self.sky_shader.set_float('uTanHalfFov', math.tan(math.radians(fov) * 0.5))
        self.sky_shader.set_float('uAspect', aspect)
        self.sky_shader.set_vec3('uCamPos', eye)
        self.sky_shader.set_vec3('uSunDir', self.sun_dir)
        self.sky_shader.set_float('uTime', self.time)
        self.sky_shader.set_float('uCloudCover', self.cloud_cover)
        self.sky_shader.set_float('uCloudHeight', 1500.0)
        self.sky_shader.set_float('uSunGlow', 1.0)
        GL.glDisable(GL.GL_DEPTH_TEST)
        self.sky_quad.draw()
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDepthMask(GL.GL_TRUE)

        # ---------- 公共 uniform
        for sh in (self.obj_shader, self.terrain_shader,
                   self.inst_shader, self.water_shader):
            sh.use()
            sh.set_mat4('uVP', VP)
            sh.set_vec3('uSunDir', self.sun_dir)
            sh.set_vec3('uCamPos', self.camera.pos)
            sh.set_vec3('uFogColor', self.fog_color)
            sh.set_float('uFogDensity', self.fog_density)

        # ---------- 地形（双层）
        self.terrain_shader.use()
        GL.glDisable(GL.GL_CULL_FACE)
        self.terrain_patch.draw(self.terrain_shader)
        GL.glEnable(GL.GL_CULL_FACE)

        # ---------- 水面（半透明，在地形之后、树之前）
        if self.show_scenery:
            self.water_shader.use()
            GL.glEnable(GL.GL_BLEND)
            GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
            GL.glDepthMask(GL.GL_FALSE)
            if getattr(self, 'debug_water', False):
                print('[water] center=%s count=%d mesh=%s' % (
                    self.water.center, self.water.count, self.water.mesh is not None))
                print('[water] err_before=%d' % GL.glGetError())
            self.water.draw(self.water_shader)
            if getattr(self, 'debug_water', False):
                print('[water] err_after=%d' % GL.glGetError())
            GL.glDepthMask(GL.GL_TRUE)
            GL.glDisable(GL.GL_BLEND)

            # ---------- 森林 + 村庄 + 石头 + 风机塔（实例化一次画完）
            self.inst_shader.use()
            self.scenery.draw_trees(self.inst_shader)
            self.scenery.draw_props(self.inst_shader)
            self.scenery.draw_turbines(self.inst_shader)

        # ---------- 物体
        self.obj_shader.use()
        ident = np.eye(4, dtype=np.float32)
        nrm = np.eye(3, dtype=np.float32)

        # 跑道 & 塔台（世界固定）
        def draw_at(mesh, pos, yaw=0.0):
            m = np.eye(4, dtype=np.float32)
            m[0, 0] = math.cos(yaw)
            m[0, 2] = math.sin(yaw)
            m[2, 0] = -math.sin(yaw)
            m[2, 2] = math.cos(yaw)
            m[0, 3] = pos[0]
            m[1, 3] = pos[1]
            m[2, 3] = pos[2]
            self.obj_shader.set_mat4('uModel', m)
            nm = m[:3, :3].astype(np.float32)
            self.obj_shader.set_mat3('uNormalMat', nm)
            mesh.draw()

        gy = terrain.height_at(0.0, 0.0)
        # 沥青层 + 标线层都正常画（标线抬了 5 mm，深度上明确压过沥青，
        # 不会 z-fighting，也不会挡住飞机）。
        draw_at(self.runway_mesh, (0.0, gy + 0.2, 0.0))
        draw_at(self.runway_paint_mesh, (0.0, gy + 0.2, 0.0))
        draw_at(self.tower_mesh, (95.0, terrain.height_at(95.0, -180.0), -180.0))

        # 飞机
        # 模型局部坐标和世界坐标一致：机头朝 -Z、右翼朝 +X、上朝 +Y，
        # 所以直接用姿态矩阵就行，不能再加镜像/翻转
        # （之前多乘了一个绕 Y 轴 180° 的 flip，它把左右机翼对调了，
        #   机头方向不变所以肉眼看不出来，但滚转方向会画反）。
        #
        # 顺序：先画地面阴影，再画飞机，这样看起来是"停在地上"而不是浮着。
        R = gfx.euler_to_matrix(self.craft.pitch, self.craft.yaw, self.craft.roll)
        shadow_m = np.eye(4, dtype=np.float32)
        shadow_m[:3, :3] = R.astype(np.float32)
        shadow_m[0, 3] = self.craft.pos[0]
        shadow_m[2, 3] = self.craft.pos[2]
        # 贴在地面上方一点点，避免和跑道/地形打架
        shadow_m[1, 3] = ground_at(self.craft.pos[0], self.craft.pos[2]) + 0.035
        self.obj_shader.set_mat4('uModel', shadow_m)
        self.obj_shader.set_mat3('uNormalMat', shadow_m[:3, :3].astype(np.float32))
        self.shadow_mesh.draw()

        model = np.eye(4, dtype=np.float32)
        model[:3, :3] = R.astype(np.float32)
        model[:3, 3] = self.craft.pos.astype(np.float32)
        self.obj_shader.set_mat4('uModel', model)
        self.obj_shader.set_mat3('uNormalMat', model[:3, :3].astype(np.float32))
        self.plane_mesh.draw()

        # 起落架：单独一个网格，收起时缩进机身（而不是突然消失）
        gear = self.craft.gear
        if gear > 0.02:
            g = max(0.02, gear)
            gz = 0.30 + 0.70 * gear          # 收起时朝机身内部缩
            gy = -0.55 * (1.0 - gear)        # 略微上收
            gear_local = np.array([
                [1.0, 0.0, 0.0, 0.0],
                [0.0, g, 0.0, gy],
                [0.0, 0.0, 1.0, gz],
                [0.0, 0.0, 0.0, 1.0],
            ], dtype=np.float32)
            gm = model @ gear_local
            self.obj_shader.set_mat4('uModel', gm)
            self.obj_shader.set_mat3('uNormalMat', gm[:3, :3].astype(np.float32))
            self.gear_mesh.draw()

        # ---------- 粒子特效（爆炸 / 扬尘 / 烟 / 凝结尾）
        # 放在最后画，这样烟和火会盖在飞机和地景之上（爆炸本来就该挡住机身）。
        self._draw_particles(VP)

    def _draw_particles(self, VP):
        """画粒子：方片展开到相机平面，所以要把相机的右/上向量传进去"""
        if self.particles is None or self.particle_shader is None:
            return
        if self.particles.count() == 0:
            return
        # 从 VP 矩阵反推相机的右/上前向量不方便，直接由相机位置和目标算
        cam = np.asarray(self.camera.pos, dtype=np.float64)
        tgt = np.asarray(self.camera.target, dtype=np.float64)
        f = tgt - cam
        ln = np.linalg.norm(f)
        if ln < 1e-6:
            return
        f = f / ln
        r = np.cross(f, np.array([0.0, 1.0, 0.0]))
        rl = np.linalg.norm(r)
        r = r / rl if rl > 1e-6 else np.array([1.0, 0.0, 0.0])
        u = np.cross(r, f)

        data, n = self.particles.visible_instances(r, u)
        if data is None or n == 0:
            return

        sh = self.particle_shader
        sh.use()
        sh.set_mat4('uVP', VP)
        sh.set_vec3('uRight', r)
        sh.set_vec3('uUp', u)
        sh.set_vec3('uCamPos', cam)
        sh.set_vec3('uFogColor', self.fog_color)
        sh.set_float('uFogDensity', self.fog_density)
        sh.set_float('uSoftness', 0.85)

        # 半透明混合：烟/火需要 alpha
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glDepthMask(GL.GL_FALSE)          # 粒子之间不互相遮挡（更蓬松）
        GL.glDisable(GL.GL_CULL_FACE)        # 方片两面都要可见
        # 网格是懒加载的（第一次画粒子时才建，需要 GL 上下文）
        self.particles.ensure_mesh()
        self.particles.mesh.set_instances(data)
        self.particles.mesh.draw_instanced()
        GL.glEnable(GL.GL_CULL_FACE)
        GL.glDepthMask(GL.GL_TRUE)
        GL.glDisable(GL.GL_BLEND)

        # ---------- 仪表盘叠加层
        if self.show_hud:
            try:
                hudmod.draw_hud(self.hud, self.hud_shader, self.craft,
                                float(fb_w), float(fb_h), self.fps)
            except Exception:
                self.show_hud = False

    # ------------------------------------------------ 运行
    def _print_banner(self, glyph_count=0):
        """启动横幅 + 操作说明（按当前语言）"""
        print('=' * 68)
        print('  %s   v%s   (%s)' % (APP_NAME, VERSION, BUILD_DATE))
        if not hudmod.font_ready():
            print('  [i18n] 系统里没找到中文字体，HUD 的中文会显示成方块')
        print('=' * 68)
        print(self.help_text())
        print('  %s   (L = 中/英 / language)' % i18n.LANG_NAMES[i18n.get_lang()])
        print()

    def toggle_language(self):
        """L 键：中英界面切换"""
        lang = i18n.toggle_lang()
        print('  [i18n] %s' % (i18n.t('msg.lang') % i18n.LANG_NAMES[lang]))
        # 切换后立刻刷新标题和帮助信息
        glfw.set_window_title(self.window, self.title_text())
        print(self.help_text())

    def toggle_sound(self):
        """N 键：音效开关

        关掉时只把音量压到 0（音频线程继续跑），这样再打开是瞬时的，
        不会因为反复开关设备而卡一下。
        """
        self.sound_on = not self.sound_on
        try:
            self.sound.set_master(0.85 if self.sound_on else 0.0)
        except Exception:
            pass
        if self.sound_on and not getattr(self.sound, 'ready', False):
            # 之前没起来（比如启动时设备被占用），这里再试一次
            self.sound = soundmod.Sound()
        state = '开启' if self.sound_on else '关闭'
        print('  [sound] %s' % state)

    def run(self):
        self.init_gl()
        # 界面语言：命令行 --lang=en / --lang=zh 可以覆盖默认值
        for a in sys.argv[1:]:
            if a.startswith('--lang='):
                i18n.set_lang(a.split('=', 1)[1])
        # 预生成 HUD 用得到的汉字字形（避免游戏中第一次显示时卡顿）
        n = hudmod.warm_font()
        self._print_banner(n)
        while not glfw.window_should_close(self.window):
            now = time.time()
            dt = now - self.last_time
            self.last_time = now
            if dt > 0.1:
                dt = 0.1
            if dt <= 0.0:
                dt = 1e-4

            self.update(dt)
            self.draw()
            glfw.swap_buffers(self.window)
            glfw.poll_events()

            # 统计 + 窗口标题
            self.frame_count += 1
            self.fps_timer += dt
            self.title_timer += dt
            if self.fps_timer >= 0.5:
                self.fps = self.frame_count / self.fps_timer
                self.frame_count = 0
                self.fps_timer = 0.0
            if self.title_timer >= 0.25:
                self.title_timer = 0.0
                glfw.set_window_title(self.window, self.title_text())

        # 收尾：先关音效（音频线程要停掉），再关窗口
        try:
            self.sound.stop()
        except Exception:
            pass
        glfw.terminate()

    def title_text(self):
        c = self.craft
        mode = [i18n.t('cam.cockpit'), i18n.t('cam.chase'), i18n.t('cam.orbit')][
            self.camera.mode]
        flag = ''
        if c.stalling:
            flag = i18n.t('title.stall')
        if c.crashed:
            flag = i18n.t('title.crashed')
        if self.paused:
            flag += '  ||' + i18n.t('warn.paused')
        if self.fullscreen:
            flag += i18n.t('title.fullscreen')
        head = math.degrees(c.yaw) % 360.0
        gear = ''
        if c.spec.gear_retract:
            gtxt = (i18n.t('title.gear_down') if c.gear > 0.99
                    else (i18n.t('title.gear_up') if c.gear < 0.01
                          else '%d%%' % int(c.gear * 100)))
            gear = i18n.t('title.gear') % gtxt
        ac_name = c.spec.name if i18n.is_zh() else c.spec.name_en
        return i18n.t('title.format') % (
            APP_NAME, VERSION, ac_name, mode, int(head),
            c.airspeed_kmh, c.altitude, math.degrees(c.roll),
            c.throttle * 100.0, gear, self.fps, flag)
    def help_text(self):
        """操作说明。所有文字都从 i18n 取，按 L 可以中英切换"""
        c = self.craft
        L = [
            i18n.t('help.title'),
            '-' * 68,
            i18n.t('help.pitch'),
            i18n.t('help.roll'),
            i18n.t('help.yaw'),
            i18n.t('help.throttle'),
            i18n.t('help.quick'),
            i18n.t('help.sys1'),
            i18n.t('help.sys2'),
            i18n.t('help.sys3'),
            i18n.t('help.sys4'),
            i18n.t('help.sys5'),
            i18n.t('help.sys6'),
            i18n.t('help.sys7'),
            '-' * 68,
            i18n.t('help.takeoff'),
            i18n.t('help.takeoff2'),
            i18n.t('help.takeoff3'),
            i18n.t('help.level'),
            i18n.t('help.turn'),
            i18n.t('help.gear'),
            i18n.t('help.gear2'),
            i18n.t('help.slow'),
            i18n.t('help.accel'),
            i18n.t('help.land'),
            i18n.t('help.land2'),
            i18n.t('help.warn'),
            '-' * 68,
            i18n.t('help.types'),
            i18n.t('help.type1'),
            i18n.t('help.type2'),
            i18n.t('help.type3'),
            '-' * 68,
            i18n.t('help.cam'),
            i18n.t('help.lang'),
            '',
            '  当前机型 / current aircraft: %s (%s)' % (c.spec.name, c.spec.name_en),
        ]
        return '\n'.join(L) + '\n'


def main():
    app = SkyFlightApp()
    try:
        app.run()
    except Exception as e:
        print('出错了:', e)
        import traceback
        traceback.print_exc()
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
