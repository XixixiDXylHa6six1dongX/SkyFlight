# -*- coding: utf-8 -*-
"""
界面语言检查

要求：
  1. 中英两张文字表的键完全一致（漏翻/多翻都能发现）
  2. 每条文字都不为空，且不是键名本身
  3. L 键的切换逻辑正确
  4. 中文字形能光栅化出来（不是空方块）
  5. 界面里不能再有"写死的中文/英文"漏网（关键位置抽查）
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skyflight import i18n, hud as hudmod

ok = True


def check(name, cond, detail=''):
    global ok
    if cond:
        print('  [OK] %-32s %s' % (name, detail))
    else:
        ok = False
        print('  [FAIL] %-32s %s' % (name, detail))


zh = i18n.STRINGS[i18n.ZH]
en = i18n.STRINGS[i18n.EN]

# ---------- 1) 键一致
print('  文字表一致性:')
only_zh = sorted(set(zh) - set(en))
only_en = sorted(set(en) - set(zh))
print('     中文条目 %d 条，英文条目 %d 条' % (len(zh), len(en)))
check('两张表的键完全一致', not only_zh and not only_en,
      ('中文多出 %s ' % only_zh if only_zh else '') +
      ('英文多出 %s' % only_en if only_en else '') or '一致')

# ---------- 2) 内容
print()
print('  条目内容:')
empty = [k for k, v in list(zh.items()) + list(en.items()) if not str(v).strip()]
check('没有空条目', not empty, str(empty[:5]))
print('     共 %d 个界面用词' % len(zh))

# ---------- 3) 切换
print()
print('  语言切换:')
i18n.set_lang(i18n.ZH)
check('默认中文', i18n.get_lang() == i18n.ZH, i18n.get_lang())
check('切到英文', i18n.toggle_lang() == i18n.EN, i18n.get_lang())
check('切回中文', i18n.toggle_lang() == i18n.ZH, i18n.get_lang())
check('非法语言回落到中文', i18n.set_lang('klingon') or i18n.get_lang() == i18n.ZH,
      i18n.get_lang())
# 取一个不存在的键应返回键名（方便发现漏翻）
i18n.set_lang(i18n.ZH)
check('缺失键返回键名', i18n.t('no.such.key') == 'no.such.key')

# ---------- 4) 每个键两种语言都能取到
print()
print('  逐条取值:')
bad = []
needs_arg = set()
for k in sorted(zh):
    for lang in (i18n.ZH, i18n.EN):
        raw = str(i18n.STRINGS[lang].get(k, ''))
        i18n.set_lang(lang)
        if '{n}' in raw:
            v = i18n.t(k, n=50)
            problems = ('{' in v)
        elif '%' in raw:
            # 含 %s/%d/%.0f 的格式串，这里只确认它不是空、也不等于键名
            needs_arg.add(k)
            v = raw
            problems = False
        else:
            v = i18n.t(k)
            problems = ('%' in v or '{' in v)
        if not v or v == k or problems:
            bad.append((lang, k, v))
check('所有键都能正常取值（无残留占位符）', not bad,
      str(bad[:4]) if bad else '%d 条全部正常（其中 %d 条需要参数）' % (
          len(zh), len(needs_arg)))

# ---------- 5) 中文字形
print()
print('  中文字形光栅化:')
check('系统字体可用', hudmod.font_ready())
n = hudmod.warm_font()
check('HUD 用到的字形能生成', n > 10, '%d 个字形' % n)
# 抽查几个字：点阵里必须有实心点，而且不能整块全实心（那是占位方块）
import skyflight.hud as H
probe_ok = True
detail = []
for ch in '空速起落架北东南迎角失速':
    # 汉字要点阵按**目标字号**生成（HUD 里汉字会出现在 15~21 几种字号上）
    rows, w = H.cjk_glyph(ch, 19)
    solid = sum(r.count('#') for r in rows)
    total = len(rows) * w
    ratio = solid / float(total)
    detail.append('%s %.0f%%' % (ch, ratio * 100))
    if solid < 4 or ratio > 0.95:
        probe_ok = False
check('汉字点阵有实际笔画（不是占位方块）', probe_ok, ' '.join(detail[:5]))

# 字号太小应该返回 None（画出来只是墨点）
check('过小字号返回 None（不画墨点）', H.cjk_glyph('空', 6) is None,
      'size=6 -> %s' % H.cjk_glyph('空', 6))
# 不同字号生成的点阵行数应该不同（说明确实是按字号光栅化）
r15 = H.cjk_glyph('空', 15)
r19 = H.cjk_glyph('空', 19)
check('按字号光栅化（15 与 19 行数不同）',
      r15 is not None and r19 is not None and len(r15[0]) < len(r19[0]),
      '%d 行 vs %d 行' % (len(r15[0]), len(r19[0])))

# ---------- 6) 界面代码里不该再写死文字
print()
print('  源码抽查（界面文字必须走 i18n）:')
base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails = []
src = io.open(os.path.join(base, 'skyflight', 'hud.py'), encoding='utf-8').read()
import re
# HUD 里只允许纯格式片段（如 '%03d'）写死，界面用词必须走 i18n
for m in re.finditer(r"hud\.text\(\s*'([^']*)'", src):
    lit = m.group(1)
    if re.fullmatch(r'[%\d\.\-+]*[a-z]?', lit):
        continue
    fails.append('hud.py: ' + lit)
src2 = io.open(os.path.join(base, 'skyflight', 'app.py'), encoding='utf-8').read()
# 启动诊断/开发提示允许保留中文（它们只出现在黑色控制台里，
# 不进入游戏界面，所以不参与游戏内语言切换）
ALLOW = ('[i18n]', '出错了', '中/英', '提示', '机型', '起落架',
         '[音效]', '[aircraft]', '[gear]', '[water]')
for m in re.finditer(r"print\(\s*'([^']*[\u4e00-\u9fff][^']*)'", src2):
    lit = m.group(1)
    if any(a in lit for a in ALLOW):
        continue
    fails.append('app.py: ' + lit[:30])
check('HUD / app 里没有写死的界面文字', not fails,
      '; '.join(fails[:4]) if fails else '干净')

print()
print('=' * 62)
print('  语言检查: %s' % ('全部通过' if ok else '有失败项'))
print('=' * 62)
sys.exit(0 if ok else 1)
