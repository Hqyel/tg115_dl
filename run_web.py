#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Web 服务启动脚本

用法:
  python run_web.py             # 启动 Web 服务（默认端口 5000）
  python run_web.py --port 8080 # 指定端口
  python run_web.py --debug     # 调试模式
"""

import argparse
import os

try:
  from dotenv import load_dotenv
  load_dotenv()
  print("已加载 .env 配置文件")
except ImportError:
  print("提示: 未安装 python-dotenv，将仅使用系统环境变量")
  print("      可以使用 pip install python-dotenv 来支持 .env 文件")

from web.app import run_server

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='TG 资源爬虫 Web 服务')
  parser.add_argument('--host', default='0.0.0.0', help='监听地址')
  parser.add_argument('--port', type=int, default=5000, help='端口号')
  parser.add_argument('--debug', action='store_true', help='调试模式')
  
  args = parser.parse_args()
  run_server(host=args.host, port=args.port, debug=args.debug)
