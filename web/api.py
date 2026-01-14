# -*- coding: utf-8 -*-
"""API 路由"""

import threading
from flask import Blueprint, request, jsonify

from .auth import login_required
from .scheduler import get_scheduler, get_jobs, add_job, remove_job

from src.channels.config import CHANNELS
from src.core.database import Database, StateManager
from src.core.crawler import ChannelCrawler
from src.core.parser import TelegraphParser

api_bp = Blueprint('api', __name__)

# 同步状态
sync_status = {
  'running': False,
  'channel': None,
  'message': '',
  'progress': 0
}


@api_bp.route('/dashboard', methods=['GET'])
@login_required
def get_dashboard():
  """获取仪表盘数据"""
  db = Database()
  state_manager = StateManager()
  
  channels_data = []
  total_resources = 0
  total_parsed = 0
  
  for ch_id, config in CHANNELS.items():
    count = db.count(ch_id)
    unparsed = db.count_unparsed(ch_id)
    latest_id = db.get_latest_message_id(ch_id)
    
    channels_data.append({
      'id': ch_id,
      'name': config['name'],
      'url': config['url'],
      'parse_mode': config['parse_mode'],
      'total': count,
      'parsed': count - unparsed,
      'unparsed': unparsed,
      'latest_id': latest_id
    })
    
    total_resources += count
    total_parsed += count - unparsed
  
  # 获取同步状态
  state = state_manager.load()
  pending_task = None
  if state:
    pending_task = {
      'channel': state.channel_id,
      'mode': state.mode,
      'crawled': state.total_crawled
    }
  
  return jsonify({
    'channels': channels_data,
    'total_resources': total_resources,
    'total_parsed': total_parsed,
    'pending_task': pending_task,
    'sync_status': sync_status
  })


@api_bp.route('/search', methods=['GET'])
@login_required
def search_resources():
  """搜索资源"""
  keyword = request.args.get('q', '').strip()
  channel_id = request.args.get('channel', None)
  
  if not keyword:
    return jsonify({'error': '请输入搜索关键词'}), 400
  
  if channel_id and channel_id not in CHANNELS:
    return jsonify({'error': f'未知频道: {channel_id}'}), 400
  
  db = Database()
  results = db.search(keyword, channel_id)
  
  resources = []
  for ch_id, r in results:
    resources.append({
      'channel_id': ch_id,
      'channel_name': CHANNELS[ch_id]['name'],
      'message_id': r.message_id,
      'title': r.title,
      'tags': r.tags,
      'pan_url': r.pan_url,
      'telegraph_url': r.telegraph_url,
      'description': r.description
    })
  
  return jsonify({
    'keyword': keyword,
    'count': len(resources),
    'resources': resources
  })


@api_bp.route('/resources', methods=['GET'])
@login_required
def list_resources():
  """获取资源列表"""
  channel_id = request.args.get('channel', 'lsp115')
  page = request.args.get('page', 1, type=int)
  per_page = request.args.get('per_page', 20, type=int)
  
  if channel_id not in CHANNELS:
    return jsonify({'error': f'未知频道: {channel_id}'}), 400
  
  per_page = min(per_page, 100)  # 限制每页最大数量
  
  db = Database()
  total = db.count(channel_id)
  resources_list = db.list_all(channel_id, limit=per_page * page)
  
  # 分页处理
  start = (page - 1) * per_page
  end = start + per_page
  page_resources = resources_list[start:end] if start < len(resources_list) else []
  
  resources = []
  for r in page_resources:
    resources.append({
      'message_id': r.message_id,
      'title': r.title,
      'tags': r.tags,
      'pan_url': r.pan_url,
      'telegraph_url': r.telegraph_url,
      'description': r.description,
      'created_at': r.created_at
    })
  
  return jsonify({
    'channel_id': channel_id,
    'channel_name': CHANNELS[channel_id]['name'],
    'page': page,
    'per_page': per_page,
    'total': total,
    'total_pages': (total + per_page - 1) // per_page,
    'resources': resources
  })


