# -*- coding: utf-8 -*-
"""
地景道具：静态几何（每个道具自己一个网格，用实例化复制很多份）

都是一次性建好的低面数几何，用 gfx.Mesh 的实例化绘制。
道具之间只共用一套"实例参数"格式（位置/缩放/朝向/颜色），
所以可以统一用 InstancedProps 管理。

已有道具：
  House        小房子（墙 + 坡屋顶 + 门窗）
  Barn         谷仓（大拱顶 + 侧门 + 筒仓）
  HangarBay    简易机库（拱形棚）
  Warehouse    仓库（平顶大厂房 + 装卸门）
  Church       小教堂（尖塔，村庄地标）
  Rock         石头（不规则多面体）
  Turbine      风力发电机（塔 + 机舱 + 三叶轮）
  WaterTower   水塔（圆柱 + 支腿）
"""
import math

import numpy as np

from . import gfx


# ==================================================================
#  建筑
# ==================================================================
def _house():
    """小房子：墙体 + 坡屋顶 + 门窗（原来的版本，保留）"""
    v = []
    v += gfx.box(0.0, 2.2, 0.0, 9.0, 4.4, 11.0, (0.86, 0.84, 0.80))
    v += gfx.box(0.0, 4.8, 0.0, 10.0, 0.8, 12.0, (0.55, 0.28, 0.22))
    v += gfx.box(0.0, 5.5, 0.0, 7.4, 0.8, 9.4, (0.60, 0.31, 0.24))
    v += gfx.box(0.0, 6.1, 0.0, 4.2, 0.7, 6.0, (0.66, 0.34, 0.26))
    v += gfx.box(0.0, 1.4, -5.6, 1.8, 2.8, 0.3, (0.35, 0.28, 0.22))
    v += gfx.box(3.2, 2.6, -5.6, 2.0, 2.0, 0.3, (0.45, 0.62, 0.72))
    v += gfx.box(-3.2, 2.6, -5.6, 2.0, 2.0, 0.3, (0.45, 0.62, 0.72))
    return v


def _barn():
    """谷仓：大红墙 + 深色拱顶 + 侧门 + 旁边一个筒仓"""
    v = []
    v += gfx.box(0.0, 4.5, 0.0, 20.0, 9.0, 30.0, (0.62, 0.20, 0.17))
    # 拱顶：两级递减
    v += gfx.box(0.0, 9.6, 0.0, 21.0, 1.4, 31.0, (0.34, 0.32, 0.33))
    v += gfx.box(0.0, 10.8, 0.0, 15.0, 1.2, 22.0, (0.36, 0.34, 0.35))
    v += gfx.box(0.0, 11.8, 0.0, 8.0, 1.0, 12.0, (0.38, 0.36, 0.37))
    # 大门（白框 + 深色门板）
    v += gfx.box(0.0, 3.0, -15.2, 9.0, 6.0, 0.4, (0.88, 0.86, 0.82))
    v += gfx.box(0.0, 3.2, -15.5, 7.0, 5.0, 0.3, (0.30, 0.26, 0.22))
    # 白十字（很多谷仓都有）
    v += gfx.box(0.0, 13.0, -14.0, 1.6, 5.0, 0.4, (0.92, 0.90, 0.86))
    v += gfx.box(0.0, 13.0, -14.0, 5.0, 1.6, 0.4, (0.92, 0.90, 0.86))
    # 筒仓
    v += gfx.box(14.0, 6.0, 4.0, 8.0, 12.0, 8.0, (0.80, 0.78, 0.72))
    v += gfx.box(14.0, 12.4, 4.0, 8.6, 0.9, 8.6, (0.55, 0.56, 0.58))
    return v


def _warehouse():
    """仓库：平顶厂房 + 装卸门 + 通风口"""
    v = []
    v += gfx.box(0.0, 4.0, 0.0, 26.0, 8.0, 44.0, (0.74, 0.75, 0.77))
    v += gfx.box(0.0, 8.5, 0.0, 27.0, 1.0, 45.0, (0.48, 0.50, 0.53))
    # 装卸门（正面三扇）
    for dz in (-12.0, 0.0, 12.0):
        v += gfx.box(0.0, 2.6, dz, 0.4, 5.2, 6.0, (0.30, 0.32, 0.35))
        v += gfx.box(0.0, 5.6, dz, 0.5, 0.7, 6.6, (0.88, 0.80, 0.30))
    # 屋顶通风口
    for dz in (-14.0, 0.0, 14.0):
        v += gfx.box(0.0, 9.6, dz, 3.0, 1.2, 3.0, (0.55, 0.57, 0.60))
    return v


