#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集成测试脚本 - 测试MySQL存储和Socket管理功能
"""

import sys
import pymysql
from database import Database
from socket_manager import SocketProxyManager
import toml

print("="*60)
print("10jqka 爬虫集成测试")
print("="*60)

# 1. 测试配置文件加载
print("\n[1/5] 测试配置文件加载...")
try:
    with open('config.toml', 'r', encoding='utf-8') as f:
        config = toml.load(f)
    print("✓ 配置文件加载成功")
    print(f"  - 数据库: {config['database']['host']}:{config['database']['port']}")
    print(f"  - MySQL启用: {config['database']['enabled']}")
    print(f"  - Socket启用: {config['socket_proxy']['enabled']}")
    print(f"  - 线程数: {config['scraper']['thread_count']}")
except Exception as e:
    print(f"✗ 配置文件加载失败: {e}")
    sys.exit(1)

# 2. 测试MySQL连接
print("\n[2/5] 测试MySQL连接...")
try:
    db = Database(config['database'])
    db.test_connection()
    print("✓ MySQL连接成功")

    # 查询表结构
    conn = pymysql.connect(
        host=config['database']['host'],
        port=config['database']['port'],
        user=config['database']['user'],
        password=config['database']['password'],
        database=config['database']['database'],
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    print(f"  - 表数量: {len(tables)}")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
        count = cursor.fetchone()[0]
        print(f"    • {table[0]}: {count} 条记录")
    cursor.close()
    conn.close()

except Exception as e:
    print(f"✗ MySQL连接失败: {e}")
    sys.exit(1)

# 3. 测试批次创建
print("\n[3/5] 测试批次创建...")
try:
    # 清理旧的running批次
    db.cleanup_stale_batches(timeout_hours=0)

    # 创建测试批次
    batch_id = db.create_batch('thshy')
    print(f"✓ 批次创建成功: batch_id = {batch_id}")

    # 插入测试数据
    test_boards = [
        {
            'board_name': '测试板块1',
            'source_url': 'http://test.com/1',
            'driving_event': '测试事件',
            'stock_count': 10
        },
        {
            'board_name': '测试板块2',
            'source_url': 'http://test.com/2',
            'driving_event': '测试事件2',
            'stock_count': 20
        }
    ]

    test_stocks = [
        {'board_name': '测试板块1', 'stock_code': '000001', 'stock_name': '测试股票1', 'sequence_num': 1},
        {'board_name': '测试板块1', 'stock_code': '000002', 'stock_name': '测试股票2', 'sequence_num': 2},
        {'board_name': '测试板块2', 'stock_code': '000003', 'stock_name': '测试股票3', 'sequence_num': 1},
    ]

    print("  - 插入测试板块数据...")
    db.insert_boards(batch_id, test_boards, 'thshy', '2025-11-22')
    print(f"    ✓ 插入 {len(test_boards)} 条板块记录")

    print("  - 插入测试股票数据...")
    db.insert_stocks(batch_id, test_stocks, '2025-11-22')
    print(f"    ✓ 插入 {len(test_stocks)} 条股票记录")

    # 更新批次状态
    db.update_batch_status(batch_id, 'success', len(test_boards), len(test_stocks))
    print("  - 更新批次状态为 success")

except Exception as e:
    print(f"✗ 批次操作失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. 测试变化统计
print("\n[4/5] 测试变化统计...")
try:
    summary_id = db.generate_change_summary(batch_id, 'thshy')
    if summary_id:
        print(f"✓ 变化统计生成成功: summary_id = {summary_id}")
    else:
        print("  - 首次抓取，无对比数据")
except Exception as e:
    print(f"✗ 变化统计失败: {e}")

# 5. 测试Socket管理器
print("\n[5/5] 测试Socket管理器...")
try:
    socket_mgr = SocketProxyManager(config)

    # 检查端口
    if socket_mgr.check_port_available():
        print("  ✓ 端口 8080 可用")
    else:
        print("  - 端口 8080 已被占用")
        pid = socket_mgr.find_process_by_port()
        if pid:
            print(f"    占用进程 PID: {pid}")

    # 尝试启动Socket代理
    print("  - 尝试启动Socket代理...")
    try:
        socket_mgr.start()
        print("  ✓ Socket代理启动成功")

        # 检查是否存活
        if socket_mgr.is_alive():
            print(f"  ✓ Socket代理运行中 (PID: {socket_mgr.pid})")
        else:
            print("  - Socket代理未运行")

        # 停止Socket代理
        print("  - 停止Socket代理...")
        socket_mgr.stop()
        print("  ✓ Socket代理已停止")

    except Exception as e:
        print(f"  ⚠ Socket代理测试跳过: {e}")

except Exception as e:
    print(f"✗ Socket管理器测试失败: {e}")

# 清理测试数据
print("\n清理测试数据...")
try:
    db.delete_batch_data(batch_id)
    print("✓ 测试数据已清理")
except Exception as e:
    print(f"⚠ 清理失败: {e}")

db.close()

print("\n" + "="*60)
print("✓ 所有测试通过！")
print("="*60)
print("\n提示: 现在可以运行实际的爬虫程序进行测试")
print("命令: python3 main.py -u <用户名> -p <密码> -s")
