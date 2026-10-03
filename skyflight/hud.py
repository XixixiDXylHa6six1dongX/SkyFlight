# -*- coding: utf-8 -*-
"""
屏幕叠加层（HUD）：空速、高度、升降率、油门、姿态仪、迎角、告警
自带一套简单字形（用矩形拼字母/数字，不依赖字体库）
"""
import math

import numpy as np
from OpenGL import GL

from . import gfx
from .version import VERSION

# ================================================================
# 字形：5x7 点阵，每个字符用 7 行 5 列的字符串表示
# '#' = 实心点
# ================================================================
FONT = {
    '0': [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    '1': ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    '.': [".....", ".....", ".....", ".....", ".....", ".##..", ".##.."],
    '#': ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    '2': [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    '3': ["#####", "...#.", "..#..", "...#.", "....#", "#...#", ".###."],
    '4': ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    '5': ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    '6': ["..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."],
    '7': ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    '8': [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    '9': [".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."],
    'A': [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    'B': ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    'C': [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    'D': ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    'E': ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    'F': ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    'G': [".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".####"],
    'H': ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    'I': [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    'J': ["..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    'K': ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    'L': ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    'M': ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    'N': ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    'O': [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    'P': ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    'Q': [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    'R': ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    'S': [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    'T': ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    'U': ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    'V': ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    'W': ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"],
    'X': ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
    'Y': ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    'Z': ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    '-': [".....", ".....", ".....", "#####", ".....", ".....", "....."],
    '+': [".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."],
    '.': [".....", ".....", ".....", ".....", ".....", "..##.", "..##."],
    ':': [".....", "..##.", "..##.", ".....", "..##.", "..##.", "....."],
    '/': ["....#", "...#.", "...#.", "..#..", ".#...", ".#...", "#...."],
    '%': ["##..#", "##.#.", "...#.", "..#..", ".#...", ".#.##", "#..##"],
    ' ': [".....", ".....", ".....", ".....", ".....", ".....", "....."],
}

CHAR_W = 5
CHAR_H = 7


class Hud:
    """2D 叠加层。坐标用像素，原点在左上角

    顶点格式：位置 (2 float) + 颜色 (4 float) = 6 float = 24 字节
    """

    def __init__(self):
        self.vao = None
        self.vbo = None
        self.verts = []

    # ------------------------------------------------ 初始化
    def _init(self):
        if self.vao is not None:
            return
        self.vao = GL.glGenVertexArrays(1)
        self.vbo = GL.glGenBuffers(1)
        GL.glBindVertexArray(self.vao)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, 6 * 4 * 12000, None, GL.GL_STREAM_DRAW)
        stride = 6 * 4          # 位置 2 + 颜色 4
        import ctypes as ct
        GL.glEnableVertexAttribArray(0)
        GL.glVertexAttribPointer(0, 2, GL.GL_FLOAT, GL.GL_FALSE, stride, ct.c_void_p(0))
        GL.glEnableVertexAttribArray(1)
        GL.glVertexAttribPointer(1, 4, GL.GL_FLOAT, GL.GL_FALSE, stride, ct.c_void_p(8))
        GL.glBindVertexArray(0)

    def begin(self):
        self._init()
        self.verts = []

    # ------------------------------------------------ 图元
    def rect(self, x, y, w, h, color):
        if w <= 0 or h <= 0:
            return
        x0, y0, x1, y1 = x, y, x + w, y + h
        r, g, b, a = color
        for p in ((x0, y0), (x1, y0), (x1, y1), (x0, y0), (x1, y1), (x0, y1)):
            self.verts.extend((p[0], p[1], r, g, b, a))

    def line(self, x0, y0, x1, y1, color, width=1.0):
        dx, dy = x1 - x0, y1 - y0
        ln = math.hypot(dx, dy)
        if ln < 1e-6:
            return
        nx, ny = -dy / ln * width * 0.5, dx / ln * width * 0.5
        r, g, b, a = color
        p = [(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny),
             (x0 + nx, y0 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)]
        for q in p:
            self.verts.extend((q[0], q[1], r, g, b, a))

    # ------------------------------------------------ 文字
    def glyph(self, ch, x, y, size, color):
        """画一个字符。size = 字符高度（像素）"""
        pat = FONT.get(ch.upper())
        if pat is None:
            return size * 0.6
        pw = size / float(CHAR_H)          # 每个点阵像素的边长
        for row in range(CHAR_H):
            line = pat[row]
            col = 0
            while col < CHAR_W:
                if line[col] == '#':
                    run = 1
                    while col + run < CHAR_W and line[col + run] == '#':
                        run += 1
                    self.rect(x + col * pw, y + row * pw, run * pw + 0.6, pw + 0.6, color)
                    col += run
                else:
                    col += 1
        return CHAR_W * pw

    def text(self, s, x, y, size, color, spacing=1.6):
        pw = size / float(CHAR_H)
        cx = x
        for ch in str(s):
            w = self.glyph(ch, cx, y, size, color)
            cx += w + pw * spacing
        return cx

    def text_width(self, s, size, spacing=1.6):
        pw = size / float(CHAR_H)
        return len(str(s)) * (CHAR_W * pw + pw * spacing)

    def commit(self, screen_w, screen_h, shader):
        """把攒好的顶点画到屏幕上（坐标：左上原点，y 向下）"""
        if not self.verts:
            return
        arr = np.asarray(self.verts, dtype=np.float32).reshape(-1, 6)
        n = arr.shape[0]
        arr[:, 0] = arr[:, 0] / float(screen_w) * 2.0 - 1.0
        arr[:, 1] = 1.0 - arr[:, 1] / float(screen_h) * 2.0

        self._init()
        GL.glBindVertexArray(self.vao)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, arr.nbytes, arr, GL.GL_STREAM_DRAW)

        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_CULL_FACE)
        GL.glDepthMask(GL.GL_FALSE)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        shader.use()
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, n)
        GL.glDisable(GL.GL_BLEND)
        GL.glDepthMask(GL.GL_TRUE)
        GL.glEnable(GL.GL_CULL_FACE)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glBindVertexArray(0)


HUD_VS = """
#version 330 core
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec4 aColor;
out vec4 vColor;
void main() {
    vColor = aColor;
    gl_Position = vec4(aPos, 0.0, 1.0);
}
"""

HUD_FS = """
#version 330 core
in vec4 vColor;
out vec4 FragColor;
void main() {
    FragColor = vColor;
}
"""


def make_hud_shader():
    return gfx.Shader(HUD_VS, HUD_FS, 'hud')


# ================================================================
# 配色
# ================================================================
WHITE = (0.96, 0.97, 0.99, 1.0)
DIM = (0.62, 0.67, 0.74, 1.0)
GREEN = (0.35, 0.94, 0.48, 1.0)
AMBER = (0.98, 0.76, 0.25, 1.0)
RED = (0.98, 0.32, 0.28, 1.0)
CYAN = (0.36, 0.87, 0.97, 1.0)
BG = (0.06, 0.09, 0.13, 0.5)


def _panel(hud, x, y, w, h, label, value, unit, vcol=WHITE, bar=None):
    """画一个数据面板：标签 + 数值 + 单位（+ 可选进度条）"""
    hud.rect(x, y, w, h, BG)
    ts = h * 0.21
    vs = h * 0.36
    hud.text(label, x + 10, y + 4, ts, DIM)
    hud.text(value, x + 10, y + h * 0.31, vs, vcol)
    if unit:
        uw = hud.text_width(unit, ts)
        hud.text(unit, x + w - uw - 10, y + h * 0.60, ts, DIM)
    if bar is not None:
        bx, by, bw2, bh2 = x + 10, y + h - 8, w - 20, 5
        hud.rect(bx, by, bw2, bh2, (0.18, 0.21, 0.26, 0.9))
        hud.rect(bx, by, bw2 * max(0.0, min(1.0, bar)), bh2,
                 GREEN if bar > 0.05 else DIM)


def _compass(hud, craft, screen_w, pad):
    """顶部罗盘：显示当前机头朝向，转弯时数字会滑动

    航向角约定：0 = 北(-Z)，向东为正，所以
      北 0° / 东 90° / 南 180° / 西 270°
    世界系 X 向东、Z 向南，机头方向 (sin yaw, 0, -cos yaw)，
    换算成"从北顺时针"的角度就是 degrees(yaw)。
    """
    head = math.degrees(craft.yaw) % 360.0
    cw = min(460.0, screen_w * 0.36)
    ch = 26.0
    cleft = screen_w * 0.5 - cw * 0.5
    top = pad - 2.0
    hud.rect(cleft, top, cw, ch, BG)

    marks = [
        (0, 'N'), (45, 'NE'), (90, 'E'), (135, 'SE'),
        (180, 'S'), (225, 'SW'), (270, 'W'), (315, 'NW'),
    ]
    px_per_deg = cw / 120.0          # 视野里显示 ±60°
    mid = cleft + cw * 0.5
    for ang, label in marks:
        # 把标记角度换算到相对当前航向的最近一份（-60..+60）
        d = (ang - head + 180.0) % 360.0 - 180.0
        if abs(d) > 58.0:
            continue
        x = mid + d * px_per_deg
        major = (ang % 90 == 0)
        col = WHITE if major else DIM
        hud.text(label, x - hud.text_width(label, 13) * 0.5, top + 5, 13, col)

    # 中央指针（固定不动）
    hud.line(mid, top, mid, top + ch, AMBER, 2.0)
    hud.text('%03d' % int(head), mid + 5, top + 5, 12, AMBER)


def draw_hud(hud, shader, craft, screen_w, screen_h, fps=0.0):
    """把仪表盘画到屏幕上"""
    hud.begin()
    pad = 16.0
    pw = min(230.0, screen_w * 0.20)      # 面板宽
    ph = max(62.0, screen_h * 0.112)      # 面板高

    # ---------------- 左下：空速 / 高度
    y0 = screen_h - pad - ph * 2 - 8
    _panel(hud, pad, y0, pw, ph, 'SPD', '%d' % craft.airspeed_kmh, 'KM/H')
    _panel(hud, pad, y0 + ph + 8, pw, ph, 'ALT', '%d' % craft.altitude, 'M')

    # ---------------- 右下：油门 / 升降率
    xr = screen_w - pad - pw
    _panel(hud, xr, y0, pw, ph, 'THR', '%d' % int(craft.throttle * 100), '%',
           vcol=GREEN if craft.throttle > 0.05 else DIM, bar=craft.throttle)
    vs_ = craft.vertical_speed
    vcol = GREEN if vs_ > 1.0 else (AMBER if vs_ < -1.0 else WHITE)
    _panel(hud, xr, y0 + ph + 8, pw, ph, 'V/S', '%+.0f' % vs_, 'M/S', vcol=vcol)

    # ---------------- 油门面板上方：减速板 / 襟翼状态
    st_y = y0 - 24.0
    if getattr(craft, 'airbrake', 0.0) > 0.05:
        hud.text('BRAKE', xr + 4, st_y, 15, AMBER)
    if abs(getattr(craft, 'flaps', 0.0)) > 0.05:
        hud.text('FLAPS', xr + 76, st_y, 15, CYAN)

    # ---------------- 顶部中间：姿态仪（往下让出罗盘的位置）
    aw, ah = 210.0, 76.0
    ax = screen_w * 0.5 - aw * 0.5
    ay = pad + 34.0
    hud.rect(ax, ay, aw, ah, BG)
    cx, cy = ax + aw * 0.5, ay + ah * 0.5
    roll, pitch = craft.roll, craft.pitch
    ex = math.cos(roll) * aw * 0.46
    ey = math.sin(roll) * aw * 0.46
    dy = math.sin(pitch) * ah * 0.42
    hud.line(cx - ex, cy - ey + dy, cx + ex, cy + ey + dy, WHITE, 2.0)
    hud.line(cx - 20, cy, cx - 7, cy, AMBER, 3.0)
    hud.line(cx + 7, cy, cx + 20, cy, AMBER, 3.0)
    hud.line(cx, cy - 6, cx, cy + 6, AMBER, 2.0)

    # ---------------- 最顶部：罗盘（航向带）
    _compass(hud, craft, screen_w, pad)

    # ---------------- 姿态仪正下方：迎角 / 过载（居中，不挡跑道）
    aoa = craft.aoa_deg
    acol = RED if craft.stalling else (AMBER if abs(aoa) > 12 else WHITE)
    ty = ay + ah + 6
    hud.text('AOA %+.1f' % aoa, cx - 58, ty, 17, acol)
    gcol = RED if craft.g_load > 3.0 else WHITE
    hud.text('G %.1f' % craft.g_load, cx - 26, ty + 20, 17, gcol)

    # ---------------- 告警（再往下）
    warns = []
    if craft.crashed:
        warns.append(('CRASHED  PRESS R', RED))
    elif craft.stalling:
        warns.append(('STALL', RED))
    if not craft.crashed:
        if craft.altitude < 120 and craft.vertical_speed < -8:
            warns.append(('PULL UP', RED))
        if craft.throttle < 0.05 and craft.altitude > 200:
            warns.append(('LOW POWER', AMBER))
        if abs(craft.aoa_deg) > 14 and not craft.stalling:
            warns.append(('HIGH AOA', AMBER))

    ts = 17.0
    wy = ty + 44
    for txt, col in warns:
        tw = hud.text_width(txt, ts)
        hud.rect(cx - tw * 0.5 - 12, wy - 5, tw + 24, ts * 1.55,
                 (0.16, 0.03, 0.03, 0.75))
        hud.text(txt, cx - tw * 0.5, wy, ts, col)
        wy += ts * 1.9

    # ---------------- 右上：FPS
    hud.text('FPS %d' % int(fps), screen_w - pad - 100, pad + 4, 17, DIM)

    # ---------------- 左上角：游戏名 + 版本号 + 机型（空白区，不会被切）
    hud.text('SKYFLIGHT', pad + 2, pad + 2, 20, WHITE)
    hud.text('V%s' % VERSION, pad + 2, pad + 28, 16, DIM)
    sp = getattr(craft, 'spec', None)
    if sp is not None:
        name = sp.name_en.upper()
        hud.text(name, pad + 62, pad + 28, 16,
                 CYAN if sp.kind == 'jet' else DIM)

    # ---------------- 机型/起落架状态（在罗盘下方左侧）
    if sp is not None:
        iy = pad + 118
        if sp.gear_retract:
            g = craft.gear
            if g > 0.99:
                gt, gc = 'GEAR DOWN', GREEN
            elif g < 0.01:
                gt, gc = 'GEAR UP', DIM
            else:
                gt, gc = 'GEAR %d%%' % int(g * 100), AMBER
            hud.text(gt, pad + 2, iy, 16, gc)
        else:
            hud.text('GEAR FIXED', pad + 2, iy, 16, DIM)
        if sp.kind == 'jet':
            hud.text('JET', pad + 2, iy + 20, 16, DIM)

    hud.commit(screen_w, screen_h, shader)
