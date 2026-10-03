# -*- coding: utf-8 -*-
"""
GitHub 连接状态检查（双击「网络诊断.bat」运行）

只做三件事：
  1. 测 github.com 通不通（它不通就没法推送）
  2. 测 api.github.com（通常另一个线路，能用来核对远程状态）
  3. 核对本地和远程的提交是否一致，告诉你"有没有东西还没推上去"
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

OWNER, REPO = 'XixixiDXylHa6six1dongX', 'SkyFlight'
GIT_CANDIDATES = [
    r'C:\Users\DELL\AppData\Local\GitHubDesktop\app-3.6.6\resources\app\git\cmd\git.exe',
]


def find_git():
    for p in GIT_CANDIDATES:
        if os.path.exists(p):
            return p
    # 退而求其次：找 GitHub Desktop 目录下任意版本的 git
    base = os.path.expandvars(r'%LOCALAPPDATA%\GitHubDesktop')
    if os.path.isdir(base):
        for d in sorted(os.listdir(base), reverse=True):
            p = os.path.join(base, d, 'resources', 'app', 'git', 'cmd', 'git.exe')
            if os.path.exists(p):
                return p
    return 'git'


def tcp_ok(host, port=443, timeout=6):
    t0 = time.time()
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True, time.time() - t0
    except Exception:
        return False, time.time() - t0


def api(url, tries=2):
    for i in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={'User-Agent': 'skyflight-status',
                              'Accept': 'application/vnd.github+json'})
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(1.0)


def main():
    print('  正在检查网络，请稍候（最多约 20 秒）...')
    print()

    # ---------- 1) github.com
    ok_push, dt = tcp_ok('github.com')
    print('  [1] github.com （推送/拉取必须走这里）')
    if ok_push:
        print('      OK  连接正常，用时 %.2f 秒' % dt)
    else:
        print('      不通  等了 %.1f 秒没连上' % dt)
        print('      说明：这是网络拦截，不是你仓库的问题。')
        print('            等一会儿再试，或者用网页版查看仓库。')

    # ---------- 2) api.github.com
    print()
    print('  [2] api.github.com （查看远程状态用的备用线路）')
    ok_api, dt2 = tcp_ok('api.github.com')
    if ok_api:
        print('      OK  连接正常，用时 %.2f 秒' % dt2)
    else:
        print('      不通  用时 %.1f 秒' % dt2)

    # ---------- 3) 本地 / 远程是否一致
    print()
    print('  [3] 你本地和 GitHub 上的内容是否一致')
    git = find_git()
    try:
        local = subprocess.run([git, 'log', '--format=%H|%s', '-1'],
                               cwd=HERE, capture_output=True, text=True,
                               encoding='utf-8', errors='replace').stdout.strip()
    except Exception as e:
        print('      读取本地提交失败: %s' % e)
        local = ''

    if local:
        lsha, lmsg = local.split('|', 1)
        print('      本地最新: %s  %s' % (lsha[:8], lmsg[:44]))
    else:
        lsha = ''

    if ok_api:
        try:
            commits = api('https://api.github.com/repos/%s/%s/commits?per_page=10'
                          % (OWNER, REPO))
            rsha = commits[0]['sha']
            print('      远程最新: %s  %s' % (
                rsha[:8], commits[0]['commit']['message'].splitlines()[0][:44]))
            print()
            if lsha and lsha == rsha:
                print('      ==> 完全一致，没有东西需要推送')
            elif lsha and any(c['sha'] == lsha for c in commits):
                print('      ==> 本地这条已经在远程历史里了')
            else:
                print('      ==> 本地有还没推上去的改动（等 github.com 通了再推）')
        except Exception as e:
            print('      查远程失败: %s' % type(e).__name__)
    else:
        print('      api 也不通，跳过远程核对')

    # ---------- 4) 结论
    print()
    print('  ' + '-' * 58)
    if ok_push:
        print('  结论：GitHub 连接正常，可以正常推送。')
    else:
        print('  结论：github.com 暂时连不上（网络拦截）。')
        print('        你的本地文件和 GitHub 上的内容都没问题，')
        print('        等网络恢复后打开 GitHub Desktop 点一下 Push 即可。')
    print('  ' + '-' * 58)
    return 0


if __name__ == '__main__':
    sys.exit(main())
