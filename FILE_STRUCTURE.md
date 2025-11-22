# 项目文件说明 (v2.0.0)

本文档说明10jqka_spider项目中每个文件的作用。

## Python核心文件

### main.py (v2.0.0 完全重写)
爬虫主程序，负责整个爬取流程：
- 解析命令行参数
- 登录同花顺账号
- 多线程爬取板块数据
- 数据自动去重
- 保存到3个独立数据库和CSV

**v2.0.0主要变化**:
- 移除 `BOARD_TYPE_NAMES` 映射，直接使用中文板块类型
- 使用 `db_instances` 字典管理3个Database实例
- 支持 `enabled_boards` 配置可选抓取
- 新增耗时追踪（`elapsed_seconds`）
- 从 `BOARD_CONFIGS` 读取URL和url_type

主要函数：
- `fetch_pages()` - 爬取指定板块类型（中文参数）
- `fetch()` - 获取板块列表
- `fetch_code()` - 获取板块成分股
- `prepare_board_data()` - 数据去重
- `store()` - 数据存储（支持3数据库）
- `save_to_mysql()` - MySQL存储（使用中文字段）
- `save_to_csv()` - CSV存储（新文件夹结构）

### database.py (v2.0.0 完全重写)
MySQL数据库操作，支持三数据库架构：

**核心设计**:
- `BOARD_CONFIGS` 常量：映射板块类型到数据库配置
- 每个Database实例连接一个专属数据库
- 所有SQL使用中文字段名（反引号包裹）

**v2.0.0主要变化**:
- 739行 → 332行（简化设计）
- 构造函数接受 `board_type` 参数（"同花顺行业"/"概念"/"地域"）
- 移除所有变化追踪方法
- 移除 `insert_board_statistics()`
- 新增 `validate_batch_integrity()` 数据完整性校验

核心类和方法：
- `Database` 类 - 数据库操作封装（多实例）
- `create_batch()` - 创建批次记录
- `insert_boards()` - 插入板块数据（中文字段）
- `insert_stocks()` - 插入股票数据（中文字段）
- `update_batch_status()` - 更新批次状态（含耗时）
- `validate_batch_integrity()` - 校验板块-股票完整性
- `delete_batch_data()` - 删除不完整批次

**数据库架构** (v2.0.0):
- 3个独立数据库：`同花顺行业板块`, `概念板块`, `地域板块`
- 每个数据库包含3张表：
  - `爬取记录` - 批次管理（批次ID, 抓取时间, 爬取耗时秒数, 执行状态）
  - `板块信息` - 板块基本信息（板块名称, 来源链接, 驱动事件, 成分股数量）
  - `成分股` - 股票-板块关系（股票代码, 股票名称, 原始序号）

### cookies.py
登录和Cookie管理（未修改）：
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
加密算法实现（未修改）：
- RSA公钥加密（密码加密）
- AES加密/解密
- Base64编解码
- 字符串异或运算

### socket_manager.py
Socket代理管理（未修改）：
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

### config.toml (v2.0.0 新增配置)
项目配置文件（TOML格式）：
- 数据库连接配置（host/port/user/password）
- **新增**: `enabled_boards` - 可选板块类型配置
- 爬虫参数（线程数/超时/间隔）
- Socket代理配置
- CSV备份开关

**v2.0.0新增**:
```toml
[scraper]
enabled_boards = ["同花顺行业", "概念", "地域"]  # 可选抓取
```

### requirements.txt
Python依赖包列表，使用 `pip install -r requirements.txt` 安装。

## SQL初始化脚本

### init_databases.sql (v2.0.0 新增)
数据库初始化脚本，创建3个独立数据库和所有表：
- 创建 `同花顺行业板块`, `概念板块`, `地域板块` 数据库
- 每个数据库包含3张表（爬取记录, 板块信息, 成分股）
- 所有字段使用中文名称
- 外键级联删除（ON DELETE CASCADE）
- utf8mb4字符集

使用方法：
```bash
mysql -u root -p < init_databases.sql
```

## 数据文件

### origin.txt
浏览器设备指纹信息，用于模拟真实浏览器环境。

