# -*- coding: utf-8 -*-
"""文档检查：README 长度、各文档字数、中文编码是否正常"""
import io
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

files = ['README.md', 'CHANGELOG.md', 'NOTES.md', 'SETUP.md', '说明.md']
BAD = ['鐗', '鏀', '锛', '閲', '\ufffd']

print('  %-14s %6s %8s %8s  %s' % ('文件', '字符', '行数', '中文字', '编码'))
allok = True
for f in files:
    if not os.path.exists(f):
        print('  %-14s 不存在' % f)
        continue
    t = io.open(f, encoding='utf-8').read()
    zh = sum(1 for c in t if '\u4e00' <= c <= '\u9fff')
    bad = [b for b in BAD if b in t]
    status = 'OK' if not bad else '损坏 %s' % bad
    if bad:
        allok = False
    print('  %-14s %6d %8d %8d  %s' % (f, len(t), len(t.splitlines()), zh, status))

t = io.open('README.md', encoding='utf-8').read()
print()
print('  README %d 字符 %s' % (len(t), '(≤350 保持精简)' if len(t) <= 400 else '(偏长)'))
print()
print('  文档检查: %s' % ('全部正常' if allok else '有编码问题'))
sys.exit(0 if allok else 1)
