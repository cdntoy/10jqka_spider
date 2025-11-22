#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库操作模块
提供MySQL连接、事务管理、CRUD操作、变化统计等功能
"""

import pymysql
from pymysql.cursors import DictCursor
from contextlib import contextmanager
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Set
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Database:
    """MySQL数据库操作类"""

    def __init__(self, config: dict, auto_create_db: bool = True):
        """
        初始化数据库连接

        Args:
            config: 数据库配置字典，包含host, port, user, password等
            auto_create_db: 数据库不存在时是否自动创建，默认True
        """
        self.config = config
        self.connection = None
        self._in_transaction = False
        self.auto_create_db = auto_create_db

        # 尝试连接数据库，失败时自动创建
        self._connect()

    def _connect(self):
        """建立数据库连接，数据库不存在时自动创建"""
        db_name = self.config.get('database', 'stock_spider')

        try:
            # 尝试连接指定数据库
            self.connection = pymysql.connect(
                host=self.config.get('host', 'localhost'),
                port=self.config.get('port', 3306),
                user=self.config.get('user', 'root'),
                password=self.config.get('password', ''),
                database=db_name,
                charset=self.config.get('charset', 'utf8mb4'),
                connect_timeout=self.config.get('connection_timeout', 5),
                cursorclass=DictCursor,
                autocommit=False  # 手动控制事务
            )
            logger.info(f"✓ MySQL连接成功: {self.config['host']}:{self.config['port']}/{db_name}")

        except pymysql.err.OperationalError as e:
            # 1049 = Unknown database
            if e.args[0] == 1049 and self.auto_create_db:
                logger.warning(f"数据库 {db_name} 不存在，正在自动创建...")
                if self._create_database_and_tables():
                    # 重新连接到新创建的数据库
                    self.connection = pymysql.connect(
                        host=self.config.get('host', 'localhost'),
                        port=self.config.get('port', 3306),
                        user=self.config.get('user', 'root'),
                        password=self.config.get('password', ''),
                        database=db_name,
                        charset=self.config.get('charset', 'utf8mb4'),
                        connect_timeout=self.config.get('connection_timeout', 5),
                        cursorclass=DictCursor,
                        autocommit=False
                    )
                    logger.info(f"✓ 数据库创建成功并已连接: {db_name}")
                else:
                    raise Exception("数据库自动创建失败")
            else:
                logger.error(f"✗ MySQL连接失败: {e}")
                raise

        except Exception as e:
            logger.error(f"✗ MySQL连接失败: {e}")
            raise

    def _create_database_and_tables(self) -> bool:
        """
        创建数据库和表结构

        Returns:
            成功返回True，失败返回False
        """
        db_name = self.config.get('database', 'stock_spider')

        try:
            # 连接MySQL服务器（不指定数据库）
            conn = pymysql.connect(
                host=self.config.get('host', 'localhost'),
                port=self.config.get('port', 3306),
                user=self.config.get('user', 'root'),
                password=self.config.get('password', ''),
                charset=self.config.get('charset', 'utf8mb4'),
                connect_timeout=self.config.get('connection_timeout', 5)
            )
            cursor = conn.cursor()

            # 创建数据库
            logger.info(f"正在创建数据库: {db_name}")
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name} DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            cursor.execute(f"USE {db_name}")

            # 创建表（使用内嵌SQL）
            logger.info("正在创建数据库表...")
            self._create_tables(cursor)

            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"✓ 数据库 {db_name} 和表结构创建成功")
            return True

        except Exception as e:
            logger.error(f"数据库创建失败: {e}")
            return False

    def _create_tables(self, cursor):
        """
        创建数据库表结构

        Args:
            cursor: 数据库游标
        """
        # 表定义（与schema.sql保持一致）
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
            """,

            'board_statistics': """
                CREATE TABLE IF NOT EXISTS board_statistics (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '统计ID',
                    batch_id INT NOT NULL COMMENT '关联的批次ID',
                    board_type ENUM('thshy', 'gn', 'dy') NOT NULL COMMENT '板块类型: thshy=同花顺行业, gn=概念, dy=地域',
                    board_name VARCHAR(100) NOT NULL COMMENT '板块名称',
                    stock_count INT NOT NULL DEFAULT 0 COMMENT '该板块下的股票数量（去重后）',
                    scrape_date DATE NOT NULL COMMENT '抓取日期',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    FOREIGN KEY (batch_id) REFERENCES scrape_batches(batch_id) ON DELETE CASCADE,
                    INDEX idx_batch_id (batch_id),
                    INDEX idx_board_type (board_type),
                    INDEX idx_board_name (board_name),
                    INDEX idx_scrape_date (scrape_date),
                    UNIQUE KEY uk_batch_board (batch_id, board_name)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='板块统计表：记录每个板块的股票数量等统计信息'
            """
        }

        # 按顺序创建表（确保外键依赖正确）
        table_order = ['scrape_batches', 'board_snapshots', 'stock_snapshots',
                      'change_summary', 'board_changes', 'stock_changes', 'board_statistics']

        for table_name in table_order:
            logger.info(f"  创建表: {table_name}")
            cursor.execute(tables[table_name])

        logger.info("✓ 所有表创建成功")

    def test_connection(self):
        """测试数据库连接是否有效"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"数据库连接测试失败: {e}")
            return False

    @contextmanager
    def transaction(self):
        """
        事务上下文管理器
        用法: with db.transaction(): ...
        """
        self._in_transaction = True
        try:
            yield
            self.connection.commit()
            logger.debug("事务提交成功")
        except Exception as e:
            self.connection.rollback()
            logger.error(f"事务回滚: {e}")
            raise
        finally:
            self._in_transaction = False

    def rollback(self):
        """手动回滚事务"""
        if self.connection:
            self.connection.rollback()
            logger.info("事务已回滚")

    def commit(self):
        """手动提交事务"""
        if self.connection:
            self.connection.commit()
            logger.debug("事务已提交")

    def cleanup_stale_batches(self, timeout_hours: int = 1):
        """
        清理僵尸批次（超过指定小时数仍为running状态）

        Args:
            timeout_hours: 超时时间（小时）
        """
        try:
            with self.connection.cursor() as cursor:
                # 查找僵尸批次
                sql = """
                    SELECT batch_id FROM scrape_batches
                    WHERE status = 'running'
                    AND started_at < DATE_SUB(NOW(), INTERVAL %s HOUR)
                """
                cursor.execute(sql, (timeout_hours,))
                stale_batches = cursor.fetchall()

                if stale_batches:
                    logger.warning(f"发现 {len(stale_batches)} 个僵尸批次，正在清理...")

                    for batch in stale_batches:
                        batch_id = batch['batch_id']
                        # 删除关联数据（外键级联删除）
                        # 标记为失败
                        update_sql = """
                            UPDATE scrape_batches
                            SET status = 'failed',
                                error_message = '程序异常中断，批次已清理',
                                completed_at = NOW()
                            WHERE batch_id = %s
                        """
                        cursor.execute(update_sql, (batch_id,))

                    self.connection.commit()
                    logger.info(f"✓ 清理了 {len(stale_batches)} 个僵尸批次")

        except Exception as e:
            logger.error(f"清理僵尸批次失败: {e}")
            self.connection.rollback()

    def create_batch(self, board_type: str) -> int:
        """
        创建新的抓取批次

        Args:
            board_type: 板块类型 (thshy/gn/dy)

        Returns:
            batch_id: 新创建的批次ID
        """
        try:
            with self.connection.cursor() as cursor:
                sql = """
                    INSERT INTO scrape_batches (board_type, status, started_at)
                    VALUES (%s, 'running', NOW())
                """
                cursor.execute(sql, (board_type,))
                self.connection.commit()
                batch_id = cursor.lastrowid
                logger.info(f"✓ 创建批次 #{batch_id} (类型: {board_type})")
                return batch_id
        except Exception as e:
            logger.error(f"创建批次失败: {e}")
            raise

    def update_batch_status(self, batch_id: int, status: str,
                           total_boards: int = None, total_stocks: int = None,
                           error_message: str = None):
        """
        更新批次状态

        Args:
            batch_id: 批次ID
            status: 状态 (running/success/failed)
            total_boards: 板块总数
            total_stocks: 股票总数
            error_message: 错误信息（失败时）
        """
        try:
            with self.connection.cursor() as cursor:
                sql = """
                    UPDATE scrape_batches
                    SET status = %s,
                        completed_at = NOW(),
                        total_boards = COALESCE(%s, total_boards),
                        total_stocks = COALESCE(%s, total_stocks),
                        error_message = %s
                    WHERE batch_id = %s
                """
                cursor.execute(sql, (status, total_boards, total_stocks, error_message, batch_id))
                self.connection.commit()
                logger.info(f"✓ 批次 #{batch_id} 状态更新为: {status}")
        except Exception as e:
            logger.error(f"更新批次状态失败: {e}")
            raise

    def insert_boards(self, batch_id: int, boards: List[Dict], board_type: str, scrape_date: str):
        """
        批量插入板块数据

        Args:
            batch_id: 批次ID
            boards: 板块数据列表 [{board_name, source_url, driving_event, stock_count}, ...]
            board_type: 板块类型
            scrape_date: 抓取日期
        """
        if not boards:
            return

        try:
            with self.connection.cursor() as cursor:
                sql = """
                    INSERT INTO board_snapshots
                    (batch_id, board_type, board_name, source_url, driving_event, stock_count, scrape_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                values = [
                    (batch_id, board_type, b['board_name'], b.get('source_url'),
                     b.get('driving_event'), b.get('stock_count'), scrape_date)
                    for b in boards
                ]
                cursor.executemany(sql, values)

                if not self._in_transaction:
                    self.connection.commit()

                logger.info(f"✓ 插入 {len(boards)} 条板块数据")
        except Exception as e:
            logger.error(f"插入板块数据失败: {e}")
            raise

    def insert_stocks(self, batch_id: int, stocks: List[Dict], scrape_date: str):
        """
        批量插入股票数据

        Args:
            batch_id: 批次ID
            stocks: 股票数据列表 [{board_name, stock_code, stock_name, sequence_num}, ...]
            scrape_date: 抓取日期
        """
        if not stocks:
            return

        try:
            with self.connection.cursor() as cursor:
                sql = """
                    INSERT INTO stock_snapshots
                    (batch_id, board_name, stock_code, stock_name, sequence_num, scrape_date)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                values = [
                    (batch_id, s['board_name'], s['stock_code'],
                     s['stock_name'], s.get('sequence_num'), scrape_date)
                    for s in stocks
                ]
                cursor.executemany(sql, values)

                if not self._in_transaction:
                    self.connection.commit()

                logger.info(f"✓ 插入 {len(stocks)} 条股票数据")
        except Exception as e:
            logger.error(f"插入股票数据失败: {e}")
            raise

    def insert_board_statistics(self, batch_id: int, board_type: str, stocks: List[Dict], scrape_date: str):
        """
        计算并插入板块统计数据

        统计每个板块下的股票数量（去重后的实际数量）

        Args:
            batch_id: 批次ID
            board_type: 板块类型（thshy/gn/dy）
            stocks: 股票数据列表 [{board_name, stock_code, ...}, ...]
            scrape_date: 抓取日期
        """
        if not stocks:
            return

        try:
            # 按板块统计股票数量
            board_stock_counts = {}
            for stock in stocks:
                board_name = stock['board_name']
                if board_name not in board_stock_counts:
                    board_stock_counts[board_name] = set()
                board_stock_counts[board_name].add(stock['stock_code'])

            # 准备插入数据
            with self.connection.cursor() as cursor:
                sql = """
                    INSERT INTO board_statistics
                    (batch_id, board_type, board_name, stock_count, scrape_date, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """
                values = [
                    (batch_id, board_type, board_name, len(codes), scrape_date)
                    for board_name, codes in board_stock_counts.items()
                ]
                cursor.executemany(sql, values)

                if not self._in_transaction:
                    self.connection.commit()

                logger.info(f"✓ 插入 {len(board_stock_counts)} 条板块统计数据")
        except Exception as e:
            logger.error(f"插入板块统计数据失败: {e}")
            raise

    def get_previous_successful_batch(self, board_type: str, current_batch_id: int) -> Optional[Dict]:
        """
        获取上一次成功的批次

        Args:
            board_type: 板块类型
            current_batch_id: 当前批次ID

        Returns:
            上一次批次信息，如果不存在则返回None
        """
        try:
            with self.connection.cursor() as cursor:
                sql = """
                    SELECT batch_id, total_boards, total_stocks, completed_at
                    FROM scrape_batches
                    WHERE board_type = %s
                      AND status = 'success'
                      AND batch_id < %s
                    ORDER BY batch_id DESC
                    LIMIT 1
                """
                cursor.execute(sql, (board_type, current_batch_id))
                return cursor.fetchone()
        except Exception as e:
            logger.error(f"查询上一批次失败: {e}")
            return None

    def generate_change_summary(self, batch_id: int, board_type: str) -> Optional[int]:
        """
        生成变化统计摘要

        Args:
            batch_id: 当前批次ID
            board_type: 板块类型

        Returns:
            summary_id: 摘要ID，如果失败返回None
        """
        try:
            # 获取上一次成功批次
            prev_batch = self.get_previous_successful_batch(board_type, batch_id)

            with self.connection.cursor() as cursor:
                # 获取当前批次数据
                current_boards = self._get_board_set(batch_id)
                current_stocks = self._get_stock_set(batch_id)

                if prev_batch is None:
                    # 第一次抓取，所有数据都是新增
                    boards_added = len(current_boards)
                    boards_removed = 0
                    stocks_added = len(current_stocks)
                    stocks_removed = 0
                    change_rate = 0.0
                    prev_batch_id = None

                    logger.info(f"首次抓取: {boards_added} 个板块, {stocks_added} 只股票")
                else:
                    # 获取上一批次数据
                    prev_batch_id = prev_batch['batch_id']
                    prev_boards = self._get_board_set(prev_batch_id)
                    prev_stocks = self._get_stock_set(prev_batch_id)

                    # 计算变化
                    added_boards = current_boards - prev_boards
                    removed_boards = prev_boards - current_boards
                    added_stocks = current_stocks - prev_stocks
                    removed_stocks = prev_stocks - current_stocks

                    boards_added = len(added_boards)
                    boards_removed = len(removed_boards)
                    stocks_added = len(added_stocks)
                    stocks_removed = len(removed_stocks)

                    # 计算变化率
                    total_change = boards_added + boards_removed + stocks_added + stocks_removed
                    total_prev = len(prev_boards) + len(prev_stocks)
                    change_rate = (total_change / total_prev * 100) if total_prev > 0 else 0.0

                    logger.info(f"变化统计 - 板块: +{boards_added}/-{boards_removed}, "
                              f"股票: +{stocks_added}/-{stocks_removed}, "
                              f"变化率: {change_rate:.2f}%")

                # 插入摘要
                sql = """
                    INSERT INTO change_summary
                    (batch_id, board_type, prev_batch_id, boards_added, boards_removed,
                     stocks_added, stocks_removed, change_rate, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """
                cursor.execute(sql, (batch_id, board_type, prev_batch_id,
                                   boards_added, boards_removed,
                                   stocks_added, stocks_removed, change_rate))
                summary_id = cursor.lastrowid

                # 如果不是首次，插入变化明细
                if prev_batch is not None:
                    self._insert_board_changes(summary_id, board_type, added_boards, removed_boards)
                    self._insert_stock_changes(summary_id, added_stocks, removed_stocks)

                self.connection.commit()
                logger.info(f"✓ 生成变化摘要 #{summary_id}")

                # 打印变化摘要
                self._print_change_summary(batch_id, boards_added, boards_removed,
                                          stocks_added, stocks_removed, change_rate)

                return summary_id

        except Exception as e:
            logger.error(f"生成变化摘要失败: {e}")
            self.connection.rollback()
            return None

    def _get_board_set(self, batch_id: int) -> Set[str]:
        """获取批次的板块名称集合"""
        with self.connection.cursor() as cursor:
            sql = "SELECT board_name FROM board_snapshots WHERE batch_id = %s"
            cursor.execute(sql, (batch_id,))
            return {row['board_name'] for row in cursor.fetchall()}

    def _get_stock_set(self, batch_id: int) -> Set[Tuple[str, str]]:
        """获取批次的股票集合 (board_name, stock_code)"""
        with self.connection.cursor() as cursor:
            sql = "SELECT board_name, stock_code FROM stock_snapshots WHERE batch_id = %s"
            cursor.execute(sql, (batch_id,))
            return {(row['board_name'], row['stock_code']) for row in cursor.fetchall()}

    def _insert_board_changes(self, summary_id: int, board_type: str,
                             added: Set[str], removed: Set[str]):
        """插入板块变化明细"""
        if not added and not removed:
            return

        with self.connection.cursor() as cursor:
            sql = """
                INSERT INTO board_changes
                (summary_id, change_type, board_name, board_type, created_at)
                VALUES (%s, %s, %s, %s, NOW())
            """
            values = []
            for board in added:
                values.append((summary_id, 'added', board, board_type))
            for board in removed:
                values.append((summary_id, 'removed', board, board_type))

            cursor.executemany(sql, values)
            logger.debug(f"插入 {len(values)} 条板块变化明细")

    def _insert_stock_changes(self, summary_id: int,
                             added: Set[Tuple[str, str]], removed: Set[Tuple[str, str]]):
        """插入股票变化明细"""
        if not added and not removed:
            return

        with self.connection.cursor() as cursor:
            sql = """
                INSERT INTO stock_changes
                (summary_id, change_type, board_name, stock_code, stock_name, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """
            values = []
            for board_name, stock_code in added:
                # 获取股票名称
                stock_name = self._get_stock_name(board_name, stock_code)
                values.append((summary_id, 'added', board_name, stock_code, stock_name))

            for board_name, stock_code in removed:
                stock_name = self._get_stock_name(board_name, stock_code)
                values.append((summary_id, 'removed', board_name, stock_code, stock_name))

            cursor.executemany(sql, values)
            logger.debug(f"插入 {len(values)} 条股票变化明细")

    def _get_stock_name(self, board_name: str, stock_code: str) -> str:
        """从最近的快照中获取股票名称"""
        with self.connection.cursor() as cursor:
            sql = """
                SELECT stock_name FROM stock_snapshots
                WHERE board_name = %s AND stock_code = %s
                ORDER BY batch_id DESC LIMIT 1
            """
            cursor.execute(sql, (board_name, stock_code))
            result = cursor.fetchone()
            return result['stock_name'] if result else ''

    def _print_change_summary(self, batch_id: int, boards_added: int, boards_removed: int,
                             stocks_added: int, stocks_removed: int, change_rate: float):
        """打印变化摘要到控制台"""
        print("\n" + "="*60)
        print(f"{'本次抓取摘要':^56}")
        print("="*60)
        print(f"批次ID: {batch_id}")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-"*60)
        print(f"板块变化: 新增 {boards_added} 个, 减少 {boards_removed} 个")
        print(f"股票变化: 新增 {stocks_added} 只, 减少 {stocks_removed} 只")
        print(f"总体变化率: {change_rate:.2f}%")
        print("="*60 + "\n")

    def delete_batch_data(self, batch_id: int):
        """
        删除批次的所有数据（用于清理不完整数据）

        Args:
            batch_id: 批次ID
        """
        try:
            with self.connection.cursor() as cursor:
                # 外键级联删除会自动删除关联的snapshots和changes
                sql = "DELETE FROM scrape_batches WHERE batch_id = %s"
                cursor.execute(sql, (batch_id,))
                self.connection.commit()
                logger.info(f"✓ 删除批次 #{batch_id} 的所有数据")
        except Exception as e:
            logger.error(f"删除批次数据失败: {e}")
            raise

    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            logger.info("数据库连接已关闭")
