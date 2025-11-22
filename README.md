# 同花顺板块数据爬虫 v1.7.5

自动化爬取同花顺金融平台的股票板块数据（同花顺行业、概念、地域）。

## 功能特性

- 🔄 Socket代理IP轮换，绕过访问限制
- 🔐 自动登录，滑块验证码识别
- 📊 爬取三类板块：同花顺行业（90个）、概念（380个）、地域（31个）
- 🧵 多线程并发，高效爬取
- 💾 MySQL数据库自动建库，支持历史快照和变化追踪
- 📁 CSV格式备份，按日期归档
- 📈 变化分析工具，追踪每日板块和股票变化

## 快速安装

```bash
# 1. 克隆项目
git clone https://github.com/your-repo/10jqka_spider.git
cd 10jqka_spider

# 2. 安装Python依赖
pip3 install -r requirements.txt

# 3. 编译Socket代理（推荐使用Socket代理模式）
make -C socket release

# 4. 配置数据库（可选，使用MySQL存储）
# 编辑 config.toml 设置数据库密码
vim config.toml

# 5. 运行爬虫（首次运行会自动创建数据库和表）
python3 main.py -u 用户名 -p 密码 -s
```

**说明：**
- ✅ 数据库不存在时会自动创建（无需手动初始化）
- ✅ Socket代理已编译为release版本（优化性能）
- ✅ 支持CSV和MySQL双模式存储
- ✅ 数据库配置直接在config.toml中设置

## 快速开始

```bash
# Socket代理模式（推荐，自动IP轮换）
python3 main.py -u <用户名> -p <密码> -s

# 本地直连模式（仅测试，容易被限制）
python3 main.py -u <用户名> -p <密码> -d

# 高级用法：自定义线程数和间隔
python3 main.py -u <用户名> -p <密码> -s -H 32 -b 2
```

## 参数

| 参数 | 说明 | 默认 |
|------|------|------|
| `-u` | 用户名 | 必填 |
| `-p` | 密码 | 必填 |
| `-H` | 线程数 | 16 |
| `-b` | 请求间隔(秒) | 1 |
| `-t` | 超时(秒) | 10 |
| `-s` | Socket代理模式 | 关闭 |
| `-P` | Socket代理端口 | 8080 |
| `-d` | 本地直连模式（仅限测试） | 关闭 |
| `-v` | 显示版本号 | - |

**注意：**
- ⚠️ **CDN代理模式已弃用**（百度CDN IP段已被封禁）
- **必须使用** Socket代理模式（`-s`）或本地直连模式（`-d`）
- `-s` 和 `-d` 参数不能同时使用
- Socket代理编译时已禁用stack protector以避免runtime检测

## 数据查询

通过MySQL客户端或任何数据库工具查询历史数据：

```sql
-- 查询最新一批爬取的板块统计
SELECT board_type, board_name, stock_count
FROM board_statistics
WHERE batch_id = (SELECT MAX(batch_id) FROM scrape_batches)
ORDER BY stock_count DESC;

-- 查询特定板块的历史快照
SELECT scrape_date, total_boards, total_stocks, elapsed_seconds
FROM board_snapshots
WHERE board_type = 'gn' AND board_name = '人工智能'
ORDER BY scrape_date DESC;

-- 查看每日抓取批次记录
SELECT batch_id, board_type, scrape_date, total_boards, total_stocks
FROM scrape_batches
ORDER BY scrape_date DESC;
```

## 定时任务配置

使用 crontab 配置每日自动运行（以 root 用户）：

```bash
# 编辑 root 用户的 crontab
sudo crontab -e

# 添加以下行（每天早上9点运行，使用Socket代理模式）
0 9 * * * cd /path/to/10jqka_spider && python3 -u main.py -u 用户名 -p 密码 -s >> /var/log/10jqka_spider.log 2>&1
```

## 输出

**CSV文件（按日期归档）：**
```
result/20251121/
├── 20251121143025_同花顺行业板块信息.csv
├── 20251121143025_同花顺行业板块代码.csv
├── 20251121143025_概念板块信息.csv
├── 20251121143025_概念板块代码.csv
├── 20251121143025_地域板块信息.csv
└── 20251121143025_地域板块代码.csv
```

**MySQL数据库（配置.env后自动存储）：**
- `scrape_batches` - 抓取批次记录
- `board_snapshots` - 板块历史快照
- `stock_snapshots` - 股票历史快照
- `change_summary` - 变化统计汇总
- `board_changes` - 板块变化明细
- `stock_changes` - 股票变化明细

## 技术架构

**Socket代理模式（`-s`参数，推荐）：**
```
requests → Socket代理(127.0.0.1:8080) → 百度CDN → 同花顺
```

**本地直连模式（`-d`参数）：**
```
requests → 本地网络 → 同花顺
```

**CDN代理模式（默认，但已被封禁）：**
```
requests → CDN适配器 → 百度CDN(110.242.70.68) → 同花顺
```

- 纯Python，无需编译
- 支持三种网络模式：Socket代理、本地直连、CDN代理
- 默认CDN代理模式已被封禁，**推荐使用Socket代理模式（`-s`）**
- 简洁请求头设计，避免反爬虫检测
- 高斯分布随机延迟，模拟人工操作

## 项目结构

```
10jqka_spider/
├── main.py            # 主程序
├── cookies.py         # 登录和Cookie管理
├── encrypt.py         # RSA/AES加密
├── database.py        # MySQL数据库操作（支持自动建库建表）
├── socket_manager.py  # Socket代理管理器
├── v_new.js           # 反爬虫Cookie生成
├── origin.txt         # 设备指纹信息
├── cookies.json       # 登录Cookie缓存（自动生成）
├── config.toml        # 配置文件（含数据库密码）
├── requirements.txt   # Python依赖包
├── CHANGELOG.md       # 更新日志
├── README.md          # 项目说明
├── FILE_STRUCTURE.md  # 文件结构说明
└── socket/            # Socket代理（C语言，独立维护）
    ├── thread_socket.c
    ├── driver.c
    ├── thread_socket.h
    ├── Makefile
    └── thread_socket  # 编译后的二进制文件
```

## 依赖

- requests - HTTP客户端
- pycryptodome - RSA/AES加密
- ddddocr - 验证码识别
- pyexecjs - JavaScript执行
- pymysql - MySQL数据库驱动
- python-dotenv - 环境变量管理
- tabulate - 表格格式化输出
- toml - TOML配置文件解析

## 注意

仅供学习研究，请遵守相关法规。
