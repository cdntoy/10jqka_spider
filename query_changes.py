#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块变化查询工具
用于查询和分析板块、股票的历史变化趋势
"""

import pymysql
import os
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dotenv import load_dotenv
from tabulate import tabulate

# 加载环境变量
load_dotenv()

# 数据库配置
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '192.168.7.22'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD'),
    'database': 'stock_spider',
    'charset': 'utf8mb4'
}

# 板块类型映射
BOARD_TYPE_NAMES = {
    'thshy': '同花顺行业',
    'gn': '概念',
    'dy': '地域'
}


def get_db_connection():
    """获取数据库连接"""
    if not DB_CONFIG['password']:
        print("错误：请配置.env文件中的DB_PASSWORD")
        exit(1)

    try:
        return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
    except Exception as e:
        print(f"数据库连接失败: {e}")
        exit(1)


def query_daily_summary(board_type: str, days: int = 7):
    """
    查询指定板块类型的每日变化汇总

    Args:
        board_type: 板块类型（thshy/gn/dy）
        days: 查询最近N天，默认7天
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    print(f"\n{'='*80}")
    print(f"{BOARD_TYPE_NAMES.get(board_type, board_type)} - 最近{days}天变化汇总")
    print(f"{'='*80}\n")

    # 查询最近N天的变化摘要
    sql = """
        SELECT
            cs.batch_id,
            cs.prev_batch_id,
            DATE(cs.created_at) as date,
            TIME(cs.created_at) as time,
            cs.boards_added,
            cs.boards_removed,
            cs.stocks_added,
            cs.stocks_removed,
            cs.change_rate,
            sb.total_boards,
            sb.total_stocks
        FROM change_summary cs
        JOIN scrape_batches sb ON cs.batch_id = sb.batch_id
        WHERE cs.board_type = %s
          AND cs.created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
        ORDER BY cs.created_at DESC
    """

    cursor.execute(sql, (board_type, days))
    results = cursor.fetchall()

    if not results:
        print(f"最近{days}天无数据")
        cursor.close()
        conn.close()
        return

    # 格式化表格
    table_data = []
    for row in results:
        table_data.append([
            row['date'],
            row['time'],
            f"#{row['batch_id']}",
            row['total_boards'],
            row['total_stocks'],
            f"+{row['boards_added']}/-{row['boards_removed']}",
            f"+{row['stocks_added']}/-{row['stocks_removed']}",
            f"{row['change_rate']:.2f}%" if row['change_rate'] else "0.00%"
        ])

    headers = ['日期', '时间', '批次', '板块总数', '股票总数', '板块变化', '股票变化', '变化率']
    print(tabulate(table_data, headers=headers, tablefmt='grid'))

    print(f"\n共 {len(results)} 条记录")

    cursor.close()
    conn.close()


def query_board_history(board_name: str, limit: int = 30):
    """
    查询单个板块的历史趋势

    Args:
        board_name: 板块名称
        limit: 显示最近N次记录
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    print(f"\n{'='*80}")
    print(f"板块历史趋势: {board_name}")
    print(f"{'='*80}\n")

    # 查询板块历史快照
    sql = """
        SELECT
            bs.batch_id,
            DATE(bs.scrape_date) as date,
            bs.board_type,
            bs.stock_count,
            bs.driving_event,
            sb.started_at
        FROM board_snapshots bs
        JOIN scrape_batches sb ON bs.batch_id = sb.batch_id
        WHERE bs.board_name = %s
          AND sb.status = 'success'
        ORDER BY bs.scrape_date DESC, bs.batch_id DESC
        LIMIT %s
    """

    cursor.execute(sql, (board_name, limit))
    results = cursor.fetchall()

    if not results:
        print(f"未找到板块: {board_name}")
        cursor.close()
        conn.close()
        return

    # 显示板块信息
    board_type_name = BOARD_TYPE_NAMES.get(results[0]['board_type'], results[0]['board_type'])
    print(f"板块类型: {board_type_name}")
    print(f"最新成分股数量: {results[0]['stock_count'] or 'N/A'}")
    if results[0]['driving_event']:
        print(f"最新驱动事件: {results[0]['driving_event']}")
    print()

    # 格式化表格
    table_data = []
    for row in results:
        table_data.append([
            row['date'],
            f"#{row['batch_id']}",
            row['stock_count'] or 'N/A',
            row['driving_event'] or '--'
        ])

    headers = ['抓取日期', '批次', '成分股数量', '驱动事件']
    print(tabulate(table_data, headers=headers, tablefmt='grid'))

    # 查询最近的变化明细
    print(f"\n{'='*80}")
    print("最近的成分股变化:")
    print(f"{'='*80}\n")

    sql = """
        SELECT
            sc.change_type,
            sc.stock_code,
            sc.stock_name,
            DATE(sc.created_at) as date,
            cs.batch_id
        FROM stock_changes sc
        JOIN change_summary cs ON sc.summary_id = cs.id
        WHERE sc.board_name = %s
        ORDER BY sc.created_at DESC
        LIMIT 20
    """

    cursor.execute(sql, (board_name,))
    changes = cursor.fetchall()

    if changes:
        change_data = []
        for change in changes:
            change_type_cn = '新增' if change['change_type'] == 'added' else '删除'
            change_data.append([
                change['date'],
                f"#{change['batch_id']}",
                change_type_cn,
                change['stock_code'],
                change['stock_name']
            ])

        headers = ['日期', '批次', '变化类型', '股票代码', '股票名称']
        print(tabulate(change_data, headers=headers, tablefmt='grid'))
    else:
        print("暂无变化记录（首次抓取或无变化）")

    cursor.close()
    conn.close()


def query_hot_changes(change_type: str = 'added', board_type: Optional[str] = None, limit: int = 20):
    """
    查询最近新增或删除的热门股票

    Args:
        change_type: 变化类型（added/removed）
        board_type: 板块类型（thshy/gn/dy），None表示所有类型
        limit: 显示数量
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    change_type_cn = '新增' if change_type == 'added' else '删除'
    board_filter = f" - {BOARD_TYPE_NAMES.get(board_type, board_type)}" if board_type else ""

    print(f"\n{'='*80}")
    print(f"最近{change_type_cn}的热门股票 TOP {limit}{board_filter}")
    print(f"{'='*80}\n")

    # 查询股票变化（按出现频率统计）
    sql = """
        SELECT
            sc.stock_code,
            sc.stock_name,
            COUNT(*) as change_count,
            GROUP_CONCAT(DISTINCT sc.board_name ORDER BY sc.board_name SEPARATOR ', ') as boards,
            MAX(DATE(sc.created_at)) as latest_date
        FROM stock_changes sc
        JOIN change_summary cs ON sc.summary_id = cs.id
        WHERE sc.change_type = %s
    """

    params = [change_type]

    if board_type:
        sql += " AND cs.board_type = %s"
        params.append(board_type)

    sql += """
        GROUP BY sc.stock_code, sc.stock_name
        ORDER BY change_count DESC, latest_date DESC
        LIMIT %s
    """

    params.append(limit)

    cursor.execute(sql, params)
    results = cursor.fetchall()

    if not results:
        print("暂无数据")
        cursor.close()
        conn.close()
        return

    # 格式化表格
    table_data = []
    for idx, row in enumerate(results, 1):
        # 截断板块名称列表（太长的话）
        boards_str = row['boards']
        if len(boards_str) > 60:
            boards_str = boards_str[:57] + '...'

        table_data.append([
            idx,
            row['stock_code'],
            row['stock_name'],
            row['change_count'],
            boards_str,
            row['latest_date']
        ])

    headers = ['排名', '股票代码', '股票名称', '出现次数', '所属板块', '最新日期']
    print(tabulate(table_data, headers=headers, tablefmt='grid'))

    cursor.close()
    conn.close()


