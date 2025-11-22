# 技术路线文档

## 网络模式说明

本项目支持两种网络模式：

1. **CDN代理模式（默认）**：通过百度CDN(110.242.70.68)轮换出口IP (180.101.81.x)
   - ⚠️ **当前状态：已被同花顺封禁**
   - 同花顺的ATS(ApacheTrafficServer)将百度CDN IP段加入黑名单
   - 所有请求返回403 Access Denied

2. **本地直连模式（`-d`参数，推荐）**：直接使用本地IP访问同花顺
   - ✅ **当前可用**
   - 适用于服务器IP未被封禁的场景
   - 仅限测试和小规模使用

## 1. 整体架构

```
┌─────────────┐     ┌───────────────┐     ┌────────────────┐     ┌──────────────┐
│   main.py   │────▶│  cdn_adapter  │────▶│  百度CDN节点   │────▶│  同花顺服务器 │
│  爬虫主程序  │     │  CONNECT隧道  │     │ 110.242.70.68  │     │  q.10jqka.cn │
└─────────────┘     └───────────────┘     └────────────────┘     └──────────────┘
       │                                          │
       │                                          ▼
       ▼                                   出口IP轮换
┌─────────────┐                          180.101.81.x
│ cookies.py  │
│  登录认证   │
└─────────────┘
       │
       ▼
┌─────────────┐
│ encrypt.py  │
│ RSA/AES加密 │
└─────────────┘
```

## 2. CDN隧道原理

### 2.1 为什么使用CDN隧道

同花顺对单IP访问频率有限制，频繁请求会触发封禁。通过百度CDN的CONNECT隧道，每次请求可获得不同出口IP。

### 2.2 隧道建立流程

```
1. TCP连接        客户端 ──────────────────▶ 百度CDN (110.242.70.68:443)
                        建立TCP Socket连接

2. CONNECT请求    客户端 ──────────────────▶ 百度CDN
                        CONNECT q.10jqka.com.cn:443 HTTP/1.1\r\n\r\n

3. 隧道响应       客户端 ◀────────────────── 百度CDN
                        HTTP/1.1 200 Connection Established

4. SSL握手        客户端 ◀═══════════════════════════════════════▶ 同花顺
                        在隧道内进行TLS握手（SNI: q.10jqka.com.cn）

5. HTTPS请求      客户端 ◀═══════════════════════════════════════▶ 同花顺
                        加密的HTTP请求/响应
```

### 2.3 IP轮换机制

```python
class CdnConnectionPool(HTTPSConnectionPool):
    def _get_conn(self, timeout=None):
        # 每次都创建新连接，不复用
        return self._new_conn()

    def _put_conn(self, conn):
        # 请求完成后关闭连接
        if conn:
            conn.close()
```

关键：**禁用连接复用**。每个请求建立新的CONNECT隧道，百度CDN负载均衡分配不同出口IP。

## 3. 登录认证流程

### 3.1 流程图

```
┌────────────────┐
│  获取设备指纹   │  origin.txt + v_new.js
└───────┬────────┘
        ▼
┌────────────────┐
│  生成device_id │  RSA加密 → hawkeye API
└───────┬────────┘
        ▼
┌────────────────┐
│   获取加盐参数  │  getGS API → dsk, ssv, dsv
└───────┬────────┘
        ▼
┌────────────────┐
│  第一次登录请求 │  触发滑块验证
└───────┬────────┘
        ▼
┌────────────────┐
│  滑块验证码识别 │  ddddocr slide_match
└───────┬────────┘
        ▼
┌────────────────┐
│  第二次登录请求 │  带验证码ticket
└───────┬────────┘
        ▼
┌────────────────┐
│   获取Cookies  │  保存到 cookies.json
└────────────────┘
```

### 3.2 密码加密

```python
# 1. 用户名/密码 RSA加密
rsa_enc(user)  # Base64(RSA(PKCS1_v1_5_PAD(user)))
rsa_enc(md5(password))

# 2. 密码盐值计算
passwdSalt = RSA(
    XOR(
        HMAC_SHA256(key, MD5(password)),
        SHA256(dsv)
    )
)
# key 从 ssv 和 SHA256(crnd+dsk) XOR解密获得
```

## 4. 数据爬取流程

### 4.1 板块类型

| 类型 | URL路径 | 说明 |
|------|---------|------|
| thshy | /thshy/ | 同花顺行业分类 |
| gn | /gn/ | 概念板块 |
| dy | /dy/ | 地域板块 |

### 4.2 爬取步骤

```
1. 获取板块列表
   GET /thshy/index/field/199112/order/desc/page/{n}/ajax/1/
   解析: 板块名称、链接、日期、成分股数量

2. 获取板块详情
   GET /thshy/detail/field/199112/order/desc/page/{n}/ajax/1/code/{code}/
   解析: 成分股代码、名称

3. 存储CSV
   板块信息.csv: 日期, 板块名称, 来源链接, 驱动事件, 成分股量
   板块代码.csv: 原始序号, 板块名称, 代码, 名称
```

### 4.3 多线程模型

```
主线程
   │
   ├──▶ 线程池 (默认16线程)
   │       ├── Thread-1: fetch_detail(板块A)
   │       ├── Thread-2: fetch_detail(板块B)
   │       ├── Thread-3: fetch_detail(板块C)
   │       └── ...
   │
   └──▶ Semaphore(64) 限制并发连接数
```

## 5. 反爬虫对抗

### 5.1 请求头伪装

完整模拟Chrome 136浏览器：

```python
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...',
    'Sec-Ch-Ua': '"Chromium";v="136", "Google Chrome";v="136"...',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    # ... 共18个标准请求头
}
```

### 5.2 Cookie动态生成

```javascript
// v_new.js - 生成反爬虫cookie 'v'
function get_v() {
    // 基于时间戳和随机数生成
    // 每次请求前刷新
}
```

### 5.3 随机延迟

```python
def random_sleep(base=1.0):
    # 高斯分布: 均值=base, 标准差=base*0.3
    delay = max(0.1, gauss(base, base * 0.3))
    sleep(delay)
```

模拟人工操作的随机间隔，避免固定频率触发检测。

## 6. 错误处理

### 6.1 重试机制

| 场景 | 最大重试 | 策略 |
|------|----------|------|
| 页面请求失败 | 20次 | 随机延迟后重试 |
| 详情页请求 | 10次 | 延迟加倍 |
| 登录失败 | 6次 | 重新获取验证码 |
| Access Denied | 16次 | 等待IP轮换 |

### 6.2 Socket泄漏防护

```python
def connect(self):
    sock = None
    try:
        sock = socket.create_connection(...)
        # ... 隧道建立
    except Exception:
        if sock:
            sock.close()  # 确保异常时关闭
        raise
```

## 7. 关键文件说明

| 文件 | 用途 | 是否必需 |
|------|------|----------|
| cookies.json | 缓存登录Cookie，避免重复登录 | 是 |
| v_new.js | 生成反爬虫Cookie 'v' | 是 |
| origin.txt | 设备指纹信息，用于登录 | 是 |

## 8. 性能指标

- 单次请求延迟: ~500ms (CDN隧道开销)
- 理论吞吐量: 64线程 × 2请求/秒 ≈ 128 req/s
- 实际吞吐量: 受限于高斯延迟，约 30-50 req/s
- IP轮换范围: 180.101.81.0/24 (约256个出口IP)
