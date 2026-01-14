# -*- coding: utf-8 -*-
"""用户认证模块"""

import os
import sqlite3
import hashlib
import hmac
import secrets
import time
import json
import base64
from functools import wraps
from pathlib import Path

from flask import Blueprint, request, jsonify, current_app

# 用户数据库路径
DATA_DIR = Path(__file__).parent.parent / "data"
USERS_DB = DATA_DIR / "users.db"

auth_bp = Blueprint('auth', __name__)


def hash_password(password: str, salt: str = None) -> tuple[str, str]:
  """使用 PBKDF2 哈希密码"""
  if salt is None:
    salt = secrets.token_hex(16)
  
  # 使用 PBKDF2 进行密码哈希
  dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
  password_hash = dk.hex()
  
  return password_hash, salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
  """验证密码"""
  calculated_hash, _ = hash_password(password, salt)
  return hmac.compare_digest(calculated_hash, stored_hash)


def create_token(user_id: int, username: str) -> str:
  """创建 JWT Token（简化版）"""
  expiration_hours = current_app.config.get('JWT_EXPIRATION_HOURS', 24)
  payload = {
    'user_id': user_id,
    'username': username,
    'exp': int(time.time()) + (expiration_hours * 3600)
  }
  
  # 编码 payload
  payload_bytes = json.dumps(payload).encode()
  payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode()
  
  # 签名
  secret = current_app.config['SECRET_KEY']
  signature = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
  
  return f"{payload_b64}.{signature}"


def verify_token(token: str) -> dict:
  """验证 Token"""
  try:
    parts = token.split('.')
    if len(parts) != 2:
      return None
    
    payload_b64, signature = parts
    
    # 验证签名
    secret = current_app.config['SECRET_KEY']
    expected_sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(signature, expected_sig):
      return None
    
    # 解码 payload
    payload_bytes = base64.urlsafe_b64decode(payload_b64)
    payload = json.loads(payload_bytes)
    
    # 检查过期
    if payload.get('exp', 0) < time.time():
      return None
    
    return payload
  except Exception:
    return None


def login_required(f):
  """登录验证装饰器"""
  @wraps(f)
  def decorated(*args, **kwargs):
    auth_header = request.headers.get('Authorization', '')
    
    if not auth_header.startswith('Bearer '):
      return jsonify({'error': '未授权访问'}), 401
    
    token = auth_header[7:]
    payload = verify_token(token)
    
    if not payload:
      return jsonify({'error': 'Token 无效或已过期'}), 401
    
    request.user = payload
    return f(*args, **kwargs)
  
  return decorated


def init_auth_db():
  """初始化用户数据库"""
  DATA_DIR.mkdir(exist_ok=True)
  
  with sqlite3.connect(USERS_DB) as conn:
    conn.execute("""
      CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_login TEXT
      )
    """)
    
    # 检查是否有用户，没有则创建默认管理员
    cursor = conn.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
      password_hash, salt = hash_password('admin123')
      conn.execute(
        "INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
        ('admin', password_hash, salt)
      )
    
    conn.commit()


@auth_bp.route('/login', methods=['POST'])
def login():
  """用户登录"""
  data = request.get_json()
  
  if not data:
    return jsonify({'error': '请提供登录信息'}), 400
  
  username = data.get('username', '').strip()
  password = data.get('password', '')
  
  if not username or not password:
    return jsonify({'error': '用户名和密码不能为空'}), 400
  
  # 查询用户
  with sqlite3.connect(USERS_DB) as conn:
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
      "SELECT * FROM users WHERE username = ?",
      (username,)
    )
    user = cursor.fetchone()
    
    if not user:
      return jsonify({'error': '用户名或密码错误'}), 401
    
    if not verify_password(password, user['password_hash'], user['salt']):
      return jsonify({'error': '用户名或密码错误'}), 401
    
    # 更新最后登录时间
    conn.execute(
      "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
      (user['id'],)
    )
    conn.commit()
    
    # 生成 Token
    token = create_token(user['id'], user['username'])
    
    return jsonify({
      'token': token,
      'username': user['username'],
      'message': '登录成功'
    })


@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
  """修改密码"""
  data = request.get_json()
  
  old_password = data.get('old_password', '')
  new_password = data.get('new_password', '')
  
  if not old_password or not new_password:
    return jsonify({'error': '请提供旧密码和新密码'}), 400
  
  if len(new_password) < 6:
    return jsonify({'error': '新密码至少6位'}), 400
  
  user_id = request.user['user_id']
  
  with sqlite3.connect(USERS_DB) as conn:
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not verify_password(old_password, user['password_hash'], user['salt']):
      return jsonify({'error': '旧密码错误'}), 401
    
    # 更新密码
    new_hash, new_salt = hash_password(new_password)
    conn.execute(
      "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
      (new_hash, new_salt, user_id)
    )
    conn.commit()
    
    return jsonify({'message': '密码修改成功'})


@auth_bp.route('/me', methods=['GET'])
@login_required
def get_current_user():
  """获取当前用户信息"""
  return jsonify({
    'user_id': request.user['user_id'],
    'username': request.user['username']
  })
