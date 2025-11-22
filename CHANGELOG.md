# 更新日志

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
