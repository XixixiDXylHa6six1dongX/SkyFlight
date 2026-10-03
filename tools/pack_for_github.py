# -*- coding: utf-8 -*-
"""
打包 SkyFlight 源码，用于上传到 GitHub 网页

排除：runtime（185 MB 内置运行环境）、__pycache__、临时文件
产物：C:\\DEEPSEEK工作区\\SkyFlight-github.zip
"""
import os
import zipfile

SRC = r'C:\DEEPSEEK工作区\飞行模拟'
OUT = r'C:\DEEPSEEK工作区\SkyFlight-github.zip'

# 顶层要排除的目录
EXCLUDE_DIRS = {'runtime', '__pycache__', '.git', '.idea', '.vscode', 'venv', '.venv'}
# 排除的文件模式
EXCLUDE_NAMES = {'Thumbs.db', 'desktop.ini'}
EXCLUDE_SUFFIX = ('.pyc', '.pyo', '.log')


def keep(rel_path, name, is_dir=False):
    parts = rel_path.replace('\\', '/').split('/')
    for p in parts:
        if p in EXCLUDE_DIRS:
            return False
    if is_dir:
        return True
    if name in EXCLUDE_NAMES:
        return False
    if name.endswith(EXCLUDE_SUFFIX):
        return False
    if name.startswith('_') and name.endswith('.png'):
        return False
    return True


def main():
    if os.path.exists(OUT):
        os.remove(OUT)

    added = []
    total = 0
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for root, dirs, files in os.walk(SRC):
            dirs[:] = [d for d in dirs
                       if d not in EXCLUDE_DIRS]
            for f in sorted(files):
                full = os.path.join(root, f)
                rel = os.path.relpath(full, SRC)
                if not keep(rel, f):
                    continue
                arc = 'SkyFlight/' + rel.replace('\\', '/')
                z.write(full, arc)
                added.append((arc, os.path.getsize(full)))
                total += os.path.getsize(full)

    print('=' * 62)
    print('  打包完成')
    print('=' * 62)
    print('  文件: %s' % OUT)
    print('  大小: %.2f MB (%d 字节)' % (os.path.getsize(OUT) / 1024 / 1024,
                                        os.path.getsize(OUT)))
    print('  压缩前合计: %.2f MB' % (total / 1024 / 1024))
    print('  条目数: %d' % len(added))
    print()
    print('  包含的目录统计:')
    buckets = {}
    for arc, sz in added:
        top = arc.split('/')[1] if len(arc.split('/')) > 2 else '(根目录)'
        if '/' in arc[9:]:
            top = arc[9:].split('/')[0]
        else:
            top = '(根目录文件)'
        b = buckets.setdefault(top, [0, 0])
        b[0] += 1
        b[1] += sz
    for k in sorted(buckets):
        n, sz = buckets[k]
        print('    %-16s %3d 个文件  %8.1f KB' % (k, n, sz / 1024))
    print()
    print('  逐条清单:')
    for arc, sz in added:
        print('    %8.1f KB  %s' % (sz / 1024, arc))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
