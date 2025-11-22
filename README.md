# 同花顺板块数据爬虫 v1.7.2

自动化爬取同花顺金融平台的股票板块数据（同花顺行业、概念、地域）。

## 功能特性

- 🔄 CDN代理IP轮换，绕过访问限制
- 🔐 自动登录，滑块验证码识别
- 📊 爬取三类板块：同花顺行业、概念、地域
- 🧵 多线程并发，高效爬取
- 📁 CSV格式输出，按日期归档

## 快速开始

```bash
pip install -r requirements.txt

# 方式1：Socket代理模式（推荐，需先启动socket代理）
./socket/thread_socket -r 110.242.70.68 -p 8080 -d  # 后台启动socket代理
python3 main.py -u <用户名> -p <密码> -s

# 方式2：本地直连模式（仅限测试）
python3 main.py -u <用户名> -p <密码> -d
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

## 定时任务配置

使用 crontab 配置每日自动运行（以 root 用户）：

```bash
# 编辑 root 用户的 crontab
sudo crontab -e

# 添加以下行（每天早上9点运行，使用-d参数本地直连）
0 9 * * * cd /path/to/10jqka_spider && python3 -u main.py -u ceshi0110 -p Qq830406 -d >> /var/log/10jqka_spider.log 2>&1
```

## 输出

```
result/20251121/
├── 20251121143025_同花顺行业板块信息.csv
├── 20251121143025_同花顺行业板块代码.csv
├── 20251121143025_概念板块信息.csv
├── 20251121143025_概念板块代码.csv
├── 20251121143025_地域板块信息.csv
└── 20251121143025_地域板块代码.csv
```

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

详细技术说明请参考 [TECHNICAL.md](TECHNICAL.md)

## 项目结构

```
10jqka_spider/
├── main.py          # 主程序
├── cookies.py       # 登录和Cookie管理
├── encrypt.py       # RSA/AES加密
├── cdn_adapter.py   # CDN转发适配器
├── v_new.js         # 反爬虫Cookie生成
├── origin.txt       # 设备指纹信息
├── cookies.json     # 登录Cookie缓存
├── requirements.txt # 依赖包
└── tests/           # 单元测试
```

## 依赖

- requests - HTTP客户端
- pycryptodome - RSA/AES加密
- ddddocr - 验证码识别
- pyexecjs - JavaScript执行

## 注意

仅供学习研究，请遵守相关法规。
