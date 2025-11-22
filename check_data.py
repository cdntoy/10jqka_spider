#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快速查看数据库数据"""

import pymysql

conn = pymysql.connect(
    host='192.168.7.22',
    port=3306,
    user='root',
    password='qQ830406!',
    database='stock_spider',
    charset='utf8mb4'
)

cursor = conn.cursor(pymysql.cursors.DictCursor)

print("="*60)
print("数据库数据概览")
print("="*60)

# 批次信息
cursor.execute("SELECT * FROM scrape_batches ORDER BY batch_id DESC")
batches = cursor.fetchall()
print(f"\n批次总数: {len(batches)}")
for b in batches:
    status_icon = "✓" if b['status'] == 'success' else "⏳" if b['status'] == 'running' else "✗"
    print(f"  {status_icon} 批次 #{b['batch_id']} | {b['board_type']} | {b['status']} | "
          f"板块:{b['total_boards']} 股票:{b['total_stocks']} | {b['started_at']}")

# 统计
cursor.execute("SELECT COUNT(*) as count FROM board_snapshots")
board_count = cursor.fetchone()['count']

cursor.execute("SELECT COUNT(*) as count FROM stock_snapshots")
stock_count = cursor.fetchone()['count']

cursor.execute("SELECT COUNT(*) as count FROM change_summary")
summary_count = cursor.fetchone()['count']

print(f"\n数据统计:")
print(f"  - 板块快照: {board_count} 条")
print(f"  - 股票快照: {stock_count} 条")
print(f"  - 变化摘要: {summary_count} 条")

# 最新变化摘要
if summary_count > 0:
    cursor.execute("""
        SELECT s.*, b.board_type
        FROM change_summary s
        JOIN scrape_batches b ON s.batch_id = b.batch_id
        ORDER BY s.id DESC LIMIT 1
    """)
    latest = cursor.fetchone()
    print(f"\n最新变化摘要 (#{latest['id']}):")
    print(f"  - 批次: #{latest['batch_id']} ({latest['board_type']})")
    print(f"  - 板块: +{latest['boards_added']} -{latest['boards_removed']}")
    print(f"  - 股票: +{latest['stocks_added']} -{latest['stocks_removed']}")
    print(f"  - 变化率: {latest['change_rate']}%")

cursor.close()
conn.close()

print("\n" + "="*60)
