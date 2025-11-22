# 同花顺板块数据爬虫 v2.0.0

自动爬取同花顺股票板块数据，支持同花顺行业、概念、地域三大分类，数据存储到MySQL或CSV文件。

## 🎉 v2.0.0 重大更新

- **三数据库架构**: 同花顺行业、概念、地域各用独立数据库，互不干扰
- **全中文化**: 所有数据库名、表名、字段名全部使用中文
- **可选抓取**: 支持只抓取需要的板块类型（配置文件或全抓）
- **简化设计**: 从7张表精简到3张表（爬取记录 + 板块信息 + 成分股）
- **性能追踪**: 自动记录每次抓取耗时
- **不向后兼容**: 完全重构，需重新初始化数据库

## 主要功能

- 自动登录同花顺账号（支持滑块验证码识别）
- 爬取三类板块数据：同花顺行业（90个）、概念（380个）、地域（31个）
- 通过Socket代理实现IP轮换，避免被封
- 多线程并发爬取，速度快
- 数据自动去重，保证质量
- MySQL三数据库存储，按板块类型分离
- CSV文件备份，按板块类型和日期归档
- 可选抓取：只抓需要的板块类型

## 安装

```bash
# 1. 克隆项目
git clone https://github.com/cdntoy/10jqka_spider.git
cd 10jqka_spider

# 2. 安装Python依赖
pip3 install -r requirements.txt

# 3. 编译Socket代理
make -C socket release

# 4. 初始化数据库（v2.0.0新架构）
mysql -u root -p < init_databases.sql

# 5. 配置
vim config.toml  # 修改数据库密码和启用的板块类型
```

## 使用

### 板块类型编号
- **1** = 同花顺行业板块
- **2** = 概念板块
- **3** = 地域板块

### 使用示例

```bash
# 推荐：使用Socket代理模式，抓取全部板块
python3 main.py -u 用户名 -p 密码 -s

# 只抓取概念板块
python3 main.py -u 用户名 -p 密码 -s -B 2

# 只抓取同花顺行业板块
python3 main.py -u 用户名 -p 密码 -s -B 1

# 抓取多个板块（概念 + 地域）
python3 main.py -u 用户名 -p 密码 -s -B 2 3

# 抓取多个板块（行业 + 概念）
python3 main.py -u 用户名 -p 密码 -s -B 1 2

# 测试：本地直连（容易被限制，不推荐）
python3 main.py -u 用户名 -p 密码 -d
```

## 命令参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-u` | 同花顺用户名 | 必填 |
| `-p` | 同花顺密码 | 必填 |
| `-s` | 启用Socket代理模式 | 关闭 |
| `-d` | 本地直连模式 | 关闭 |
| `-B` | 指定抓取板块编号（1=行业 2=概念 3=地域，可多选） | 配置文件 |
| `-H` | 线程数 | 16 |
| `-b` | 请求间隔（秒） | 1 |
| `-t` | 超时时间（秒） | 10 |
| `-P` | Socket代理端口 | 8080 |

注意：
- `-s` 和 `-d` 不能同时使用，推荐使用Socket代理模式
- `-B` 参数会覆盖配置文件中的 `enabled_boards` 设置
- 不指定 `-B` 时，使用配置文件中的设置
- 程序启动时会显示板块类型说明和本次抓取的板块

## 配置文件

编辑 `config.toml` 选择要抓取的板块类型：

```toml
[scraper]
# 可选值: "同花顺行业", "概念", "地域"
# 只抓概念板块示例：
enabled_boards = ["概念"]

# 抓取全部（默认）：
enabled_boards = ["同花顺行业", "概念", "地域"]
```

## 数据查询

### CSV文件（v2.0.0新结构）

数据按板块类型分文件夹保存：

```
result/
├── 同花顺行业板块/
│   └── 20251123/
│       ├── 板块信息_20251123090000.csv
│       └── 成分股_20251123090000.csv
├── 概念板块/
│   └── 20251123/
│       ├── 板块信息_20251123090000.csv
│       └── 成分股_20251123090000.csv
└── 地域板块/
    └── 20251123/
        ├── 板块信息_20251123090000.csv
        └── 成分股_20251123090000.csv
```

### MySQL数据库（v2.0.0新架构）

三个独立数据库，每个包含3张表：

**数据库**:
- `同花顺行业板块`
- `概念板块`
- `地域板块`

