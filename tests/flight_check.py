# -*- coding: utf-8 -*-
"""飞行性验收测试（不开窗口）"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from skyflight import flight, terrain

FLAT = lambda x, z: 0.0
results = []


def record(name, ok, detail):
    results.append((name, ok, detail))
    print('  %s %-20s %s' % ('[OK]  ' if ok else '[FAIL]', name, detail))


def cruise(pos=(0.0, 1500.0, 0.0), thr=0.62, spd=80.0):
    a = flight.Aircraft(pos=pos)
    a.throttle = thr
    a.vel = np.array([0.0, 0.0, -spd], dtype=float)
    a.speed_val = spd
    return a


# ---------- 1) 平飞稳定性
a = cruise()
ma = mp = 0.0
for i in range(60 * 30):
    a.update(1/60.0, {'pitch': 0, 'roll': 0, 'yaw': 0, 'flaps': 0, 'throttle': 0.62}, FLAT)
    ma = max(ma, abs(a.aoa_deg))
    mp = max(mp, abs(math.degrees(a.pitch)))
ok = ma < 8 and mp < 8 and not a.crashed and all(math.isfinite(v) for v in np.concatenate([a.pos, a.vel]))
record('平飞稳定(30s)', ok, '迎角≤%.1f° 俯仰≤%.1f° 速度%.0f 高度%.0f' % (ma, mp, a.airspeed_kmh, a.altitude))

# ---------- 2) 拉杆抬头
a = cruise((0, 1500, 0))
p0 = math.degrees(a.pitch)
for i in range(60 * 4):
    a.update(1/60.0, {'pitch': 0.8, 'roll': 0, 'yaw': 0, 'flaps': 0, 'throttle': 0.85}, FLAT)
p1 = math.degrees(a.pitch)
ok = p1 > p0 + 8 and a.altitude > 1500
record('拉杆抬头', ok, '俯仰 %.1f° -> %.1f°  高度 %.0f m  迎角 %.1f°' % (p0, p1, a.altitude, a.aoa_deg))

# ---------- 3) 推杆低头
a = cruise((0, 1500, 0))
for i in range(60 * 4):
    a.update(1/60.0, {'pitch': -0.8, 'roll': 0, 'yaw': 0, 'flaps': 0, 'throttle': 0.6}, FLAT)
ok = math.degrees(a.pitch) < -8 and a.altitude < 1500
record('推杆低头', ok, '俯仰 %.1f°  高度 %.0f m' % (math.degrees(a.pitch), a.altitude))

# ---------- 4) 右滚方向
a = cruise((0, 1500, 0))
for i in range(int(60 * 1.5)):
    a.update(1/60.0, {'pitch': 0, 'roll': 1.0, 'yaw': 0, 'flaps': 0, 'throttle': 0.65}, FLAT)
ok = math.radians(40) < a.roll < math.radians(120)
record('右滚方向正确', ok, '滚转 = %.1f°（正=右翼下沉）' % math.degrees(a.roll))

# ---------- 5) 左滚
a = cruise((0, 1500, 0))
for i in range(int(60 * 1.5)):
    a.update(1/60.0, {'pitch': 0, 'roll': -1.0, 'yaw': 0, 'flaps': 0, 'throttle': 0.65}, FLAT)
ok = -math.radians(120) < a.roll < -math.radians(40)
record('左滚方向正确', ok, '滚转 = %.1f°' % math.degrees(a.roll))

# ---------- 6) 松杆自动回正（上反角自稳）
a = cruise((0, 1500, 0))
for i in range(int(60 * 2)):
    a.update(1/60.0, {'pitch': 0, 'roll': 1.0, 'yaw': 0, 'flaps': 0, 'throttle': 0.65}, FLAT)
r1 = a.roll
for i in range(int(60 * 3)):
    a.update(1/60.0, {'pitch': 0, 'roll': 0, 'yaw': 0, 'flaps': 0, 'throttle': 0.65}, FLAT)
record('松杆自动回正', abs(a.roll) < math.radians(12),
       '滚转 %.0f° -> %.0f°（松杆后自动恢复平飞）' % (math.degrees(r1), math.degrees(a.roll)))

# ---------- 7) 失速
a = cruise((0, 3000, 0), thr=0.0, spd=60.0)
st = False
for i in range(60 * 15):
    a.update(1/60.0, {'pitch': 1.0, 'roll': 0, 'yaw': 0, 'flaps': 0, 'throttle': 0.0}, FLAT)
    if a.stalling:
        st = True
recovered = not a.stalling
record('失速可触发', st, '迎角 %.1f°  末速 %.0f km/h' % (a.aoa_deg, a.airspeed_kmh))

# ---------- 8) 起飞
a = flight.Aircraft(pos=(0.0, 1.0, 1200.0))
a.vel = np.zeros(3)
a.speed_val = 0.0
a.throttle = 1.0
lift = False
for i in range(60 * 40):
    a.update(1/60.0, {'pitch': 0.75 if a.airspeed_kmh > 70 else 0.0, 'roll': 0,
                      'yaw': 0, 'flaps': 0.5, 'throttle': 1.0}, FLAT)
    if a.altitude > 15:
        lift = True
        break
record('地面起飞', lift, '%s  用时 %.1f s  速度 %.0f km/h' % ('成功' if lift else '失败', i / 60, a.airspeed_kmh))

# ---------- 9) 带地形长航时（爬升后保持平飞，测试地形跟随 + 撞地判定）
a = flight.Aircraft(pos=(0.0, terrain.height_at(0, 0) + 2.0, 1200.0))
a.vel = np.zeros(3)
a.speed_val = 0.0
a.on_ground = True
crashed = False
target_alt = None
for i in range(60 * 90):
    # 先滑跑起飞，爬到 400 m 后改平，之后按高度误差微调
    if a.airspeed_kmh < 70:
        pitch_cmd = 0.0
    elif target_alt is None:
        pitch_cmd = 0.55
        if a.altitude > 400.0:
            target_alt = a.altitude
    else:
        err = target_alt - a.altitude
        pitch_cmd = max(-0.35, min(0.35, err * 0.010))
    a.update(1 / 60.0, {'pitch': pitch_cmd, 'roll': 0, 'yaw': 0,
                        'flaps': 0.0, 'throttle': 0.65},
             lambda x, z: terrain.height_at(x, z))
    if a.crashed:
        crashed = True
        break
agl = a.altitude - terrain.height_at(a.pos[0], a.pos[2])
record('真实地形飞行90s', not crashed,
       '离地 %.0f m  速度 %.0f km/h  高度 %.0f m  %s' % (
           agl, a.airspeed_kmh, a.altitude, '坠毁' if crashed else '正常'))

# ---------- 10) 重来功能
a = cruise()
a.crash()
a.reset((0.0, 60.0, 1200.0))
record('坠毁后重来', not a.crashed and abs(a.speed_val - 78.0) < 35,
       '速度 %.0f m/s  坠毁=%s' % (a.speed_val, a.crashed))

print()
n_ok = sum(1 for _, ok, _ in results if ok)
print('=' * 62)
print('  飞行测试: %d/%d 通过' % (n_ok, len(results)))
print('=' * 62)
sys.exit(0 if n_ok == len(results) else 1)
