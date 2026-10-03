# -*- coding: utf-8 -*-
"""
界面语言：中 / 英 可切换

用法：
    from . import i18n
    i18n.set_lang(i18n.ZH)
    i18n.t('hud.airspeed')          # -> '空速'
    i18n.t('hud.gear_down')         # -> '起落架 放下'

设计约定：
  - 所有用户可见的文字都放这里的 STRINGS 表，键名用 "模块.用途"
  - 缺失的键会把键名原样返回，方便一眼看出漏翻的条目
  - 中文点阵字形由 hud.py 用系统字体（微软雅黑）现场光栅化，
    所以 HUD 不需要预存上千个汉字字形
"""

ZH = 'zh'
EN = 'en'

LANG_NAMES = {ZH: '中文', EN: 'English'}

# 当前语言。默认中文（用户是中文使用者）
_lang = ZH


def set_lang(lang):
    """设置语言，返回是否发生了变化"""
    global _lang
    lang = (lang or '').lower()
    if lang not in (ZH, EN):
        lang = ZH
    changed = (lang != _lang)
    _lang = lang
    return changed


def get_lang():
    return _lang


def toggle_lang():
    """中英互换，返回新语言"""
    set_lang(EN if _lang == ZH else ZH)
    return _lang


def is_zh():
    return _lang == ZH


def t(key, **kw):
    """取一条文字。缺失时返回键名本身（便于发现漏翻）

    支持两种占位符：
      %s / %d / %.0f   ——  老式 % 格式化，用 **kw 里的同名参数
      {name}           ——  str.format，用来处理"参数顺序不确定"的情况
    两者都能用，优先走 % 格式化（保持和老代码一致）。
    """
    table = STRINGS.get(_lang) or STRINGS[ZH]
    s = table.get(key)
    if s is None:
        s = STRINGS[ZH].get(key, key)
    if not kw:
        return s
    # 有 {xxx} 就先用 format（这类键的参数是命名的）
    if '{' in s:
        try:
            return s.format(**kw)
        except (KeyError, IndexError):
            return s
    try:
        return s % kw
    except (TypeError, KeyError):
        return s


