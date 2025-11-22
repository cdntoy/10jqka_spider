#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库初始化脚本 - 简化版
"""

import pymysql
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

config = {
    'host': os.getenv('DB_HOST', '192.168.7.22'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD'),  # 从环境变量读取，不再硬编码
    'charset': 'utf8mb4'
}

# 检查密码是否设置
if not config['password']:
    print("错误：请设置环境变量 DB_PASSWORD 或创建 .env 文件")
    print("示例：export DB_PASSWORD=your_password")
    print("或复制 .env.example 为 .env 并填写密码")
    exit(1)

print("正在连接MySQL...")
conn = pymysql.connect(**config)
cursor = conn.cursor()
print("✓ 连接成功\n")

# 创建数据库
print("创建数据库...")
cursor.execute("CREATE DATABASE IF NOT EXISTS stock_spider DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
cursor.execute("USE stock_spider")
print("✓ 数据库已创建\n")

# 创建表
print("创建表...")

tables = {
    'scrape_batches': """
        CREATE TABLE IF NOT EXISTS scrape_batches (
            batch_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '批次ID',
            board_type ENUM('thshy', 'gn', 'dy') NOT NULL COMMENT '板块类型',
            status ENUM('running', 'success', 'failed') DEFAULT 'running' COMMENT '执行状态',
            total_boards INT DEFAULT 0 COMMENT '板块总数',
            total_stocks INT DEFAULT 0 COMMENT '股票总数',
            started_at DATETIME NOT NULL COMMENT '开始时间',
            completed_at DATETIME DEFAULT NULL COMMENT '完成时间',
            error_message TEXT DEFAULT NULL COMMENT '错误信息',
            INDEX idx_status_type (status, board_type),
            INDEX idx_started_at (started_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='抓取批次记录表'
    """,

    'board_snapshots': """
        CREATE TABLE IF NOT EXISTS board_snapshots (
            id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
            batch_id INT NOT NULL COMMENT '关联的批次ID',
            board_type ENUM('thshy', 'gn', 'dy') NOT NULL COMMENT '板块类型',
            board_name VARCHAR(100) NOT NULL COMMENT '板块名称',
            source_url VARCHAR(255) DEFAULT NULL COMMENT '来源链接',
            driving_event VARCHAR(255) DEFAULT NULL COMMENT '驱动事件（领涨股等）',
            stock_count INT DEFAULT NULL COMMENT '成分股数量',
            scrape_date DATE NOT NULL COMMENT '抓取日期',
            FOREIGN KEY (batch_id) REFERENCES scrape_batches(batch_id) ON DELETE CASCADE,
            INDEX idx_batch_id (batch_id),
            INDEX idx_scrape_date (scrape_date),
            INDEX idx_board_name (board_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='板块快照表'
    """,

    'stock_snapshots': """
        CREATE TABLE IF NOT EXISTS stock_snapshots (
            id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
            batch_id INT NOT NULL COMMENT '关联的批次ID',
            board_name VARCHAR(100) NOT NULL COMMENT '所属板块名称',
            stock_code VARCHAR(10) NOT NULL COMMENT '股票代码',
            stock_name VARCHAR(100) NOT NULL COMMENT '股票名称',
            sequence_num INT DEFAULT NULL COMMENT '原始序号',
            scrape_date DATE NOT NULL COMMENT '抓取日期',
            FOREIGN KEY (batch_id) REFERENCES scrape_batches(batch_id) ON DELETE CASCADE,
            INDEX idx_batch_id (batch_id),
            INDEX idx_stock_code (stock_code),
            INDEX idx_board_name (board_name),
            INDEX idx_scrape_date (scrape_date),
            INDEX idx_batch_stock (batch_id, stock_code)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票快照表'
    """,

    'change_summary': """
        CREATE TABLE IF NOT EXISTS change_summary (
            id INT AUTO_INCREMENT PRIMARY KEY COMMENT '摘要ID',
            batch_id INT NOT NULL COMMENT '当前批次ID',
            board_type ENUM('thshy', 'gn', 'dy') NOT NULL COMMENT '板块类型',
            prev_batch_id INT DEFAULT NULL COMMENT '上一次批次ID（第一次为NULL）',
            boards_added INT DEFAULT 0 COMMENT '新增板块数',
            boards_removed INT DEFAULT 0 COMMENT '减少板块数',
            stocks_added INT DEFAULT 0 COMMENT '新增股票数',
            stocks_removed INT DEFAULT 0 COMMENT '减少股票数',
            change_rate DECIMAL(5,2) DEFAULT NULL COMMENT '总体变化率(%)',
            created_at DATETIME NOT NULL COMMENT '创建时间',
            FOREIGN KEY (batch_id) REFERENCES scrape_batches(batch_id) ON DELETE CASCADE,
            INDEX idx_batch_id (batch_id),
            INDEX idx_created_at (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='变化统计摘要表'
    """,

    'board_changes': """
        CREATE TABLE IF NOT EXISTS board_changes (
            id INT AUTO_INCREMENT PRIMARY KEY COMMENT '明细ID',
            summary_id INT NOT NULL COMMENT '关联的摘要ID',
            change_type ENUM('added', 'removed') NOT NULL COMMENT '变化类型: added=新增, removed=删除',
            board_name VARCHAR(100) NOT NULL COMMENT '板块名称',
            board_type ENUM('thshy', 'gn', 'dy') NOT NULL COMMENT '板块类型',
            source_url VARCHAR(255) DEFAULT NULL COMMENT '来源链接',
            created_at DATETIME NOT NULL COMMENT '创建时间',
            FOREIGN KEY (summary_id) REFERENCES change_summary(id) ON DELETE CASCADE,
            INDEX idx_summary_id (summary_id),
            INDEX idx_change_type (change_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='板块变化明细表'
    """,

    'stock_changes': """
        CREATE TABLE IF NOT EXISTS stock_changes (
            id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '明细ID',
            summary_id INT NOT NULL COMMENT '关联的摘要ID',
            change_type ENUM('added', 'removed') NOT NULL COMMENT '变化类型: added=新增, removed=删除',
            board_name VARCHAR(100) NOT NULL COMMENT '所属板块名称',
            stock_code VARCHAR(10) NOT NULL COMMENT '股票代码',
            stock_name VARCHAR(100) NOT NULL COMMENT '股票名称',
            created_at DATETIME NOT NULL COMMENT '创建时间',
            FOREIGN KEY (summary_id) REFERENCES change_summary(id) ON DELETE CASCADE,
            INDEX idx_summary_id (summary_id),
            INDEX idx_stock_code (stock_code),
            INDEX idx_change_type (change_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票变化明细表'
    """
}

for table_name, create_sql in tables.items():
    try:
        cursor.execute(create_sql)
        print(f"  ✓ {table_name}")
    except Exception as e:
        print(f"  ✗ {table_name}: {e}")

conn.commit()

# 验证
print("\n验证表结构...")
cursor.execute("SHOW TABLES")
result = cursor.fetchall()
print(f"✓ 共 {len(result)} 张表:")
for row in result:
    print(f"  - {row[0]}")

cursor.close()
conn.close()

print("\n✓ 数据库初始化完成！")
