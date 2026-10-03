# -*- coding: utf-8 -*-
"""
屏幕叠加层（HUD）：空速、高度、升降率、油门、姿态仪、迎角、告警

文字分两套：
  1. ASCII 用自带的 5x7 点阵（FONT 表，不依赖任何字体文件）
  2. 中文（以及其它非 ASCII）按需用系统字体（微软雅黑等）光栅化成
     同样的点阵格式并缓存 —— 所以 HUD 不需要预存上千个汉字字形
"""
import math

import numpy as np
from OpenGL import GL

from . import gfx
from . import i18n
from .version import VERSION

# ================================================================
# 中文（及其它非 ASCII）字形：用系统字体现场光栅化
# 找不到字体时退化成空心方块占位，HUD 不会崩
# ================================================================
_CJK_PIX_MAX = 30             # 光栅化方格最大边长（像素）
_CJK_MIN_SIZE = 11            # 小于这个字号就不渲染汉字了（糊得认不出）
_CJK_ROWS_FACTOR = 1.3        # 汉字行数 = 字号 * 这个系数（比 ASCII 细，视觉高度才一致）
_CJK_CACHE = {}
_CJK_FONT = None
_CJK_FONT_PATH = None
_CJK_TRIED = False

_CJK_FONT_PATHS = [
    r'C:\Windows\Fonts\msyh.ttc',      # 微软雅黑
    r'C:\Windows\Fonts\msyhbd.ttc',
    r'C:\Windows\Fonts\simhei.ttf',    # 黑体
    r'C:\Windows\Fonts\Deng.ttf',      # 等线
    r'C:\Windows\Fonts\simsun.ttc',    # 宋体
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/System/Library/Fonts/PingFang.ttc',
]


def _load_cjk_font():
    """找到一个能显示中文的字体文件（只找一次）

    注意：这里只确认"有哪些字体可用"，真正光栅化时会按目标字号
    重新建 ImageFont 对象（见 cjk_glyph）。
    """
    global _CJK_FONT, _CJK_FONT_PATH, _CJK_TRIED
    if _CJK_TRIED:
        return _CJK_FONT
    _CJK_TRIED = True
    try:
        from PIL import ImageFont
    except Exception:
        return None
    for p in _CJK_FONT_PATHS:
        try:
            import os
            if not os.path.exists(p):
                continue
            _CJK_FONT = ImageFont.truetype(p, 24)
            _CJK_FONT_PATH = p
            return _CJK_FONT
        except Exception:
            continue
    return None


def warm_font(chars=None):
    """预先生成一批字形（在启动时调用，避免游戏中第一次显示时卡顿）

    HUD 里的汉字会出现在 15 / 17 / 19 / 21 几种字号上，
    这里每种都预生成一遍。字形按 (字符, 字号) 缓存。
    """
    _load_cjk_font()
    sizes = (15, 17, 19, 21)
    for ch in (chars if chars is not None else i18n.hud_characters()):
        if ord(ch) > 127:
            for s in sizes:
                cjk_glyph(ch, s)
    return len(_CJK_CACHE)


def cjk_glyph(ch, size):
    """把非 ASCII 字符按**目标字号**光栅化成点阵（结果按字号缓存）

    返回 (rows, width)：rows 是 '#'/'.' 字符串列表，width 是列数。

    为什么必须按字号光栅化：
      汉字笔画密度远高于拉丁字母。如果先按固定大尺寸光栅化、再缩到
      HUD 的 13~15 px，笔画会糊成一坨（实测"帧率"会糊成"帧字"）。
      所以这里按实际显示尺寸算，笔画才分得开。
    尺寸很小（< _CJK_MIN_SIZE）时干脆返回 None，让调用方跳过 —— 画出来
    也只是一团墨点，不如不画。
    """
    key = (ch, size)
    if key in _CJK_CACHE:
        return _CJK_CACHE[key]
    _load_cjk_font()
    pat = None
    if size < _CJK_MIN_SIZE:
        _CJK_CACHE[key] = None
        return None
    if _CJK_FONT is not None:
        try:
            from PIL import Image, ImageDraw, ImageFont
            R = max(7, int(round(size * _CJK_ROWS_FACTOR)))
            # 字号越小，笔画相对越粗，容易出现"横竖不分"。
            # 所以小字号额外再加行数（点阵更细），大字号保持 1.3 就够。
            if size < 15:
                R = max(R, int(round(size * 2.0)))
            # 高分辨率画布：约 2.5 倍行数就够，再大只是浪费（缩小时会平均掉）
            n = max(20, int(R * 2.5))
            font = ImageFont.truetype(_CJK_FONT_PATH, int(n * 0.82))
            img = Image.new('L', (n, n), 0)
            ImageDraw.Draw(img).text((0, 0), ch, fill=255, font=font)
            px = img.load()
            xs = [x for x in range(n) for y in range(n) if px[x, y] > 90]
            ys = [y for x in range(n) for y in range(n) if px[x, y] > 90]
            if not xs:
                pat = (['.'], 1)
            else:
                x0, x1 = min(xs), max(xs)
                y0, y1 = min(ys), max(ys)
                w = max(1, x1 - x0 + 1)
                h = max(1, y1 - y0 + 1)
                cols = max(2, int(round(w * R * 0.72 / float(h))))
                # 用覆盖率把高分辨率图缩到 R 行 cols 列：
                # 每个格子看平均亮度，超过阈值就算实心 —— 比点采样稳定得多
                rows = []
                for r in range(R):
                    ya = y0 + int(r * h / R)
                    yb = y0 + max(ya - y0 + 1, int((r + 1) * h / R))
                    line = ''
                    for c in range(cols):
                        xa = x0 + int(c * w / cols)
                        xb = x0 + max(xa - x0 + 1, int((c + 1) * w / cols))
                        tot = 0
                        cnt = 0
                        for yy in range(ya, min(yb, n)):
                            for xx in range(xa, min(xb, n)):
                                tot += px[xx, yy]
                                cnt += 1
                        line += '#' if cnt and (tot / float(cnt)) > 105 else '.'
                    rows.append(line)
                pat = (rows, cols)
        except Exception:
            pat = None
    if pat is None:
        # 没有字体时画个空心方块占位，至少能看出"这里有个字"
        pat = (['#####', '#...#', '#...#', '#...#', '#####'], 5)
    _CJK_CACHE[key] = pat
    return pat