def do_sync(channel_id: str, mode: str):
  """执行同步任务（在后台线程）"""
  global sync_status
  
  try:
    sync_status['running'] = True
    sync_status['channel'] = channel_id
    sync_status['message'] = f'正在同步 {CHANNELS[channel_id]["name"]}...'
    
    db = Database()
    state_manager = StateManager()
    crawler = ChannelCrawler(channel_id)
    
    if mode == 'full':
      crawler.crawl_all(db, state_manager)
    else:
      crawler.crawl_incremental(db)
    
    # 如果是 telegraph 模式，解析链接
    if CHANNELS[channel_id]['parse_mode'] == 'telegraph':
      sync_status['message'] = f'正在解析 {CHANNELS[channel_id]["name"]} 的链接...'
      parser = TelegraphParser()
      unparsed = db.count_unparsed(channel_id)
      if unparsed > 0:
        parser.parse_batch(db, channel_id, limit=unparsed)
    
    sync_status['message'] = f'{CHANNELS[channel_id]["name"]} 同步完成'
  except Exception as e:
    sync_status['message'] = f'同步失败: {str(e)}'
  finally:
    sync_status['running'] = False
    sync_status['channel'] = None


@api_bp.route('/sync/full', methods=['POST'])
@login_required
def sync_full():
  """全量同步"""
  if sync_status['running']:
    return jsonify({'error': '已有同步任务在运行'}), 400
  
  data = request.get_json() or {}
  channel_id = data.get('channel', 'lsp115')
  
  if channel_id not in CHANNELS:
    return jsonify({'error': f'未知频道: {channel_id}'}), 400
  
  # 在后台线程执行
  thread = threading.Thread(target=do_sync, args=(channel_id, 'full'))
  thread.daemon = True
  thread.start()
  
  return jsonify({
    'message': f'已启动全量同步: {CHANNELS[channel_id]["name"]}',
    'channel': channel_id
  })


@api_bp.route('/sync/incremental', methods=['POST'])
@login_required
def sync_incremental():
  """增量同步"""
  if sync_status['running']:
    return jsonify({'error': '已有同步任务在运行'}), 400
  
  data = request.get_json() or {}
  channel_id = data.get('channel', 'lsp115')
  
  if channel_id not in CHANNELS:
    return jsonify({'error': f'未知频道: {channel_id}'}), 400
  
  thread = threading.Thread(target=do_sync, args=(channel_id, 'incremental'))
  thread.daemon = True
  thread.start()
  
  return jsonify({
    'message': f'已启动增量同步: {CHANNELS[channel_id]["name"]}',
    'channel': channel_id
  })


@api_bp.route('/sync/all', methods=['POST'])
@login_required
def sync_all():
  """同步所有频道"""
  if sync_status['running']:
    return jsonify({'error': '已有同步任务在运行'}), 400
  
  data = request.get_json() or {}
  mode = 'full' if data.get('full', False) else 'incremental'
  
  def sync_all_channels():
    global sync_status
    sync_status['running'] = True
    
    for ch_id in CHANNELS.keys():
      if not sync_status['running']:
        break
      do_sync(ch_id, mode)
    
    sync_status['running'] = False
    sync_status['message'] = '所有频道同步完成'
  
  thread = threading.Thread(target=sync_all_channels)
  thread.daemon = True
  thread.start()
  
  return jsonify({
    'message': f'已启动{" 全量 " if mode == "full" else " 增量 "}同步所有频道'
  })


@api_bp.route('/sync/status', methods=['GET'])
@login_required
def get_sync_status():
  """获取同步状态"""
  return jsonify(sync_status)


@api_bp.route('/tasks', methods=['GET'])
@login_required
def list_tasks():
  """获取定时任务列表"""
  jobs = get_jobs()
  return jsonify({'tasks': jobs})


@api_bp.route('/tasks', methods=['POST'])
@login_required
def create_task():
  """创建定时任务"""
  data = request.get_json()
  
  if not data:
    return jsonify({'error': '请提供任务配置'}), 400
  
  channel_id = data.get('channel', 'all')
  mode = data.get('mode', 'incremental')
  interval_hours = data.get('interval_hours', 6)
  
  if channel_id != 'all' and channel_id not in CHANNELS:
    return jsonify({'error': f'未知频道: {channel_id}'}), 400
  
  try:
    job_id = add_job(channel_id, mode, interval_hours)
    return jsonify({
      'message': '定时任务已创建',
      'job_id': job_id
    })
  except Exception as e:
    return jsonify({'error': str(e)}), 400


@api_bp.route('/tasks/<job_id>', methods=['DELETE'])
@login_required
def delete_task(job_id):
  """删除定时任务"""
  try:
    remove_job(job_id)
    return jsonify({'message': '任务已删除'})
  except Exception as e:
    return jsonify({'error': str(e)}), 400


@api_bp.route('/channels', methods=['GET'])
@login_required
def list_channels():
  """获取频道列表"""
  channels = []
  for ch_id, config in CHANNELS.items():
    channels.append({
      'id': ch_id,
      'name': config['name'],
      'url': config['url'],
      'parse_mode': config['parse_mode']
    })
  
  return jsonify({'channels': channels})
