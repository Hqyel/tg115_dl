# -*- coding: utf-8 -*-
"""API 路由"""

import json
import threading
from pathlib import Path
from flask import Blueprint, request, jsonify

from .auth import login_required

from src.channels.config import CHANNELS
from src.core.database import Database, StateManager
from src.core.crawler import ChannelCrawler
from src.core.parser import TelegraphParser

api_bp = Blueprint('api', __name__)

sync_status = {'running': False, 'channel': None, 'message': ''}

# 定时任务配置
DATA_DIR = Path(__file__).parent.parent / "data"
TASKS_FILE = DATA_DIR / "scheduled_tasks.json"
_scheduler = None
_scheduler_started = False


def get_scheduler():
  global _scheduler, _scheduler_started
  if _scheduler is None:
    try:
      from apscheduler.schedulers.background import BackgroundScheduler
      from apscheduler.triggers.interval import IntervalTrigger
      _scheduler = BackgroundScheduler()
    except ImportError:
      return None
  if not _scheduler_started:
    try:
      _scheduler.start()
      _scheduler_started = True
      load_saved_tasks()
    except:
      pass
  return _scheduler


def sync_channel_task(channel_id: str, mode: str):
  """定时任务执行的同步函数"""
  print(f"[定时任务] 同步 {channel_id} ({mode})")
  try:
    db = Database()
    state_manager = StateManager()
    crawler = ChannelCrawler(channel_id)
    if mode == 'full':
      crawler.crawl_all(db, state_manager)
    else:
      crawler.crawl_incremental(db)
    if CHANNELS[channel_id]['parse_mode'] == 'telegraph':
      parser = TelegraphParser()
      unparsed = db.count_unparsed(channel_id)
      if unparsed > 0:
        parser.parse_batch(db, channel_id, limit=unparsed)
  except Exception as e:
    print(f"[定时任务] 同步失败: {e}")


def sync_all_task(mode: str):
  """同步所有频道"""
  for ch_id in CHANNELS.keys():
    sync_channel_task(ch_id, mode)


def save_tasks():
  """保存任务到文件"""
  scheduler = get_scheduler()
  if not scheduler:
    return
  DATA_DIR.mkdir(exist_ok=True)
  tasks = []
  for job in scheduler.get_jobs():
    if job.id.startswith('sync_'):
      parts = job.id.split('_')
      if len(parts) >= 3:
        interval = 6
        if hasattr(job.trigger, 'interval'):
          interval = int(job.trigger.interval.total_seconds() / 3600)
        tasks.append({'channel': parts[1], 'mode': parts[2], 'interval_hours': interval})
  with open(TASKS_FILE, 'w', encoding='utf-8') as f:
    json.dump(tasks, f, ensure_ascii=False, indent=2)


def load_saved_tasks():
  """加载已保存的任务"""
  if not TASKS_FILE.exists():
    return
  try:
    with open(TASKS_FILE, 'r', encoding='utf-8') as f:
      tasks = json.load(f)
    for task in tasks:
      add_scheduled_job(task['channel'], task['mode'], task['interval_hours'])
  except Exception as e:
    print(f"加载任务失败: {e}")


def add_scheduled_job(channel_id: str, mode: str, interval_hours: int) -> str:
  """添加定时任务"""
  scheduler = get_scheduler()
  if not scheduler:
    raise Exception("APScheduler 未安装")

  from apscheduler.triggers.interval import IntervalTrigger

  job_id = f"sync_{channel_id}_{mode}"
  if scheduler.get_job(job_id):
    scheduler.remove_job(job_id)

  if channel_id == 'all':
    func = sync_all_task
    args = (mode,)
    name = f"同步全部频道 ({mode})"
  else:
    func = sync_channel_task
    args = (channel_id, mode)
    name = f"同步 {CHANNELS.get(channel_id, {}).get('name', channel_id)} ({mode})"

  scheduler.add_job(func, trigger=IntervalTrigger(hours=interval_hours),
                    id=job_id, args=args, name=name, replace_existing=True)
  save_tasks()
  return job_id


@api_bp.route('/dashboard', methods=['GET'])
@login_required
def get_dashboard():
  db = Database()
  channels_data = []
  total_resources = 0
  total_parsed = 0

  for ch_id, config in CHANNELS.items():
    count = db.count(ch_id)
    unparsed = db.count_unparsed(ch_id)
    channels_data.append({
      'id': ch_id,
      'name': config['name'],
      'parse_mode': config['parse_mode'],
      'total': count,
      'parsed': count - unparsed,
      'unparsed': unparsed
    })
    total_resources += count
    total_parsed += count - unparsed

  return jsonify({
    'channels': channels_data,
    'total_resources': total_resources,
    'total_parsed': total_parsed,
    'sync_status': sync_status
  })


@api_bp.route('/search', methods=['GET'])
@login_required
def search():
  keyword = request.args.get('q', '').strip()
  channel_id = request.args.get('channel', None)

  if not keyword:
    return jsonify({'error': '请输入关键词'}), 400

  db = Database()
  results = db.search(keyword, channel_id if channel_id else None)

  resources = [{
    'channel_id': ch_id,
    'channel_name': CHANNELS[ch_id]['name'],
    'channel_username': CHANNELS[ch_id]['url'].split('/')[-1],
    'message_id': r.message_id,
    'title': r.title,
    'tags': r.tags,
    'pan_url': r.pan_url,
    'description': r.description
  } for ch_id, r in results]

  return jsonify({'count': len(resources), 'resources': resources})


