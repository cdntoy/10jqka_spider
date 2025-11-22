-- ============================================
-- 数据库迁移脚本: v1.7.6 → v1.7.7
-- 日期: 2025-11-23
-- ============================================

-- 使用说明：
-- 1. 备份现有数据库：mysqldump -u root -p stock_spider > backup_v1.7.6.sql
-- 2. 执行此迁移脚本：mysql -u root -p < migrate_v1.7.7.sql
-- 3. 更新config.toml中的database配置为"10jqka_bankuai"
-- 4. 重新编译socket代理：make -C socket release

-- ============================================
-- 步骤1：创建新数据库
-- ============================================
CREATE DATABASE IF NOT EXISTS `10jqka_bankuai`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ============================================
-- 步骤2：从旧库复制数据到新库
-- ============================================

-- 使用新库
USE `10jqka_bankuai`;

-- 复制scrape_batches表
CREATE TABLE IF NOT EXISTS scrape_batches LIKE stock_spider.scrape_batches;
INSERT INTO scrape_batches SELECT * FROM stock_spider.scrape_batches;

-- 复制board_snapshots表
CREATE TABLE IF NOT EXISTS board_snapshots LIKE stock_spider.board_snapshots;
INSERT INTO board_snapshots SELECT * FROM stock_spider.board_snapshots;

-- 复制stock_snapshots表（旧名称）并重命名为stock_board_memberships
CREATE TABLE IF NOT EXISTS stock_board_memberships LIKE stock_spider.stock_snapshots;
INSERT INTO stock_board_memberships SELECT * FROM stock_spider.stock_snapshots;

-- 修改表注释
ALTER TABLE stock_board_memberships COMMENT = '股票-板块成员关系表';

-- 复制change_summary表
CREATE TABLE IF NOT EXISTS change_summary LIKE stock_spider.change_summary;
INSERT INTO change_summary SELECT * FROM stock_spider.change_summary;

-- 复制board_changes表
CREATE TABLE IF NOT EXISTS board_changes LIKE stock_spider.board_changes;
INSERT INTO board_changes SELECT * FROM stock_spider.board_changes;

-- 复制stock_changes表
CREATE TABLE IF NOT EXISTS stock_changes LIKE stock_spider.stock_changes;
INSERT INTO stock_changes SELECT * FROM stock_spider.stock_changes;

-- 复制board_statistics表
CREATE TABLE IF NOT EXISTS board_statistics LIKE stock_spider.board_statistics;
INSERT INTO board_statistics SELECT * FROM stock_spider.board_statistics;

-- ============================================
-- 步骤3：验证数据完整性
-- ============================================
SELECT
    '数据迁移验证' AS 检查项,
    (SELECT COUNT(*) FROM stock_spider.scrape_batches) AS 旧库记录数,
    (SELECT COUNT(*) FROM `10jqka_bankuai`.scrape_batches) AS 新库记录数,
    CASE
        WHEN (SELECT COUNT(*) FROM stock_spider.scrape_batches) = (SELECT COUNT(*) FROM `10jqka_bankuai`.scrape_batches)
        THEN '✓ 一致'
        ELSE '✗ 不一致'
    END AS 状态;

SELECT
    '股票-板块关系表' AS 检查项,
    (SELECT COUNT(*) FROM stock_spider.stock_snapshots) AS 旧库记录数,
    (SELECT COUNT(*) FROM `10jqka_bankuai`.stock_board_memberships) AS 新库记录数,
    CASE
        WHEN (SELECT COUNT(*) FROM stock_spider.stock_snapshots) = (SELECT COUNT(*) FROM `10jqka_bankuai`.stock_board_memberships)
        THEN '✓ 一致'
        ELSE '✗ 不一致'
    END AS 状态;

-- ============================================
-- 步骤4：（可选）删除旧库
-- ============================================
-- 验证数据无误后，可执行以下命令删除旧库：
-- DROP DATABASE stock_spider;

-- 迁移完成提示
SELECT
    '迁移完成' AS 状态,
    '请更新config.toml中的database配置为"10jqka_bankuai"' AS 下一步操作;
