# 项目文件说明

本文档详细说明了10jqka_spider项目中每个文件的作用和功能。

## Python核心代码

### main.py
**核心爬虫程序**
- 程序入口,负责协调整个爬取流程
- 主要功能:
  - 命令行参数解析(`argparse`)
  - 登录验证和Cookie管理
  - 多线程并发爬取板块数据
  - 数据去重和清洗
  - 调用database.py保存数据到MySQL
  - 调用save_to_csv保存CSV备份
- 支持三种板块类型: 同花顺行业(thshy)、概念(gn)、地域(dy)
- 关键函数:
  - `main()`: 程序入口
  - `fetch()`: 获取板块列表
  - `fetch_code()`: 获取板块成分股
  - `prepare_board_data()`: 数据去重和准备
  - `store()`: 数据存储协调

### database.py
**数据库操作模块**
- 提供MySQL数据库的完整操作接口
- 主要功能:
  - 自动创建数据库和表结构(首次运行无需手动初始化)
  - 事务管理(支持回滚)
  - CRUD操作(创建/读取/更新/删除)
  - 变化统计和追踪
  - 板块统计数据生成
- 关键类:
  - `Database`: 数据库操作类
- 关键方法:
  - `_create_database_and_tables()`: 自动建库建表
  - `insert_boards()`: 插入板块数据
  - `insert_stocks()`: 插入股票数据
  - `insert_board_statistics()`: 插入板块统计
  - `generate_change_summary()`: 生成变化摘要
- 数据表说明:
  - `scrape_batches`: 抓取批次记录
  - `board_snapshots`: 板块历史快照
  - `stock_snapshots`: 股票历史快照
  - `change_summary`: 变化统计摘要
  - `board_changes`: 板块变化明细
  - `stock_changes`: 股票变化明细
  - `board_statistics`: 板块统计表(每个板块的股票数量)

### cookies.py
**登录和Cookie管理**
- 处理同花顺网站的登录流程
- 主要功能:
  - 用户登录(用户名/密码)
  - 滑块验证码识别(ddddocr)
  - Cookie生成和维护
  - 设备指纹生成
  - 反爬虫Cookie(v字段)动态生成
- 关键类:
  - `Cookies`: Cookie管理类
- 核心方法:
  - `login()`: 执行登录
  - `get_v()`: 获取反爬虫Cookie
  - `slide()`: 滑块验证处理

### encrypt.py
**加密解密模块**
- 实现登录所需的加密算法
- 主要功能:
  - RSA公钥加密(密码加密)
  - AES加密/解密
  - Base64编解码
  - 字符串异或运算
- 关键函数:
  - `rsa_encrypt()`: RSA加密
  - `aes_encrypt()/aes_decrypt()`: AES加解密
  - `str_xor()`: 字符串异或

### socket_manager.py
**Socket代理管理器**
- 管理本地Socket代理进程的生命周期
- 主要功能:
  - 启动/停止Socket代理进程
  - 端口可用性检查
  - 代理进程健康检查
  - 进程PID管理
- 关键类:
  - `SocketProxyManager`: 代理管理器
- 核心方法:
  - `start()`: 启动代理
  - `stop()`: 停止代理
  - `_is_port_ready()`: 检查端口就绪

### query_changes.py
**数据变化查询工具**
- 查询和分析板块/股票的历史变化
- 主要功能:
  - 查询每日变化汇总
  - 查询单个板块历史趋势
  - 查询热门新增/删除股票
  - 查询指定批次详情
- 命令行工具,独立运行
- 使用方式: `python3 query_changes.py --type gn --days 7`

## JavaScript文件

### v_new.js
**反爬虫Cookie生成脚本**
- Node.js脚本,用于生成同花顺反爬虫参数
- 被cookies.py调用(通过pyexecjs执行)
- 生成v字段Cookie值,用于绕过网站的反爬虫检测

## 配置文件