def _hangar_bay():
    """简易机库：拱形棚，正面敞开"""
    v = []
    # 侧墙
    for side in (1, -1):
        v += gfx.box(side * 11.0, 4.0, 0.0, 2.0, 8.0, 26.0, (0.70, 0.72, 0.74))
    # 后墙
    v += gfx.box(0.0, 4.0, 12.0, 24.0, 8.0, 2.0, (0.68, 0.70, 0.72))
    # 拱顶（三级）
    v += gfx.box(0.0, 8.6, 0.0, 24.0, 1.2, 27.0, (0.52, 0.54, 0.57))
    v += gfx.box(0.0, 9.8, 0.0, 18.0, 1.0, 27.0, (0.55, 0.57, 0.60))
    v += gfx.box(0.0, 10.7, 0.0, 10.0, 0.8, 27.0, (0.58, 0.60, 0.63))
    # 门框
    v += gfx.box(0.0, 6.4, -12.6, 24.0, 0.8, 1.2, (0.40, 0.42, 0.45))
    return v


def _church():
    """小教堂：主厅 + 高尖塔（村庄里的地标）"""
    v = []
    v += gfx.box(0.0, 4.0, 0.0, 12.0, 8.0, 22.0, (0.90, 0.88, 0.82))
    v += gfx.box(0.0, 8.6, 0.0, 13.0, 1.2, 23.0, (0.42, 0.32, 0.30))
    # 尖塔
    v += gfx.box(0.0, 11.0, -8.0, 7.0, 14.0, 7.0, (0.88, 0.86, 0.80))
    v += gfx.box(0.0, 19.0, -8.0, 5.0, 4.0, 5.0, (0.38, 0.30, 0.28))
    v += gfx.box(0.0, 22.6, -8.0, 2.2, 5.0, 2.2, (0.40, 0.32, 0.30))
    v += gfx.box(0.0, 25.6, -8.0, 0.7, 2.6, 0.7, (0.85, 0.75, 0.35))
    # 长条窗
    for dz in (-6.0, 0.0, 6.0):
        v += gfx.box(6.1, 4.6, dz, 0.3, 4.0, 1.6, (0.55, 0.35, 0.55))
        v += gfx.box(-6.1, 4.6, dz, 0.3, 4.0, 1.6, (0.55, 0.35, 0.55))
    return v


def _water_tower():
    """水塔：圆柱 + 支腿 + 顶盖"""
    v = []
    for sx in (-1, 1):
        for sz in (-1, 1):
            v += gfx.box(sx * 2.2, 3.0, sz * 2.2, 0.7, 6.0, 0.7, (0.52, 0.54, 0.56))
    v += gfx.box(0.0, 9.0, 0.0, 7.0, 7.0, 7.0, (0.76, 0.78, 0.80))
    v += gfx.box(0.0, 12.9, 0.0, 8.0, 0.9, 8.0, (0.48, 0.50, 0.53))
    v += gfx.box(0.0, 14.0, 0.0, 1.0, 1.6, 1.0, (0.55, 0.57, 0.60))
    return v


# ==================================================================
#  自然物
# ==================================================================
def _rock():
    """石头：用错位的盒子拼出不规则感"""
    v = []
    v += gfx.box(0.0, 0.9, 0.0, 4.2, 1.8, 3.4, (0.46, 0.45, 0.44))
    v += gfx.box(0.9, 1.9, -0.4, 2.4, 1.4, 2.2, (0.51, 0.50, 0.49))
    v += gfx.box(-1.1, 1.6, 0.6, 1.8, 1.2, 1.9, (0.42, 0.41, 0.40))
    v += gfx.box(0.3, 0.5, 1.5, 2.6, 1.0, 1.4, (0.48, 0.47, 0.46))
    return v


def _turbine():
    """风力发电机：锥形塔 + 机舱 + 三叶轮（竖直摆好，叶片在 XY 平面）

    局部坐标：塔基在 y=0，机舱在顶部，叶片绕 Z 轴排布。
    这是静态几何；要让叶片转需要单独一个绕 Z 旋转的网格。
    """
    v = []
    col_tower = (0.86, 0.87, 0.88)
    col_blade = (0.90, 0.91, 0.92)
    # 塔（三级递减，做出锥形）
    v += gfx.box(0.0, 4.0, 0.0, 3.2, 8.0, 3.2, col_tower)
    v += gfx.box(0.0, 12.0, 0.0, 2.4, 8.0, 2.4, col_tower)
    v += gfx.box(0.0, 19.0, 0.0, 1.7, 6.0, 1.7, col_tower)
    # 机舱
    v += gfx.box(0.0, 22.6, 0.0, 2.2, 2.0, 5.6, (0.78, 0.79, 0.81))
    return v


