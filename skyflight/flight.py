# -*- coding: utf-8 -*-
"""
飞行力学模型（6 自由度刚体 + 气动力）

======================= 符号约定（务必一致） =======================
世界系：X 向东，Y 向上，Z 向南（右手系）
机体系：前 = -Z，上 = +Y，右 = +X

姿态角：
  pitch > 0 = 抬头
  yaw   > 0 = 机头向右偏
  roll  > 0 = 右翼下沉（向右滚转）

操纵输入（Controls 输出的值，均为 -1..1）：
  pitch  > 0 = 拉杆抬头
  roll   > 0 = 右滚
  yaw    > 0 = 右偏航（右舵）

角速度：
  p = 滚转角速度，q = 俯仰角速度，r = 偏航角速度
  约定 p/q/r 与"抬头/右滚"同向
===================================================================
"""
import math

import numpy as np

from . import gfx
from . import specs


class Aircraft:
    # ---------------- 基本参数（一架轻型运动飞机，类似塞斯纳 172 尺寸）
    mass = 1100.0            # kg
    wing_area = 16.2         # m^2
    rho = 1.225              # 海平面空气密度 kg/m^3
    max_thrust = 3600.0      # N
    V_ref = 75.0             # 参考空速（操纵效能基准）m/s
    cruise_speed = 78.0      # 巡航速度 m/s

    # 升力（CL0 让零迎角也有基础升力，配平迎角接近真实飞机）
    CL0 = 0.10
    CL_alpha = 4.6           # 每弧度
    CL_max = 1.42
    stall_angle = math.radians(16.0)
    CD0 = 0.030
    k_induced = 0.048
    airbrake_drag = 0.075       # 减速板全开时额外增加的阻力系数
    gear_drag = 0.022           # 起落架放下时的额外阻力系数
    gear_rate = 0.55            # 起落架收放速度（每秒变化量，约 1.8 秒走完）
    CY_beta = -0.95          # 侧滑侧力

    # 惯性矩
    Ixx = 1250.0             # 滚转
    Iyy = 2400.0             # 俯仰
    Izz = 3300.0             # 偏航

    # 操纵效能（rad/s^2 每单位输入）
    roll_power = 12.5
    pitch_power = 3.1
    yaw_power = 2.6

    # ---- 俯仰（迎角指令；响应时间 alpha_tau 越小越灵敏）
    alpha_travel = math.radians(14.0)    # 杆满偏改变多少迎角
    alpha_tau = 0.30                     # 迎角响应时间（秒）
    alpha_rate_max = math.radians(45.0)  # 迎角最大变化率 rad/s
    gamma_limit = math.radians(42.0)     # 爬升角超过此值限制抬头
    # ---- 滚转 / 偏航
    roll_rate_cmd = 1.15      # 杆满偏 -> 期望滚转角速度 rad/s（约 66°/s）
    max_bank_deg = 58.0       # 满杆能达到的最大倾角（所有机型都压不过它）
    roll_stiff = 5200.0       # 滚转跟踪 -> 力矩
    yaw_stiff = 2600.0        # 偏航跟踪 -> 力矩

    # 阻尼（每 rad/s）
    roll_damp = 3.0
    pitch_damp = 4.6
    yaw_damp = 3.4

    # 静稳定性
    pitch_stability = 3.0    # 迎角回正（越大越"粘"）
    weathercock = 2.8        # 风标效应
    dihedral = 2.2           # 上反角效应

    # 起落架高度（机身原点离地）会按机型在 __init__ 里覆盖。
    # 模型最低点（轮胎底）在局部坐标 -gear_height，
    # 所以轮胎着地时机身原点离地 gear_height 米。改模型尺寸要同步改 specs.py。
    GEAR_HEIGHT = 1.07

    def __init__(self, pos=(0.0, 60.0, 1200.0), spec=None, aircraft_key=None):
        # ---------------- 机型参数（换机型就是换这一整组）
        if spec is None:
            spec = specs.get(aircraft_key) if aircraft_key else specs.DEFAULT
        self.spec = spec
        self.aircraft_key = spec.key
        self.mass = spec.mass
        self.wing_area = spec.wing_area
        self.max_thrust = spec.max_thrust
        self.V_ref = spec.V_ref
        self.cruise_speed = spec.cruise_speed
        self.CL0 = spec.CL0
        self.CL_alpha = spec.CL_alpha
        self.CL_max = spec.CL_max
        self.stall_angle = math.radians(spec.stall_deg)
        self.CD0 = spec.CD0
        self.k_induced = spec.k_induced
        self.roll_power = spec.roll_power
        self.pitch_power = spec.pitch_power
        self.yaw_power = spec.yaw_power
        self.roll_rate_cmd = spec.roll_rate_cmd
        self.thrust_lapse_max = spec.thrust_lapse
        self.GEAR_HEIGHT = spec.gear_height

        self.pos = np.array(pos, dtype=np.float64)
        self.vel = np.array([0.0, 0.0, -self.cruise_speed], dtype=np.float64)
        self.speed_val = float(np.linalg.norm(self.vel))
        if self.speed_val < 0.1:
            self.speed_val = 0.0
        self.pitch = 0.0
        self.yaw = 0.0
        self.roll = 0.0
        self.p = 0.0
        self.q = 0.0
        self.r = 0.0

        self.throttle = 0.0
        self.elevator = 0.0
        self.aileron = 0.0
        self.rudder = 0.0
        self.flaps = 0.0
        self.airbrake = 0.0          # 减速板 0~1

        # ---------------- 起落架
        # gear  = 1.0 放下（可着陆）/ 0.0 收起（减阻提速）
        # 螺旋桨教练机是固定式，永远 1.0
        self.gear = 1.0 if not spec.gear_retract else 0.0
        self.gear_up_locked = False
        self.gear_down_locked = False

        self.on_ground = False
        self.crashed = False
        self.crash_timer = 0.0
        self.alpha = math.radians(2.0)
        self.beta = 0.0
        self.aoa_deg = 2.0
        self.stalling = False
        self.g_load = 1.0
        self.last_acc = np.zeros(3)
        self.gamma = 0.0

    # ------------------------------------------------ 机型
    def set_aircraft(self, key):
        """换机型（会重置到该机型的初始状态）"""
        self.__init__(pos=tuple(self.pos), aircraft_key=key)

    @property
    def gear_retractable(self):
        return bool(self.spec.gear_retract)

    @property
    def gear_deployed(self):
        """起落架是否算"放下"（放下度 > 0.99）"""
        return self.gear > 0.99

    def toggle_gear(self):
        """按 G：收起落架 / 放起落架

        返回 (是否接受, 说明)。只有能安全动作时才执行：
          - 固定式起落架：不接受
          - 地面上要收起：不接受（收起会擦地）
          - 空速低于 8 m/s 要收起：不接受
        要"放下"则任何时候都允许（进近时可能速度很低，但必须放得下来）。
        """
        if not self.spec.gear_retract:
            return False, '固定式起落架，不能收放'
        want_up = self.gear > 0.5
        if want_up:
            if self.on_ground:
                return False, '地面上不能收起落架'
            if self.speed_val < 8.0:
                return False, '速度太低（<29 km/h），不能收起落架'
            self.gear_up_locked = True
            self.gear_down_locked = False
            return True, '正在收起起落架'
        self.gear_down_locked = True
        self.gear_up_locked = False
        return True, '正在放下起落架'


    # ------------------------------------------------ 坐标变换
    def basis(self):
        """返回 (前, 右, 上, 旋转矩阵)"""
        R = gfx.euler_to_matrix(self.pitch, self.yaw, self.roll)
        fwd = R @ np.array([0.0, 0.0, -1.0])
        right = R @ np.array([1.0, 0.0, 0.0])
        up = R @ np.array([0.0, 1.0, 0.0])
        return fwd, right, up, R

    def reset(self, pos=(0.0, 60.0, 1200.0)):
        self.__init__(pos)

    @property
    def speed(self):
        return float(np.linalg.norm(self.vel))

    @property
    def airspeed_kmh(self):
        return self.speed * 3.6

    @property
    def altitude(self):
        return float(self.pos[1])

    @property
    def vertical_speed(self):
        return float(self.vel[1])

    # ------------------------------------------------ 主积分
    def update(self, dt, controls, ground_height):
        if dt <= 0.0:
            return
        if self.crashed:
            self.crash_timer += dt
            self.vel[1] -= 9.81 * dt
            self.pos = self.pos + self.vel * dt
            gh = ground_height(self.pos[0], self.pos[2])
            if self.pos[1] < gh + 1.0:
                self.pos[1] = gh + 1.0
                self.vel *= 0.4
            return

        # ---------------- 操纵面平滑跟随
        k = min(1.0, 5.0 * dt)
        self.elevator += (controls.get('pitch', 0.0) - self.elevator) * k
        self.aileron += (controls.get('roll', 0.0) - self.aileron) * k
        self.rudder += (controls.get('yaw', 0.0) - self.rudder) * k
        self.flaps += (controls.get('flaps', self.flaps) - self.flaps) * min(1.0, 2.5 * dt)
        # 减速板开合稍慢一点，手感更像真的
        self.airbrake += (controls.get('airbrake', self.airbrake) - self.airbrake) * min(1.0, 3.0 * dt)

        # ---------------- 起落架收放
        if self.spec.gear_retract:
            # 空中没速度时收不起来；地面上压着收不起来
            can_move = (not self.on_ground) and self.speed_val > 8.0
            if self.gear_up_locked and can_move:
                self.gear = max(0.0, self.gear - self.gear_rate * dt)
            elif self.gear_down_locked:
                self.gear = min(1.0, self.gear + self.gear_rate * dt)
            else:
                # 没指令时：离地且空速够 -> 自动收；进近/接地 -> 自动放
                want_gear = 1.0 if (self.on_ground or self.speed_val < 55.0) else 0.0
                self.gear += (want_gear - self.gear) * min(1.0, 0.5 * dt)

        want = controls.get('throttle', None)
        if want is not None:
            self.throttle = float(np.clip(want, 0.0, 1.0))
        else:
            self.throttle = float(np.clip(
                self.throttle + controls.get('throttle_delta', 0.0), 0.0, 1.0))

        # ---------------- 空速
        V = max(1.0, self.speed)
        q_dyn = 0.5 * self.rho * V * V
        eff = max(0.18, min(1.8, (V / self.V_ref) ** 2))

        # ---------------- 升力 / 阻力
        CL = self.CL0 + self.CL_alpha * self.alpha
        if abs(self.alpha) > self.stall_angle:
            over = abs(self.alpha) - self.stall_angle
            CL = math.copysign(self.CL_max * math.exp(-over * 2.4), self.alpha)
            self.stalling = True
        else:
            self.stalling = False
        CL = max(-1.7, min(1.7, CL))
        # 阻力：寄生 + 诱导 + 襟翼 + 减速板 + 起落架
        # airbrake 是独立操作的减速板，空中按 B 打开，能明显减速
        # gear 放下时也有可观阻力（真实飞机放下起落架通常掉 10~20 节）
        CD = self.CD0 + self.k_induced * CL * CL + abs(self.flaps) * 0.045
        CD += abs(self.airbrake) * self.airbrake_drag
        CD += self.gear * self.gear_drag
        CD += abs(self.elevator) * 0.0035

        # 升阻比（供配平使用）
        lift_force = CL * q_dyn * self.wing_area
        weight = self.mass * 9.81
        n_ratio = lift_force / weight      # >1 表示升力大于重力

        # ---------------- 速度大小：推力 - 阻力 - 重力分量
        thrust = self.throttle * self.max_thrust * (1.0 - self.thrust_lapse_max * min(1.0, max(0.0, self.pos[1]) / 9000.0))
        drag = CD * q_dyn * self.wing_area
        # 爬升时重力分量拉低速度
        gamma = math.asin(max(-1.0, min(1.0, self.vel[1] / V)))
        acc_speed = (thrust - drag) / self.mass - 9.81 * math.sin(gamma) * (1.0 - max(0.0, n_ratio - 1.0) * 0.0)
        # 失速时额外减速
        if self.stalling:
            acc_speed -= 3.5
        self.speed_val = max(0.0, self.speed_val + acc_speed * dt)
        self.speed_val = min(self.speed_val, 330.0)

        # ---------------- 轨迹角（速度矢量方向）
        # 升力大于重力 -> 速度矢量上抬（离地就是靠这个）
        gamma_dot = (n_ratio - math.cos(gamma)) * 9.81 / V
        gamma_dot = max(-1.5, min(1.5, gamma_dot))
        # 侧滑影响（简化：滚转后转弯由 yaw 处理）
        heading_dot = (self.r * 0.55 + self.roll * 0.55) * min(1.0, V / 55.0)
        gamma += gamma_dot * dt
        self.yaw += heading_dot * dt
        gamma = max(-1.3, min(1.3, gamma))

        # 速度矢量（世界）
        cg = math.cos(gamma)
        self.vel[0] = self.speed_val * cg * math.sin(self.yaw)
        self.vel[1] = self.speed_val * math.sin(gamma)
        self.vel[2] = -self.speed_val * cg * math.cos(self.yaw)

        # ---------------- 迎角 + 俯仰（迎角以最大角速度趋向目标）
        cos_gamma = max(0.25, math.cos(gamma))
        CL_req = (2.0 * self.mass * 9.81 * cos_gamma) / max(1.0, self.rho * V * V * self.wing_area)
        CL_req = max(0.02, min(1.10, CL_req))
        alpha_trim = (CL_req - self.CL0) / self.CL_alpha
        alpha_des = alpha_trim + self.elevator * self.alpha_travel
        alpha_des = max(-self.stall_angle * 1.15, min(self.stall_angle * 1.15, alpha_des))
        # 大爬升角 / 失速保护：限制抬头
        if gamma > self.gamma_limit:
            alpha_des = min(alpha_des, alpha_trim * 0.3)
        if self.stalling:
            alpha_des = min(alpha_des, alpha_trim * 0.4)
        # 迎角以最大角速度趋向目标（角速度 = 误差 / 响应时间，限幅）
        err = alpha_des - self.alpha
        alpha_rate = max(-self.alpha_rate_max, min(self.alpha_rate_max, err / self.alpha_tau))
        # 俯仰角速度 = 迎角变化率 + 速度矢量旋转率（保持物理自洽）
        self.alpha += alpha_rate * dt
        self.alpha = max(-1.9, min(1.9, self.alpha))
        self.aoa_deg = math.degrees(self.alpha)
        self.q = alpha_rate + gamma_dot

        # ---------------- 滚转 / 偏航力矩
        # 约定：roll > 0 = 右翼下沉，所以右杆 -> 正滚转角速度
        #
        # 操纵手感 = "压杆 -> 目标倾角"，而不是"压杆 -> 恒定滚转角速度"。
        # 这样任何机型都压不过 max_bank（默认约 62°），
        # 松杆则目标回 0，自然滚回水平。
        # 之前是纯比例控制（没有倾角上限），滚转力强的喷气机会一路压到 90°
        # 变成刀锋飞行——这就是"喷气机压杆会翻过去"的原因。
        bank_deg = math.degrees(abs(self.roll))
        max_bank = self.max_bank_deg
        if abs(self.aileron) > 0.05:
            # 压杆：目标倾角 = 满杆到 max_bank
            bank_target = math.copysign(
                max_bank * min(1.0, abs(self.aileron)), self.aileron)
        else:
            # 松杆：目标回平（上反角自稳）
            bank_target = 0.0
        # 超限时强制往回压（防止外力/过冲把飞机掀过去）
        if bank_deg > max_bank + 6.0:
            bank_target = math.copysign(
                max_bank * 0.85, self.roll)

        # 目标倾角 -> 目标滚转角速度
        # 只在"还没到目标倾角"时才往外压；接近目标时 p 归零（不越过），
        # 这样机构不会在目标附近来回震荡。
        k_bank = 2.2
        err = bank_target - self.roll
        p_cmd = err * k_bank
        if (self.aileron > 0.05 and self.roll >= bank_target - 1e-4) or \
           (self.aileron < -0.05 and self.roll <= bank_target + 1e-4):
            p_cmd = 0.0
        p_cmd = max(-self.roll_rate_cmd, min(self.roll_rate_cmd, p_cmd))

        M_roll = (p_cmd - self.p) * self.roll_stiff * eff
        M_roll = max(-self.Ixx * 6.0, min(self.Ixx * 6.0, M_roll))
        r_cmd = self.rudder * 0.9 * min(1.0, V / 30.0)
        # 滚转产生的转弯（倾斜转弯）
        turn = -math.sin(self.roll) * 9.81 / V * 0.9
        M_yaw = (r_cmd - self.r) * self.yaw_stiff * eff
        M_yaw = max(-self.Izz * 3.0, min(self.Izz * 3.0, M_yaw))

        # ---------------- 角速度积分（俯仰已由迎角控制直接给出 q）
        self.p += (M_roll / self.Ixx) * dt
        self.r += (M_yaw / self.Izz) * dt
        # 倾斜转弯的自发偏航
        self.r += turn * dt
        lim = 4.0
        # 滚转角速度限幅：约 150°/s，避免倒扣
        self.p = max(-2.6, min(2.6, self.p))
        self.q = max(-lim, min(lim, self.q))
        self.r = max(-lim, min(lim, self.r))

        # ---------------- 姿态积分
        self.pitch += self.q * dt
        self.roll += self.p * dt
        self.pitch = max(-1.45, min(1.45, self.pitch))
        # 滚转角硬限幅：任何机型都不允许翻过 max_bank + 8°。
        # 这是最后一道保险——控制器再好也可能被扰动/过冲突破。
        # 一旦撞到限幅就把滚转角速度清零，避免"贴边抖动"。
        bank_cap = math.radians(self.max_bank_deg + 5.0)
        if self.roll > bank_cap:
            self.roll = bank_cap
            self.p = min(0.0, self.p)
        elif self.roll < -bank_cap:
            self.roll = -bank_cap
            self.p = max(0.0, self.p)
        if self.yaw > math.pi:
            self.yaw -= 2 * math.pi
        elif self.yaw < -math.pi:
            self.yaw += 2 * math.pi

        # ---------------- 位置积分
        self.pos = self.pos + self.vel * dt

        # ---------------- 过载
        self.g_load = abs(n_ratio) if not self.stalling else 0.4

        # ---------------- 地面 / 撞地
        # 注意：ground_height 返回的是"地面高度"，但机身原点在起落架之上
        # GEAR_HEIGHT 米，所以轮胎着地时机身原点 = 地面 + GEAR_HEIGHT。
        gh = ground_height(self.pos[0], self.pos[2])
        rest_y = gh + self.GEAR_HEIGHT       # 停在地面时的机身原点高度
        agl = self.pos[1] - rest_y           # 轮胎离地高度
        if agl <= 0.0:
            # 先记下接触瞬间的下降率，再清零（顺序反了会导致永远判不出坠毁）
            vs = abs(self.vel[1])
            self.pos[1] = rest_y
            self.vel[1] = 0.0
            bank_bad = abs(self.roll) > math.radians(32)
            nose_bad = abs(self.pitch) > math.radians(26)
            # 下降太快 / 机身太斜 / 机头扎地角度太大 -> 坠毁
            if vs > 19.0 or bank_bad or nose_bad:
                self.crash()
            else:
                # 正常擦地/落地滑跑：不要砍迎角（砍了就永远飞不起来）
                self.pitch *= 0.86
                self.roll *= 0.80
                self.p = 0.0
                # 地面摩擦减速
                brake = controls.get('brakes', 0.0)
                fric = 0.020 + 0.32 * brake
                self.speed_val = max(0.0, self.speed_val - (fric * 9.81) * dt)
        on_ground = agl <= 1.2 and not self.crashed
        self.on_ground = on_ground
        if on_ground:
            # 地面上：机头不会往上抬太多（抬前轮上限 15°），也不会往下扎
            if self.pitch > math.radians(15.0):
                self.pitch = math.radians(15.0)
            if self.pitch < 0.0:
                self.pitch = 0.0
            # 迎角也限住，避免低速配平算出巨大迎角把机头压下去
            if self.alpha > math.radians(8.0):
                self.alpha = math.radians(8.0)
                self.aoa_deg = math.degrees(self.alpha)
            elif self.alpha < 0.0:
                self.alpha = 0.0
                self.aoa_deg = 0.0
            # 飞行员没拉杆时，迎角回到平飞配平（防止停着不动自己飘起来）
            V_now = max(1.0, self.speed)
            CL_need = (2.0 * self.mass * 9.81) / (self.rho * V_now * V_now * self.wing_area)
            a_trim_now = (max(0.02, min(1.1, CL_need)) - self.CL0) / self.CL_alpha
            if self.alpha > a_trim_now and self.elevator < 0.20:
                self.alpha += (a_trim_now - self.alpha) * min(1.0, 3.2 * dt)
            if self.alpha < -self.stall_angle:
                self.alpha = -self.stall_angle
            # 地面保护：轮子撑着的时候飞机不可能自己往下钻。
            # 低速时升力为 0，gamma_dot 公式会算出巨大的负值把机头压下去，
            # 所以地面上把轨迹角锁在 0~小幅抬头之间。
            if self.speed_val < 40.0:
                gamma = max(-0.02, min(gamma, math.radians(4.0)))
        else:
            # 已经离地：俯仰角由迎角和轨迹角自然给出
            self.pitch = self.alpha + gamma
            self.pitch = max(-1.45, min(1.45, self.pitch))
        self.gamma = gamma

    def crash(self):
        if not self.crashed:
            self.crashed = True
            self.crash_timer = 0.0
            self.vel[1] = -abs(self.vel[1]) - 4.0
            self.p += 3.0
            self.r += 2.0

    def status(self):
        if self.crashed:
            return '坠毁 - 按 R 重来'
        if self.stalling:
            return '失速!'
        return ''