### config.toml
**项目配置文件**
- TOML格式配置
- 包含:
  - 数据库连接配置(host/port/user/database)
  - 爬虫参数(线程数/超时/间隔)
  - 存储模式配置
  - CSV备份开关

### .env.example
**环境变量模板**
- 敏感配置的模板文件
- 用户需复制为.env并填写实际值
- 主要配置: `DB_PASSWORD` (数据库密码)

### requirements.txt
**Python依赖清单**
- 列出项目所需的所有Python包及版本
- 使用 `pip install -r requirements.txt` 安装

## 数据文件

### origin.txt
**设备指纹模板**
- 存储浏览器设备指纹信息
- 用于模拟真实浏览器环境
- cookies.py读取此文件生成登录指纹

### cookies.json
**Cookie缓存文件**
- 自动生成,存储登录后的Cookie
- 避免频繁登录
- 格式: JSON

## 文档文件

### README.md
**项目主文档**
- 项目简介和快速上手指南
- 安装步骤
- 使用说明
- 参数说明
- 技术架构

### CHANGELOG.md
**版本更新日志**
- 记录每个版本的新增功能、改进、修复
- 按版本号和日期组织
- 帮助用户了解项目演进

### MYSQL_GUIDE.md
**MySQL使用指南**
- MySQL数据库的使用说明
- 表结构解释
- 常用SQL查询示例
- 数据分析方法

### TECHNICAL.md
**技术文档**
- 详细的技术实现说明
- 网络代理原理
- 反爬虫策略
- 性能优化建议

### FILE_STRUCTURE.md
**文件结构说明(本文档)**
- 项目所有文件的详细说明
- 帮助开发者快速了解项目结构

## Socket代理(C语言)

### socket/
Socket代理子项目,使用C语言实现高性能代理服务器

**核心文件**:
- `thread_socket.c`: 多线程Socket代理实现
- `driver.c`: 代理驱动程序(命令行入口)
- `thread_socket.h`: 头文件
- `Makefile`: 编译配置
- `thread_socket`: 编译后的二进制可执行文件

**功能**:
- 通过百度CDN转发请求
- 实现IP轮换,绕过访问限制
- 多线程并发处理
- 高性能(C语言实现)

**编译**:
```bash
make -C socket release  # 编译优化版本
```

## 测试文件

### tests/test_main.py
**单元测试**
- 使用pytest框架
- 测试核心功能的正确性
- 运行: `pytest tests/`

## 输出目录

### result/
**爬取结果存储目录**(自动生成)
- 按日期组织子目录,如 `result/20251122/`
- 每次爬取生成6个CSV文件:
  - 板块信息CSV (3个: 同花顺行业/概念/地域)
  - 板块代码CSV (3个: 同花顺行业/概念/地域)

## 项目依赖关系

```
main.py (主程序)
  ├─> cookies.py (登录管理)
  │     ├─> encrypt.py (密码加密)
  │     ├─> v_new.js (反爬虫Cookie)
  │     └─> origin.txt (设备指纹)
  ├─> database.py (数据存储)
  │     └─> MySQL数据库
  ├─> socket_manager.py (代理管理)
  │     └─> socket/thread_socket (C代理程序)
  └─> config.toml (配置读取)

query_changes.py (独立查询工具)
  └─> database.py (数据读取)
```

## 文件修改建议

- **配置修改**: 编辑 `config.toml` 和 `.env`
- **扩展功能**: 修改 `main.py` 和 `database.py`
- **调试爬虫**: 查看 `main.py` 的日志输出
- **分析数据**: 使用 `query_changes.py` 或直接查询MySQL

## 注意事项

1. **环境配置**: 首次使用需配置 `.env` 文件(复制自 `.env.example`)
2. **依赖安装**: 运行前需 `pip install -r requirements.txt`
3. **代理编译**: Socket代理需先编译 `make -C socket release`
4. **数据库**: 首次运行会自动创建数据库和表,无需手动初始化
5. **敏感信息**: cookies.json和.env包含敏感信息,不要提交到Git
