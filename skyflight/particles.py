# -*- coding: utf-8 -*-
"""
粒子特效：爆炸、接地扬尘、轮胎烟、高空凝结尾

做法：
  - 一个固定大小的粒子池（默认 600 个），每个粒子是朝向相机的小方片
  - 每帧在 CPU 上更新位置/速度/寿命，然后写进实例缓冲一次性画完
  - 用实例化绘制，所以几百个粒子只有一次 draw call
  - 粒子永远面向相机（billboard）：用相机的右/上向量拼矩阵

生成的实例数据格式和树/道具一样（8 个 float）：
    x, y, z, scale, yaw, r, g, b
实例数据里 yaw 没用到（billboard 自己算朝向），保留是为格式统一。
"""
import math

import numpy as np

from . import gfx

MAX_PARTICLES = 700


class Particles:
    """粒子池 + 实例化绘制"""

    def __init__(self, capacity=MAX_PARTICLES):
        self.cap = int(capacity)
        self.pos = np.zeros((self.cap, 3), dtype=np.float64)
        self.vel = np.zeros((self.cap, 3), dtype=np.float64)
        self.life = np.zeros(self.cap, dtype=np.float64)      # 剩余寿命（秒）
        self.total = np.ones(self.cap, dtype=np.float64)      # 初始寿命
        self.size0 = np.zeros(self.cap, dtype=np.float64)     # 初始尺寸
        self.grow = np.zeros(self.cap, dtype=np.float64)      # 尺寸增长
        self.col0 = np.zeros((self.cap, 3), dtype=np.float64)
        self.col1 = np.zeros((self.cap, 3), dtype=np.float64)
        self.drag = np.zeros(self.cap, dtype=np.float64)
        self.gravity = np.zeros(self.cap, dtype=np.float64)
        self.alive = np.zeros(self.cap, dtype=bool)
        self.next = 0
        self.mesh = None
        self._instbuf = None

    # ------------------------------------------------ 生成
    def _alloc(self, n):
        """找 n 个空位（环形扫描），返回索引数组"""
        idx = []
        cap = self.cap
        i = self.next
        tried = 0
        while len(idx) < n and tried < cap:
            if not self.alive[i]:
                idx.append(i)
            i = (i + 1) % cap
            tried += 1
        # 不够就抢最老的
        while len(idx) < n:
            idx.append((self.next + len(idx)) % cap)
        self.next = (i + 1) % cap
        return np.asarray(idx, dtype=np.int64)

    def spawn(self, n, pos, spread=0.0, vel=None, speed=(0.0, 0.0),
              life=(0.6, 1.4), size=(0.6, 2.2), grow=0.0,
              col0=(1.0, 0.7, 0.2), col1=(0.15, 0.10, 0.10),
              drag=1.2, gravity=-3.0, rng=None):
        """批量生成粒子

        pos    中心位置
        spread 位置随机半径
        vel    统一初速度（比如爆炸喷出方向）
        speed  在 vel 基础上的随机加减速范围
        life   寿命范围（秒）
        size   初始尺寸范围
        grow   每秒尺寸增长
        col0/1 起始颜色 -> 结束颜色
        drag   空气阻力（越大越快停下来）
        gravity 重力加速度
        """
        if rng is None:
            rng = np.random.default_rng()
        n = int(n)
        if n <= 0:
            return
        idx = self._alloc(n)
        pos = np.asarray(pos, dtype=np.float64)
        # 位置抖动
        self.pos[idx] = pos + rng.normal(0.0, max(1e-6, spread), (n, 3))
        if vel is None:
            base = np.zeros(3)
        else:
            base = np.asarray(vel, dtype=np.float64)
        dirs = rng.normal(0.0, 1.0, (n, 3))
        ln = np.linalg.norm(dirs, axis=1, keepdims=True)
        ln[ln < 1e-6] = 1.0
        dirs = dirs / ln
        sp = rng.uniform(speed[0], speed[1], (n, 1))
        self.vel[idx] = base + dirs * sp
        self.total[idx] = rng.uniform(life[0], life[1], n)
        self.life[idx] = self.total[idx]
        self.size0[idx] = rng.uniform(size[0], size[1], n)
        self.grow[idx] = float(grow)
        self.col0[idx] = np.asarray(col0, dtype=np.float64)
        self.col1[idx] = np.asarray(col1, dtype=np.float64)
        self.drag[idx] = float(drag)
        self.gravity[idx] = float(gravity)
        self.alive[idx] = True

    # ------------------------------------------------ 预设特效
    def explosion(self, pos, scale=1.0):
        """爆炸：火球 + 冲击碎片 + 黑烟，四段一起放

        比例调过：火球和碎片要多、要亮，烟要少一点 —— 否则烟一多就把
        火光全糊住了，看着像一团灰云而不是爆炸。
        """
        rng = np.random.default_rng(1234)
        s = float(scale)
        # 1) 火球（亮黄橙，快速膨胀、短命）—— 数量最多、最亮
        self.spawn(int(140 * s), pos, spread=1.8 * s,
                   speed=(7.0 * s, 26.0 * s), life=(0.45, 1.05),
                   size=(2.2 * s, 5.2 * s), grow=9.0 * s,
                   col0=(1.0, 0.98, 0.72), col1=(1.0, 0.42, 0.05),
                   drag=2.4, gravity=5.0, rng=rng)
        # 2) 内层白热核心（小、极亮、一闪就没）
        self.spawn(int(40 * s), pos, spread=0.7 * s,
                   speed=(3.0 * s, 14.0 * s), life=(0.18, 0.45),
                   size=(2.0 * s, 4.5 * s), grow=6.0 * s,
                   col0=(1.0, 1.0, 0.98), col1=(1.0, 0.85, 0.35),
                   drag=3.0, gravity=2.0, rng=rng)
        # 3) 火星碎片（向各方向飞溅，带重力）
        self.spawn(int(90 * s), pos, spread=1.0 * s,
                   speed=(12.0 * s, 40.0 * s), life=(0.7, 1.8),
                   size=(0.35 * s, 0.95 * s), grow=-0.2,
                   col0=(1.0, 0.92, 0.55), col1=(0.75, 0.18, 0.04),
                   drag=0.35, gravity=-16.0, rng=rng)
        # 4) 黑烟（慢、少一点，别把火盖住）
        self.spawn(int(46 * s), pos, spread=3.2 * s,
                   speed=(1.5 * s, 5.0 * s), life=(1.6, 3.2),
                   size=(2.4 * s, 4.6 * s), grow=3.6 * s,
                   col0=(0.34, 0.31, 0.30), col1=(0.13, 0.13, 0.14),
                   drag=1.6, gravity=1.0, rng=rng)
        # 5) 地面扬尘
        self.spawn(int(34 * s), pos, spread=4.5 * s,
                   speed=(3.0 * s, 13.0 * s), life=(0.9, 1.8),
                   size=(2.0 * s, 4.5 * s), grow=3.0 * s,
                   col0=(0.58, 0.53, 0.45), col1=(0.44, 0.42, 0.38),
                   drag=2.2, gravity=0.6, rng=rng)

    def dust(self, pos, strength=1.0, n=26):
        """接地扬尘：从轮子位置往两侧散开"""
        rng = np.random.default_rng(int(pos[0] * 13.7 + pos[2] * 7.1) & 0xFFFF)
        s = float(np.clip(strength, 0.3, 1.6))
        self.spawn(int(n * s), pos, spread=1.4,
                   speed=(2.0 * s, 7.0 * s), life=(0.5, 1.2),
                   size=(1.2 * s, 3.0 * s), grow=2.2,
                   col0=(0.62, 0.58, 0.50), col1=(0.48, 0.46, 0.42),
                   drag=2.4, gravity=0.4, rng=rng)
        self.spawn(int(n * 0.5 * s), pos, spread=1.0,
                   speed=(1.0 * s, 4.0 * s), life=(0.4, 0.9),
                   size=(0.8, 2.0), grow=1.6,
                   col0=(0.72, 0.70, 0.66), col1=(0.55, 0.54, 0.52),
                   drag=2.8, gravity=0.2, rng=rng)

    def smoke_trail(self, pos, vel, strength=1.0, n=4, dark=False):
        """持续冒烟（发动机受损/坠落后）或轮胎烟"""
        rng = np.random.default_rng()
        if dark:
            c0, c1 = (0.22, 0.22, 0.23), (0.08, 0.08, 0.09)
        else:
            c0, c1 = (0.78, 0.76, 0.72), (0.60, 0.59, 0.57)
        self.spawn(int(n), pos, spread=0.9,
                   vel=vel, speed=(0.5, 2.5), life=(0.8, 1.8),
                   size=(1.0, 2.6) , grow=2.6,
                   col0=c0, col1=c1, drag=1.4, gravity=0.3, rng=rng)

    def contrail(self, pos, vel, strength=1.0, n=2):
        """高空凝结尾：又白又淡又长命"""
        rng = np.random.default_rng()
        self.spawn(int(n), pos, spread=0.6,
                   vel=vel, speed=(0.2, 1.0), life=(2.0, 4.0),
                   size=(1.2, 2.4), grow=2.2,
                   col0=(0.95, 0.96, 0.98), col1=(0.88, 0.90, 0.94),
                   drag=0.8, gravity=0.05, rng=rng)

    # ------------------------------------------------ 更新
    def update(self, dt):
        """推进所有粒子：位置、速度、尺寸、颜色、寿命"""
        if not np.any(self.alive):
            return
        a = self.alive
        dt = float(min(dt, 0.1))
        # 阻力（指数衰减）
        d = self.drag[a]
        damp = np.exp(-d * dt)
        self.vel[a] = self.vel[a] * damp[:, None]
        # 重力
        self.vel[a, 1] += self.gravity[a] * dt
        # 位置
        self.pos[a] += self.vel[a] * dt
        # 寿命
        self.life[a] -= dt
        dead = self.life <= 0.0
        self.alive[dead] = False

    def count(self):
        return int(np.count_nonzero(self.alive))

    # ------------------------------------------------ 绘制
    def _ensure(self):
        if self.mesh is None:
            self.mesh = gfx.Mesh(self._quad())
        if self._instbuf is None:
            self._instbuf = np.zeros((self.cap, 8), dtype=np.float32)

    @staticmethod
    def _quad():
        """单位方片（面向 +Z，billboard 时用相机矩阵转到屏幕朝向）"""
        v = []
        # 位置 xyz + 法线 xyz + 颜色 rgb
        pts = ((-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5))
        for i in (0, 1, 2, 0, 2, 3):
            x, y = pts[i]
            v.extend([x, y, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0])
        return np.asarray(v, dtype=np.float32)

    def visible_instances(self, cam_right, cam_up):
        """返回 (实例数据, 数量)，不涉及任何 GL 调用

        位置是世界坐标；朝向由 particle 着色器用相机右/上向量展开，
        所以这里不需要算朝向。cam_right / cam_up 目前没用到，
        保留参数是为了接口清晰（说明粒子是 billboard）。
        """
        a = np.nonzero(self.alive)[0]
        if a.size == 0:
            return None, 0
        # 寿命比例 -> 颜色插值和淡出
        t = 1.0 - np.clip(self.life[a] / np.maximum(1e-6, self.total[a]), 0.0, 1.0)
        col = (self.col0[a] * (1.0 - t)[:, None] + self.col1[a] * t[:, None])
        # 淡出：越接近死亡越暗（不用 alpha，省得开混合）
        fade = np.clip(1.0 - t * t, 0.0, 1.0)[:, None]
        col = col * fade
        size = self.size0[a] + self.grow[a] * (self.total[a] - self.life[a])
        size = np.maximum(0.05, size)
        if self._instbuf is None or self._instbuf.shape[0] < a.size:
            self._instbuf = np.zeros((max(a.size, 64), 8), dtype=np.float32)
        buf = self._instbuf[:a.size]
        buf[:, 0:3] = self.pos[a]
        buf[:, 3] = size
        buf[:, 4] = 0.0
        buf[:, 5:8] = np.clip(col, 0.0, 1.0)
        return buf, int(a.size)

    def draw_instances(self):
        """把当前粒子画出来（这里才会用到 GL）"""
        if self.mesh is None:
            return
        self.mesh.draw_instanced()

    def ensure_mesh(self):
        self._ensure()
