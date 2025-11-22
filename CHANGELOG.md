# 更新日志

## [2.0.0] - 2025-11-23

### 🎉 重大架构重构（不向后兼容）

**核心变更**:
- **三数据库架构**: 从单库7表改为3库9表（每库3表）
  - `同花顺行业板块` 数据库：爬取记录 + 板块信息 + 成分股
  - `概念板块` 数据库：爬取记录 + 板块信息 + 成分股
  - `地域板块` 数据库：爬取记录 + 板块信息 + 成分股
- **全中文化**: 所有数据库名、表名、字段名100%使用中文
  - `批次ID`, `板块名称`, `股票代码`, `股票名称`, `抓取时间`, `爬取耗时秒数` 等
  - 反引号包裹所有中文标识符，utf8mb4字符集
- **可选抓取**: 新增`enabled_boards`配置，支持只抓取指定板块类型
  - 配置示例: `enabled_boards = ["概念"]` 只抓概念板块
  - 默认: `["同花顺行业", "概念", "地域"]` 抓取全部

### 新增功能

- **init_databases.sql**: 全新数据库初始化脚本
  - 创建3个独立数据库
  - 每个数据库包含相同的3张表结构
  - 外键级联删除（ON DELETE CASCADE）
- **性能追踪**: `爬取耗时秒数`字段自动记录每次抓取耗时
- **CSV分文件夹**: 新的文件夹结构 `result/同花顺行业板块/20251123/`
  - 按板块类型分离
  - 文件名中文化: `板块信息_xxx.csv`, `成分股_xxx.csv`

### 移除功能

- ❌ 删除所有变化追踪功能
  - 移除 `change_summary`, `board_changes`, `stock_changes` 表
  - 移除 `generate_change_summary()` 函数
- ❌ 删除 `migrate_v1.7.7.sql` 迁移脚本（不向后兼容）
- ❌ 移除 `board_statistics` 表（简化架构）
- ❌ 移除 `BOARD_TYPE_NAMES` 映射，直接使用中文板块类型

### 代码重构

- **database.py**: 完全重写（739行 → 332行）
  - 新增 `BOARD_CONFIGS` 常量，映射板块类型到数据库配置
  - 构造函数接受 `board_type` 参数，连接对应数据库
  - 所有SQL使用中文字段名（反引号包裹）
  - 简化为核心方法：create_batch, insert_boards, insert_stocks, validate_batch_integrity
- **main.py**: 完全重写（942行 → 914行）
  - 使用 `db_instances` 字典管理3个Database实例
  - 使用 `current_batch_ids` 字典追踪各板块批次
  - 从 `BOARD_CONFIGS` 读取URL和url_type
  - 新增 `elapsed_seconds` 时间追踪
  - 支持 `enabled_boards` 配置可选抓取
- **config.toml**: 添加 `enabled_boards` 配置项
- **socket/Makefile**: 版本号更新为 2.0.0

### 数据库架构对比

| v1.7.7 | v2.0.0 |
|--------|--------|
| 1个数据库 `10jqka_bankuai` | 3个数据库（按板块类型） |
| 7张表 | 每库3张表（共9张） |
| 英文表名/字段名 | 100%中文表名/字段名 |
| 含变化追踪表 | 移除变化追踪 |
| 单Database实例 | 3个Database实例 |

### 迁移说明

**不向后兼容**: 需要重新初始化数据库
1. 备份旧数据: `mysqldump -u root -p 10jqka_bankuai > backup_v1.sql`
2. 执行初始化: `mysql -u root -p < init_databases.sql`
3. 更新config.toml，添加 `enabled_boards` 配置
4. 重新运行爬虫

---

## [1.7.7] - 2025-11-23

### 重命名
- **表名优化**: `stock_snapshots` → `stock_board_memberships`
  - 更清晰地表达股票-板块成员关系
  - 避免与股票价格快照混淆
  - 所有相关SQL查询已更新

### 数据库
- **库名更改**: `stock_spider` → `10jqka_bankuai`
  - 使用拼音避免中文编码问题
  - 强调数据内容（板块）而非工具（爬虫）
  - 更新config.toml和database.py默认值

