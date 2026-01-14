# Telegram 公开频道资源爬虫

无需 Telegram API，直接爬取公开频道网页版，解析资源信息并提取 115 网盘链接。

## 功能特性

- ✅ 多频道支持（每频道独立数据库表）
- ✅ 全量爬取 / 增量爬取 / 断点续传
- ✅ 关键词搜索（支持跨频道搜索）
- ✅ 自动过滤，只保存 115cdn.com 链接

## 支持的频道

| 频道ID | 名称 | 解析模式 |
|--------|------|----------|
| lsp115 | 115网盘资源分享频道 | telegraph（需二次解析） |
| vip115hot | 懒狗集中营 | inline（直接提取） |
| qukanmovie | 115影视资源分享 | button（从按钮提取） |

## 安装

```bash
pip install -r requirements.txt
```

## 使用方法

```bash
python main.py channels                        # 列出可用频道
python main.py crawl -c lsp115 --all           # 全量爬取
python main.py crawl -c lsp115 --incremental   # 增量爬取
python main.py crawl -c lsp115 --resume        # 断点续传
python main.py parse -c lsp115                 # 解析链接
python main.py search "仙逆"                   # 搜索
python main.py get "仙逆"                      # 获取链接
python main.py list -c vip115hot               # 列出资源
python main.py status                          # 查看状态
python main.py sync                            # 同步所有频道（增量）
python main.py sync --full                     # 同步所有频道（全量）
```

## 项目结构

```
tg_dl/
├── main.py                   # 入口文件
├── requirements.txt
├── README.md
├── .gitignore
├── src/
│   ├── core/                 # 核心逻辑
│   │   ├── crawler.py
│   │   ├── parser.py
│   │   └── database.py
│   ├── channels/             # 频道配置
│   │   └── config.py
│   ├── models/               # 数据模型
│   │   └── resource.py
│   └── cli/                  # 命令行
│       └── commands.py
└── data/                     # 数据文件（自动生成）
```

## 添加新频道

编辑 `src/channels/config.py`，在 `CHANNELS` 字典中添加：

```python
"new_channel": {
  "url": "https://t.me/s/频道用户名",
  "name": "频道显示名称",
  "parse_mode": "inline",  # 或 "telegraph" / "button"
},
```

## Web 管理界面

### 安装依赖

```bash
pip install flask flask-cors apscheduler
```

### 启动 Web 服务

```bash
python run_web.py
# 或指定端口
python run_web.py --port 8080
```

访问 http://localhost:5000，默认账号：`admin` / `admin123`（请及时修改密码）

### 功能

- 📊 仪表盘：查看资源统计和同步状态
- 🔍 影视搜索：关键词搜索，一键复制链接
- 📁 数据库：分页浏览所有资源
- ⚙️ 同步管理：手动同步、定时任务管理
