# MySQL存储功能使用指南

本指南介绍如何使用10jqka爬虫的MySQL存储功能。

## 📋 目录

- [快速开始](#快速开始)
- [功能特性](#功能特性)
- [配置说明](#配置说明)
- [数据库初始化](#数据库初始化)
- [使用示例](#使用示例)
- [数据查询](#数据查询)
- [故障排查](#故障排查)

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install pymysql toml
```

### 2. 初始化数据库

```bash
# 登录MySQL
mysql -u root -p

# 创建数据库并导入表结构
source schema.sql
```

### 3. 配置文件

编辑 `config.toml` 修改数据库连接信息：

```toml
[database]
enabled = true              # 启用MySQL
host = "localhost"
port = 3306
user = "root"
password = "your_password"  # 修改为实际密码
database = "stock_spider"
```

### 4. 运行爬虫

```bash
# 使用Socket代理模式（推荐）
python3 main.py -u 用户名 -p 密码 -s

# 或使用本地直连模式（测试）
python3 main.py -u 用户名 -p 密码 -d
```

---

## ✨ 功能特性

### 1. 自动存储管理

- **MySQL主存储**：数据自动保存到MySQL数据库
- **CSV备份**：可选同时生成CSV文件备份
- **自动降级**：MySQL连接失败时自动切换到CSV模式
- **完整历史**：每次抓取生成独立快照，支持历史追溯

### 2. Socket进程管理

- **自动启动**：程序启动时自动启动Socket代理
- **健康监控**：后台监控Socket进程，异常时自动重启
- **优雅退出**：程序退出时确保Socket进程也被关闭
- **端口检测**：启动前检测端口占用，自动清理僵尸进程

### 3. 变化统计

每次抓取完成后自动生成变化摘要：

- **数量统计**：板块和股票的新增/减少数量
- **具体明细**：详细记录哪些板块和股票发生了变化
- **变化率**：计算相对上次抓取的变化百分比
- **控制台输出**：实时显示变化摘要

示例输出：

```
============================================================
                      本次抓取摘要
============================================================
批次ID: 123
时间: 2025-11-22 18:30:45
------------------------------------------------------------
板块变化: 新增 3 个, 减少 1 个
股票变化: 新增 125 只, 减少 58 只
总体变化率: 2.35%
============================================================
```

### 4. 优雅中断

- **Ctrl+C响应**：所有操作支持Ctrl+C中断
- **数据清理**：中断时自动回滚不完整数据
- **资源释放**：确保数据库连接和Socket进程正确关闭

### 5. 并发优化

- **可配置线程数**：默认32线程（Socket模式）
- **并发控制**：内置信号量限制最大并发连接数
- **请求间隔**：支持自定义请求间隔避免封禁

---

## ⚙️ 配置说明

### config.toml 完整说明

```toml
[database]
# 是否启用MySQL存储（false时仅保存CSV）
enabled = true
# 数据库主机地址
host = "localhost"
# 数据库端口
port = 3306
# 数据库用户名
user = "root"
# 数据库密码
password = "your_password"
# 数据库名称
database = "stock_spider"
# 字符集
charset = "utf8mb4"
# 连接超时时间（秒），超时则降级到CSV模式
connection_timeout = 5

[socket_proxy]
# 是否启用Socket代理（推荐）
enabled = true
# Socket代理监听端口
port = 8080
# 目标服务器IP（百度CDN）
server_ip = "110.242.70.68"
# 目标服务器端口
server_port = 443
# 以守护进程模式运行
daemon_mode = true
# Socket异常时自动重启
auto_restart = true
# 健康检查间隔（秒）
health_check_interval = 5
# 启动超时时间（秒）
startup_timeout = 10

[scraper]
# 是否保存CSV备份（即使MySQL可用）
enable_csv_backup = true
# 请求间隔时间（秒）
interval_seconds = 1
# 最大重试次数
max_retries = 20
# 并发抓取线程数（Socket模式建议32）
thread_count = 32

[path]
# CSV文件保存路径
result_dir = "result"
# Socket代理可执行文件路径
socket_binary = "./socket/thread_socket"
# Socket代理PID文件路径
socket_pid_file = "socket_proxy.pid"
```

### 命令行参数

命令行参数会覆盖配置文件：

```bash
python3 main.py \
  -u 用户名 \                    # 必需：登录用户名
  -p 密码 \                      # 必需：登录密码
  -s \                          # 可选：启用Socket代理
  -P 8080 \                     # 可选：Socket代理端口
  -H 32 \                       # 可选：并发线程数
  -b 1 \                        # 可选：请求间隔（秒）
  -t 10 \                       # 可选：请求超时（秒）
  -c config.toml                # 可选：配置文件路径
```

---

## 💾 数据库初始化

### 方式一：使用SQL脚本

```bash
mysql -u root -p < schema.sql
```

### 方式二：手动执行

```bash
mysql -u root -p
```

```sql
source /path/to/10jqka_spider/schema.sql
```

### 验证表结构

```sql
USE stock_spider;
SHOW TABLES;
```

应该看到6张表：

- `scrape_batches` - 抓取批次表
- `board_snapshots` - 板块快照表
- `stock_snapshots` - 股票快照表
- `change_summary` - 变化统计摘要表
- `board_changes` - 板块变化明细表
- `stock_changes` - 股票变化明细表

---

## 📖 使用示例

### 示例1：仅使用MySQL（不生成CSV）

```toml
# config.toml
[database]
enabled = true

[scraper]
enable_csv_backup = false  # 关闭CSV备份
```

### 示例2：MySQL + CSV双重备份

```toml
# config.toml
[database]
enabled = true

[scraper]
enable_csv_backup = true   # 保留CSV备份
```

### 示例3：仅使用CSV（禁用MySQL）

```toml
# config.toml
[database]
enabled = false

[scraper]
enable_csv_backup = true
```

### 示例4：高并发Socket模式

```toml
# config.toml
[socket_proxy]
enabled = true
port = 8080

[scraper]
thread_count = 32  # 32线程并发
interval_seconds = 0.5
```

### 示例5：保守直连模式

```bash
# 命令行
python3 main.py -u 用户名 -p 密码 -d -H 8
```

---

## 🔍 数据查询

### 查询最近一次抓取

```sql
SELECT * FROM scrape_batches
WHERE status = 'success'
ORDER BY completed_at DESC
LIMIT 1;
```

### 查询某次抓取的板块列表

```sql
SELECT board_name, stock_count
FROM board_snapshots
WHERE batch_id = 123;
```

### 查询某次抓取新增了哪些板块

```sql
SELECT board_name, source_url
FROM board_changes
WHERE summary_id = 45
  AND change_type = 'added';
```

### 查询某次抓取删除了哪些股票

```sql
SELECT board_name, stock_code, stock_name
FROM stock_changes
WHERE summary_id = 45
  AND change_type = 'removed';
```

### 查询某个板块的历史变化趋势

```sql
SELECT scrape_date, stock_count
FROM board_snapshots
WHERE board_name = '多元金融'
ORDER BY scrape_date;
```

### 统计每日抓取次数

```sql
SELECT DATE(started_at) as date, COUNT(*) as count
FROM scrape_batches
WHERE status = 'success'
GROUP BY DATE(started_at);
```

### 查询变化率超过10%的抓取

```sql
SELECT b.batch_id, b.board_type, b.completed_at, s.change_rate
FROM scrape_batches b
JOIN change_summary s ON b.batch_id = s.batch_id
WHERE s.change_rate > 10
ORDER BY s.change_rate DESC;
```

---

## 🔧 故障排查

### 问题1：MySQL连接失败

**症状：**

```
⚠ MySQL连接失败: (2003, "Can't connect to MySQL server...")
降级到CSV存储模式
```

**解决方案：**

1. 检查MySQL服务是否启动：`systemctl status mysql`
2. 检查 `config.toml` 中的连接信息是否正确
3. 检查数据库是否存在：`SHOW DATABASES;`
4. 检查用户权限：`GRANT ALL PRIVILEGES ON stock_spider.* TO 'root'@'localhost';`

### 问题2：Socket代理启动失败

**症状：**

```
Socket代理启动失败: Socket代理程序不存在: ./socket/thread_socket
降级到本地直连模式
```

**解决方案：**

1. 检查Socket代理可执行文件是否存在：`ls -l socket/thread_socket`
2. 检查是否有执行权限：`chmod +x socket/thread_socket`
3. 或使用直连模式：`python3 main.py -u 用户名 -p 密码 -d`

### 问题3：端口被占用

**症状：**

```
端口 8080 被进程 12345 占用，正在终止...
```

**解决方案：**

程序会自动清理，如需手动清理：

```bash
# 查找占用端口的进程
lsof -i :8080

# 终止进程
kill -9 <PID>
```

### 问题4：数据不完整（程序中断）

**症状：**

数据库中有 `status='running'` 的批次记录。

**解决方案：**

程序启动时会自动清理僵尸批次。或手动清理：

```sql
DELETE FROM scrape_batches
WHERE status = 'running'
  AND started_at < DATE_SUB(NOW(), INTERVAL 1 HOUR);
```

### 问题5：没有生成变化统计

**症状：**

`change_summary` 表为空。

**可能原因：**

- 首次运行（无历史数据对比）
- MySQL模式未启用
- 批次状态为 `failed`

---

## 📊 数据迁移（可选）

如果有历史CSV数据需要导入MySQL，可以编写导入脚本：

```python
#!/usr/bin/env python3
import csv
import pymysql
from datetime import datetime

# 连接数据库
conn = pymysql.connect(
    host='localhost',
    user='root',
    password='your_password',
    database='stock_spider',
    charset='utf8mb4'
)

cursor = conn.cursor()

# 创建批次
cursor.execute("""
    INSERT INTO scrape_batches (board_type, status, started_at, completed_at)
    VALUES ('thshy', 'success', %s, %s)
""", (datetime.now(), datetime.now()))
batch_id = cursor.lastrowid

# 读取CSV并导入
with open('result/20251122/20251122170147_同花顺行业板块信息.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        cursor.execute("""
            INSERT INTO board_snapshots
            (batch_id, board_type, board_name, source_url, driving_event, stock_count, scrape_date)
            VALUES (%s, 'thshy', %s, %s, %s, %s, %s)
        """, (batch_id, row['板块名称'], row['来源链接'], row['驱动事件'],
              row['成分股量'], datetime.now().date()))

conn.commit()
conn.close()
```

---

## 📝 最佳实践

1. **生产环境推荐配置**：
   - 启用MySQL存储
   - 启用Socket代理
   - 开启CSV备份（双重保险）
   - 32线程并发

2. **定期维护**：
   - 定期备份MySQL数据库
   - 清理过期的CSV文件
   - 监控数据库大小

3. **安全建议**：
   - 不要将 `config.toml` 提交到版本控制
   - 使用环境变量管理敏感信息
   - 定期更换数据库密码

---

## 📞 支持

如有问题，请查看：

- 主文档：`README.md`
- 技术文档：`TECHNICAL.md`
- 问题反馈：GitHub Issues
