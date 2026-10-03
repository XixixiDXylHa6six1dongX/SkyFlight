# -*- coding: utf-8 -*-
"""
音效系统

设计：
  - 所有声音都用 numpy **现场合成**，不依赖任何音频文件
  - 用 Windows 的 waveOut（winmm.dll）做**真正的混音**：
    引擎声 + 风噪 + 一次性音效可以同时播放，互不打断
  - 合成在一个后台线程里按固定节奏跑，不拖慢游戏主循环
  - 任何一步失败都自动降级（先用 waveOut；不行就退回 winsound；再不行静音）
    游戏本身绝不因为音频问题崩溃

声音清单：
  引擎      和油门/转速相关的基频 + 谐波（喷气机偏啸叫，螺旋桨偏低频轰鸣）
  风噪      和空速相关的宽带噪声
  滑跑      轮胎和跑道摩擦的隆隆声（贴地且速度快时）
  接地      落地瞬间的一声闷响
  失速告警  间歇性短促警告音
  爆炸      坠毁时的低频冲击 + 噪声爆裂
"""
import ctypes
import ctypes.wintypes as wt
import math
import struct
import sys
import threading
import time

import numpy as np

RATE = 22050          # 采样率（够用又省 CPU）
BLOCK = 1024          # 每次提交的采样数
CHANNELS = 1

# ================================================================
#  waveOut 封装
# ================================================================
_WAVE_MAPPER = -1
WAVE_FORMAT_PCM = 1
CALLBACK_NULL = 0
WHDR_DONE = 0x00000001


class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [
        ('wFormatTag', wt.WORD),
        ('nChannels', wt.WORD),
        ('nSamplesPerSec', wt.DWORD),
        ('nAvgBytesPerSec', wt.DWORD),
        ('nBlockAlign', wt.WORD),
        ('wBitsPerSample', wt.WORD),
        ('cbSize', wt.WORD),
    ]


class WAVEHDR(ctypes.Structure):
    _fields_ = [
        ('lpData', ctypes.c_char_p),
        ('dwBufferLength', wt.DWORD),
        ('dwBytesRecorded', wt.DWORD),
        ('dwUser', ctypes.c_void_p),
        ('dwFlags', wt.DWORD),
        ('dwLoops', wt.DWORD),
        ('lpNext', ctypes.c_void_p),
        ('reserved', ctypes.c_void_p),
    ]


