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

from . import gfx, shaders, sky, terrain, flight, plane, scenery, hud as hudmod
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


def ground_at(x, z):
    """飞机能落脚的地面高度（含跑道面）"""
    return plane.surface_height(x, z, terrain.height_at(x, z))


def spawn_position():
    """返回出生位置：轮胎正好落在跑道面上"""
    x, _, z = RUNWAY_START
    ground = ground_at(x, z)
    # 飞机模型最低点（轮胎底）在局部坐标 -1.07，所以机身原点 = 地面 + 1.07
    return np.array([x, ground + WHEEL_DROP, z], dtype=np.float64)

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
    def __init__(self):
        self.window = None
        self.keys = {}
        self.mouse = {'dx': 0.0, 'dy': 0.0, 'x': 0.0, 'y': 0.0, 'left': False, 'right': False}
        self.craft = flight.Aircraft()
        self.camera = Camera()
        # 出生在跑道上（停住，需要自己加油门滑跑起飞）
        if SPAWN_ON_RUNWAY:
            p0 = spawn_position()
            self.craft.pos = p0.copy()
            self.craft.vel = np.zeros(3)
            self.craft.speed_val = 0.0
            self.craft.pitch = 0.0
            self.craft.on_ground = True
            self.camera.pos = p0 + np.array([0.0, 6.0, 30.0])
            self.camera.target = p0 + np.array([0.0, 1.0, -20.0])
            self.camera.smooth = self.camera.pos.copy()
        self.controls = flight.Controls()
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
        self.runway_mesh = None
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
        self.hud_shader = hudmod.make_hud_shader()
        self.hud = hudmod.Hud()
        self.show_hud = True
        self.show_scenery = True

        self.plane_mesh = plane.build_plane()
        self.shadow_mesh = plane.build_shadow()
        self.runway_mesh = plane.build_runway()
        self.tower_mesh = plane.build_tower()
        # 双层地形：近处细、远处大范围
        self.terrain_patch = terrain.Terrain()
        # 成片地景：森林 + 湖面 + 路边房屋
        self.scenery = scenery.Scenery(radius=2600.0, cell=52.0)
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
        """在窗口和全屏之间切换"""
        monitor = glfw.get_primary_monitor()
        if monitor is None:
            return
        if self.fullscreen:
            # 回到窗口模式：还原原来的位置和大小
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
        elif n == 'R':
            # 重来：回到跑道起点，停住
            if SPAWN_ON_RUNWAY:
                p0 = spawn_position()
                self.craft.reset(tuple(p0))
                self.craft.vel = np.zeros(3)
                self.craft.speed_val = 0.0
                self.craft.on_ground = True
                self.throttle_cmd = 0.0
                self.controls.flaps = 0.0
                self.camera.smooth = p0 + np.array([0.0, 6.0, 30.0])
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

            # ---------- 森林 + 房屋（实例化一次画完）
            self.inst_shader.use()
            self.scenery.draw_trees(self.inst_shader)
            self.scenery.draw_houses(self.inst_shader)

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
        draw_at(self.runway_mesh, (0.0, gy + 0.2, 0.0))
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

        # ---------- 仪表盘叠加层
        if self.show_hud:
            try:
                hudmod.draw_hud(self.hud, self.hud_shader, self.craft,
                                float(fb_w), float(fb_h), self.fps)
            except Exception:
                self.show_hud = False

    # ------------------------------------------------ 运行
    def run(self):
        self.init_gl()
        print('=' * 64)
        print('  %s   v%s   (%s)' % (APP_NAME, VERSION, BUILD_DATE))
        print('=' * 64)
        print(self.help_text())
        print()
        print('  提示：按 F11 可以全屏，再按一次回到窗口')
        print()
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

        glfw.terminate()

    def title_text(self):
        c = self.craft
        mode = ['驾驶舱', '追尾', '环绕'][self.camera.mode]
        flag = ''
        if c.stalling:
            flag = '  ⚠失速'
        if c.crashed:
            flag = '  ✖坠毁(按R重来)'
        if self.paused:
            flag += '  ‖暂停'
        if self.fullscreen:
            flag += '  [全屏 F11 退出]'
        head = math.degrees(c.yaw) % 360.0
        return ('%s v%s  |  %s  |  航向 %03d°  |  速度 %.0f km/h  |  高度 %.0f m  |  '
                '倾角 %+.0f°  |  油门 %.0f%%  |  FPS %.0f%s'
                % (APP_NAME, VERSION, mode, int(head), c.airspeed_kmh, c.altitude,
                   math.degrees(c.roll), c.throttle * 100.0, self.fps, flag))
    def help_text(self):
        return """操作说明
--------------------------------------------------------------------
  【俯仰】S 或 ↓ = 拉杆抬头      W 或 ↑ = 推杆低头
  【滚转】D 或 → = 向右倾        A 或 ← = 向左倾
  【偏航】E = 右舵               Q = 左舵
  【油门】Shift = 加大           Ctrl = 减小
  【快速】Z = 油门加满           X = 油门收光
  【系统】F = 襟翼    B = 刹车/减速板    C = 切视角
          M = 鼠标操纵    P = 暂停
          R = 重来（回跑道）
          F11 或 Alt+回车 = 全屏 / 退出全屏
          H = 隐藏/显示本说明    Esc = 退出
--------------------------------------------------------------------
  【起飞】按 Z 加满油门 → 速度到约 100 km/h → 按住 S 抬前轮
          → 俯仰到 12~15° 时松杆 → 飞机会自己离地
  【平飞】松杆就行，飞机会自动配平；需要调节时轻点 S / W
  【转弯】按住 D 或 A，最多约 60° 倾角；松杆 2 秒自动回正
  【减速】按住 B 打开减速板（空中也管用）；配合 F 放襟翼减得更快
  【加速】俯冲（推杆 W）会掉高度但速度涨；要收速度就拉平 + 开减速板
  【降落】对准跑道 → 油门收到 20% → F 放襟翼 → 轻拉杆让下降率变缓
  【告警】屏幕下方出现 STALL 表示失速，立刻推杆（W）并加油门
--------------------------------------------------------------------
  在"环绕"视角下（按 C 切换到第 3 个），按住鼠标右键拖动可转视角
"""


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
