# -*- coding: utf-8 -*-
"""
机型检查：三种机型的几何、性能参数、起落架一致性

必须通过的硬性条件：
  1. 每种机型的模型顶点能正常生成，机翼/机身尺寸和 specs 声明一致
  2. 起落架模型的最低点 = -specs.gear_height（否则停机高度会错）
  3. 每种机型都能起飞、能平飞、能转弯
  4. 可收放机型的起落架能收能放，收起后阻力变小（速度更快）
  5. 固定起落架机型拒绝收起指令
"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from skyflight import gfx, plane, specs, flight


def _ground(x, z):
    """测试用地面高度函数：一律当平地（update 需要一个可调用对象）"""
    return 0.0

ok = True


def check(name, fn):
    global ok
    try:
        fn()
        print('  [OK] %s' % name)
    except AssertionError as e:
        ok = False
        print('  [FAIL] %s' % name)
        print('        %s' % e)
    except Exception as e:
        ok = False
        print('  [FAIL] %s' % name)
        print('        %s: %s' % (type(e).__name__, e))


def capture_all(builder):
    saved = []

    class _Cap:
        def __init__(self, v, indices=None):
            a = np.asarray(v, dtype=np.float32).reshape(-1, 9)
            saved.append(a)
            self.count = a.shape[0]

    orig = gfx.Mesh
    gfx.Mesh = _Cap
    try:
        builder()
    finally:
        gfx.Mesh = orig
    return saved


MEASURED = {}


def t_geometry():
    print('     机型几何（模型实测 vs specs 声明）:')
    print('     %-11s %-16s %8s %8s %9s %9s %8s' % (
        'key', '名称', '翼展', '声明', '机长', '声明', '起落架'))
    for sp in specs.CATALOG:
        meshes = capture_all(lambda k=sp.key: plane.build_plane(k))
        assert len(meshes) == 2, '%s 应返回 (机身, 起落架)' % sp.key
        body, gear = meshes[0], meshes[1]
        span = float(body[:, 0].max() - body[:, 0].min())
        length = float(body[:, 2].max() - body[:, 2].min())
        gmin = float(gear[:, 1].min())
        MEASURED[sp.key] = (span, length, gmin)
        print('     %-11s %-16s %8.2f %8.1f %9.2f %9.1f %8.2f' % (
            sp.key, sp.name, span, sp.wing_span, length, sp.fuse_len, gmin))
        assert body.shape[0] > 300, '%s 机身顶点太少' % sp.key
        assert gear.shape[0] >= 60, '%s 起落架顶点太少' % sp.key
        # 尺寸允许 1.0 m / 1.5 m 误差（模型有翼尖小翼、天线等小部件）
        assert abs(span - sp.wing_span) < 1.0, (
            '%s 翼展不符：模型 %.2f m，specs 写 %.1f m' % (sp.key, span, sp.wing_span))
        assert abs(length - sp.fuse_len) < 1.5, (
            '%s 机长不符：模型 %.2f m，specs 写 %.1f m' % (sp.key, length, sp.fuse_len))
        # 起落架最低点必须恰好等于 -gear_height
        assert abs(gmin + sp.gear_height) < 0.06, (
            '%s 起落架高度不符：模型最低 %+.2f m，specs 写 -%.2f m'
            % (sp.key, gmin, sp.gear_height))
        # 地面阴影
        sh = capture_all(lambda k=sp.key: plane.build_shadow(k))[0]
        assert sh.shape[0] >= 36, '%s 阴影顶点太少' % sp.key

    # 三种机型必须真的长得不一样
    spans = [MEASURED[s.key][0] for s in specs.CATALOG]
    assert max(spans) - min(spans) > 3.0, '三种机型翼展差别太小，看起来会像同一架'
    lens = [MEASURED[s.key][1] for s in specs.CATALOG]
    assert max(lens) - min(lens) > 5.0, '三种机型机长差别太小'


def t_specs():
    print('     机型性能参数:')
    print('     %-11s %-8s %7s %7s %8s %8s %7s' % (
        'key', '类型', '质量kg', '推力N', '翼面积', '失速°', '可收轮'))
    for sp in specs.CATALOG:
        print('     %-11s %-8s %7.0f %7.0f %8.1f %8.0f %7s' % (
            sp.key, sp.kind, sp.mass, sp.max_thrust, sp.wing_area,
            sp.stall_deg, '是' if sp.gear_retract else '否'))
        assert sp.mass > 0 and sp.max_thrust > 0 and sp.wing_area > 0
        if sp.kind == 'jet':
            # 喷气机推力应当明显大于螺旋桨，而且可收起落架
            assert sp.max_thrust > 10000, '%s 涡喷推力太小' % sp.key
            assert sp.gear_retract, '%s 是喷气机却不可收起落架' % sp.key
            assert sp.CD0 <= 0.022, '%s 喷气机外形应更干净（CD0 更小）' % sp.key
        else:
            assert not sp.gear_retract, '%s 螺旋桨机不该有可收起落架' % sp.key

    # 至少两种涡喷机型
    jets = [s for s in specs.CATALOG if s.kind == 'jet']
    assert len(jets) >= 2, '要求至少 2 种涡喷机型，现在只有 %d 种' % len(jets)
    print('     涡喷机型 %d 种：%s' % (len(jets), ', '.join(s.name for s in jets)))


def t_flight_each():
    """每种机型都要能飞：起飞 → 爬升 → 平飞 → 转弯"""
    print('     每种机型试飞（满油门 60 秒）:')
    for sp in specs.CATALOG:
        a = flight.Aircraft(aircraft_key=sp.key)
        a.pos = np.array([0.0, 200.0, 0.0])
        a.yaw = 0.0
        a.speed_val = sp.cruise_speed
        a.vel = np.array([0.0, 0.0, -sp.cruise_speed])
        a.on_ground = False
        a.gear = 1.0
        ctrl = {'throttle': 1.0, 'pitch': 0.0, 'roll': 0.0, 'yaw': 0.0,
                'flaps': 0.0, 'airbrake': 0.0, 'brakes': 0.0}
        for _ in range(30 * 60):
            a.update(1 / 60.0, ctrl, _ground)
        v0 = a.airspeed_kmh
        # 右转 5 秒。航向可能越过 ±180°，所以归一化到 -180..180 再判断
        ctrl['roll'] = 1.0
        y0 = a.yaw
        for _ in range(5 * 60):
            a.update(1 / 60.0, ctrl, _ground)
        raw = math.degrees(a.yaw - y0)
        dyaw = (raw + 180.0) % 360.0 - 180.0
        right_low = (a.basis()[3] @ np.array([5.0, 0, 0]))[1] < 0
        print('     %-11s 60秒后 %.0f km/h  高度 %.0f m  迎角 %+.1f°  '
              '右杆5秒航向 %+.0f°  右翼下沉 %s' % (
                  sp.key, v0, a.pos[1], a.aoa_deg, dyaw,
                  '是' if right_low else '否'))
        assert not a.crashed, '%s 平飞时坠毁了' % sp.key
        assert v0 > 60, '%s 满油门飞不起来，只有 %.0f km/h' % (sp.key, v0)
        # 右杆必须右转（航向增加）且右翼下沉
        assert dyaw > 20, '%s 按 D 没往右转（航向变化 %+.1f°）' % (sp.key, dyaw)
        assert right_low, '%s 按 D 时右翼没有下沉' % sp.key


def t_gear():
    """起落架收放"""
    print('     起落架收放:')
    for sp in specs.CATALOG:
        a = flight.Aircraft(aircraft_key=sp.key)
        a.pos = np.array([0.0, 1500.0, 0.0])
        a.speed_val = sp.cruise_speed * 1.4
        a.vel = np.array([0.0, 0.0, -sp.cruise_speed * 1.4])
        a.on_ground = False
        a.gear = 1.0

        if not sp.gear_retract:
            # 固定式：按 G 无效，档位必须保持 1.0
            moved, msg = a.toggle_gear()
            for _ in range(180):
                a.update(1 / 60.0, {'throttle': 0.8}, _ground)
            print('     %-11s 固定式起落架：toggle 返回 %s（%s），gear=%.2f（应恒为 1.0）' % (
                sp.key, moved, msg, a.gear))
            assert moved is False, '%s 固定起落架不该接受收起指令' % sp.key
            assert a.gear > 0.99, '%s 固定起落架被改动了' % sp.key
            continue

        # 可收放：先确认放下时能收起来
        assert a.gear > 0.99, '%s 初始应放下起落架' % sp.key
        moved, msg = a.toggle_gear()
        assert moved, '%s 空中按 G 被拒绝了：%s' % (sp.key, msg)
        assert a.gear_up_locked, '%s 按 G 后应进入收起状态' % sp.key
        t_up = 0.0
        for _ in range(600):
            a.update(1 / 60.0, {'throttle': 0.6}, _ground)
            t_up += 1 / 60.0
            if a.gear < 0.01:
                break
        print('     %-11s 收起：%.1f 秒收到 %.2f' % (sp.key, t_up, a.gear))
        assert a.gear < 0.01, '%s 起落架收不起来（%.2f）' % (sp.key, a.gear)
        assert t_up < 5.0, '%s 收放太慢（%.1f 秒）' % (sp.key, t_up)

        # 再放下来
        a.toggle_gear()
        t_dn = 0.0
        for _ in range(600):
            a.update(1 / 60.0, {'throttle': 0.3}, _ground)
            t_dn += 1 / 60.0
            if a.gear > 0.99:
                break
        print('     %-11s 放下：%.1f 秒回到 %.2f' % (sp.key, t_dn, a.gear))
        assert a.gear > 0.99, '%s 起落架放不下来（%.2f）' % (sp.key, a.gear)


def t_gear_drag():
    """收起落架后阻力必须变小（同样油门跑得更快）"""
    print('     起落架阻力效果（同样油门下速度对比）:')
    for sp in specs.CATALOG:
        if not sp.gear_retract:
            continue
        speeds = {}
        for gear in (1.0, 0.0):
            a = flight.Aircraft(aircraft_key=sp.key)
            a.pos = np.array([0.0, 3000.0, 0.0])
            a.speed_val = sp.cruise_speed
            a.vel = np.array([0.0, 0.0, -sp.cruise_speed])
            a.on_ground = False
            a.gear = gear
            a.gear_up_locked = (gear < 0.5)
            a.gear_down_locked = (gear > 0.5)
            for _ in range(40 * 60):
                a.update(1 / 60.0, {'throttle': 0.85, 'pitch': 0.0, 'roll': 0.0}, _ground)
            speeds[gear] = a.airspeed_kmh
        gain = speeds[0.0] - speeds[1.0]
        print('     %-11s 放下 %.0f km/h  →  收起 %.0f km/h   快 %+.0f km/h' % (
            sp.key, speeds[1.0], speeds[0.0], gain))
        assert gain > 2.0, '%s 收起落架后速度没有提升（%+.1f km/h）' % (sp.key, gain)


def t_switch():
    """换机型逻辑"""
    keys = [s.key for s in specs.CATALOG]
    cur = keys[0]
    seen = [cur]
    for _ in range(len(keys)):
        cur = specs.next_key(cur)
        seen.append(cur)
    print('     循环切换：%s' % ' → '.join(seen))
    assert seen[-1] == seen[0], '切换一圈应回到起点'
    assert len(set(seen[:-1])) == len(keys), '切换覆盖了所有机型'


check('机型几何', t_geometry)
check('机型性能参数', t_specs)
check('每种机型试飞', t_flight_each)
check('起落架收放', t_gear)
check('起落架阻力', t_gear_drag)
check('机型切换', t_switch)

print()
print('=' * 62)
print('  机型检查: %s' % ('全部通过' if ok else '有失败项'))
print('=' * 62)
sys.exit(0 if ok else 1)
