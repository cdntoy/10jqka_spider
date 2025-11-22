-- ============================================
-- 10jqka爬虫数据库表结构
-- 创建时间: 2025-11-22
-- 说明: 用于存储同花顺板块和股票快照数据
-- ============================================

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS stock_spider DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE stock_spider;

-- ============================================
-- 1. 抓取批次表
-- 用途: 记录每次抓取任务的元数据和状态
-- ============================================
CREATE TABLE IF NOT EXISTS scrape_batches (
    batch_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '批次ID',
    board_type ENUM('thshy', 'gn', 'dy') NOT NULL COMMENT '板块类型: thshy=同花顺行业, gn=概念, dy=地域',
    status ENUM('running', 'success', 'failed') DEFAULT 'running' COMMENT '执行状态: running=进行中, success=成功, failed=失败',
    total_boards INT DEFAULT 0 COMMENT '抓取到的板块总数',
    total_stocks INT DEFAULT 0 COMMENT '抓取到的股票总数',
    started_at DATETIME NOT NULL COMMENT '开始时间',
    completed_at DATETIME DEFAULT NULL COMMENT '完成时间',
    error_message TEXT DEFAULT NULL COMMENT '错误信息（失败时记录）',
    INDEX idx_status_type (status, board_type),
    INDEX idx_started_at (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='抓取批次记录表';

-- ============================================
-- 2. 板块快照表
-- 用途: 存储每次抓取的板块信息快照
-- ============================================
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='板块快照表';

-- ============================================
-- 3. 股票快照表
-- 用途: 存储每次抓取的股票信息快照
-- ============================================
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票快照表';

-- ============================================
-- 4. 变化统计摘要表
-- 用途: 记录每次抓取相对上次的变化统计
-- ============================================
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='变化统计摘要表';

-- ============================================
-- 5. 板块变化明细表
-- 用途: 记录具体新增/删除了哪些板块
-- ============================================
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='板块变化明细表';

-- ============================================
-- 6. 股票变化明细表
-- 用途: 记录具体新增/删除了哪些股票
-- ============================================
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票变化明细表';

-- ============================================
-- 常用查询示例（供参考）
-- ============================================

-- 查询最近一次成功的抓取批次
-- SELECT * FROM scrape_batches WHERE status = 'success' ORDER BY completed_at DESC LIMIT 1;

-- 查询某次抓取新增了哪些板块
-- SELECT board_name, source_url FROM board_changes WHERE summary_id = ? AND change_type = 'added';

-- 查询某次抓取删除了哪些股票
-- SELECT board_name, stock_code, stock_name FROM stock_changes WHERE summary_id = ? AND change_type = 'removed';

-- 查询某个板块的历史变化趋势
-- SELECT b.scrape_date, b.stock_count FROM board_snapshots b WHERE b.board_name = '多元金融' ORDER BY b.scrape_date;

-- 统计每日抓取次数
-- SELECT DATE(started_at) as date, COUNT(*) as count FROM scrape_batches WHERE status = 'success' GROUP BY DATE(started_at);
