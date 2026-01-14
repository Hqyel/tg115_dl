# -*- coding: utf-8 -*-
"""命令行处理模块"""

import argparse

from src.channels.config import CHANNELS
from src.core.database import Database, StateManager
from src.core.crawler import ChannelCrawler
from src.core.parser import TelegraphParser


def cmd_channels(args):
  """列出可用频道"""
  print("可用频道:")
  print("-" * 50)
  for ch_id, config in CHANNELS.items():
    print(f"  {ch_id:15} - {config['name']}")
    print(f"                   URL: {config['url']}")
    print(f"                   解析模式: {config['parse_mode']}")
    print()


def cmd_crawl(args):
  """爬取命令"""
  channel_id = args.channel
  if channel_id not in CHANNELS:
    print(f"错误: 未知频道 '{channel_id}'")
    print(f"可用频道: {', '.join(CHANNELS.keys())}")
    return

  db = Database()
  crawler = ChannelCrawler(channel_id)
  state_manager = StateManager()

  if args.resume:
    state = state_manager.load()
    if state and state.channel_id == channel_id:
      crawler.crawl_all(db, state_manager, resume_state=state)
    else:
      print("没有该频道的未完成任务")
    return

  if args.incremental:
    count = crawler.crawl_incremental(db)
    if count > 0 and args.parse and CHANNELS[channel_id]["parse_mode"] == "telegraph":
      print("\n开始解析网盘链接...")
      parser = TelegraphParser()
      parser.parse_batch(db, channel_id, limit=count)
    return

  if args.all:
    crawler.crawl_all(db, state_manager)
    if args.parse and CHANNELS[channel_id]["parse_mode"] == "telegraph":
      print("\n开始解析网盘链接...")
      parser = TelegraphParser()
      parser.parse_batch(db, channel_id)
    return

  count = crawler.crawl_with_limit(args.limit, db)
  if count > 0 and args.parse and CHANNELS[channel_id]["parse_mode"] == "telegraph":
    print("\n开始解析网盘链接...")
    parser = TelegraphParser()
    parser.parse_batch(db, channel_id, limit=count)


def cmd_parse(args):
  """解析命令"""
  channel_id = args.channel
  if channel_id not in CHANNELS:
    print(f"错误: 未知频道 '{channel_id}'")
    return

  if CHANNELS[channel_id]["parse_mode"] != "telegraph":
    print(f"频道 {channel_id} 不需要额外解析（链接已在消息中）")
    return

  db = Database()
  parser = TelegraphParser()

  unparsed = db.count_unparsed(channel_id)
  print(f"未解析资源: {unparsed}")

  if unparsed == 0:
    return

  limit = args.limit if args.limit > 0 else unparsed
  parser.parse_batch(db, channel_id, limit=limit)


def cmd_search(args):
  """搜索命令"""
  db = Database()
  keyword = args.keyword
  channel_id = args.channel if hasattr(args, 'channel') and args.channel else None

  if channel_id and channel_id not in CHANNELS:
    print(f"错误: 未知频道 '{channel_id}'")
    return

  print(f"搜索: {keyword}")
  if channel_id:
    print(f"频道: {CHANNELS[channel_id]['name']}")
  else:
    print("频道: 全部")
  print("-" * 50)

  results = db.search(keyword, channel_id)

  if not results:
    print("未找到匹配的资源")
    return

  print(f"找到 {len(results)} 条结果:\n")

  for i, (ch_id, r) in enumerate(results, 1):
    ch_name = CHANNELS[ch_id]['name'][:10]
    print(f"[{i}] [{ch_name}] {r.title}")
    print(f"    标签: {r.tags}")
    if r.pan_url:
      print(f"    115: {r.pan_url}")
    elif r.telegraph_url:
      print(f"    详情: {r.telegraph_url}")
    print()


def cmd_list(args):
  """列出命令"""
  channel_id = args.channel
  if channel_id not in CHANNELS:
    print(f"错误: 未知频道 '{channel_id}'")
    return

  db = Database()

  total = db.count(channel_id)
  unparsed = db.count_unparsed(channel_id)

  print(f"频道: {CHANNELS[channel_id]['name']}")
  print(f"统计: 总计 {total} 条，已解析 {total - unparsed} 条，未解析 {unparsed} 条")
  print("-" * 50)

  results = db.list_all(channel_id, limit=args.limit)

  for i, r in enumerate(results, 1):
    status = "✓" if r.pan_url else "✗"
    print(f"[{i}] [{status}] {r.title[:40]}")
    if r.tags:
      print(f"    {r.tags}")


def cmd_get(args):
  """获取链接命令"""
  db = Database()
  keyword = args.keyword
  channel_id = args.channel if hasattr(args, 'channel') and args.channel else None

  results = db.search(keyword, channel_id)

  if not results:
    print(f"未找到匹配 '{keyword}' 的资源")
    return

  if len(results) == 1:
    ch_id, r = results[0]
  else:
    print(f"找到 {len(results)} 条，请选择:\n")
    for i, (ch_id, r) in enumerate(results, 1):
      print(f"  [{i}] [{CHANNELS[ch_id]['name'][:8]}] {r.title}")

    print()
    try:
      choice = int(input("序号: ")) - 1
      if 0 <= choice < len(results):
        ch_id, r = results[choice]
      else:
        print("无效选择")
        return
    except (ValueError, KeyboardInterrupt):
      print("\n已取消")
      return

  print()
  print(f"资源: {r.title}")
  print(f"标签: {r.tags}")
  print(f"频道: {CHANNELS[ch_id]['name']}")

  if r.pan_url:
    print(f"\n115链接: {r.pan_url}")
  elif r.telegraph_url:
    print("\n正在解析...")
    parser = TelegraphParser()
    pan_url, desc = parser.parse_pan_link(r.telegraph_url)

    if pan_url:
      r.pan_url = pan_url
      r.description = desc
      db.save_resource(ch_id, r)
      print(f"115链接: {pan_url}")
    else:
      print("未能解析")
      print(f"手动访问: {r.telegraph_url}")


