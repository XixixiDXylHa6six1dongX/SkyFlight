# -*- coding: utf-8 -*-
"""让 `python -m skyflight` 可以直接启动游戏"""
import sys

from .app import main

if __name__ == '__main__':
    sys.exit(main())
