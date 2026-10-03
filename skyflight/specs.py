# -*- coding: utf-8 -*-
"""
机型规格表

每种机型有自己的几何尺寸、飞行性能参数和起落架特性。
flight.Aircraft 会读这里的参数来初始化，所以换机型 = 换一套飞行手感。

性能参数说明（想调机型手感就改这里）：
  mass          质量 kg —— 越大越"重"，加速慢、转弯半径大
  wing_area     机翼面积 m² —— 越大升力越足，失速速度越低
  max_thrust    最大推力 N —— 涡喷推力远大于螺旋桨
  V_ref         参考空速 m/s —— 操纵效能的基准速度
  CD0           寄生阻力系数 —— 喷气机外形干净，比螺旋桨小
  stall_angle   失速迎角 rad —— 后掠翼喷气机失速迎角略低
  gear_height   轮胎底到机身原点的距离 m —— 决定停机高度
  gear_retract  起落架能否收放 —— 螺旋桨教练机是固定式，不能收
"""


class Spec:
    def __init__(self, key, name, name_en, kind, desc, **kw):
        self.key = key
        self.name = name
        self.name_en = name_en
        self.kind = kind          # 'piston' | 'jet'
        self.desc = desc
        # 几何
        self.wing_span = kw.get('wing_span', 11.0)
        self.fuse_len = kw.get('fuse_len', 8.4)
        self.gear_height = kw.get('gear_height', 1.07)
        self.gear_retract = kw.get('gear_retract', False)
        # 飞行性能
        self.mass = kw.get('mass', 1100.0)
        self.wing_area = kw.get('wing_area', 16.2)
        self.max_thrust = kw.get('max_thrust', 3600.0)
        self.V_ref = kw.get('V_ref', 75.0)
        self.cruise_speed = kw.get('cruise_speed', 78.0)
        self.CL0 = kw.get('CL0', 0.10)
        self.CL_alpha = kw.get('CL_alpha', 4.6)
        self.CL_max = kw.get('CL_max', 1.42)
        self.stall_deg = kw.get('stall_deg', 16.0)
        self.CD0 = kw.get('CD0', 0.030)
        self.k_induced = kw.get('k_induced', 0.048)
        self.roll_power = kw.get('roll_power', 12.5)
        self.pitch_power = kw.get('pitch_power', 3.1)
        self.yaw_power = kw.get('yaw_power', 2.6)
        self.roll_rate_cmd = kw.get('roll_rate_cmd', 1.15)
        self.thrust_lapse = kw.get('thrust_lapse', 0.20)


CATALOG = [
    Spec(
        'trainer', '螺旋桨教练机', 'Prop Trainer', 'piston',
        '低速好飞，固定起落架，适合练手',
        wing_span=11.0, fuse_len=8.4, gear_height=1.07, gear_retract=False,
        mass=1100.0, wing_area=16.2, max_thrust=3600.0,
        V_ref=75.0, cruise_speed=78.0,
        CL0=0.10, CL_alpha=4.6, CL_max=1.42, stall_deg=16.0,
        CD0=0.030, k_induced=0.048,
        roll_power=12.5, pitch_power=3.1, yaw_power=2.6,
    ),
    Spec(
        'jet_light', '轻型涡喷教练机', 'Light Jet', 'jet',
        '单发涡喷，可收起落架，爬升和加速都快',
        wing_span=10.7, fuse_len=11.6, gear_height=1.34, gear_retract=True,
        mass=3200.0, wing_area=17.5, max_thrust=16500.0,
        V_ref=105.0, cruise_speed=145.0,
        CL0=0.06, CL_alpha=4.0, CL_max=1.30, stall_deg=15.0,
        CD0=0.020, k_induced=0.052,
        roll_power=18.0, pitch_power=4.2, yaw_power=3.4,
        roll_rate_cmd=1.55, thrust_lapse=0.28,
    ),
    Spec(
        'jet_heavy', '双发涡喷公务机', 'Twin Jet', 'jet',
        '双发涡喷，机身重、翼载高，速度快但转弯半径大',
        wing_span=15.6, fuse_len=16.8, gear_height=1.62, gear_retract=True,
        mass=9800.0, wing_area=39.0, max_thrust=48000.0,
        V_ref=145.0, cruise_speed=210.0,
        CL0=0.05, CL_alpha=4.4, CL_max=1.34, stall_deg=16.0,
        CD0=0.019, k_induced=0.045,
        roll_power=11.0, pitch_power=3.6, yaw_power=3.0,
        roll_rate_cmd=0.95, thrust_lapse=0.30,
    ),
]

BY_KEY = {s.key: s for s in CATALOG}
DEFAULT = CATALOG[0]


def get(key):
    return BY_KEY.get(key, DEFAULT)


def index_of(key):
    for i, s in enumerate(CATALOG):
        if s.key == key:
            return i
    return 0


def next_key(current):
    i = index_of(current)
    return CATALOG[(i + 1) % len(CATALOG)].key
