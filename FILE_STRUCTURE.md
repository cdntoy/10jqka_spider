# 项目文件说明

本文档说明10jqka_spider项目中每个文件的作用。

## Python核心文件

### main.py
爬虫主程序，负责整个爬取流程：
- 解析命令行参数
- 登录同花顺账号
- 多线程爬取板块数据
- 数据去重处理
- 保存到MySQL和CSV

主要函数：
- `main()` - 程序入口
- `fetch()` - 获取板块列表
- `fetch_code()` - 获取板块成分股
- `prepare_board_data()` - 数据去重
- `store()` - 数据存储

### database.py
MySQL数据库操作：
- 自动创建数据库和表（首次运行）
- 插入板块和股票数据
- 生成变化统计
- 计算板块统计信息

核心类和方法：
- `Database` 类 - 数据库操作封装
- `_create_database_and_tables()` - 自动建库建表
- `insert_boards()` - 插入板块数据
- `insert_stocks()` - 插入股票数据
- `insert_board_statistics()` - 插入统计数据
- `generate_change_summary()` - 生成变化摘要

数据表：
- `scrape_batches` - 批次记录
- `board_snapshots` - 板块快照
- `stock_snapshots` - 股票快照
- `board_statistics` - 板块统计
- `change_summary` - 变化汇总
- `board_changes` - 板块变化
- `stock_changes` - 股票变化

### cookies.py
登录和Cookie管理：
- 用户登录
- 滑块验证码识别
- Cookie生成和维护
- 设备指纹生成
- 反爬虫Cookie（v字段）

核心方法：
- `login()` - 执行登录
- `get_v()` - 获取反爬虫Cookie
- `slide()` - 滑块验证处理

### encrypt.py
加密算法实现：
- RSA公钥加密（密码加密）
- AES加密/解密
- Base64编解码
- 字符串异或运算

### socket_manager.py
Socket代理管理：
- 启动/停止Socket代理进程
- 端口检查
- 进程健康检查
- PID管理

核心方法：
- `start()` - 启动代理
- `stop()` - 停止代理
- `_is_port_ready()` - 检查端口就绪

## JavaScript文件

### v_new.js
生成同花顺反爬虫Cookie（v字段），被cookies.py通过pyexecjs调用。

## 配置文件

### config.toml
项目配置文件（TOML格式）：
- 数据库连接配置（host/port/user/password/database）
- 爬虫参数（线程数/超时/间隔）
- 存储模式配置
- CSV备份开关

数据库密码直接在此文件配置。

### requirements.txt
Python依赖包列表，使用 `pip install -r requirements.txt` 安装。

## 数据文件

### origin.txt
浏览器设备指纹信息，用于模拟真实浏览器环境。

### cookies.json
登录后的Cookie缓存（自动生成），避免频繁登录。

## 文档文件

### README.md
项目主文档：
- 快速上手指南
- 安装步骤
- 使用说明
- 参数说明

### CHANGELOG.md
版本更新日志，记录每个版本的新增功能、改进和修复。

### FILE_STRUCTURE.md
本文档，说明项目所有文件的作用。

## Socket代理（C语言）

### socket/
Socket代理子项目，C语言实现的高性能代理服务器。

文件：
- `thread_socket.c` - 多线程Socket代理实现
- `driver.c` - 命令行入口
- `thread_socket.h` - 头文件
- `Makefile` - 编译配置
- `thread_socket` - 编译后的可执行文件

功能：
- 通过百度CDN转发请求
- 自动切换IP，避免被封
- 多线程并发处理
- 高性能（C语言）

编译：
```bash
make -C socket release
```

说明：
- 独立维护的代码，不依赖外部仓库
- 已从git submodule改为普通目录

## 输出目录

### result/
爬取结果存储目录（自动生成），按日期组织：
```
result/20251123/
├── 20251123090000_同花顺行业板块信息.csv
├── 20251123090000_同花顺行业板块代码.csv
├── 20251123090000_概念板块信息.csv
├── 20251123090000_概念板块代码.csv
├── 20251123090000_地域板块信息.csv
└── 20251123090000_地域板块代码.csv
```

## 依赖关系

```
main.py
  ├─> cookies.py
  │     ├─> encrypt.py
  │     ├─> v_new.js
  │     └─> origin.txt
  ├─> database.py
  ├─> socket_manager.py
  │     └─> socket/thread_socket
  └─> config.toml
```

## 使用建议

- **配置修改**：编辑 `config.toml`
- **扩展功能**：修改 `main.py` 和 `database.py`
- **调试**：查看控制台日志
- **数据分析**：直接查询MySQL数据库

## 注意事项

1. 首次使用需在 `config.toml` 中设置数据库密码
2. 运行前需安装依赖：`pip install -r requirements.txt`
3. Socket代理需先编译：`make -C socket release`
4. 首次运行会自动创建数据库和表
5. `cookies.json` 包含登录信息，不要提交到Git
