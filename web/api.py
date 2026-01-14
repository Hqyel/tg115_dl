# -*- coding: utf-8 -*-
"""API 路由"""

import threading
from flask import Blueprint, request, jsonify

from .auth import login_required

from src.channels.config import CHANNELS
from src.core.database import Database, StateManager
from src.core.crawler import ChannelCrawler
from src.core.parser import TelegraphParser

api_bp = Blueprint('api', __name__)

sync_status = {'running': False, 'channel': None, 'message': ''}


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
    'total_pages': (total + per_page - 1) // per_page,
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
  channels = [{'id': ch_id, 'name': config['name'], 'parse_mode': config['parse_mode']}
              for ch_id, config in CHANNELS.items()]
  return jsonify({'channels': channels})