### cookies.json
登录后的Cookie缓存（自动生成），避免频繁登录。

## 文档文件

### README.md (v2.0.0 重写)
项目主文档，更新为v2.0.0架构：
- 三数据库架构说明
- 可选抓取功能
- 新的SQL查询示例（中文字段）
- 迁移指南

### CHANGELOG.md (v2.0.0 新增)
版本更新日志，记录v2.0.0重大架构重构：
- 三数据库架构对比
- 全中文化说明
- 移除功能列表
- 代码重构详情

### FILE_STRUCTURE.md
本文档，说明项目所有文件的作用（已更新到v2.0.0）。

## Socket代理（C语言）

### socket/
Socket代理子项目，C语言实现的高性能代理服务器。

文件：
- `thread_socket.c` - 多线程Socket代理实现
- `driver.c` - 命令行入口
- `Makefile` - 编译配置（VERSION = 2.0.0）
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

## 输出目录 (v2.0.0 新结构)

### result/
爬取结果存储目录（自动生成），按板块类型和日期组织：

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

**v2.0.0变化**:
- 一级目录按板块类型分离（中文名称）
- 二级目录按日期归档
- 文件名中文化

## 依赖关系

```
main.py (v2.0.0)
  ├─> cookies.py
  │     ├─> encrypt.py
  │     ├─> v_new.js
  │     └─> origin.txt
  ├─> database.py (v2.0.0 - 支持多实例)
  ├─> socket_manager.py
  │     └─> socket/thread_socket
  └─> config.toml (v2.0.0 - 新增enabled_boards)
```

## v2.0.0 架构图

```
┌─────────────────────────────────────────┐
│           main.py (主程序)               │
├─────────────────────────────────────────┤
│ db_instances = {                        │
│   "同花顺行业": Database("同花顺行业板块") │
│   "概念": Database("概念板块")           │
│   "地域": Database("地域板块")           │
│ }                                       │
└─────────────────────────────────────────┘
           ↓           ↓          ↓
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ 同花顺行业板块  │ │   概念板块    │ │   地域板块    │
├──────────────┤ ├──────────────┤ ├──────────────┤
│ 爬取记录      │ │ 爬取记录      │ │ 爬取记录      │
│ 板块信息      │ │ 板块信息      │ │ 板块信息      │
│ 成分股        │ │ 成分股        │ │ 成分股        │
└──────────────┘ └──────────────┘ └──────────────┘
```

## 使用建议

- **配置修改**：编辑 `config.toml`（可选抓取板块）
- **扩展功能**：修改 `main.py` 和 `database.py`
- **调试**：查看控制台日志（含耗时统计）
- **数据分析**：直接查询MySQL数据库（中文字段）

## 注意事项

1. **v2.0.0 不向后兼容**：需执行 `init_databases.sql` 初始化新数据库
2. 首次使用需在 `config.toml` 中设置数据库密码
3. 运行前需安装依赖：`pip install -r requirements.txt`
4. Socket代理需先编译：`make -C socket release`
5. 配置 `enabled_boards` 选择要抓取的板块类型
6. `cookies.json` 包含登录信息，不要提交到Git
7. 旧版本数据需手动迁移（无自动迁移脚本）

## 文件清单

**核心代码** (v2.0.0 重写):
- `main.py` (914行，支持可选抓取)
- `database.py` (332行，三数据库架构)

**配置文件** (v2.0.0 更新):
- `config.toml` (新增 enabled_boards)
- `init_databases.sql` (新增，替代自动建库)

**文档** (v2.0.0 更新):
- `README.md` (v2.0.0架构说明)
- `CHANGELOG.md` (v2.0.0重构详情)
- `FILE_STRUCTURE.md` (本文档)

**未修改文件**:
- `cookies.py`
- `encrypt.py`
- `socket_manager.py`
- `v_new.js`
- `origin.txt`
- `requirements.txt`

**Socket代理** (v2.0.0 版本号更新):
- `socket/Makefile` (VERSION = 2.0.0)
- `socket/thread_socket.c`
- `socket/driver.c`