# ==================================================================
#  文字表
#  规则：中文和英文两张表的键必须完全一致（tests/i18n_check.py 会校验）
# ==================================================================
STRINGS = {
    ZH: {
        # ---------------- HUD 左上
        'hud.title': 'SKYFLIGHT',
        'hud.version': '版本',
        'hud.gear_down': '起落架 放下',
        'hud.gear_up': '起落架 收起',
        'hud.gear_moving': '起落架 {n}%',
        'hud.gear_fixed': '起落架 固定',
        'hud.engine_jet': '涡喷',
        'hud.engine_piston': '活塞',
        'hud.fps': '帧率 {n}',

        # ---------------- HUD 左下 / 右下
        'hud.spd': '空速',
        'hud.alt': '高度',
        'hud.thr': '油门',
        'hud.vs': '升降',
        'hud.brake': '减速板',
        'hud.flaps': '襟翼',
        'hud.aoa': '迎角',
        'hud.gload': '过载',

        # ---------------- 罗盘方向
        'compass.n': '北',
        'compass.ne': '东北',
        'compass.e': '东',
        'compass.se': '东南',
        'compass.s': '南',
        'compass.sw': '西南',
        'compass.w': '西',
        'compass.nw': '西北',

        # ---------------- 告警
        'warn.stall': '失速',
        'warn.pullup': '拉起来',
        'warn.lowpower': '功率低',
        'warn.highaoa': '迎角大',
        'warn.crashed': '坠毁 按R重来',
        'warn.paused': '已暂停',

        # ---------------- 相机
        'cam.chase': '追尾',
        'cam.cockpit': '驾驶舱',
        'cam.orbit': '环绕',

        # ---------------- 窗口标题
        'title.format': '%s v%s  [%s]  |  %s  |  航向 %03d°  |  速度 %.0f km/h  |  '
                        '高度 %.0f m  |  倾角 %+.0f°  |  油门 %.0f%%%s  |  帧率 %.0f%s',
        'title.fullscreen': '  [全屏 F11 退出]',
        'title.gear': '  |  起落架 %s',
        'title.gear_down': '放下',
        'title.gear_up': '收起',
        'title.crashed': '  ✖坠毁(按R重来)',
        'title.stall': '  ⚠失速',

        # ---------------- 控制台 / 提示
        'msg.gear_fixed': '固定式起落架，不能收放',
        'msg.gear_ground': '地面上不能收起落架',
        'msg.gear_slow': '速度太低（<29 km/h），不能收起落架',
        'msg.gear_up_go': '正在收起起落架',
        'msg.gear_down_go': '正在放下起落架',
        'msg.aircraft': '机型已切换到 %s  (%s)',
        'msg.lang': '界面语言已切换到 %s',

        # ---------------- 帮助文字（启动时那个黑窗口）
        'help.title': '操作说明',
        'help.pitch': '【俯仰】S 或 ↓ = 拉杆抬头      W 或 ↑ = 推杆低头',
        'help.roll': '【滚转】D 或 → = 向右倾        A 或 ← = 向左倾',
        'help.yaw': '【偏航】E = 右舵               Q = 左舵',
        'help.throttle': '【油门】Shift = 加大           Ctrl = 减小',
        'help.quick': '【快速】Z = 油门加满           X = 油门收光',
        'help.sys1': '【系统】F = 襟翼    B = 刹车/减速板    C = 切视角',
        'help.sys2': '          G = 收起落架 / 放起落架（喷气机用）',
        'help.sys3': '          V = 换机型    L = 切换中英文界面    N = 音效开关',
        'help.sys4': '          M = 鼠标操纵    P = 暂停',
        'help.sys5': '          R = 重来（回跑道）',
        'help.sys6': '          F11 或 Alt+回车 = 全屏 / 退出全屏',
        'help.sys7': '          H = 隐藏/显示本说明    Esc = 退出',
        'help.takeoff': '【起飞】按 Z 加满油门 → 速度到约 100 km/h → 按住 S 抬前轮',
        'help.takeoff2': '          → 俯仰到 12~15° 时松杆 → 飞机会自己离地',
        'help.takeoff3': '          （喷气机推力大，抬前轮更快，注意别拉太猛）',
        'help.level': '【平飞】松杆就行，飞机会自动配平；需要调节时轻点 S / W',
        'help.turn': '【转弯】按住 D 或 A，最多约 60° 倾角；松杆 2 秒自动回正',
        'help.gear': '【起落架】离地后按 G 收起落架，速度能快一截；',
        'help.gear2': '          降落前务必再按 G 放下来（没放下就接地会擦地）',
        'help.slow': '【减速】按住 B 打开减速板（空中也管用）；配合 F 放襟翼减得更快',
        'help.accel': '【加速】俯冲（推杆 W）会掉高度但速度涨；要收速度就拉平 + 开减速板',
        'help.land': '【降落】对准跑道 → 油门收到 20% → F 放襟翼 → 按 G 放起落架',
        'help.land2': '          → 轻拉杆让下降率变缓',
        'help.warn': '【告警】屏幕下方出现 STALL 表示失速，立刻推杆（W）并加油门',
        'help.types': '三种机型（按 V 切换）：',
        'help.type1': '  螺旋桨教练机  低速好飞，固定起落架，适合练手',
        'help.type2': '  轻型涡喷      单发，可收起落架，爬升和加速都快',
        'help.type3': '  双发涡喷      机身重、翼载高，速度快但转弯半径大',
        'help.cam': '在"环绕"视角下（按 C 切换到第 3 个），按住鼠标右键拖动可转视角',
        'help.lang': '界面语言：中英随时按 L 切换（HUD、窗口标题、帮助文字都会跟着变）',

        # ---------------- 启动横幅
        'banner.loading': '正在启动 SkyFlight ...',
        'banner.ready': '就绪，按 H 查看操作说明',
    },

    EN: {
        # ---------------- HUD 左上
        'hud.title': 'SKYFLIGHT',
        'hud.version': 'VER',
        'hud.gear_down': 'GEAR DOWN',
        'hud.gear_up': 'GEAR UP',
        'hud.gear_moving': 'GEAR {n}%',
        'hud.gear_fixed': 'GEAR FIXED',
        'hud.engine_jet': 'TURBOJET',
        'hud.engine_piston': 'PISTON',
        'hud.fps': 'FPS {n}',

        # ---------------- HUD 左下 / 右下
        'hud.spd': 'SPD',
        'hud.alt': 'ALT',
        'hud.thr': 'THR',
        'hud.vs': 'V/S',
        'hud.brake': 'BRAKE',
        'hud.flaps': 'FLAPS',
        'hud.aoa': 'AOA',
        'hud.gload': 'G',

        # ---------------- 罗盘方向
        'compass.n': 'N',
        'compass.ne': 'NE',
        'compass.e': 'E',
        'compass.se': 'SE',
        'compass.s': 'S',
        'compass.sw': 'SW',
        'compass.w': 'W',
        'compass.nw': 'NW',

        # ---------------- 告警
        'warn.stall': 'STALL',
        'warn.pullup': 'PULL UP',
        'warn.lowpower': 'LOW POWER',
        'warn.highaoa': 'HIGH AOA',
        'warn.crashed': 'CRASHED  PRESS R',
        'warn.paused': 'PAUSED',

        # ---------------- 相机
        'cam.chase': 'CHASE',
        'cam.cockpit': 'COCKPIT',
        'cam.orbit': 'ORBIT',

        # ---------------- 窗口标题
        'title.format': '%s v%s  [%s]  |  %s  |  HDG %03d  |  SPD %.0f km/h  |  '
                        'ALT %.0f m  |  BANK %+.0f  |  THR %.0f%%%s  |  FPS %.0f%s',
        'title.fullscreen': '  [FULLSCREEN F11]',
        'title.gear': '  |  GEAR %s',
        'title.gear_down': 'DN',
        'title.gear_up': 'UP',
        'title.crashed': '  X CRASHED (R)',
        'title.stall': '  ! STALL',

        # ---------------- 控制台 / 提示
        'msg.gear_fixed': 'Fixed landing gear cannot be retracted',
        'msg.gear_ground': 'Cannot retract gear on the ground',
        'msg.gear_slow': 'Too slow to retract gear (< 29 km/h)',
        'msg.gear_up_go': 'Raising landing gear',
        'msg.gear_down_go': 'Lowering landing gear',
        'msg.aircraft': 'Aircraft changed to %s  (%s)',
        'msg.lang': 'Interface language changed to %s',

        # ---------------- 帮助文字
        'help.title': 'CONTROLS',
        'help.pitch': '[PITCH]  S or Down = nose up      W or Up = nose down',
        'help.roll': '[ROLL]   D or Right = bank right   A or Left = bank left',
        'help.yaw': '[YAW]    E = rudder right         Q = rudder left',
        'help.throttle': '[THROTTLE] Shift = up             Ctrl = down',
        'help.quick': '[QUICK]  Z = full throttle        X = idle',
        'help.sys1': '[SYSTEM] F = flaps    B = brake/airbrake    C = camera',
        'help.sys2': '         G = landing gear up/down (jets only)',
        'help.sys3': '[SYSTEM] V = change aircraft    L = switch language    N = sound on/off',
        'help.sys4': '         M = mouse flying       P = pause',
        'help.sys5': '         R = restart on runway',
        'help.sys6': '         F11 or Alt+Enter = toggle fullscreen',
        'help.sys7': '         H = show/hide help     Esc = quit',
        'help.takeoff': '[TAKEOFF] Z for full throttle -> accelerate to about 100 km/h -> hold S',
        'help.takeoff2': '          -> release at 12-15 deg pitch -> it lifts off by itself',
        'help.takeoff3': '          (jets have much more thrust: rotate sooner, gently)',
        'help.level': '[LEVEL]  Let go - the aircraft trims itself. Tap S/W to adjust',
        'help.turn': '[TURN]   Hold D or A, up to about 60 deg bank; release to level in 2 s',
        'help.gear': '[GEAR]   Press G after takeoff to raise it - you gain real speed;',
        'help.gear2': '         press G again before landing (landing gear-up scrapes)',
        'help.slow': '[SLOW]   Hold B for the airbrake (works in the air); add F for flaps',
        'help.accel': '[SPEED]  Diving (W) loses height but gains speed.',
        'help.land': '[LAND]   Line up -> throttle to 20% -> F for flaps -> G for gear',
        'help.land2': '         -> tap S gently to reduce the sink rate',
        'help.warn': '[WARNING] STALL on screen means the wing stalled: push (W) and add power',
        'help.types': 'Three aircraft (press V to cycle):',
        'help.type1': '  Prop Trainer  easy and slow, fixed gear, good for practice',
        'help.type2': '  Light Jet     single turbojet, retractable gear, quick',
        'help.type3': '  Twin Jet      heavy, fast, wide turns',
        'help.cam': 'In ORBIT camera (press C), hold the right mouse button and drag',
        'help.lang': 'Language: press L any time (HUD, title bar and this text all switch)',

        # ---------------- 启动横幅
        'banner.loading': 'Starting SkyFlight ...',
        'banner.ready': 'Ready. Press H for controls.',
    },
}


# ------------------------------------------------------------------
#  HUD 用到的汉字集合（hud.py 只光栅化这些字，避免启动时卡顿）
# ------------------------------------------------------------------
def hud_characters():
    """返回 HUD 可能显示的所有字符（中文字形预先生成用）"""
    keys = [
        'hud.version', 'hud.gear_down', 'hud.gear_up', 'hud.gear_moving',
        'hud.gear_fixed', 'hud.engine_jet', 'hud.engine_piston',
        'hud.spd', 'hud.alt', 'hud.thr', 'hud.vs', 'hud.brake', 'hud.flaps',
        'compass.n', 'compass.ne', 'compass.e', 'compass.se',
        'compass.s', 'compass.sw', 'compass.w', 'compass.nw',
        'warn.stall', 'warn.pullup', 'warn.lowpower', 'warn.highaoa',
        'warn.crashed', 'warn.paused',
    ]
    out = set()
    for k in keys:
        for lang in (ZH, EN):
            s = STRINGS[lang].get(k, '')
            for ch in s:
                if ch.strip():
                    out.add(ch)
    # 数字和百分号也要（GEAR 50%）
    out.update('0123456789%')
    return out
