# -*- coding: utf-8 -*-
"""日志管理模块"""

import json
from datetime import datetime
from pathlib import Path
from threading import Lock

DATA_DIR = Path(__file__).parent.parent / "data"
LOGS_FILE = DATA_DIR / "sync_logs.json"
MAX_LOGS = 100

_lock = Lock()


def add_log(log_type: str, channel: str, message: str, status: str = "info"):
  """添加日志记录"""
  DATA_DIR.mkdir(exist_ok=True)
  
  log_entry = {
    "id": int(datetime.now().timestamp() * 1000),
    "timestamp": datetime.now().isoformat(),
    "type": log_type,  # sync, scheduled, parse
    "channel": channel,
    "message": message,
    "status": status  # info, success, error, warning
  }
  
  with _lock:
    logs = get_logs()
    logs.insert(0, log_entry)
    logs = logs[:MAX_LOGS]  # 只保留最近 100 条
    
    with open(LOGS_FILE, 'w', encoding='utf-8') as f:
      json.dump(logs, f, ensure_ascii=False, indent=2)
  
  return log_entry


def get_logs(limit: int = 50, log_type: str = None) -> list:
  """获取日志列表"""
  if not LOGS_FILE.exists():
    return []
  
  try:
    with open(LOGS_FILE, 'r', encoding='utf-8') as f:
      logs = json.load(f)
  except:
    return []
  
  if log_type:
    logs = [l for l in logs if l.get('type') == log_type]
  
  return logs[:limit]


def clear_logs():
  """清空日志"""
  with _lock:
    if LOGS_FILE.exists():
      LOGS_FILE.unlink()
