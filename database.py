#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库操作模块 v2.0.0
支持3个独立数据库（同花顺行业板块、概念板块、地域板块）
全面中文化，简化表结构
"""

import pymysql
from pymysql.cursors import DictCursor
from contextlib import contextmanager
from datetime import datetime
from typing import List, Dict, Optional
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# 板块类型配置
BOARD_CONFIGS = {
    '同花顺行业': {
        'database': '同花顺行业板块',
        'url_type': 'thshy',
        'url': 'https://q.10jqka.com.cn/thshy/index/field/199112/order/desc/page/1/ajax/1/'
    },
    '概念': {
        'database': '概念板块',
        'url_type': 'gn',
        'url': 'https://q.10jqka.com.cn/gn/index/field/addtime/order/desc/page/30/ajax/1/'
    },
    '地域': {
        'database': '地域板块',
        'url_type': 'dy',
        'url': 'https://q.10jqka.com.cn/dy/index/field/199112/order/desc/page/1/ajax/1/'
    }
}


class Database:
    """MySQL数据库操作类（支持多数据库）"""

    def __init__(self, config: dict, board_type: str):
        """
        初始化数据库连接

        Args:
            config: 数据库配置字典，包含host, port, user, password等
            board_type: 板块类型（同花顺行业/概念/地域）
        """
        if board_type not in BOARD_CONFIGS:
            raise ValueError(f"不支持的板块类型: {board_type}，必须是：{list(BOARD_CONFIGS.keys())}")

        self.board_type = board_type
        self.database_name = BOARD_CONFIGS[board_type]['database']
        self.config = config
        self.connection = None
        self._in_transaction = False

        # 建立数据库连接
        self._connect()

    def _connect(self):
        """建立数据库连接"""
        try:
            self.connection = pymysql.connect(
                host=self.config.get('host', 'localhost'),
                port=self.config.get('port', 3306),
                user=self.config.get('user', 'root'),
                password=self.config.get('password', ''),
                database=self.database_name,
                charset=self.config.get('charset', 'utf8mb4'),
                connect_timeout=self.config.get('connection_timeout', 5),
                cursorclass=DictCursor,
                autocommit=False  # 手动控制事务
            )
            logger.info(f"✓ MySQL连接成功: {self.config['host']}:{self.config['port']}/{self.database_name}")

        except pymysql.err.OperationalError as e:
            # 数据库不存在
            if e.args[0] == 1049:
                logger.error(f"✗ 数据库 {self.database_name} 不存在，请先执行 init_databases.sql 初始化")
                raise Exception(f"数据库未初始化，请执行: mysql -u root -p < init_databases.sql")
            else:
                logger.error(f"✗ MySQL连接失败: {e}")
                raise

        except Exception as e:
            logger.error(f"✗ MySQL连接失败: {e}")
            raise

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

    def create_batch(self) -> int:
        """
        创建新的抓取批次

        Returns:
            批次ID: 新创建的批次ID
        """
        try:
            with self.connection.cursor() as cursor:
                sql = """
                    INSERT INTO `爬取记录` (`抓取时间`, `执行状态`)
                    VALUES (NOW(), '进行中')
                """
                cursor.execute(sql)
                self.connection.commit()
                batch_id = cursor.lastrowid
                logger.info(f"✓ 创建批次 #{batch_id} (类型: {self.board_type})")
                return batch_id
        except Exception as e:
            logger.error(f"创建批次失败: {e}")
            raise

    def update_batch_status(self, batch_id: int, status: str,
                           total_boards: int = None, total_stocks: int = None,
                           elapsed_seconds: float = None, error_message: str = None):
        """
        更新批次状态

        Args:
            batch_id: 批次ID
            status: 状态 (进行中/成功/失败)
            total_boards: 板块总数
            total_stocks: 股票总数
            elapsed_seconds: 耗时（秒）
            error_message: 错误信息（失败时）
        """
        try:
            with self.connection.cursor() as cursor:
                sql = """
                    UPDATE `爬取记录`
                    SET `执行状态` = %s,
                        `结束时间` = NOW(),
                        `板块总数` = COALESCE(%s, `板块总数`),
                        `股票总数` = COALESCE(%s, `股票总数`),
                        `爬取耗时秒数` = COALESCE(%s, `爬取耗时秒数`),
                        `错误信息` = %s
                    WHERE `批次ID` = %s
                """
                cursor.execute(sql, (status, total_boards, total_stocks, elapsed_seconds, error_message, batch_id))
                self.connection.commit()
                logger.info(f"✓ 批次 #{batch_id} 状态更新为: {status}")
        except Exception as e:
            logger.error(f"更新批次状态失败: {e}")
            raise

    def insert_boards(self, batch_id: int, boards: List[Dict]):
        """
        批量插入板块数据

        Args:
            batch_id: 批次ID
            boards: 板块数据列表 [{board_name, source_url, driving_event, stock_count}, ...]
        """
        if not boards:
            return

        try:
            with self.connection.cursor() as cursor:
                sql = """
                    INSERT INTO `板块信息`
                    (`批次ID`, `板块名称`, `来源链接`, `驱动事件`, `成分股数量`)
                    VALUES (%s, %s, %s, %s, %s)
                """
                values = [
                    (batch_id, b['board_name'], b.get('source_url'),
                     b.get('driving_event'), b.get('stock_count'))
                    for b in boards
                ]
                cursor.executemany(sql, values)

                if not self._in_transaction:
                    self.connection.commit()

                logger.info(f"✓ 插入 {len(boards)} 条板块数据")
        except Exception as e:
            logger.error(f"插入板块数据失败: {e}")
            raise

    def insert_stocks(self, batch_id: int, stocks: List[Dict]):
        """
        批量插入股票数据

        Args:
            batch_id: 批次ID
            stocks: 股票数据列表 [{board_name, stock_code, stock_name, sequence_num}, ...]
        """
        if not stocks:
            return

        try:
            with self.connection.cursor() as cursor:
                sql = """
                    INSERT INTO `成分股`
                    (`批次ID`, `板块名称`, `股票代码`, `股票名称`, `原始序号`)
                    VALUES (%s, %s, %s, %s, %s)
                """
                values = [
                    (batch_id, s['board_name'], s['stock_code'],
                     s['stock_name'], s.get('sequence_num'))
                    for s in stocks
                ]
                cursor.executemany(sql, values)

                if not self._in_transaction:
                    self.connection.commit()

                logger.info(f"✓ 插入 {len(stocks)} 条股票数据")
        except Exception as e:
            logger.error(f"插入股票数据失败: {e}")
            raise

    def validate_batch_integrity(self, batch_id: int) -> tuple[bool, str]:
        """
        验证批次数据完整性

        检查项：
        1. 板块-股票一致性：确保每个板块都有股票数据

        Args:
            batch_id: 批次ID

        Returns:
            (is_valid, error_message): 验证结果和错误信息
        """
        try:
            with self.connection.cursor() as cursor:
                # 检查：查找没有股票数据的板块
                sql_orphan_boards = """
                    SELECT b.`板块名称`
                    FROM `板块信息` b
                    LEFT JOIN `成分股` s
                        ON s.`批次ID` = b.`批次ID` AND s.`板块名称` = b.`板块名称`
                    WHERE b.`批次ID` = %s
                    GROUP BY b.`板块名称`
                    HAVING COUNT(s.`记录ID`) = 0
                """
                cursor.execute(sql_orphan_boards, (batch_id,))
                orphan_boards = cursor.fetchall()

                if orphan_boards:
                    board_names = [b['板块名称'] for b in orphan_boards]
                    error_msg = f"发现 {len(orphan_boards)} 个板块没有股票数据: {', '.join(board_names[:5])}"
                    if len(orphan_boards) > 5:
                        error_msg += f" 等（共{len(orphan_boards)}个）"
                    logger.error(f"✗ 数据完整性校验失败: {error_msg}")
                    return (False, error_msg)

                logger.info(f"✓ 批次 #{batch_id} 数据完整性校验通过")
                return (True, None)

        except Exception as e:
            error_msg = f"数据完整性校验异常: {e}"
            logger.error(error_msg)
            return (False, error_msg)

    def delete_batch_data(self, batch_id: int):
        """
        删除批次的所有数据（用于清理不完整数据）

        Args:
            batch_id: 批次ID
        """
        try:
            with self.connection.cursor() as cursor:
                # 外键级联删除会自动删除关联的板块信息和成分股
                sql = "DELETE FROM `爬取记录` WHERE `批次ID` = %s"
                cursor.execute(sql, (batch_id,))
                self.connection.commit()
                logger.info(f"✓ 删除批次 #{batch_id} 的所有数据")
        except Exception as e:
            logger.error(f"删除批次数据失败: {e}")
            raise

    def get_latest_batch_id(self) -> Optional[int]:
        """获取最新的批次ID"""
        try:
            with self.connection.cursor() as cursor:
                sql = "SELECT MAX(`批次ID`) as max_id FROM `爬取记录`"
                cursor.execute(sql)
                result = cursor.fetchone()
                return result['max_id'] if result and result['max_id'] else None
        except Exception as e:
            logger.error(f"获取最新批次ID失败: {e}")
            return None

    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            logger.info(f"数据库连接已关闭: {self.database_name}")
