-- ============================================
-- 10jqka板块爬虫数据库初始化脚本 v2.0.0
-- 日期: 2025-11-23
-- 说明: 创建3个独立数据库，每库3张表，全中文化
-- ============================================

-- ============================================
-- 数据库1: 同花顺行业板块
-- ============================================
CREATE DATABASE IF NOT EXISTS `同花顺行业板块`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `同花顺行业板块`;

-- 表1: 爬取记录（批次管理）
CREATE TABLE IF NOT EXISTS `爬取记录` (
  `批次ID` INT AUTO_INCREMENT PRIMARY KEY COMMENT '批次唯一标识（自增）',
  `抓取时间` DATETIME NOT NULL COMMENT '本次抓取开始时间',
  `结束时间` DATETIME DEFAULT NULL COMMENT '本次抓取结束时间',
  `爬取耗时秒数` DECIMAL(10,2) DEFAULT NULL COMMENT '总耗时（秒）',
  `板块总数` INT DEFAULT 0 COMMENT '本次抓取的板块总数',
  `股票总数` INT DEFAULT 0 COMMENT '本次抓取的股票总数（去重）',
  `执行状态` ENUM('进行中', '成功', '失败') DEFAULT '进行中' COMMENT '执行状态',
  `错误信息` TEXT DEFAULT NULL COMMENT '失败时的错误信息',
  INDEX `idx_抓取时间` (`抓取时间`),
  INDEX `idx_执行状态` (`执行状态`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='爬取任务批次记录表';

-- 表2: 板块信息
CREATE TABLE IF NOT EXISTS `板块信息` (
  `记录ID` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录唯一标识（自增）',
  `批次ID` INT NOT NULL COMMENT '关联的批次ID',
  `板块名称` VARCHAR(100) NOT NULL COMMENT '板块名称',
  `来源链接` VARCHAR(255) DEFAULT NULL COMMENT '10jqka来源URL',
  `驱动事件` VARCHAR(255) DEFAULT NULL COMMENT '领涨股等驱动因素',
  `成分股数量` INT DEFAULT NULL COMMENT '该板块的成分股总数',
  FOREIGN KEY (`批次ID`) REFERENCES `爬取记录`(`批次ID`) ON DELETE CASCADE,
  INDEX `idx_批次ID` (`批次ID`),
  INDEX `idx_板块名称` (`板块名称`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='板块基本信息表';

-- 表3: 成分股
CREATE TABLE IF NOT EXISTS `成分股` (
  `记录ID` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录唯一标识（自增）',
  `批次ID` INT NOT NULL COMMENT '关联的批次ID',
  `板块名称` VARCHAR(100) NOT NULL COMMENT '所属板块名称',
  `股票代码` VARCHAR(10) NOT NULL COMMENT '股票代码（如600000）',
  `股票名称` VARCHAR(100) NOT NULL COMMENT '股票名称（如浦发银行）',
  `原始序号` INT DEFAULT NULL COMMENT '在10jqka页面的原始排序',
  FOREIGN KEY (`批次ID`) REFERENCES `爬取记录`(`批次ID`) ON DELETE CASCADE,
  INDEX `idx_批次ID` (`批次ID`),
  INDEX `idx_股票代码` (`股票代码`),
  INDEX `idx_板块名称` (`板块名称`),
  INDEX `idx_批次板块股票` (`批次ID`, `板块名称`, `股票代码`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='板块成分股明细表';

-- ============================================
-- 数据库2: 概念板块
-- ============================================
CREATE DATABASE IF NOT EXISTS `概念板块`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `概念板块`;

-- 复制同花顺行业板块的表结构
CREATE TABLE IF NOT EXISTS `爬取记录` (
  `批次ID` INT AUTO_INCREMENT PRIMARY KEY COMMENT '批次唯一标识（自增）',
  `抓取时间` DATETIME NOT NULL COMMENT '本次抓取开始时间',
  `结束时间` DATETIME DEFAULT NULL COMMENT '本次抓取结束时间',
  `爬取耗时秒数` DECIMAL(10,2) DEFAULT NULL COMMENT '总耗时（秒）',
  `板块总数` INT DEFAULT 0 COMMENT '本次抓取的板块总数',
  `股票总数` INT DEFAULT 0 COMMENT '本次抓取的股票总数（去重）',
  `执行状态` ENUM('进行中', '成功', '失败') DEFAULT '进行中' COMMENT '执行状态',
  `错误信息` TEXT DEFAULT NULL COMMENT '失败时的错误信息',
  INDEX `idx_抓取时间` (`抓取时间`),
  INDEX `idx_执行状态` (`执行状态`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='爬取任务批次记录表';

CREATE TABLE IF NOT EXISTS `板块信息` (
  `记录ID` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录唯一标识（自增）',
  `批次ID` INT NOT NULL COMMENT '关联的批次ID',
  `板块名称` VARCHAR(100) NOT NULL COMMENT '板块名称',
  `来源链接` VARCHAR(255) DEFAULT NULL COMMENT '10jqka来源URL',
  `驱动事件` VARCHAR(255) DEFAULT NULL COMMENT '领涨股等驱动因素',
  `成分股数量` INT DEFAULT NULL COMMENT '该板块的成分股总数',
  FOREIGN KEY (`批次ID`) REFERENCES `爬取记录`(`批次ID`) ON DELETE CASCADE,
  INDEX `idx_批次ID` (`批次ID`),
  INDEX `idx_板块名称` (`板块名称`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='板块基本信息表';

CREATE TABLE IF NOT EXISTS `成分股` (
  `记录ID` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录唯一标识（自增）',
  `批次ID` INT NOT NULL COMMENT '关联的批次ID',
  `板块名称` VARCHAR(100) NOT NULL COMMENT '所属板块名称',
  `股票代码` VARCHAR(10) NOT NULL COMMENT '股票代码（如600000）',
  `股票名称` VARCHAR(100) NOT NULL COMMENT '股票名称（如浦发银行）',
  `原始序号` INT DEFAULT NULL COMMENT '在10jqka页面的原始排序',
  FOREIGN KEY (`批次ID`) REFERENCES `爬取记录`(`批次ID`) ON DELETE CASCADE,
  INDEX `idx_批次ID` (`批次ID`),
  INDEX `idx_股票代码` (`股票代码`),
  INDEX `idx_板块名称` (`板块名称`),
  INDEX `idx_批次板块股票` (`批次ID`, `板块名称`, `股票代码`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='板块成分股明细表';

-- ============================================
-- 数据库3: 地域板块
-- ============================================
CREATE DATABASE IF NOT EXISTS `地域板块`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `地域板块`;

-- 复制同花顺行业板块的表结构
CREATE TABLE IF NOT EXISTS `爬取记录` (
  `批次ID` INT AUTO_INCREMENT PRIMARY KEY COMMENT '批次唯一标识（自增）',
  `抓取时间` DATETIME NOT NULL COMMENT '本次抓取开始时间',
  `结束时间` DATETIME DEFAULT NULL COMMENT '本次抓取结束时间',
  `爬取耗时秒数` DECIMAL(10,2) DEFAULT NULL COMMENT '总耗时（秒）',
  `板块总数` INT DEFAULT 0 COMMENT '本次抓取的板块总数',
  `股票总数` INT DEFAULT 0 COMMENT '本次抓取的股票总数（去重）',
  `执行状态` ENUM('进行中', '成功', '失败') DEFAULT '进行中' COMMENT '执行状态',
  `错误信息` TEXT DEFAULT NULL COMMENT '失败时的错误信息',
  INDEX `idx_抓取时间` (`抓取时间`),
  INDEX `idx_执行状态` (`执行状态`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='爬取任务批次记录表';

CREATE TABLE IF NOT EXISTS `板块信息` (
  `记录ID` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录唯一标识（自增）',
  `批次ID` INT NOT NULL COMMENT '关联的批次ID',
  `板块名称` VARCHAR(100) NOT NULL COMMENT '板块名称',
  `来源链接` VARCHAR(255) DEFAULT NULL COMMENT '10jqka来源URL',
  `驱动事件` VARCHAR(255) DEFAULT NULL COMMENT '领涨股等驱动因素',
  `成分股数量` INT DEFAULT NULL COMMENT '该板块的成分股总数',
  FOREIGN KEY (`批次ID`) REFERENCES `爬取记录`(`批次ID`) ON DELETE CASCADE,
  INDEX `idx_批次ID` (`批次ID`),
  INDEX `idx_板块名称` (`板块名称`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='板块基本信息表';

CREATE TABLE IF NOT EXISTS `成分股` (
  `记录ID` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录唯一标识（自增）',
  `批次ID` INT NOT NULL COMMENT '关联的批次ID',
  `板块名称` VARCHAR(100) NOT NULL COMMENT '所属板块名称',
  `股票代码` VARCHAR(10) NOT NULL COMMENT '股票代码（如600000）',
  `股票名称` VARCHAR(100) NOT NULL COMMENT '股票名称（如浦发银行）',
  `原始序号` INT DEFAULT NULL COMMENT '在10jqka页面的原始排序',
  FOREIGN KEY (`批次ID`) REFERENCES `爬取记录`(`批次ID`) ON DELETE CASCADE,
  INDEX `idx_批次ID` (`批次ID`),
  INDEX `idx_股票代码` (`股票代码`),
  INDEX `idx_板块名称` (`板块名称`),
  INDEX `idx_批次板块股票` (`批次ID`, `板块名称`, `股票代码`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='板块成分股明细表';

-- ============================================
-- 初始化完成
-- ============================================
SELECT '数据库初始化完成！' AS 状态,
       '已创建3个数据库：同花顺行业板块、概念板块、地域板块' AS 说明,
       '每个库包含3张表：爬取记录、板块信息、成分股' AS 详情;
