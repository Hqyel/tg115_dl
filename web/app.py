# -*- coding: utf-8 -*-
"""Flask 应用"""

import os
from flask import Flask, send_from_directory
from flask_cors import CORS

from .auth import auth_bp, init_auth_db
from .api import api_bp


def create_app():
  """创建 Flask 应用"""
  app = Flask(__name__, static_folder='static')
  
  # 配置
  app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'tg-spider-secret-key-change-in-production')
  app.config['JWT_EXPIRATION_HOURS'] = 24
  
  # CORS 配置（生产环境应限制）
  CORS(app, resources={r"/api/*": {"origins": "*"}})
  
  # 初始化用户数据库
  init_auth_db()
  
  # 注册蓝图
  app.register_blueprint(auth_bp, url_prefix='/api/auth')
  app.register_blueprint(api_bp, url_prefix='/api')
  
  # 前端静态文件
  @app.route('/')
  @app.route('/<path:path>')
  def serve_frontend(path='index.html'):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
      return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')
  
  return app


def run_server(host='0.0.0.0', port=5000, debug=False):
  """启动服务器"""
  app = create_app()
  print(f"Web 服务启动: http://{host}:{port}")
  print("默认账户: admin / admin123 (请及时修改密码)")
  app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
  run_server(debug=True)