class WaveOut:
    """极简 waveOut 输出：几块缓冲区循环提交，实现连续播放"""

    def __init__(self, rate=RATE, channels=1, buffers=4):
        self.ok = False
        self.rate = rate
        self.channels = channels
        self.nbuf = buffers
        self._h = ctypes.c_void_p()
        self._hdrs = []
        self._bufs = []
        try:
            self.winmm = ctypes.WinDLL('winmm')
        except Exception:
            return
        self.winmm.waveOutOpen.argtypes = [
            ctypes.POINTER(ctypes.c_void_p), wt.UINT, ctypes.c_void_p,
            ctypes.c_void_p, ctypes.c_void_p, wt.DWORD]
        self.winmm.waveOutPrepareHeader.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(WAVEHDR), wt.UINT]
        self.winmm.waveOutWrite.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(WAVEHDR), wt.UINT]
        self.winmm.waveOutUnprepareHeader.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(WAVEHDR), wt.UINT]

        fmt = WAVEFORMATEX()
        fmt.wFormatTag = WAVE_FORMAT_PCM
        fmt.nChannels = channels
        fmt.nSamplesPerSec = rate
        fmt.wBitsPerSample = 16
        fmt.nBlockAlign = channels * 2
        fmt.nAvgBytesPerSec = rate * fmt.nBlockAlign
        fmt.cbSize = 0
        res = self.winmm.waveOutOpen(ctypes.byref(self._h), _WAVE_MAPPER,
                                     ctypes.byref(fmt), None, None,
                                     CALLBACK_NULL)
        if res != 0:
            return
        # 预分配缓冲区
        self.nsamp = BLOCK
        for _ in range(self.nbuf):
            buf = ctypes.create_string_buffer(self.nsamp * 2 * channels)
            hdr = WAVEHDR()
            hdr.lpData = ctypes.cast(buf, ctypes.c_char_p)
            hdr.dwBufferLength = self.nsamp * 2 * channels
            self.winmm.waveOutPrepareHeader(self._h, ctypes.byref(hdr),
                                            ctypes.sizeof(WAVEHDR))
            self._bufs.append(buf)
            self._hdrs.append(hdr)
        self.ok = True

    def busy_count(self):
        n = 0
        for h in self._hdrs:
            if not (h.dwFlags & WHDR_DONE):
                n += 1
        return n

    def write(self, samples):
        """samples: float32 [-1,1]，长度 = self.nsamp * channels"""
        for i, h in enumerate(self._hdrs):
            if h.dwFlags & WHDR_DONE or h.dwFlags == 0:
                data = np.clip(samples, -1.0, 1.0)
                ints = (data * 32767.0).astype('<i2')
                raw = ints.tobytes()
                n = min(len(raw), self._bufs[i].raw and len(raw))
                ctypes.memmove(self._bufs[i], raw, n)
                h.dwBufferLength = n
                h.dwFlags &= ~WHDR_DONE
                self.winmm.waveOutWrite(self._h, ctypes.byref(h),
                                        ctypes.sizeof(WAVEHDR))
                return True
        return False

    def close(self):
        if not self.ok:
            return
        try:
            self.winmm.waveOutReset(self._h)
            for h in self._hdrs:
                self.winmm.waveOutUnprepareHeader(self._h, ctypes.byref(h),
                                                  ctypes.sizeof(WAVEHDR))
            self.winmm.waveOutClose(self._h)
        except Exception:
            pass
        self.ok = False


# ================================================================
#  合成器：各种声音的生成函数
# ================================================================
def _env(n, attack=0.01, release=0.2):
    """简单的攻击/衰减包络"""
    a = max(1, int(n * attack))
    r = max(1, int(n * release))
    e = np.ones(n, dtype=np.float32)
    e[:a] = np.linspace(0.0, 1.0, a)
    e[-r:] = np.linspace(1.0, 0.0, r)
    return e


def noise(n, seed=0):
    rng = np.random.default_rng(seed)
    return rng.standard_normal(n).astype(np.float32)


def lowpass(x, alpha=0.15):
    """一阶低通（简单平滑），alpha 越大越闷"""
    y = np.empty_like(x)
    acc = 0.0
    a = float(alpha)
    for i in range(len(x)):
        acc += a * (x[i] - acc)
        y[i] = acc
    return y


def lowpass_fast(x, k=8):
    """箱式平滑（比逐样本循环快很多），近似低通"""
    if k <= 1:
        return x
    kernel = np.ones(k, dtype=np.float32) / k
    return np.convolve(x, kernel, mode='same').astype(np.float32)


