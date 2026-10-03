# -*- coding: utf-8 -*-
"""音效系统检查：合成、混音、播放是否正常"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from skyflight import sound as S

ok = True


def check(name, cond, detail=''):
    global ok
    if cond:
        print('  [OK] %-30s %s' % (name, detail))
    else:
        ok = False
        print('  [FAIL] %-30s %s' % (name, detail))


print('  采样率 %d Hz，块大小 %d 采样（约 %.1f ms）' % (
    S.RATE, S.BLOCK, 1000.0 * S.BLOCK / S.RATE))

# ---------- 合成
print()
print('  合成各种声音:')
gen = [
    ('引擎(活塞)', lambda: S.synth_engine(0.7, 0.5, 'piston')),
    ('引擎(涡喷)', lambda: S.synth_engine(0.9, 1.0, 'jet')),
    ('引擎(怠速)', lambda: S.synth_engine(0.05, 0.0, 'piston')),
    ('风噪(慢)', lambda: S.synth_wind(0.2)),
    ('风噪(快)', lambda: S.synth_wind(1.2)),
    ('滑跑', lambda: S.synth_roll(0.6)),
    ('接地', S.synth_touchdown),
    ('起落架', S.synth_gear),
    ('失速告警', S.synth_stall_beep),
    ('爆炸', S.synth_explosion),
    ('擦地', S.synth_hit),
]
for name, fn in gen:
    a = fn()
    dur = len(a) / float(S.RATE)
    peak = float(np.max(np.abs(a)))
    rms = float(np.sqrt(np.mean(a ** 2)))
    bad = (not np.all(np.isfinite(a))) or peak > 1.001 or peak < 0.01
    if bad:
        ok = False
    print('  %s %-14s 时长 %.2fs  峰值 %.2f  能量 %.3f' % (
        '[FAIL]' if bad else '[OK]  ', name, dur, peak, rms))

# ---------- 循环片段必须无爆音（首尾接近）
print()
print('  循环片段首尾连续性（避免每圈"咔哒"）:')
for name, fn in (('引擎', lambda: S.synth_engine(0.6, 0.4, 'piston')),
                 ('风噪', lambda: S.synth_wind(0.6)),
                 ('滑跑', lambda: S.synth_roll(0.5))):
    a = fn()
    # 看首尾各 32 采样是否接近（差别太大循环时会响）
    head = float(np.mean(np.abs(a[:32])))
    tail = float(np.mean(np.abs(a[-32:])))
    jump = abs(head - tail)
    check('%s 首尾电平接近' % name, jump < 0.25,
          '首 %.3f 尾 %.3f 差 %.3f' % (head, tail, jump))

# ---------- 混音器
print()
print('  混音器（waveOut）:')
snd = S.Sound()
if snd.ready:
    check('waveOut 已打开', True, '缓冲区 %d 块' % snd.out.nbuf)
    # 设置状态让它出声音
    snd.set_state(throttle=0.8, speed_frac=0.6, kind='piston', on_ground=True)
    time.sleep(0.35)
    busy = snd.out.busy_count()
    check('持续输出音频（缓冲区在使用）', busy > 0, '占用 %d/%d 块' % (busy, snd.out.nbuf))

    # 混一段看看有没有爆音/NaN
    snd.set_state(throttle=1.0, speed_frac=1.0, kind='jet', on_ground=False)
    time.sleep(0.2)
    block = snd._mix(1024)
    check('混音输出有限且不削顶',
          bool(np.all(np.isfinite(block))) and float(np.max(np.abs(block))) <= 1.001,
          '峰值 %.3f' % float(np.max(np.abs(block))))

    # 一次性音效（爆炸）
    snd.explosion()
    time.sleep(0.15)
    check('爆炸音效可以叠加播放', True)

    snd.stop()
    check('能正常关闭', True)
else:
    print('  [跳过] 本机没有可用音频输出: %s' % (snd.error or '未知'))
    print('         （游戏会自动静音运行，不会崩）')

# ---------- 静音替身
print()
print('  静音替身（没声卡时的兜底）:')
ss = S.SilentSound()
ss.set_state(throttle=1.0)
ss.play(np.zeros(10, dtype=np.float32))
ss.touchdown()
ss.explosion()
ss.gear()
ss.hit()
ss.stop()
check('静音替身接口完整', True)

print()
print('=' * 62)
print('  音效检查: %s' % ('全部通过' if ok else '有失败项'))
print('=' * 62)
sys.exit(0 if ok else 1)
