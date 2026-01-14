#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Telegram 公开频道资源爬虫

无需 Telegram API，直接爬取公开频道网页版，解析资源信息并提取网盘链接。
支持多频道、关键词搜索、增量爬取和断点续传。

用法:
  python main.py channels                # 列出可用频道
  python main.py crawl -c lsp115 --all   # 全量爬取
  python main.py search "仙逆"           # 搜索
  python main.py sync                    # 同步所有频道
"""

from src.cli.commands import main

if __name__ == "__main__":
  main()