class Controls:
    """键盘/鼠标 -> 操纵面输入"""

    def __init__(self):
        self.pitch = 0.0     # >0 抬头
        self.roll = 0.0      # >0 右滚
        self.yaw = 0.0       # >0 右偏航
        self.flaps = 0.0
        self.brakes = 0.0
        self.gear_toggle = False
        self.mouse_mode = False
        self.mx = 0.0
        self.my = 0.0

    def update(self, keys, dt, mouse):
        if self.mouse_mode:
            p = -self.my
            r = self.mx
        else:
            # 俯仰：S / ↓ = 拉杆抬头（和绝大多数飞行游戏一致），W / ↑ = 推杆低头
            p = 0.0
            if keys.get('S') or keys.get('DOWN'):
                p += 1.0
            if keys.get('W') or keys.get('UP'):
                p -= 1.0
            # 滚转：D / → = 右滚，A / ← = 左滚
            r = 0.0
            if keys.get('D') or keys.get('RIGHT'):
                r += 1.0
            if keys.get('A') or keys.get('LEFT'):
                r -= 1.0
        yaw = 0.0
        if keys.get('E'):
            yaw += 1.0
        if keys.get('Q'):
            yaw -= 1.0

        self.pitch = max(-1.0, min(1.0, p))
        self.roll = max(-1.0, min(1.0, r))
        self.yaw = max(-1.0, min(1.0, yaw))
        self.brakes = 1.0 if keys.get('B') else 0.0
        # B 键：地面上是轮刹，空中是减速板（同一个键，两套用法）
        self.airbrake = 1.0 if keys.get('B') else 0.0
        # G 键：收起落架 / 放起落架（只有可收放机型有效）
        self.gear_toggle = bool(keys.get('G'))
        return self

    def as_dict(self, throttle=None, throttle_delta=0.0):
        d = {
            'pitch': self.pitch,
            'roll': self.roll,
            'yaw': self.yaw,
            'flaps': self.flaps,
            'brakes': self.brakes,
            'airbrake': self.airbrake,
        }
        if throttle is not None:
            d['throttle'] = throttle
        else:
            d['throttle_delta'] = throttle_delta
        return d
