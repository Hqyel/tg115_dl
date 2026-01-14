# -*- coding: utf-8 -*-
"""数据模型"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Resource:
  """资源数据模型"""
  message_id: int
  title: str
  tags: str
  telegraph_url: str = ""
  pan_url: str = ""
  description: str = ""
  created_at: str = ""


@dataclass
class CrawlState:
  """爬取状态（用于断点续传）"""
  channel_id: str = ""
  last_before_id: Optional[int] = None
  total_crawled: int = 0
  mode: str = ""

  def to_dict(self) -> dict:
    return {
      "channel_id": self.channel_id,
      "last_before_id": self.last_before_id,
      "total_crawled": self.total_crawled,
      "mode": self.mode,
    }

  @classmethod
  def from_dict(cls, data: dict) -> "CrawlState":
    return cls(
      channel_id=data.get("channel_id", ""),
      last_before_id=data.get("last_before_id"),
      total_crawled=data.get("total_crawled", 0),
      mode=data.get("mode", ""),
    )
