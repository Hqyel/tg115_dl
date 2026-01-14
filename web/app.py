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

  app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'tg-spider-secret-2024')
  app.config['JWT_EXPIRATION_HOURS'] = 24

  CORS(app, resources={r"/api/*": {"origins": "*"}})

  init_auth_db()

  app.register_blueprint(auth_bp, url_prefix='/api/auth')
  app.register_blueprint(api_bp, url_prefix='/api')

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
  print(f"\n{'='*50}")
  print(f"  TG 资源爬虫 Web 服务")
  print(f"{'='*50}")
  default_user = os.environ.get('TG_WEB_USER', 'admin')
  print(f"  地址: http://{host}:{port}")
  print(f"  账号: {default_user} (密码: {os.environ.get('TG_WEB_PASSWORD', 'admin123')})")
  print(f"{'='*50}\n")
  app.run(host=host, port=port, debug=debug, threaded=True)
