# -*- coding: utf-8 -*-
"""
粒子特效检查

要保证：
  1. 粒子池能生成、更新、回收（不会越界、不会泄漏）
  2. 爆炸会生成足够多的粒子（火球+碎片+烟+扬尘）
  3. 粒子会随时间消亡（不能永远堆着）
  4. 实例数据格式正确（8 个 float，颜色在 0~1）
  5. 数量上限不会超过池容量
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from skyflight import particles as P

ok = True


def check(name, cond, detail=''):
    global ok
    if cond:
        print('  [OK] %-32s %s' % (name, detail))
    else:
        ok = False
        print('  [FAIL] %-32s %s' % (name, detail))


p = P.Particles(capacity=700)
print('  粒子池容量: %d' % p.cap)

# ---------- 爆炸
print()
print('  爆炸:')
p.explosion((100.0, 50.0, 200.0), scale=1.0)
n0 = p.count()
print('     一次爆炸生成 %d 个粒子' % n0)
check('爆炸粒子数量足够（>150）', n0 > 150, '%d 个' % n0)

# 位置应该集中在爆炸点附近
alive = np.nonzero(p.alive)[0]
d = np.linalg.norm(p.pos[alive] - np.array([100.0, 50.0, 200.0]), axis=1)
check('粒子生成在爆炸点附近', float(d.max()) < 16.0,
      '最远 %.1f m' % float(d.max()))

# ---------- 实例数据
print()
print('  实例数据:')
data, n = p.visible_instances(np.array([1.0, 0, 0]), np.array([0, 1.0, 0]))
print('     返回 %d 条实例，形状 %s' % (n, data.shape if data is not None else None))
check('实例数据是 8 列', data is not None and data.shape[1] == 8)
check('颜色在 0~1 范围',
      data is not None and float(data[:, 5:8].min()) >= 0.0
      and float(data[:, 5:8].max()) <= 1.0,
      '最小 %.3f 最大 %.3f' % (
          float(data[:, 5:8].min()), float(data[:, 5:8].max())))
check('尺寸为正', data is not None and float(data[:, 3].min()) > 0.0,
      '最小 %.3f' % float(data[:, 3].min()))
check('数据无 NaN/Inf', data is not None and bool(np.all(np.isfinite(data))))

# ---------- 随时间消亡
print()
print('  生命周期:')
p2 = P.Particles(capacity=700)
p2.explosion((0.0, 20.0, 0.0))
print('     初始 %d 个' % p2.count())
for i in range(1, 7):
    for _ in range(30):          # 每次推进 0.5 秒
        p2.update(1 / 60.0)
    print('     %.1f 秒后 %d 个' % (i * 0.5, p2.count()))
check('粒子会随时间消亡', p2.count() < 20, '6 秒后剩 %d 个' % p2.count())

# ---------- 溢出保护（连续爆炸不能越界）
print()
print('  溢出保护:')
p3 = P.Particles(capacity=300)
for i in range(20):
    p3.explosion((i * 10.0, 10.0, 0.0))
    p3.update(1 / 60.0)
cnt = p3.count()
check('持续爆炸不超出容量', cnt <= p3.cap, '%d / %d' % (cnt, p3.cap))
data3, n3 = p3.visible_instances(np.array([1.0, 0, 0]), np.array([0, 1.0, 0]))
check('实例数不超过容量', n3 <= p3.cap, '%d' % n3)

# ---------- 扬尘 / 烟 / 凝结尾
print()
print('  其他特效:')
p4 = P.Particles(capacity=700)
for name, fn in (('接地扬尘', lambda: p4.dust((0.0, 0.3, 0.0), 1.2)),
                 ('轮胎烟', lambda: p4.smoke_trail((0.0, 0.3, 0.0),
                                                   np.zeros(3), 1.0, n=3)),
                 ('轮胎烟(黑)', lambda: p4.smoke_trail((0.0, 1.0, 0.0),
                                                       np.zeros(3), 1.0, n=3,
                                                       dark=True)),
                 ('凝结尾', lambda: p4.contrail((0.0, 2000.0, 0.0),
                                                np.array([0.0, 0, -80.0])))):
    before = p4.count()
    fn()
    after = p4.count()
    check('%s 能生成' % name, after > before, '+%d 个' % (after - before))

# ---------- 性能
print()
print('  性能（700 个粒子满池时每帧更新耗时）:')
p5 = P.Particles(capacity=700)
for i in range(6):
    p5.explosion((i * 5.0, 10.0, 0.0))
print('     池内 %d 个粒子' % p5.count())
t0 = time.time()
for _ in range(120):
    p5.update(1 / 60.0)
    p5.visible_instances(np.array([1.0, 0, 0]), np.array([0, 1.0, 0]))
dt = (time.time() - t0) / 120.0
print('     每帧 %.3f ms（60 帧预算 16.7 ms）' % (dt * 1000))
check('每帧耗时 < 3 ms', dt < 0.003, '%.3f ms' % (dt * 1000))

print()
print('=' * 62)
print('  粒子检查: %s' % ('全部通过' if ok else '有失败项'))
print('=' * 62)
sys.exit(0 if ok else 1)