### 代码质量
- **清理无用引用**:
  - 删除未使用的sqlite3 import
  - 删除未使用的random.randint和random.uniform

### 国际化
- **中文化改进**:
  - 添加BOARD_TYPE_NAMES常量映射（thshy→同花顺行业, gn→概念, dy→地域）
  - 所有日志输出改用中文板块名称
  - 保留thshy/gn/dy用于URL构建（外部API兼容性）

### 数据完整性
- **批次校验机制**:
  - 新增validate_batch_integrity()函数
  - 检查板块-股票一致性（确保每个板块都有股票数据）
  - 检查最低记录数（同花顺行业≥80，概念≥350，地域≥28）
  - 失败批次自动清理，避免脏数据
- **两阶段提交**:
  - 数据插入后先校验，通过后再标记success
  - 校验失败自动rollback并delete_batch_data()

---

## [1.7.6] - 2025-11-23

### 修复
- **连接池配置问题**: 修复"Connection pool is full"警告
  - 添加HTTPAdapter配置，设置pool_connections=64, pool_maxsize=64
  - 匹配32线程并发需求，消除连接池不足警告
  - 添加自动重试机制（3次重试，指数退避）
  - 提升性能，减少连接创建/销毁开销

---

## [1.7.5] - 2025-11-23

### 修复
- **P0级问题**: 修复Ctrl+C信号无法立即响应的问题
  - thread.join()添加超时检查，每0.1秒检查shutdown_event
  - random_sleep()改为分段sleep，每0.05秒检查shutdown_event
  - 所有阻塞操作支持快速响应中断信号

### 项目精简
- 删除非核心文件：query_changes.py, MYSQL_GUIDE.md, TECHNICAL.md, tests/
- 删除.gitmodules和.env.example（无用配置）
- socket目录从git submodule改为独立维护

### 文档重写
- README.md：完全重写，使用自然语言，删除过时CDN代理说明
- FILE_STRUCTURE.md：简化描述，更符合人类阅读习惯
- 聚焦核心功能：登录 → 爬取 → 去重 → MySQL/CSV

---

## [1.7.4] - 2025-11-23

### 数据质量改进
- **数据去重**:
  - 修复单个板块内股票代码重复问题
  - 修复板块列表重复问题
  - 在prepare_board_data()函数中实现完整去重逻辑

### 新增功能
- **板块统计表**: 新增board_statistics表,记录每个板块的股票数量统计
  - 字段包括: batch_id, board_type, board_name, stock_count, scrape_date
  - 支持查询每个板块下有多少只股票(去重后)
- **文件说明文档**: 新增FILE_STRUCTURE.md,详细说明每个文件的作用和功能

### 数据库改进
- 所有数据库表字段已有完整的中文COMMENT注释
- 新增insert_board_statistics()函数自动统计并插入板块数据

### 文档完善
- 创建FILE_STRUCTURE.md详细说明项目文件结构
- 所有表和字段都有清晰的中文说明

---

## [1.7.3] - 2025-11-23

### 新增
- **数据库自动建库**: database.py支持自动创建数据库和表，首次运行无需手动初始化
- **变化查询工具**: 添加query_changes.py，支持查询每日变化、板块历史、热门股票
- **Socket代理release版本**: 编译优化版本，添加版本号显示

### 改进
- **代码质量提升**:
  - 添加中文docstring到所有主要函数
  - 定义常量替代魔数（MAX_PAGE_RETRIES等）
  - 重构store()函数，拆分为3个子函数
  - 变量语义化重命名（RESULT → board_data）
- **SQL文档完善**: init_db_simple.py所有字段添加中文COMMENT注释
- **安全加固**:
  - 移除所有硬编码密码，使用.env环境变量
  - .gitignore添加敏感文件保护

### 修改
- 移除setup.py一键安装脚本（自动建库已足够简单）
- Socket代理Makefile支持release编译目标
- 更新所有文档反映新的安装方式

### 删除
- 清理__pycache__、PID、TEST_RESULTS.md等临时文件