# ---------------------------------------------------------------- 引擎
def synth_engine(throttle, speed_frac, kind='piston', seconds=1.0, seed=0):
    """合成可无缝循环的引擎声

    kind='piston'  -> 低频轰鸣 + 螺旋桨拍频
    kind='jet'     -> 高频啸叫 + 宽带喷气噪声
    返回 float32 数组（长度 = RATE * seconds，正好整周期，可循环）
    """
    n = int(RATE * seconds)
    t = np.arange(n, dtype=np.float32) / RATE
    thr = float(np.clip(throttle, 0.0, 1.0))
    spd = float(np.clip(speed_frac, 0.0, 1.5))

    # 基频随油门上升
    if kind == 'jet':
        f0 = 55.0 + 150.0 * thr
    else:
        f0 = 22.0 + 70.0 * thr
    # 取整到"每秒整数个周期"，这样循环处不会咔哒
    f0 = max(15.0, round(f0 * seconds) / seconds)

    out = np.zeros(n, dtype=np.float32)
    for h, amp in ((1, 1.0), (2, 0.45), (3, 0.28), (4, 0.16), (6, 0.09)):
        out += amp * np.sin(2 * math.pi * f0 * h * t)

    if kind == 'piston':
        # 螺旋桨拍频（叶片通过频率），让声音有"嗡嗡"的颗粒感
        blade = f0 * 3.0
        out += 0.5 * np.sin(2 * math.pi * blade * t) * (0.4 + 0.6 * thr)
    else:
        # 喷气：加一层高频啸叫
        whine = 900.0 + 2600.0 * thr
        whine = round(whine * seconds) / seconds
        out += 0.20 * np.sin(2 * math.pi * whine * t)
        out += 0.10 * np.sin(2 * math.pi * whine * 2.02 * t)

    # 喷流/进气噪声（低通后像"风箱声"）
    nz = noise(n, seed + 1) * (0.35 if kind == 'jet' else 0.22)
    nz = lowpass_fast(nz, 6 if kind == 'jet' else 10)
    out += nz * (0.35 + 0.65 * thr)

    # 转速越高越亮
    out *= (0.35 + 0.65 * thr)
    # 归一化，避免叠加后削顶
    peak = float(np.max(np.abs(out))) or 1.0
    return (out / peak).astype(np.float32)


# ---------------------------------------------------------------- 风噪
def synth_wind(speed_frac, seconds=1.0, seed=7):
    """可循环的风噪：随空速变响变亮"""
    n = int(RATE * seconds)
    s = float(np.clip(speed_frac, 0.0, 1.5))
    nz = noise(n, seed)
    nz = lowpass_fast(nz, max(2, int(14 - 8 * min(1.0, s))))
    nz *= (0.15 + 0.85 * min(1.0, s))
    peak = float(np.max(np.abs(nz))) or 1.0
    return (nz / peak).astype(np.float32)


# ---------------------------------------------------------------- 滑跑
def synth_roll(speed_frac, seconds=1.0, seed=11):
    """轮胎在跑道上滚的隆隆声"""
    n = int(RATE * seconds)
    s = float(np.clip(speed_frac, 0.0, 1.0))
    nz = noise(n, seed)
    nz = lowpass_fast(nz, 22)
    # 加一点周期性的"接缝"感
    t = np.arange(n, dtype=np.float32) / RATE
    seam = 0.5 + 0.5 * np.sin(2 * math.pi * (6.0 + 20.0 * s) * t)
    out = nz * seam * (0.25 + 0.75 * s)
    peak = float(np.max(np.abs(out))) or 1.0
    return (out / peak).astype(np.float32)


# ---------------------------------------------------------------- 一次性
def synth_touchdown(strength=1.0):
    """接地：一声闷响（低频冲击 + 短噪声）"""
    n = int(RATE * 0.45)
    t = np.arange(n, dtype=np.float32) / RATE
    thump = np.sin(2 * math.pi * (70.0 - 25.0 * t / 0.45) * t) * np.exp(-t * 11.0)
    nz = noise(n, 21) * np.exp(-t * 26.0) * 0.5
    out = (thump + nz) * float(np.clip(strength, 0.2, 1.5))
    peak = float(np.max(np.abs(out))) or 1.0
    return (out / peak * 0.9).astype(np.float32)


def synth_stall_beep():
    """失速告警：短促的蜂鸣"""
    n = int(RATE * 0.20)
    t = np.arange(n, dtype=np.float32) / RATE
    out = np.sin(2 * math.pi * 880.0 * t) * _env(n, 0.05, 0.3)
    return (out * 0.5).astype(np.float32)


def synth_gear():
    """起落架收放：液压马达的"嗡——"声"""
    n = int(RATE * 0.7)
    t = np.arange(n, dtype=np.float32) / RATE
    motor = np.sin(2 * math.pi * 120.0 * t) * 0.6
    motor += np.sin(2 * math.pi * 240.0 * t) * 0.2
    nz = lowpass_fast(noise(n, 33), 12) * 0.4
    out = (motor + nz) * _env(n, 0.05, 0.15)
    peak = float(np.max(np.abs(out))) or 1.0
    return (out / peak * 0.45).astype(np.float32)