def query_batch_details(batch_id: int):
    """
    查询指定批次的详细信息

    Args:
        batch_id: 批次ID
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    print(f"\n{'='*80}")
    print(f"批次 #{batch_id} 详细信息")
    print(f"{'='*80}\n")

    # 查询批次基本信息
    sql = "SELECT * FROM scrape_batches WHERE batch_id = %s"
    cursor.execute(sql, (batch_id,))
    batch = cursor.fetchone()

    if not batch:
        print(f"批次 #{batch_id} 不存在")
        cursor.close()
        conn.close()
        return

    # 显示批次信息
    board_type_name = BOARD_TYPE_NAMES.get(batch['board_type'], batch['board_type'])
    status_cn = {'running': '进行中', 'success': '成功', 'failed': '失败'}[batch['status']]

    print(f"板块类型: {board_type_name}")
    print(f"状态: {status_cn}")
    print(f"开始时间: {batch['started_at']}")
    print(f"完成时间: {batch['completed_at'] or 'N/A'}")
    print(f"板块总数: {batch['total_boards']}")
    print(f"股票总数: {batch['total_stocks']}")
    if batch['error_message']:
        print(f"错误信息: {batch['error_message']}")

    # 查询变化摘要
    sql = "SELECT * FROM change_summary WHERE batch_id = %s"
    cursor.execute(sql, (batch_id,))
    summary = cursor.fetchone()

    if summary:
        print(f"\n{'='*80}")
        print("变化统计:")
        print(f"{'='*80}\n")

        print(f"上一批次: #{summary['prev_batch_id'] or 'N/A（首次抓取）'}")
        print(f"板块变化: +{summary['boards_added']}/-{summary['boards_removed']}")
        print(f"股票变化: +{summary['stocks_added']}/-{summary['stocks_removed']}")
        print(f"变化率: {summary['change_rate']:.2f}%")

    cursor.close()
    conn.close()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='10jqka板块变化查询工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 查询概念板块最近7天的每日变化
  python3 query_changes.py --type gn --days 7

  # 查询"人工智能"板块的历史趋势
  python3 query_changes.py --board 人工智能

  # 查询最近新增的TOP 20热门股票
  python3 query_changes.py --hot-added

  # 查询批次#5的详细信息
  python3 query_changes.py --batch 5
        """
    )

    parser.add_argument('--type', choices=['thshy', 'gn', 'dy'],
                       help='查询指定类型的每日变化汇总')
    parser.add_argument('--days', type=int, default=7,
                       help='查询最近N天的数据（配合--type使用），默认7天')
    parser.add_argument('--board', type=str,
                       help='查询单个板块的历史趋势（输入板块名称）')
    parser.add_argument('--hot-added', action='store_true',
                       help='查询最近新增的热门股票')
    parser.add_argument('--hot-removed', action='store_true',
                       help='查询最近删除的热门股票')
    parser.add_argument('--batch', type=int,
                       help='查询指定批次的详细信息（输入批次ID）')
    parser.add_argument('--limit', type=int, default=20,
                       help='显示数量限制，默认20')

    args = parser.parse_args()

    # 检查是否提供了至少一个查询参数
    if not any([args.type, args.board, args.hot_added, args.hot_removed, args.batch]):
        parser.print_help()
        exit(0)

    # 执行查询
    if args.type:
        query_daily_summary(args.type, args.days)

    if args.board:
        query_board_history(args.board, args.limit)

    if args.hot_added:
        query_hot_changes('added', None, args.limit)

    if args.hot_removed:
        query_hot_changes('removed', None, args.limit)

    if args.batch:
        query_batch_details(args.batch)


if __name__ == '__main__':
    main()