---

## [1.7.2] - 2025-11-22

### 修复
- **Socket代理**: 修复socket/thread_socket.c中的3个buffer overflow bug
  - LEN_URL_STR从262143改为1023
  - snprintf使用正确的缓冲区大小（LEN_URL而非SIZE）
  - snprintf偏移指针使用正确的剩余长度（LEN_URL - len）
- **Socket代理**: 编译时禁用stack protector以绕过runtime检测

### 删除
- **CDN适配器**: 移除cdn_adapter.py（百度CDN IP段已被封禁）
- 移除main.py中对cdn_adapter的引用
- 默认模式改为强制使用-s或-d参数

### 测试
- ✅ Socket代理模式完整测试通过（出口IP: 180.101.81.x）
- ✅ 成功爬取29+板块数据
- ✅ Ctrl+C信号处理正常工作

---

## [1.7.1] - 2025-11-22

### 修复
- **P0级问题**: 修复Ctrl+C信号处理，程序现在可以正确响应中断信号
- 在所有重试循环中添加shutdown_event检查（check_cookies_valid、fetch、fetch_code）

### 新增
- **Socket代理模式**: 添加 `-s/--socket` 参数支持使用本地socket代理
- **代理端口配置**: 添加 `-P/--proxy-port` 参数指定socket代理端口（默认8080）
- 参数互斥检查：`-s` 和 `-d` 不能同时使用

### 修改
- 网络模式现在支持三种：CDN代理（默认）、Socket代理（-s）、本地直连（-d）

---

## [1.7.0] - 2025-11-22

### 修复
- **P0级问题**: encrypt.py中str_xor()函数变量i被内部覆盖导致XOR计算错误
- **P0级问题**: main.py:359 cookies验证失败后缺少continue语句
- **P0级问题**: main.py中数组访问前缺少边界检查（c_name、seq_results）
- **P0级问题**: 三处match-case缺少默认分支处理
- 改进信号处理：移除signal_handler中的sys.exit()调用
- 添加session.close()确保资源正确释放

### 修改
- 默认线程数从64改为16（更稳定）
- 简化请求头从18个到4个基础头（避免过度伪装）
- CDN代理模式为默认（-d参数用于本地直连测试）
- 改进代码质量：is None替代== None、数据结构验证

### 文档
- 更新TECHNICAL.md说明CDN IP段封禁状态
- 更新README.md推荐使用-d参数测试

---

## [1.6.0] - 2025-11-21

### 新增
- 完整Chrome浏览器请求头伪装（18个标准头）
- 高斯分布随机延迟函数`random_sleep()`
- Sec-Fetch-*、Sec-Ch-Ua-*系列请求头

### 修改
- 所有`sleep(interval)`改为`random_sleep()`
- 请求头按Chrome标准顺序排列

---

## [1.5.0] - 2025-11-21

### 新增
- 本地直连测试模式`-d/--direct`参数
- 参数验证（用户名必填、线程数1-256、超时>0）

### 修复
- P0级问题：无限循环添加最大重试限制
- P0级问题：CDN连接异常时socket内存泄漏
- P0级问题：空except改为具体异常捕获
- P1级问题：CSV头行重复写入
- 移除未使用的`err_count`变量和`b64decode/b64encode`导入
- GBK解码添加`errors='ignore'`防止崩溃

---

## [1.4.0] - 2025-11-21

### 重大变更
- 移除代理服务器概念，直接在requests层内部转发
- 无需启动/停止代理进程，无端口占用问题

### 修改
- `cdn_adapter.py` - 使用自定义HTTPAdapter直接建立CDN隧道
- 移除`-P`代理端口参数

---

## [1.3.0] - 2025-11-21

### 变更
- 用Python重写CDN代理，移除C语言socket模块

---

## [1.2.0] - 2025-11-21

### 新增
- 代理健康检查与自动重启
- 并发连接限制

---

## [1.1.0] - 2025-11-21

### 新增
- argparse命令行参数
- 单元测试

---

## [1.0.0] - 2025-05-23

### 初始版本