@api_bp.route('/resources', methods=['GET'])
@login_required
def list_resources():
  channel_id = request.args.get('channel', 'lsp115')
  page = request.args.get('page', 1, type=int)
  per_page = min(request.args.get('per_page', 20, type=int), 100)

  if channel_id not in CHANNELS:
    return jsonify({'error': '未知频道'}), 400

  db = Database()
  total = db.count(channel_id)
  all_resources = db.list_all(channel_id, limit=per_page * page)

  start = (page - 1) * per_page
  page_resources = all_resources[start:start + per_page]

  resources = [{
    'message_id': r.message_id,
    'title': r.title,
    'tags': r.tags,
    'pan_url': r.pan_url,
    'created_at': r.created_at
  } for r in page_resources]

  return jsonify({
    'channel': channel_id,
    'page': page,
    'per_page': per_page,
    'total': total,
    'total_pages': max(1, (total + per_page - 1) // per_page),
    'resources': resources
  })


def do_sync(channel_id: str, mode: str):
  global sync_status
  try:
    sync_status = {'running': True, 'channel': channel_id, 'message': f'正在同步 {CHANNELS[channel_id]["name"]}...'}
    db = Database()
    state_manager = StateManager()
    crawler = ChannelCrawler(channel_id)

    if mode == 'full':
      crawler.crawl_all(db, state_manager)
    else:
      crawler.crawl_incremental(db)

    if CHANNELS[channel_id]['parse_mode'] == 'telegraph':
      sync_status['message'] = f'正在解析链接...'
      parser = TelegraphParser()
      unparsed = db.count_unparsed(channel_id)
      if unparsed > 0:
        parser.parse_batch(db, channel_id, limit=unparsed)

    sync_status = {'running': False, 'channel': None, 'message': f'{CHANNELS[channel_id]["name"]} 同步完成'}
  except Exception as e:
    sync_status = {'running': False, 'channel': None, 'message': f'同步失败: {str(e)}'}


@api_bp.route('/sync', methods=['POST'])
@login_required
def sync():
  if sync_status['running']:
    return jsonify({'error': '已有同步任务在运行'}), 400

  data = request.get_json() or {}
  channel_id = data.get('channel', 'lsp115')
  mode = data.get('mode', 'incremental')

  if channel_id not in CHANNELS:
    return jsonify({'error': '未知频道'}), 400

  thread = threading.Thread(target=do_sync, args=(channel_id, mode))
  thread.daemon = True
  thread.start()

  return jsonify({'message': f'已启动同步: {CHANNELS[channel_id]["name"]}'})


@api_bp.route('/sync/all', methods=['POST'])
@login_required
def sync_all():
  if sync_status['running']:
    return jsonify({'error': '已有同步任务在运行'}), 400

  data = request.get_json() or {}
  mode = 'full' if data.get('full') else 'incremental'

  def sync_all_channels():
    global sync_status
    for ch_id in CHANNELS.keys():
      do_sync(ch_id, mode)
    sync_status = {'running': False, 'channel': None, 'message': '所有频道同步完成'}

  thread = threading.Thread(target=sync_all_channels)
  thread.daemon = True
  thread.start()

  return jsonify({'message': '已启动同步所有频道'})


@api_bp.route('/sync/status', methods=['GET'])
@login_required
def get_sync_status():
  return jsonify(sync_status)


@api_bp.route('/channels', methods=['GET'])
@login_required
def get_channels():
  channels = [{'id': ch_id, 'name': config['name'], 'parse_mode': config['parse_mode'], 'username': config['url'].split('/')[-1]}
              for ch_id, config in CHANNELS.items()]
  return jsonify({'channels': channels})


@api_bp.route('/tasks', methods=['GET'])
@login_required
def list_tasks():
  scheduler = get_scheduler()
  if not scheduler:
    return jsonify({'tasks': []})

  jobs = []
  for job in scheduler.get_jobs():
    if job.id.startswith('sync_'):
      next_run = job.next_run_time
      jobs.append({
        'id': job.id,
        'name': job.name,
        'next_run': next_run.isoformat() if next_run else None
      })
  return jsonify({'tasks': jobs})


@api_bp.route('/tasks', methods=['POST'])
@login_required
def create_task():
  data = request.get_json()
  if not data:
    return jsonify({'error': '请提供任务配置'}), 400

  channel_id = data.get('channel', 'all')
  mode = data.get('mode', 'incremental')
  interval_hours = data.get('interval_hours', 6)

  if channel_id != 'all' and channel_id not in CHANNELS:
    return jsonify({'error': f'未知频道: {channel_id}'}), 400

  try:
    job_id = add_scheduled_job(channel_id, mode, interval_hours)
    return jsonify({'message': '任务已创建', 'job_id': job_id})
  except Exception as e:
    return jsonify({'error': str(e)}), 400


@api_bp.route('/tasks/<job_id>', methods=['DELETE'])
@login_required
def delete_task(job_id):
  scheduler = get_scheduler()
  if not scheduler:
    return jsonify({'error': 'APScheduler 未安装'}), 400

  job = scheduler.get_job(job_id)
  if not job:
    return jsonify({'error': '任务不存在'}), 404

  scheduler.remove_job(job_id)
  save_tasks()
  return jsonify({'message': '任务已删除'})
