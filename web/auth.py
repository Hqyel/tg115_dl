# -*- coding: utf-8 -*-
"""用户认证模块"""

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

DATA_DIR = Path(__file__).parent.parent / "data"
USERS_DB = DATA_DIR / "users.db"

auth_bp = Blueprint('auth', __name__)


def hash_password(password: str, salt: str = None) -> tuple[str, str]:
  if salt is None:
    salt = secrets.token_hex(16)
  dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
  return dk.hex(), salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
  calculated_hash, _ = hash_password(password, salt)
  return hmac.compare_digest(calculated_hash, stored_hash)


def create_token(user_id: int, username: str) -> str:
  expiration_hours = current_app.config.get('JWT_EXPIRATION_HOURS', 24)
  payload = {
    'user_id': user_id,
    'username': username,
    'exp': int(time.time()) + (expiration_hours * 3600)
  }
  payload_bytes = json.dumps(payload).encode()
  payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode()
  secret = current_app.config['SECRET_KEY']
  signature = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
  return f"{payload_b64}.{signature}"


def verify_token(token: str) -> dict:
  try:
    parts = token.split('.')
    if len(parts) != 2:
      return None
    payload_b64, signature = parts
    secret = current_app.config['SECRET_KEY']
    expected_sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_sig):
      return None
    payload_bytes = base64.urlsafe_b64decode(payload_b64)
    payload = json.loads(payload_bytes)
    if payload.get('exp', 0) < time.time():
      return None
    return payload
  except Exception:
    return None


def login_required(f):
  @wraps(f)
  def decorated(*args, **kwargs):
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
      return jsonify({'error': '未授权'}), 401
    token = auth_header[7:]
    payload = verify_token(token)
    if not payload:
      return jsonify({'error': 'Token 无效'}), 401
    request.user = payload
    return f(*args, **kwargs)
  return decorated


def init_auth_db():
  DATA_DIR.mkdir(exist_ok=True)
  with sqlite3.connect(USERS_DB) as conn:
    conn.execute("""
      CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
      )
    """)
    cursor = conn.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
      password_hash, salt = hash_password('admin123')
      conn.execute("INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
                   ('admin', password_hash, salt))
    conn.commit()


@auth_bp.route('/login', methods=['POST'])
def login():
  data = request.get_json()
  if not data:
    return jsonify({'error': '请提供登录信息'}), 400
  username = data.get('username', '').strip()
  password = data.get('password', '')
  if not username or not password:
    return jsonify({'error': '用户名和密码不能为空'}), 400

  with sqlite3.connect(USERS_DB) as conn:
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    if not user or not verify_password(password, user['password_hash'], user['salt']):
      return jsonify({'error': '用户名或密码错误'}), 401
    token = create_token(user['id'], user['username'])
    return jsonify({'token': token, 'username': user['username']})


@auth_bp.route('/me', methods=['GET'])
@login_required
def get_me():
  return jsonify({'username': request.user['username']})
