# -*- coding: utf-8 -*-
"""定时任务调度器"""

import json
from pathlib import Path
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.channels.config import CHANNELS
from src.core.database import Database, StateManager
from src.core.crawler import ChannelCrawler
from src.core.parser import TelegraphParser

# 任务配置文件
DATA_DIR = Path(__file__).parent.parent / "data"
TASKS_FILE = DATA_DIR / "scheduled_tasks.json"

# 全局调度器
_scheduler = None


def get_scheduler():
  """获取调度器实例"""
  global _scheduler
  if _scheduler is None:
    _scheduler = BackgroundScheduler()
    _scheduler.start()
    # 加载已保存的任务
    load_saved_tasks()
  return _scheduler


def sync_channel(channel_id: str, mode: str):
  """同步指定频道"""
  print(f"[定时任务] 开始同步 {channel_id} ({mode})")
  
  try:
    db = Database()
    state_manager = StateManager()
    crawler = ChannelCrawler(channel_id)
    
    if mode == 'full':
      crawler.crawl_all(db, state_manager)
    else:
      crawler.crawl_incremental(db)
    
    # 如果是 telegraph 模式，解析链接
    if CHANNELS[channel_id]['parse_mode'] == 'telegraph':
      parser = TelegraphParser()
      unparsed = db.count_unparsed(channel_id)
      if unparsed > 0:
        parser.parse_batch(db, channel_id, limit=unparsed)
    
    print(f"[定时任务] {channel_id} 同步完成")
  except Exception as e:
    print(f"[定时任务] {channel_id} 同步失败: {e}")


def sync_all_channels(mode: str):
  """同步所有频道"""
  print(f"[定时任务] 开始同步所有频道 ({mode})")
  for ch_id in CHANNELS.keys():
    sync_channel(ch_id, mode)
  print(f"[定时任务] 所有频道同步完成")


def add_job(channel_id: str, mode: str, interval_hours: int) -> str:
  """添加定时任务"""
  scheduler = get_scheduler()
  
  job_id = f"sync_{channel_id}_{mode}"
  
  # 检查是否已存在
  if scheduler.get_job(job_id):
    scheduler.remove_job(job_id)
  
  if channel_id == 'all':
    func = sync_all_channels
    args = (mode,)
  else:
    func = sync_channel
    args = (channel_id, mode)
  
  scheduler.add_job(
    func,
    trigger=IntervalTrigger(hours=interval_hours),
    id=job_id,
    args=args,
    name=f"同步 {channel_id} ({mode})",
    replace_existing=True
  )
  
  # 保存任务配置
  save_tasks()
  
  return job_id


def remove_job(job_id: str):
  """删除定时任务"""
  scheduler = get_scheduler()
  
  job = scheduler.get_job(job_id)
  if not job:
    raise ValueError(f"任务不存在: {job_id}")
  
  scheduler.remove_job(job_id)
  save_tasks()


def get_jobs() -> list:
  """获取所有定时任务"""
  scheduler = get_scheduler()
  
  jobs = []
  for job in scheduler.get_jobs():
    next_run = job.next_run_time
    jobs.append({
      'id': job.id,
      'name': job.name,
      'next_run': next_run.isoformat() if next_run else None,
      'trigger': str(job.trigger)
    })
  
  return jobs


def save_tasks():
  """保存任务配置到文件"""
  scheduler = get_scheduler()
  
  DATA_DIR.mkdir(exist_ok=True)
  
  tasks = []
  for job in scheduler.get_jobs():
    # 解析任务 ID 获取配置
    parts = job.id.split('_')
    if len(parts) >= 3 and parts[0] == 'sync':
      channel_id = parts[1]
      mode = parts[2]
      
      # 获取间隔时间
      interval_hours = 6  # 默认值
      if hasattr(job.trigger, 'interval'):
        interval_hours = job.trigger.interval.total_seconds() / 3600
      
      tasks.append({
        'channel': channel_id,
        'mode': mode,
        'interval_hours': interval_hours
      })
  
  with open(TASKS_FILE, 'w', encoding='utf-8') as f:
    json.dump(tasks, f, ensure_ascii=False, indent=2)


def load_saved_tasks():
  """从文件加载已保存的任务"""
  if not TASKS_FILE.exists():
    return
  
  try:
    with open(TASKS_FILE, 'r', encoding='utf-8') as f:
      tasks = json.load(f)
    
    for task in tasks:
      try:
        add_job(
          task['channel'],
          task['mode'],
          int(task['interval_hours'])
        )
      except Exception as e:
        print(f"加载任务失败: {e}")
  except Exception as e:
    print(f"读取任务配置失败: {e}")