**表结构**（每个数据库相同）:
- `爬取记录` - 批次管理，记录抓取时间、耗时、状态
- `板块信息` - 板块基本信息（名称、链接、驱动事件、成分股数量）
- `成分股` - 股票-板块成员关系（股票代码、名称、序号）

常用查询示例：

```sql
-- 查看最新批次的概念板块统计
USE `概念板块`;
SELECT b.`板块名称`, COUNT(s.`股票代码`) as 股票数量
FROM `板块信息` b
JOIN `成分股` s ON s.`批次ID` = b.`批次ID` AND s.`板块名称` = b.`板块名称`
WHERE b.`批次ID` = (SELECT MAX(`批次ID`) FROM `爬取记录`)
GROUP BY b.`板块名称`
ORDER BY 股票数量 DESC
LIMIT 10;

-- 查看爬取历史
USE `同花顺行业板块`;
SELECT `批次ID`, `抓取时间`, `板块总数`, `股票总数`, `爬取耗时秒数`, `执行状态`
FROM `爬取记录`
ORDER BY `抓取时间` DESC
LIMIT 10;

-- 查询"人工智能"板块的成分股
USE `概念板块`;
SELECT s.`股票代码`, s.`股票名称`, s.`原始序号`
FROM `成分股` s
WHERE s.`板块名称` = '人工智能'
  AND s.`批次ID` = (SELECT MAX(`批次ID`) FROM `爬取记录`)
ORDER BY s.`原始序号`;
```

## 定时任务

使用crontab设置每天自动运行：

```bash
# 编辑定时任务
crontab -e

# 每天早上9点运行
0 9 * * * cd /path/to/10jqka_spider && python3 main.py -u 用户名 -p 密码 -s >> /var/log/10jqka.log 2>&1
```

## 工作原理

程序通过本地Socket代理访问同花顺网站：

```
爬虫 → Socket代理(本地8080端口) → 百度CDN → 同花顺网站
```

Socket代理会自动切换CDN节点IP，避免被封禁。每次请求间隔随机延迟（高斯分布），模拟真实用户行为。

## 项目结构

```
10jqka_spider/
├── main.py              # 主程序（v2.0.0完全重写）
├── cookies.py           # 登录和Cookie管理
├── encrypt.py           # 加密算法（RSA/AES）
├── database.py          # 数据库操作（v2.0.0完全重写）
├── socket_manager.py    # Socket代理管理
├── v_new.js             # 反爬虫Cookie生成
├── origin.txt           # 设备指纹
├── config.toml          # 配置文件（v2.0.0新增enabled_boards）
├── init_databases.sql   # 数据库初始化脚本（v2.0.0新增）
└── socket/              # Socket代理源码（C语言）
    ├── thread_socket.c
    ├── driver.c
    ├── Makefile
    └── thread_socket    # 编译后的可执行文件
```

## 依赖包

- `requests` - HTTP请求
- `pycryptodome` - 加密算法
- `ddddocr` - 验证码识别
- `pyexecjs` - 执行JavaScript
- `pymysql` - MySQL数据库
- `toml` - 配置文件解析

## v2.0.0 迁移指南

**重要**: v2.0.0 不向后兼容，需要重新初始化数据库。

### 从 v1.x 升级步骤：

1. **备份旧数据**（如需保留）:
   ```bash
   mysqldump -u root -p 10jqka_bankuai > backup_v1.sql
   ```

2. **初始化新数据库**:
   ```bash
   mysql -u root -p < init_databases.sql
   ```

3. **更新配置文件**:
   - 编辑 `config.toml`，添加 `enabled_boards` 配置
   - 数据库连接保持不变（仍连接MySQL服务器，但程序会自动连接3个数据库）

4. **首次运行**:
   ```bash
   python3 main.py -u 用户名 -p 密码 -s
   ```

### v2.0.0 主要变化：

- ❌ 移除：7张表（scrape_batches, board_snapshots, stock_board_memberships等）
- ✅ 新增：3个独立数据库，每个3张表
- ❌ 移除：变化追踪功能（change_summary, board_changes, stock_changes）
- ✅ 新增：可选抓取（enabled_boards配置）
- ✅ 新增：CSV文件按板块类型分文件夹
- ✅ 新增：自动记录抓取耗时

## 注意事项

本项目仅供学习研究使用，请遵守相关法律法规。
