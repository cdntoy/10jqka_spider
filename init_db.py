#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库初始化脚本
"""

import pymysql
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 数据库配置
config = {
    'host': os.getenv('DB_HOST', '192.168.7.22'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD'),  # 从环境变量读取
    'charset': 'utf8mb4'
}

# 检查密码是否设置
if not config['password']:
    print("错误：请设置环境变量 DB_PASSWORD 或创建 .env 文件")
    print("示例：export DB_PASSWORD=your_password")
    print("或复制 .env.example 为 .env 并填写密码")
    exit(1)

print("正在连接MySQL服务器...")
try:
    # 连接到MySQL服务器（不指定数据库）
    conn = pymysql.connect(**config)
    cursor = conn.cursor()
    print("✓ MySQL连接成功")

    # 先创建数据库
    print("\n创建数据库 stock_spider...")
    cursor.execute("CREATE DATABASE IF NOT EXISTS stock_spider DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cursor.execute("USE stock_spider")
    conn.commit()
    print("  ✓ 数据库已创建")

    # 读取并执行schema.sql中的表创建语句
    print("\n正在创建表...")
    with open('schema.sql', 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # 分割SQL语句并执行
    statements = sql_content.split(';')
    for i, statement in enumerate(statements):
        statement = statement.strip()
        if statement and not statement.startswith('--'):
            # 跳过CREATE DATABASE和USE语句（已经执行过）
            if 'CREATE DATABASE' in statement.upper() or statement.upper().startswith('USE '):
                continue

            try:
                cursor.execute(statement)
                if 'CREATE TABLE' in statement.upper():
                    # 提取表名
                    if 'IF NOT EXISTS' in statement.upper():
                        table_name = statement.split('IF NOT EXISTS')[1].split('(')[0].strip()
                    else:
                        table_name = statement.split('CREATE TABLE')[1].split('(')[0].strip().split()[0]
                    print(f"  ✓ 创建表 {table_name}")
            except Exception as e:
                if 'table exists' in str(e).lower():
                    continue  # 忽略表已存在的错误
                print(f"  警告: {e}")

    conn.commit()

    # 验证表结构
    print("\n验证数据库表...")
    cursor.execute("USE stock_spider")
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()

    print(f"\n✓ 成功创建 {len(tables)} 张表:")
    for table in tables:
        print(f"  - {table[0]}")

    cursor.close()
    conn.close()

    print("\n✓ 数据库初始化完成！")

except Exception as e:
    print(f"✗ 错误: {e}")
    import traceback
    traceback.print_exc()