def font_ready():
    """系统字体是否可用（不可用时中文会显示成方块）"""
    _load_cjk_font()
    return _CJK_FONT is not None


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
            # 非 ASCII（中文等）：走系统字体光栅化那条路。
            # 字号必须传进去 —— 中文要按实际显示尺寸光栅化才清晰。
            pat2 = cjk_glyph(ch, int(round(size)))
            if pat2 is None:
                return 0.0     # 字号太小，画出来只是墨点，跳过
            rows, gwidth = pat2
            gh = len(rows)
            pw = size / float(gh)
            for row in range(gh):
                line = rows[row]
                col = 0
                while col < gwidth:
                    if line[col] == '#':
                        run = 1
                        while col + run < gwidth and line[col + run] == '#':
                            run += 1
                        self.rect(x + col * pw, y + row * pw,
                                  run * pw + 0.6, pw + 0.7, color)
                        col += run
                    else:
                        col += 1
            return gwidth * pw
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
    """画一个数据面板：标签 + 数值 + 单位（+ 可选进度条）

    中文标签需要更大的字号才清晰（拉丁字母 5x7 点阵在 15px 下很清楚，
    汉字笔画多，同样的高度会糊），所以中文时标签字号乘一个系数。
    """
    hud.rect(x, y, w, h, BG)
    ts = h * 0.21 * (1.35 if i18n.is_zh() else 1.0)
    vs = h * 0.36
    hud.text(label, x + 10, y + 3, ts, DIM)
    hud.text(value, x + 10, y + h * 0.34, vs, vcol)
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
        (0, i18n.t('compass.n')), (45, i18n.t('compass.ne')),
        (90, i18n.t('compass.e')), (135, i18n.t('compass.se')),
        (180, i18n.t('compass.s')), (225, i18n.t('compass.sw')),
        (270, i18n.t('compass.w')), (315, i18n.t('compass.nw')),
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
    zh = i18n.is_zh()

    # ---------------- 左下：空速 / 高度
    y0 = screen_h - pad - ph * 2 - 8
    _panel(hud, pad, y0, pw, ph, i18n.t('hud.spd'), '%d' % craft.airspeed_kmh, 'KM/H')
    _panel(hud, pad, y0 + ph + 8, pw, ph, i18n.t('hud.alt'), '%d' % craft.altitude, 'M')

    # ---------------- 右下：油门 / 升降率
    xr = screen_w - pad - pw
    _panel(hud, xr, y0, pw, ph, i18n.t('hud.thr'),
           '%d' % int(craft.throttle * 100), '%',
           vcol=GREEN if craft.throttle > 0.05 else DIM, bar=craft.throttle)
    vs_ = craft.vertical_speed
    vcol = GREEN if vs_ > 1.0 else (AMBER if vs_ < -1.0 else WHITE)
    _panel(hud, xr, y0 + ph + 8, pw, ph, i18n.t('hud.vs'), '%+.0f' % vs_, 'M/S', vcol=vcol)

    # ---------------- 油门面板上方：减速板 / 襟翼状态
    st_y = y0 - 24.0
    stx = xr + 4
    if getattr(craft, 'airbrake', 0.0) > 0.05:
        bt = i18n.t('hud.brake')
        hud.text(bt, stx, st_y, 15, AMBER)
        stx += hud.text_width(bt, 15) + 12
    if abs(getattr(craft, 'flaps', 0.0)) > 0.05:
        hud.text(i18n.t('hud.flaps'), stx, st_y, 15, CYAN)

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
    aoa_txt = '%s %+.1f' % (i18n.t('hud.aoa'), aoa)
    hud.text(aoa_txt, cx - hud.text_width(aoa_txt, 17) * 0.5, ty, 17, acol)
    g_txt = '%s %.1f' % (i18n.t('hud.gload'), craft.g_load)
    gcol = RED if craft.g_load > 3.0 else WHITE
    hud.text(g_txt, cx - hud.text_width(g_txt, 17) * 0.5, ty + 20, 17, gcol)

    # ---------------- 告警（再往下）
    warns = []
    if craft.crashed:
        warns.append((i18n.t('warn.crashed'), RED))
    elif craft.stalling:
        warns.append((i18n.t('warn.stall'), RED))
    if not craft.crashed:
        if craft.altitude < 120 and craft.vertical_speed < -8:
            warns.append((i18n.t('warn.pullup'), RED))
        if craft.throttle < 0.05 and craft.altitude > 200:
            warns.append((i18n.t('warn.lowpower'), AMBER))
        if abs(craft.aoa_deg) > 14 and not craft.stalling:
            warns.append((i18n.t('warn.highaoa'), AMBER))
    if getattr(craft, 'paused', False):
        warns.append((i18n.t('warn.paused'), WHITE))

    ts = 17.0
    wy = ty + 44
    for txt, col in warns:
        tw = hud.text_width(txt, ts)
        hud.rect(cx - tw * 0.5 - 12, wy - 5, tw + 24, ts * 1.55,
                 (0.16, 0.03, 0.03, 0.75))
        hud.text(txt, cx - tw * 0.5, wy, ts, col)
        wy += ts * 1.9

    # ---------------- 右上：FPS（带底衬，亮天空下也看得清）
    fps_txt = i18n.t('hud.fps', n=int(fps))
    fw = hud.text_width(fps_txt, 17)
    hud.rect(screen_w - pad - fw - 8, pad, fw + 8, 24, BG)
    hud.text(fps_txt, screen_w - pad - fw - 4, pad + 4, 17,
             (0.82, 0.86, 0.92, 1.0))

    # ---------------- 左上角：游戏名 / 版本号 + 机型 / 起落架状态
    # 排版用实测文字宽度累加，不要再手写 x 偏移（之前把机型名写死在
    # pad+62，而 "V1.4.0" 实际有 90.5 px 宽，两段就叠在一起了）。
    lx = pad + 2
    hud.text(i18n.t('hud.title'), lx, pad + 2, 20, WHITE)

    ny = pad + 30
    if i18n.is_zh():
        vtxt = '%s %s' % (i18n.t('hud.version'), VERSION)
    else:
        vtxt = 'V%s' % VERSION
    hud.text(vtxt, lx, ny, 16, DIM)
    vw = hud.text_width(vtxt, 16)

    sp = getattr(craft, 'spec', None)
    if sp is not None:
        name = sp.name if i18n.is_zh() else sp.name_en.upper()
        hud.text(name, lx + vw + 14, ny, 16,
                 CYAN if sp.kind == 'jet' else WHITE)

    # 机型特征 / 起落架状态：单独一行，带半透明底板，亮天空下也看得清
    if sp is not None:
        iy = pad + 62
        lines = []
        if sp.gear_retract:
            g = craft.gear
            if g > 0.99:
                lines.append((i18n.t('hud.gear_down'), GREEN))
            elif g < 0.01:
                lines.append((i18n.t('hud.gear_up'), CYAN))
            else:
                lines.append((i18n.t('hud.gear_moving', n=int(g * 100)), AMBER))
        else:
            lines.append((i18n.t('hud.gear_fixed'), DIM))
        lines.append((i18n.t('hud.engine_jet') if sp.kind == 'jet'
                      else i18n.t('hud.engine_piston'), DIM))

        # 底板尺寸按最长那行算。汉字需要更大的绘制字号才清晰
        # （点阵化后笔画密度高，字号太小会糊成一团）
        zh = i18n.is_zh()
        ts = 19.0 if zh else 15.0
        lh = 22.0 if zh else 17.0
        bw = max(hud.text_width(t, ts) for t, _ in lines) + 16
        bh = lh * len(lines) + 10
        hud.rect(lx - 3, iy - 4, bw, bh, BG)
        for i, (t, col) in enumerate(lines):
            hud.text(t, lx + 5, iy + i * lh, ts, col)

    hud.commit(screen_w, screen_h, shader)
