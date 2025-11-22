# 同花顺板块数据爬虫 v1.7.6

自动爬取同花顺股票板块数据，支持同花顺行业、概念、地域三大分类，数据存储到MySQL或CSV文件。

## 主要功能

- 自动登录同花顺账号（支持滑块验证码识别）
- 爬取三类板块数据：同花顺行业（90个）、概念（380个）、地域（31个）
- 通过Socket代理实现IP轮换，避免被封
- 多线程并发爬取，速度快
- 数据自动去重，保证质量
- MySQL数据库存储，支持历史追踪
- CSV文件备份，按日期归档

## 安装

```bash
# 1. 克隆项目
git clone https://github.com/cdntoy/10jqka_spider.git
cd 10jqka_spider

# 2. 安装Python依赖
pip3 install -r requirements.txt

# 3. 编译Socket代理
make -C socket release

# 4. 配置数据库（可选）
vim config.toml  # 修改数据库密码
```

首次运行会自动创建数据库和表，无需手动初始化。

## 使用

```bash
# 推荐：使用Socket代理模式
python3 main.py -u 用户名 -p 密码 -s

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
| `-H` | 线程数 | 16 |
| `-b` | 请求间隔（秒） | 1 |
| `-t` | 超时时间（秒） | 10 |
| `-P` | Socket代理端口 | 8080 |

注意：`-s` 和 `-d` 不能同时使用，推荐使用Socket代理模式。

## 数据查询

### CSV文件

数据保存在 `result/日期/` 目录下，每次运行生成6个CSV文件：

```
result/20251123/
├── 20251123090000_同花顺行业板块信息.csv
├── 20251123090000_同花顺行业板块代码.csv
├── 20251123090000_概念板块信息.csv
├── 20251123090000_概念板块代码.csv
├── 20251123090000_地域板块信息.csv
└── 20251123090000_地域板块代码.csv
```

### MySQL数据库

配置好`config.toml`后，数据会自动存储到MySQL。主要数据表：

- `scrape_batches` - 每次爬取的批次记录
- `board_snapshots` - 板块历史快照
- `stock_snapshots` - 股票历史快照
- `board_statistics` - 板块统计（含股票数量）
- `change_summary` - 变化统计汇总
- `board_changes` - 板块变化明细
- `stock_changes` - 股票变化明细

常用查询示例：

```sql
-- 查看最新爬取的板块统计
SELECT board_type, board_name, stock_count
FROM board_statistics
WHERE batch_id = (SELECT MAX(batch_id) FROM scrape_batches)
ORDER BY stock_count DESC;

-- 查看"人工智能"板块的历史数据
SELECT scrape_date, total_stocks
FROM board_snapshots
WHERE board_name = '人工智能'
ORDER BY scrape_date DESC;
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
├── main.py            # 主程序
├── cookies.py         # 登录和Cookie管理
├── encrypt.py         # 加密算法（RSA/AES）
├── database.py        # 数据库操作
├── socket_manager.py  # Socket代理管理
├── v_new.js           # 反爬虫Cookie生成
├── origin.txt         # 设备指纹
├── config.toml        # 配置文件
└── socket/            # Socket代理源码（C语言）
    ├── thread_socket.c
    ├── driver.c
    ├── Makefile
    └── thread_socket  # 编译后的可执行文件
```

## 依赖包

- `requests` - HTTP请求
- `pycryptodome` - 加密算法
- `ddddocr` - 验证码识别
- `pyexecjs` - 执行JavaScript
- `pymysql` - MySQL数据库
- `toml` - 配置文件解析
- `tabulate` - 表格输出

## 注意事项

本项目仅供学习研究使用，请遵守相关法律法规。
