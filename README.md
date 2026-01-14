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

### 查看可用频道

```bash
python tg_spider.py channels
```

### 爬取频道

```bash
# 全量爬取（支持 Ctrl+C 中断保存进度）
python tg_spider.py crawl -c lsp115 --all

# 限量爬取（最近 N 条）
python tg_spider.py crawl -c vip115hot --limit 100

# 增量爬取（只爬新消息，适合定时任务）
python tg_spider.py crawl -c lsp115 --incremental

# 断点续传（从上次中断处继续）
python tg_spider.py crawl -c lsp115 --resume

# 爬取后自动解析网盘链接（仅 telegraph 模式需要）
python tg_spider.py crawl -c lsp115 --limit 50 --parse
```

### 解析网盘链接

仅 `lsp115` 频道需要二次解析：

```bash
# 解析所有未解析的资源
python tg_spider.py parse -c lsp115

# 限制解析数量
python tg_spider.py parse -c lsp115 --limit 50
```

### 搜索资源

```bash
# 搜索指定频道
python tg_spider.py search "仙逆" -c lsp115

# 搜索所有频道
python tg_spider.py search "仙逆"
```

### 获取网盘链接

```bash
# 搜索并获取链接（支持交互选择）
python tg_spider.py get "仙逆"

# 指定频道
python tg_spider.py get "仙逆" -c lsp115
```

### 列出资源

```bash
# 列出最近的资源
python tg_spider.py list -c vip115hot

# 列出更多
python tg_spider.py list -c vip115hot --limit 100
```

### 查看状态

```bash
# 查看所有频道状态
python tg_spider.py status

# 查看指定频道
python tg_spider.py status -c lsp115
```

### 同步所有频道

一键爬取和解析所有配置的频道：

```bash
# 增量同步（推荐用于定时任务）
python tg_spider.py sync

# 全量同步
python tg_spider.py sync --full
```

## 典型工作流程

### 首次使用

```bash
# 1. 全量爬取频道
python tg_spider.py crawl -c lsp115 --all

# 2. 解析网盘链接（仅 lsp115 需要）
python tg_spider.py parse -c lsp115

# 3. 搜索并获取资源
python tg_spider.py get "仙逆"
```

### 日常增量更新

```bash
# 增量爬取 + 自动解析
python tg_spider.py crawl -c lsp115 --incremental --parse
```

### 定时任务

创建批处理文件 `auto_crawl.bat`：

```batch
@echo off
cd /d "你的目录路径"
python tg_spider.py crawl -c lsp115 --incremental --parse
python tg_spider.py crawl -c vip115hot --incremental
python tg_spider.py crawl -c qukanmovie --incremental
```

## 项目结构

```
tg_dl/
├── tg_spider.py    # 主入口
├── config.py       # 配置（频道、常量）
├── models.py       # 数据模型
├── database.py     # 数据库操作
├── crawler.py      # 爬虫模块
├── parser.py       # 解析器
├── cli.py          # 命令行处理
├── resources.db    # SQLite 数据库（自动生成）
└── requirements.txt
```

## 添加新频道

编辑 `config.py`，在 `CHANNELS` 字典中添加：

```python
"new_channel": {
  "url": "https://t.me/s/频道用户名",
  "name": "频道显示名称",
  "parse_mode": "inline",  # 或 "telegraph" / "button"
},
```

解析模式说明：
- `telegraph`: 链接在 telegra.ph 页面中
- `inline`: 链接直接在消息文本中
- `button`: 链接在 "点击跳转" 按钮中
