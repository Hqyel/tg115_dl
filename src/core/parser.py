# -*- coding: utf-8 -*-
"""解析器模块"""

import time

import requests
from bs4 import BeautifulSoup

from src.channels.config import HEADERS, REQUEST_DELAY, is_valid_115_url
from src.models.resource import Resource
from src.core.database import Database


class TelegraphParser:
  """Telegraph 页面解析器（用于 Lsp115 频道）"""

  def __init__(self):
    self.session = requests.Session()
    self.session.headers.update(HEADERS)

  def parse_pan_link(self, telegraph_url: str) -> tuple[str, str]:
    """从 telegraph 页面解析 115 链接"""
    try:
      response = self.session.get(telegraph_url, timeout=30)
      response.raise_for_status()
    except requests.RequestException as e:
      print(f"请求失败: {e}")
      return "", ""

    soup = BeautifulSoup(response.text, "lxml")

    pan_url = ""
    for link in soup.find_all("a", href=True):
      href = link.get("href", "")
      link_text = link.get_text(strip=True)
      if is_valid_115_url(href):
        pan_url = href
        break
      if ("查看链接" in link_text or "🔗" in link_text) and is_valid_115_url(href):
        pan_url = href
        break

    description = ""
    article = soup.find("article")
    if article:
      text = article.get_text(separator="\n", strip=True)
      lines = [l for l in text.split("\n") if l.strip()][:5]
      description = "\n".join(lines)

    if not is_valid_115_url(pan_url):
      return "", description

    return pan_url, description

  def parse_batch(self, db: Database, channel_id: str, limit: int = 100) -> int:
    """批量解析未解析的资源"""
    resources = db.get_unparsed(channel_id, limit)

    if not resources:
      print("没有需要解析的资源")
      return 0

    print(f"开始解析网盘链接，共 {len(resources)} 条...")
    print("-" * 50)

    parsed_count = 0
    for i, r in enumerate(resources, 1):
      print(f"[{i}/{len(resources)}] {r.title[:30]}...")

      pan_url, description = self.parse_pan_link(r.telegraph_url)
      r.description = description

      if pan_url:
        r.pan_url = pan_url
        print(f"  ✓ {pan_url[:50]}...")
        parsed_count += 1
      else:
        # 标记为已处理但无有效链接，避免重复解析
        r.pan_url = "N/A"
        print(f"  ✗ 未找到115链接（已标记）")

      db.save_resource(channel_id, r)
      time.sleep(REQUEST_DELAY)

    print("-" * 50)
    print(f"解析完成，成功 {parsed_count} 条")
    return parsed_count