def synth_explosion():
    """爆炸：低频冲击 + 宽带爆裂 + 尾巴"""
    n = int(RATE * 2.0)
    t = np.arange(n, dtype=np.float32) / RATE
    # 低频冲击（频率下滑）
    boom = np.sin(2 * math.pi * (95.0 * np.exp(-t * 3.2) + 28.0) * t) * np.exp(-t * 2.4)
    # 爆裂噪声
    nz = noise(n, 55) * np.exp(-t * 3.0)
    nz = lowpass_fast(nz, 3)
    # 碎片/回响
    crack = noise(n, 56) * np.exp(-t * 9.0) * 0.55
    out = boom * 1.0 + nz * 0.9 + crack * 0.7
    peak = float(np.max(np.abs(out))) or 1.0
    return (out / peak).astype(np.float32)


def synth_hit():
    """擦地/撞小东西：金属刮擦"""
    n = int(RATE * 0.35)
    t = np.arange(n, dtype=np.float32) / RATE
    nz = noise(n, 77) * np.exp(-t * 14.0)
    sc = np.sin(2 * math.pi * 1700.0 * t) * np.exp(-t * 20.0) * 0.4
    out = nz * 0.8 + sc
    peak = float(np.max(np.abs(out))) or 1.0
    return (out / peak * 0.7).astype(np.float32)


