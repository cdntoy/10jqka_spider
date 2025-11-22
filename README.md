# 同花顺板块数据爬虫 v1.6.0

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
python3 main.py -u <用户名> -p <密码>
```

## 参数

| 参数 | 说明 | 默认 |
|------|------|------|
| `-u` | 用户名 | 必填 |
| `-p` | 密码 | 必填 |
| `-H` | 线程数 | 16 |
| `-b` | 请求间隔(秒) | 1 |
| `-t` | 超时(秒) | 10 |
| `--cdn` | 启用CDN代理模式（通过百度CDN轮换IP） | 关闭 |
| `-v` | 显示版本号 | - |

## 定时任务配置

使用 crontab 配置每日自动运行（以 root 用户）：

```bash
# 编辑 root 用户的 crontab
sudo crontab -e

# 添加以下行（每天早上9点运行）
0 9 * * * cd /path/to/10jqka_spider && python3 -u main.py -u ceshi0110 -p Qq830406 >> /var/log/10jqka_spider.log 2>&1
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

**默认模式（直连）：**
```
requests → 本地网络 → 同花顺
```

**CDN模式（`--cdn`参数）：**
```
requests → CDN适配器 → 百度CDN(110.242.70.68) → 同花顺
```

- 纯Python，无需编译
- 默认本地直连，可选CDN代理轮换IP
- CDN模式下负载均衡自动分配出口IP (180.101.81.x)
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
