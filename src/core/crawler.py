# -*- coding: utf-8 -*-
"""爬虫模块"""

import re
import signal
import time
from typing import Optional
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

from src.channels.config import CHANNELS, HEADERS, REQUEST_DELAY, PAN_115_PATTERN, PAN_115_PATTERN_ALT, is_valid_115_url
from src.models.resource import Resource, CrawlState
from src.core.database import Database, StateManager


class ChannelCrawler:
  """Telegram 频道爬虫"""

  def __init__(self, channel_id: str):
    if channel_id not in CHANNELS:
      raise ValueError(f"未知频道: {channel_id}")

    self.channel_id = channel_id
    self.channel_config = CHANNELS[channel_id]
    self.channel_url = self.channel_config["url"]
    self.parse_mode = self.channel_config["parse_mode"]

    self.session = requests.Session()
    self.session.headers.update(HEADERS)
    self._interrupted = False

  def setup_signal_handler(self, state_manager: StateManager, state: CrawlState):
    """设置中断信号处理"""
    def handler(signum, frame):
      print("\n\n收到中断信号，正在保存进度...")
      state_manager.save(state)
      print(f"进度已保存。使用 --resume 继续爬取。")
      self._interrupted = True

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

  def crawl_all(self, db: Database, state_manager: StateManager,
          resume_state: Optional[CrawlState] = None) -> int:
    """全量爬取"""
    if resume_state:
      state = resume_state
      print(f"从断点恢复，已爬取: {state.total_crawled}")
    else:
      state = CrawlState(channel_id=self.channel_id, mode="all")

    self.setup_signal_handler(state_manager, state)

    print(f"开始爬取频道: {self.channel_config['name']}")
    print(f"模式: 全量爬取 (Ctrl+C 可中断保存)")
    print("-" * 50)

    current_before_id = state.last_before_id
    saved_count = state.total_crawled

    while not self._interrupted:
      url = self.channel_url
      if current_before_id:
        url = f"{self.channel_url}?before={current_before_id}"

      print(f"正在请求: {url}")

      try:
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
      except requests.RequestException as e:
        print(f"请求失败: {e}，等待 10 秒重试...")
        time.sleep(10)
        continue

      soup = BeautifulSoup(response.text, "lxml")
      messages = self._parse_messages(soup)

      if not messages:
        print("没有更多消息了，爬取完成！")
        state_manager.clear()
        break

      new_count = 0
      for msg in messages:
        if self._interrupted:
          break
        if not db.exists(self.channel_id, msg.message_id):
          db.save_resource(self.channel_id, msg)
          new_count += 1
          saved_count += 1

      print(f"本页: {len(messages)} 条，新增: {new_count} 条，累计: {saved_count} 条")

      current_before_id = min(msg.message_id for msg in messages)
      state.last_before_id = current_before_id
      state.total_crawled = saved_count

      if saved_count % 100 == 0:
        state_manager.save(state)

      time.sleep(REQUEST_DELAY)

    print("-" * 50)
    print(f"爬取完成，共保存 {saved_count} 条资源")
    return saved_count

  def crawl_incremental(self, db: Database) -> int:
    """增量爬取"""
    latest_id = db.get_latest_message_id(self.channel_id)

    print(f"开始增量爬取: {self.channel_config['name']}")
    print(f"数据库最新消息 ID: {latest_id}")
    print("-" * 50)

    if latest_id == 0:
      print("数据库为空，请先使用 --all 进行初始爬取")
      return 0

    new_count = 0
    current_before_id = None
    consecutive_exists = 0

    while consecutive_exists < 20:
      url = self.channel_url
      if current_before_id:
        url = f"{self.channel_url}?before={current_before_id}"

      print(f"正在请求: {url}")

      try:
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
      except requests.RequestException as e:
        print(f"请求失败: {e}")
        break

      soup = BeautifulSoup(response.text, "lxml")
      messages = self._parse_messages(soup)

      if not messages:
        break

      page_new = 0
      for msg in messages:
        if db.exists(self.channel_id, msg.message_id):
          consecutive_exists += 1
        else:
          consecutive_exists = 0
          db.save_resource(self.channel_id, msg)
          page_new += 1
          new_count += 1

      print(f"本页: {len(messages)} 条，新增: {page_new} 条")

      current_before_id = min(msg.message_id for msg in messages)
      time.sleep(REQUEST_DELAY)

    print("-" * 50)
    print(f"增量爬取完成，新增 {new_count} 条资源")
    return new_count

  def crawl_with_limit(self, limit: int, db: Database) -> int:
    """限量爬取"""
    print(f"开始爬取: {self.channel_config['name']}")
    print(f"目标数量: {limit}")
    print("-" * 50)

    current_before_id = None
    saved_count = 0

    while saved_count < limit:
      url = self.channel_url
      if current_before_id:
        url = f"{self.channel_url}?before={current_before_id}"

      print(f"正在请求: {url}")

      try:
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
      except requests.RequestException as e:
        print(f"请求失败: {e}")
        break

      soup = BeautifulSoup(response.text, "lxml")
      messages = self._parse_messages(soup)

      if not messages:
        print("没有更多消息了")
        break

      for msg in messages:
        if saved_count >= limit:
          break
        if not db.exists(self.channel_id, msg.message_id):
          db.save_resource(self.channel_id, msg)
          saved_count += 1

      print(f"本页: {len(messages)} 条，累计: {saved_count} 条")

      current_before_id = min(msg.message_id for msg in messages)
      time.sleep(REQUEST_DELAY)

    print("-" * 50)
    print(f"爬取完成，共保存 {saved_count} 条资源")
    return saved_count

  def _parse_messages(self, soup: BeautifulSoup) -> list[Resource]:
    """解析页面消息"""
    resources = []
    message_divs = soup.find_all("div", class_="tgme_widget_message_wrap")

    for div in message_divs:
      try:
        resource = self._parse_single_message(div)
        if resource:
          resources.append(resource)
      except Exception as e:
        print(f"解析消息失败: {e}")
        continue

    return resources

  def _parse_single_message(self, div) -> Optional[Resource]:
    """解析单条消息"""
    message_elem = div.find("div", class_="tgme_widget_message")
    if not message_elem:
      return None

    data_post = message_elem.get("data-post", "")
    if "/" not in data_post:
      return None

    message_id = int(data_post.split("/")[-1])

    # 提取标签
    tags = []
    title_parts = []
    text_div = div.find("div", class_="tgme_widget_message_text")

    if text_div:
      for link in text_div.find_all("a", href=True):
        href = link.get("href", "")
        if "?q=%23" in href:
          tag_text = link.get_text(strip=True)
          if tag_text.startswith("#"):
            tags.append(tag_text)
            title_parts.append(tag_text.lstrip("#"))

    # 根据解析模式处理
    # 获取清理后的原始HTML
    raw_html = self._get_clean_html(div)

    if self.parse_mode == "telegraph":
      return self._parse_telegraph_mode(div, message_id, tags, title_parts, raw_html)
    elif self.parse_mode == "button":
      return self._parse_button_mode(div, message_id, tags, title_parts, text_div, raw_html)
    else:
      return self._parse_inline_mode(div, message_id, tags, title_parts, text_div, raw_html)

  def _get_clean_html(self, div) -> str:
    """获取清理后的消息卡片HTML"""
    from copy import copy
    # 复制元素以避免修改原始数据
    div_copy = copy(div)
    # 移除不必要的元素
    for script in div_copy.find_all(['script', 'style']):
      script.decompose()
    return str(div_copy)

  def _parse_telegraph_mode(self, div, message_id: int, tags: list, title_parts: list, raw_html: str) -> Optional[Resource]:
    """解析 telegraph 模式（Lsp115）"""
    telegraph_url = ""
    for link in div.find_all("a", href=True):
      href = link.get("href", "")
      link_text = link.get_text(strip=True)
      if "telegra.ph" in href and ("查看资源" in link_text or "📎" in link_text):
        telegraph_url = href
        break

    if not telegraph_url:
      return None

    title = self._extract_title_from_url(telegraph_url)
    if not title and title_parts:
      title = " ".join(title_parts)
    if not title:
      title = f"资源_{message_id}"

    return Resource(
      message_id=message_id,
      title=title,
      tags=",".join(tags),
      telegraph_url=telegraph_url,
      raw_html=raw_html
    )

  def _parse_inline_mode(self, div, message_id: int, tags: list, title_parts: list, text_div, raw_html: str) -> Optional[Resource]:
    """解析 inline 模式（vip115hot）"""
    pan_url = ""
    description = ""
    title = ""

    if text_div:
      text_content = text_div.get_text(separator="\n", strip=True)

      for link in text_div.find_all("a", href=True):
        href = link.get("href", "")
        if is_valid_115_url(href):
          pan_url = href
          break

      if not pan_url:
        match = PAN_115_PATTERN.search(text_content)
        if match:
          pan_url = match.group(0)
        else:
          match = PAN_115_PATTERN_ALT.search(text_content)
          if match:
            pan_url = match.group(0)

      lines = [l for l in text_content.split("\n") if l.strip()][:10]
      description = "\n".join(lines)

      # 优先从描述中提取标题（"名称："后面的内容）
      for line in lines:
        if line.startswith("名称：") or line.startswith("名称:"):
          title = line.split("：", 1)[-1].split(":", 1)[-1].strip()
          break

    if not is_valid_115_url(pan_url):
      return None

    # 如果没有从描述提取到标题，使用标签或默认值
    if not title:
      if title_parts:
        title = " ".join(title_parts[:3])
      else:
        title = f"资源_{message_id}"

    return Resource(
      message_id=message_id,
      title=title,
      tags=",".join(tags),
      pan_url=pan_url,
      description=description,
      raw_html=raw_html
    )

  def _parse_button_mode(self, div, message_id: int, tags: list, title_parts: list, text_div, raw_html: str) -> Optional[Resource]:
    """解析 button 模式（QukanMovie）"""
    pan_url = ""
    description = ""
    title = ""

    for link in div.find_all("a", href=True):
      link_text = link.get_text(strip=True)
      href = link.get("href", "")
      if "点击跳转" in link_text:
        if is_valid_115_url(href):
          pan_url = href
          break

    if not is_valid_115_url(pan_url):
      return None

    if text_div:
      text_content = text_div.get_text(separator="\n", strip=True)
      lines = [l for l in text_content.split("\n") if l.strip()][:10]
      description = "\n".join(lines)

      # 从描述中提取标题
      for line in lines:
        # 跳过纯表情符号的行
        clean_line = re.sub(r'[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]', '', line).strip()
        if not clean_line:
          continue
        # 查找包含资源名称的行（如 "电视剧｜凡人修仙传..."）
        if "｜" in line or "|" in line:
          title = line.split("｜", 1)[-1].split("|", 1)[-1].strip()
          break
        # 或者取第一个非表情符号的行
        if not title and len(clean_line) > 2:
          title = clean_line
          break

    # 如果没有提取到标题，使用标签或默认值
    if not title:
      if title_parts:
        title = " ".join(title_parts[:3])
      else:
        title = f"资源_{message_id}"

    return Resource(
      message_id=message_id,
      title=title,
      tags=",".join(tags),
      pan_url=pan_url,
      description=description,
      raw_html=raw_html
    )

  def _extract_title_from_url(self, url: str) -> str:
    """从 telegraph URL 提取标题"""
    try:
      path = url.split("telegra.ph/")[-1]
      title = unquote(path)
      title = re.sub(r'-\d{2}-\d{2}(-\d+)?$', '', title)
      return title
    except Exception:
      return ""
