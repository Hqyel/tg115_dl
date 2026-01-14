# -*- coding: utf-8 -*-
"""频道配置"""

import re
from pathlib import Path

# ============================================================
# 路径配置
# ============================================================

BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "resources.db"
STATE_FILE = DATA_DIR / "crawl_state.json"

# 确保 data 目录存在
DATA_DIR.mkdir(exist_ok=True)

# ============================================================
# 频道配置
# ============================================================

CHANNELS = {
  "lsp115": {
    "url": "https://t.me/s/Lsp115",
    "name": "115网盘资源分享频道",
    "parse_mode": "telegraph",
  },
  "vip115hot": {
    "url": "https://t.me/s/vip115hot",
    "name": "懒狗集中营",
    "parse_mode": "inline",
  },
  "qukanmovie": {
    "url": "https://t.me/s/QukanMovie",
    "name": "115影视资源分享",
    "parse_mode": "button",
  },
}

# ============================================================
# 请求配置
# ============================================================

REQUEST_DELAY = 1  # 请求间隔（秒）

HEADERS = {
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
  "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# ============================================================
# 链接验证
# ============================================================

PAN_115_PATTERN = re.compile(r'https?://115cdn\.com/s/[a-zA-Z0-9]+\?password=[a-zA-Z0-9]+')
PAN_115_PATTERN_ALT = re.compile(r'https?://115\.com/s/[a-zA-Z0-9]+')


def is_valid_115_url(url: str) -> bool:
  """验证是否为有效的 115cdn.com 链接"""
  if not url:
    return False
  return "115cdn.com" in url