def cmd_status(args):
  """状态命令"""
  db = Database()
  state_manager = StateManager()

  channel_id = args.channel if hasattr(args, 'channel') and args.channel else None
  channels = [channel_id] if channel_id else list(CHANNELS.keys())

  print("=== 数据库状态 ===")
  for ch_id in channels:
    if ch_id not in CHANNELS:
      continue
    total = db.count(ch_id)
    unparsed = db.count_unparsed(ch_id)
    latest = db.get_latest_message_id(ch_id)
    print(f"\n[{ch_id}] {CHANNELS[ch_id]['name']}")
    print(f"  资源: {total} 条 (已解析: {total - unparsed}, 未解析: {unparsed})")
    print(f"  最新ID: {latest}")

  print("\n=== 爬取状态 ===")
  state = state_manager.load()
  if state:
    print(f"有未完成任务: {state.channel_id}")
    print(f"  模式: {state.mode}")
    print(f"  已爬取: {state.total_crawled}")
    print(f"使用 'crawl -c {state.channel_id} --resume' 继续")
  else:
    print("无未完成任务")


def cmd_sync(args):
  """同步所有频道（增量爬取 + 解析）"""
  db = Database()
  state_manager = StateManager()
  parser = TelegraphParser()

  print("="*50)
  print("开始同步所有频道")
  print("="*50)

  for ch_id, config in CHANNELS.items():
    print(f"\n>>> [{ch_id}] {config['name']}")
    print("-" * 40)

    crawler = ChannelCrawler(ch_id)

    # 根据模式选择爬取方式
    if args.full:
      crawler.crawl_all(db, state_manager)
    else:
      crawler.crawl_incremental(db)

    # 如果是 telegraph 模式，解析网盘链接
    if config["parse_mode"] == "telegraph":
      unparsed = db.count_unparsed(ch_id)
      if unparsed > 0:
        print(f"\n解析未处理的 {unparsed} 条资源...")
        parser.parse_batch(db, ch_id, limit=unparsed)

  print("\n" + "="*50)
  print("所有频道同步完成")
  print("="*50)


def main():
  """主入口"""
  parser = argparse.ArgumentParser(
    description="Telegram 公开频道资源爬虫（多频道支持）",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
示例:
  python main.py channels                        列出可用频道
  python main.py crawl -c lsp115 --all           全量爬取
  python main.py crawl -c vip115hot --limit 50   限量爬取
  python main.py crawl -c lsp115 --incremental   增量爬取
  python main.py crawl -c lsp115 --resume        断点续传
  python main.py parse -c lsp115                 解析链接
  python main.py search "仙逆" -c lsp115         搜索
  python main.py get "仙逆"                      获取链接
  python main.py list -c vip115hot               列出资源
  python main.py status                          查看状态
  python main.py sync                            同步所有频道（增量）
  python main.py sync --full                     同步所有频道（全量）
    """
  )

  subparsers = parser.add_subparsers(dest="command", help="命令")

  # channels
  subparsers.add_parser("channels", help="列出可用频道")

  # crawl
  crawl_p = subparsers.add_parser("crawl", help="爬取频道")
  crawl_p.add_argument("-c", "--channel", required=True, help="频道ID")
  crawl_g = crawl_p.add_mutually_exclusive_group()
  crawl_g.add_argument("--all", action="store_true", help="全量爬取")
  crawl_g.add_argument("--limit", type=int, default=50, help="限量爬取")
  crawl_g.add_argument("--incremental", action="store_true", help="增量爬取")
  crawl_g.add_argument("--resume", action="store_true", help="断点续传")
  crawl_p.add_argument("--parse", action="store_true", help="爬取后解析链接")

  # parse
  parse_p = subparsers.add_parser("parse", help="解析网盘链接")
  parse_p.add_argument("-c", "--channel", required=True, help="频道ID")
  parse_p.add_argument("--limit", type=int, default=0, help="限制数量")

  # search
  search_p = subparsers.add_parser("search", help="搜索资源")
  search_p.add_argument("keyword", help="关键词")
  search_p.add_argument("-c", "--channel", help="指定频道")

  # get
  get_p = subparsers.add_parser("get", help="获取网盘链接")
  get_p.add_argument("keyword", help="关键词")
  get_p.add_argument("-c", "--channel", help="指定频道")

  # list
  list_p = subparsers.add_parser("list", help="列出资源")
  list_p.add_argument("-c", "--channel", required=True, help="频道ID")
  list_p.add_argument("--limit", type=int, default=50, help="显示数量")

  # status
  status_p = subparsers.add_parser("status", help="查看状态")
  status_p.add_argument("-c", "--channel", help="指定频道")

  # sync
  sync_p = subparsers.add_parser("sync", help="同步所有频道")
  sync_p.add_argument("--full", action="store_true", help="全量爬取（默认增量）")

  args = parser.parse_args()

  if args.command == "channels":
    cmd_channels(args)
  elif args.command == "crawl":
    cmd_crawl(args)
  elif args.command == "parse":
    cmd_parse(args)
  elif args.command == "search":
    cmd_search(args)
  elif args.command == "get":
    cmd_get(args)
  elif args.command == "list":
    cmd_list(args)
  elif args.command == "status":
    cmd_status(args)
  elif args.command == "sync":
    cmd_sync(args)
  else:
    parser.print_help()


if __name__ == "__main__":
  main()