# ================================================================
#  声音管理
# ================================================================
class Sound:
    """音效管理器。任何失败都静默降级，不影响游戏"""

    def __init__(self, enabled=True):
        self.enabled = bool(enabled)
        self.out = None
        self.thread = None
        self.running = False
        self.ready = False
        self.error = ''
        # 混音状态（主循环写，音频线程读）
        self.lock = threading.Lock()
        self._throttle = 0.0
        self._speed = 0.0
        self._kind = 'piston'
        self._on_ground = True
        self._brakes = 0.0
        self._master = 0.85
        self._oneshots = []          # [(samples, gain)]
        self._engine = None
        self._wind = None
        self._roll = None
        self._engine_key = None
        self._wind_key = None
        self._roll_key = None
        self._engine_pos = 0
        self._wind_pos = 0
        self._roll_pos = 0
        self._beep_timer = 0.0
        self._beep_on = False
        if self.enabled:
            self._start()

    # ------------------------------------------------ 启动
    def _start(self):
        try:
            self.out = WaveOut()
            if not self.out.ok:
                self.error = 'waveOut 打不开（可能没有声卡）'
                self.enabled = False
                return
            self.running = True
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
            self.ready = True
        except Exception as e:
            self.error = str(e)
            self.enabled = False

    def _loop(self):
        """音频线程：按固定节奏合成并提交"""
        nsamp = self.out.nsamp
        while self.running:
            # 缓冲没空就稍微等一下（避免 CPU 空转）
            if self.out.busy_count() >= self.out.nbuf * 0.8:
                time.sleep(0.004)
                continue
            try:
                block = self._mix(nsamp)
            except Exception:
                block = np.zeros(nsamp, dtype=np.float32)
            if not self.out.write(block):
                time.sleep(0.004)

    # ------------------------------------------------ 对外接口
    def set_state(self, throttle=0.0, speed_frac=0.0, kind='piston',
                  on_ground=False, brakes=0.0, stalled=False, paused=False):
        with self.lock:
            self._throttle = float(np.clip(throttle, 0.0, 1.0))
            self._speed = float(np.clip(speed_frac, 0.0, 1.5))
            self._kind = kind
            self._on_ground = bool(on_ground)
            self._brakes = float(np.clip(brakes, 0.0, 1.0))
            self._stalled = bool(stalled) and not paused

    def play(self, samples, gain=1.0):
        """播放一个一次性音效（和现有声音混在一起）"""
        if not self.enabled or samples is None:
            return
        with self.lock:
            self._oneshots.append((np.asarray(samples, dtype=np.float32),
                                   float(gain)))
            # 防止堆积太多
            if len(self._oneshots) > 6:
                self._oneshots = self._oneshots[-6:]

    def touchdown(self, strength=1.0):
        self.play(synth_touchdown(strength))

    def explosion(self):
        self.play(synth_explosion(), 1.0)

    def gear(self):
        self.play(synth_gear(), 0.9)

    def hit(self):
        self.play(synth_hit(), 0.8)

    def set_master(self, v):
        with self.lock:
            self._master = float(np.clip(v, 0.0, 2.0))

    def stop(self):
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=0.8)
        if self.out is not None:
            self.out.close()

    # ------------------------------------------------ 混音
    def _get_loop(self, which, key, fn):
        """按需重建循环片段（参数变化才重算）"""
        cache = getattr(self, '_cache_' + which, None)
        if cache is None or getattr(self, '_' + which + '_key') != key:
            cache = fn()
            setattr(self, '_cache_' + which, cache)
            setattr(self, '_' + which + '_key', key)
        return cache

    def _mix(self, n):
        with self.lock:
            thr = self._throttle
            spd = self._speed
            kind = self._kind
            on_ground = self._on_ground
            brakes = self._brakes
            master = self._master
            oneshots = self._oneshots
            self._oneshots = []
            stalled = getattr(self, '_stalled', False)

        out = np.zeros(n, dtype=np.float32)

        # ---- 引擎（按油门量化到 0.05 一档，避免每帧重算）
        if thr > 0.01:
            ekey = (round(thr * 20) / 20, kind)
            eng = self._get_loop('engine', ekey,
                                 lambda: synth_engine(ekey[0], spd, ekey[1]))
            take = min(n, len(eng))
            out[:take] += eng[:take] * 0.55
            self._engine_pos = (self._engine_pos + take) % len(eng)
        # ---- 风噪
        if spd > 0.05:
            wkey = round(spd * 10) / 10
            wnd = self._get_loop('wind', wkey, lambda: synth_wind(wkey))
            take = min(n, len(wnd))
            out[:take] += wnd[:take] * 0.30
            self._wind_pos = (self._wind_pos + take) % len(wnd)
        # ---- 滑跑隆隆声
        if on_ground and spd > 0.02:
            rkey = round(spd * 10) / 10
            rol = self._get_loop('roll', rkey, lambda: synth_roll(rkey))
            take = min(n, len(rol))
            out[:take] += rol[:take] * (0.28 + 0.22 * brakes)
            self._roll_pos = (self._roll_pos + take) % len(rol)

        # ---- 失速告警（每 0.6 秒响一下）
        if stalled:
            self._beep_timer -= n / float(RATE)
            if self._beep_timer <= 0.0:
                self._beep_timer = 0.6
                oneshots = list(oneshots) + [(synth_stall_beep(), 0.9)]

        # ---- 一次性音效（爆炸等）叠加
        for samples, gain in oneshots:
            take = min(n, len(samples))
            out[:take] += samples[:take] * gain

        out *= master
        # 软限幅，避免爆音
        out = np.tanh(out * 1.1).astype(np.float32)
        return out


# ================================================================
#  空实现（给 --no-sound 或没有声卡时用）
# ================================================================
class SilentSound:
    """没有声音时的替身，接口和 Sound 完全一样"""

    def __init__(self, *a, **kw):
        self.enabled = False
        self.ready = False
        self.error = '已禁用'

    def set_state(self, **kw):
        pass

    def play(self, *a, **kw):
        pass

    def touchdown(self, *a, **kw):
        pass

    def explosion(self, *a, **kw):
        pass

    def gear(self, *a, **kw):
        pass

    def hit(self, *a, **kw):
        pass

    def set_master(self, *a, **kw):
        pass

    def stop(self):
        pass
