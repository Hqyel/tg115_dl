# -*- coding: utf-8 -*-
"""数据库模块"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Optional

from src.channels.config import CHANNELS, DATABASE_PATH, STATE_FILE
from src.models.resource import Resource, CrawlState


class StateManager:
  """爬取状态管理器"""

  def __init__(self, state_file: Path = STATE_FILE):
    self.state_file = state_file

  def load(self) -> Optional[CrawlState]:
    if not self.state_file.exists():
      return None
    try:
      with open(self.state_file, "r", encoding="utf-8") as f:
        return CrawlState.from_dict(json.load(f))
    except Exception:
      return None

  def save(self, state: CrawlState):
    try:
      with open(self.state_file, "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
    except Exception as e:
      print(f"保存状态失败: {e}")

  def clear(self):
    if self.state_file.exists():
      self.state_file.unlink()


class Database:
  """SQLite 数据库管理（支持多频道独立表）"""

  def __init__(self, db_path: Path = DATABASE_PATH):
    self.db_path = db_path

  def _get_table_name(self, channel_id: str) -> str:
    return f"resources_{channel_id}"

  def _init_table(self, channel_id: str):
    table = self._get_table_name(channel_id)
    with sqlite3.connect(self.db_path) as conn:
      conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {table} (
          message_id INTEGER PRIMARY KEY,
          title TEXT NOT NULL,
          tags TEXT,
          telegraph_url TEXT,
          pan_url TEXT,
          description TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
      """)
      conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{channel_id}_title ON {table}(title)")
      conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{channel_id}_tags ON {table}(tags)")
      conn.commit()

  def save_resource(self, channel_id: str, resource: Resource) -> bool:
    self._init_table(channel_id)
    table = self._get_table_name(channel_id)
    with sqlite3.connect(self.db_path) as conn:
      conn.execute(f"""
        INSERT OR REPLACE INTO {table}
        (message_id, title, tags, telegraph_url, pan_url, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
      """, (
        resource.message_id,
        resource.title,
        resource.tags,
        resource.telegraph_url,
        resource.pan_url,
        resource.description,
        resource.created_at or time.strftime("%Y-%m-%d %H:%M:%S")
      ))
      conn.commit()
    return True

  def exists(self, channel_id: str, message_id: int) -> bool:
    self._init_table(channel_id)
    table = self._get_table_name(channel_id)
    with sqlite3.connect(self.db_path) as conn:
      cursor = conn.execute(f"SELECT 1 FROM {table} WHERE message_id = ?", (message_id,))
      return cursor.fetchone() is not None

  def get_unparsed(self, channel_id: str, limit: int = 100) -> list[Resource]:
    self._init_table(channel_id)
    table = self._get_table_name(channel_id)
    with sqlite3.connect(self.db_path) as conn:
      conn.row_factory = sqlite3.Row
      cursor = conn.execute(f"""
        SELECT * FROM {table}
        WHERE pan_url IS NULL OR pan_url = ''
        ORDER BY message_id DESC LIMIT ?
      """, (limit,))
      return [Resource(**dict(row)) for row in cursor.fetchall()]

  def search(self, keyword: str, channel_id: Optional[str] = None) -> list[tuple[str, Resource]]:
    """搜索资源（只搜索标题和标签）"""
    results = []
    channels = [channel_id] if channel_id else list(CHANNELS.keys())

    with sqlite3.connect(self.db_path) as conn:
      conn.row_factory = sqlite3.Row
      for ch_id in channels:
        table = self._get_table_name(ch_id)
        try:
          cursor = conn.execute(f"""
            SELECT * FROM {table}
            WHERE (title LIKE ? OR tags LIKE ?) AND pan_url != 'N/A'
            ORDER BY message_id DESC
          """, (f"%{keyword}%", f"%{keyword}%"))
          for row in cursor.fetchall():
            results.append((ch_id, Resource(**dict(row))))
        except sqlite3.OperationalError:
          continue

    return results

  def list_all(self, channel_id: str, limit: int = 50) -> list[Resource]:
    self._init_table(channel_id)
    table = self._get_table_name(channel_id)
    with sqlite3.connect(self.db_path) as conn:
      conn.row_factory = sqlite3.Row
      cursor = conn.execute(f"SELECT * FROM {table} ORDER BY message_id DESC LIMIT ?", (limit,))
      return [Resource(**dict(row)) for row in cursor.fetchall()]

  def get_latest_message_id(self, channel_id: str) -> int:
    self._init_table(channel_id)
    table = self._get_table_name(channel_id)
    with sqlite3.connect(self.db_path) as conn:
      cursor = conn.execute(f"SELECT MAX(message_id) FROM {table}")
      result = cursor.fetchone()[0]
      return result or 0

  def count(self, channel_id: str) -> int:
    self._init_table(channel_id)
    table = self._get_table_name(channel_id)
    with sqlite3.connect(self.db_path) as conn:
      cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
      return cursor.fetchone()[0]

  def count_unparsed(self, channel_id: str) -> int:
    self._init_table(channel_id)
    table = self._get_table_name(channel_id)
    with sqlite3.connect(self.db_path) as conn:
      cursor = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE pan_url IS NULL OR pan_url = ''")
      return cursor.fetchone()[0]