def _turbine_rotor():
    """风机的三片叶轮（单独一个网格，好让它绕 Z 轴转）"""
    v = []
    col = (0.92, 0.93, 0.94)
    for k in range(3):
        a = math.radians(120.0 * k)
        ca, sa = math.cos(a), math.sin(a)
        # 叶片：从轮毂往外伸，长 13，宽 1.1
        ln, wd = 13.0, 1.1
        # 叶片的四个角（先做未旋转的竖直叶片，再绕 Z 转 a）
        pts = []
        for dx, dy in ((0.0, 1.6), (0.0, 1.6 + ln),
                       (wd, 1.6 + ln), (wd, 1.6)):
            pts.append((dx * ca - dy * sa, dx * sa + dy * ca))
        # 用 gfx.box 不方便做旋转，直接用三角形拼一个薄片
        (x0, y0), (x1, y1), (x2, y2), (x3, y3) = pts
        n = (0.0, 0.0, 1.0)
        for tri in ((x0, y0, x1, y1, x2, y2), (x0, y0, x2, y2, x3, y3)):
            for i in range(0, 6, 2):
                v.extend([tri[i], tri[i + 1], 0.0, n[0], n[1], n[2],
                          col[0], col[1], col[2]])
    # 轮毂
    v += gfx.box(0.0, 0.0, -0.6, 2.6, 2.6, 1.4, (0.72, 0.73, 0.75))
    return v


# ==================================================================
#  实例化道具管理
# ==================================================================
class Props:
    """管理一组静态道具（每个自己一个网格，靠实例化复制）

    实例数据格式和树完全一样（8 个 float）：
        x, y, z, scale, yaw, r, g, b
    """

    def __init__(self, name, builder, cast_shadow=False):
        self.name = name
        self.builder = builder
        self.mesh = None
        self.count = 0
        self.center = None
        self.radius = 2600.0
        self.cell = 46.0
        self._pending = None
        self.min_spacing = 0.0

    def ensure(self):
        if self.mesh is None:
            self.mesh = gfx.Mesh(self.builder())

    def set_instances(self, data):
        if data is None or len(data) == 0:
            self.count = 0
            return
        self.ensure()
        self.mesh.set_instances(data)
        self.count = data.shape[0]

    def draw(self, shader):
        if self.count and self.mesh is not None:
            self.mesh.draw_instanced()


class TurbineRotor:
    """风机的叶轮：单独一个网格，绕自己的 Z 轴缓慢旋转

    动起来的风车地标很好看，而且成本极低（每帧只改一个矩阵）。
    """

    def __init__(self):
        self.mesh = None
        self.instances = None
        self.angle = 0.0
        self.rate = 0.35          # rad/s

    def ensure(self):
        if self.mesh is None:
            self.mesh = gfx.Mesh(_turbine_rotor())

    def set_instances(self, data):
        self.instances = data
        self.ensure()

    def update(self, dt):
        self.angle = (self.angle + self.rate * dt) % (2 * math.pi)

    def draw(self, shader):
        """叶轮要单独画：位置 = 风机塔顶，并且绕自己的 Z 轴转

        实例化没法表达"每个实例再自转"的层级关系，但风机的叶轮
        只有少数几个，用一个实例化网格 + 每帧算一次旋转矩阵即可。
        """
        if self.instances is None or len(self.instances) == 0:
            return
        # 数量很少（几十个），逐个画，每个带自己的旋转
        ca, sa = math.cos(self.angle), math.sin(self.angle)
        R = np.array([[ca, -sa, 0.0, 0.0],
                      [sa, ca, 0.0, 0.0],
                      [0.0, 0.0, 1.0, 0.0],
                      [0.0, 0.0, 0.0, 1.0]], dtype=np.float32)
        for row in self.instances:
            x, y, z = float(row[0]), float(row[1]), float(row[2])
            sc = float(row[3])
            yaw = float(row[4])
            cy, sy = math.cos(yaw), math.sin(yaw)
            Y = np.array([[cy, 0.0, sy, 0.0],
                          [0.0, 1.0, 0.0, 0.0],
                          [-sy, 0.0, cy, 0.0],
                          [0.0, 0.0, 0.0, 1.0]], dtype=np.float32)
            M = np.eye(4, dtype=np.float32)
            M[0, 3] = x
            M[1, 3] = y
            M[2, 3] = z
            S = np.diag([sc, sc, sc, 1.0]).astype(np.float32)
            model = M @ Y @ S @ R
            shader.set_mat4('uModel', model)
            shader.set_mat3('uNormalMat', model[:3, :3])
            self.mesh.draw()


# ==================================================================
#  构建所有道具（模块级单例，懒加载）
# ==================================================================
PROP_BUILDERS = {
    'house': _house,
    'barn': _barn,
    'warehouse': _warehouse,
    'hangar': _hangar_bay,
    'church': _church,
    'water_tower': _water_tower,
    'rock': _rock,
}


def build_all():
    """返回 {名字: 顶点数组}。只建一次，之后复用"""
    return {k: fn() for k, fn in PROP_BUILDERS.items()}
