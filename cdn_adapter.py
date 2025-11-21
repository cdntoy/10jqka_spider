"""
CDN转发适配器 - 通过百度CDN建立CONNECT隧道实现IP轮换

原理：
1. 直接连接百度CDN服务器(110.242.70.68:443)
2. 发送CONNECT请求建立隧道
3. 在隧道内进行SSL握手和HTTP请求
4. 百度CDN负载均衡分配不同出口IP (180.101.81.x)

使用方式：
    from cdn_adapter import create_cdn_session
    session = create_cdn_session()
    resp = session.get('https://example.com')
"""

import socket
import ssl
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.poolmanager import PoolManager
from urllib3.connection import HTTPSConnection
from urllib3.connectionpool import HTTPSConnectionPool

# 百度CDN服务器
CDN_SERVER = "110.242.70.68"
CDN_PORT = 443


class CdnConnection(HTTPSConnection):
    """通过CDN隧道的HTTPS连接"""

    def __init__(self, host, port=None, **kwargs):
        self._real_host = host
        self._real_port = port or 443
        # 连接到CDN而不是真实主机
        super().__init__(CDN_SERVER, CDN_PORT, **kwargs)

    def connect(self):
        """建立CONNECT隧道后再做SSL握手"""
        sock = None
        try:
            # 1. 建立到CDN的TCP连接
            sock = socket.create_connection(
                (CDN_SERVER, CDN_PORT),
                timeout=self.timeout
            )

            # 2. 发送CONNECT请求（百度CDN仅接受简单格式）
            connect_req = f"CONNECT {self._real_host}:{self._real_port} HTTP/1.1\r\n\r\n"
            sock.sendall(connect_req.encode())

            # 3. 读取响应
            response = b''
            while b'\r\n\r\n' not in response:
                chunk = sock.recv(4096)
                if not chunk:
                    raise ConnectionError("CDN连接关闭")
                response += chunk

            # 4. 检查是否成功
            status_line = response.split(b'\r\n')[0].decode()
            if '200' not in status_line:
                raise ConnectionError(f"CONNECT隧道失败: {status_line}")

            # 5. 在隧道上建立SSL
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            self.sock = context.wrap_socket(
                sock,
                server_hostname=self._real_host
            )
        except Exception:
            # 确保异常时关闭socket，防止泄漏
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
            raise


class CdnConnectionPool(HTTPSConnectionPool):
    """CDN连接池 - 禁用连接复用以确保IP轮换"""
    ConnectionCls = CdnConnection

    def _get_conn(self, timeout=None):
        """每次都创建新连接，不复用，确保IP轮换"""
        return self._new_conn()

    def _put_conn(self, conn):
        """请求完成后关闭连接而非归还池"""
        if conn:
            conn.close()


class CdnPoolManager(PoolManager):
    """CDN连接池管理器"""

    def _new_pool(self, scheme, host, port, request_context=None):
        if scheme == 'https':
            return CdnConnectionPool(
                host, port,
                timeout=self.connection_pool_kw.get('timeout'),
                maxsize=1,  # 不复用连接
                block=False
            )
        return super()._new_pool(scheme, host, port, request_context)


class CdnAdapter(HTTPAdapter):
    """通过CDN转发的HTTP适配器"""

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        self.poolmanager = CdnPoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            **pool_kwargs
        )


def create_cdn_session(pool_connections=64, pool_maxsize=64, max_retries=3):
    """
    创建通过CDN转发的Session

    Args:
        pool_connections: 连接池数量
        pool_maxsize: 每个池的最大连接数
        max_retries: 最大重试次数

    Returns:
        配置好的requests.Session对象
    """
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    session = requests.Session()

    retry = Retry(
        total=max_retries,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )

    adapter = CdnAdapter(
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize,
        max_retries=retry
    )

    session.mount('https://', adapter)

    return session


def test():
    """测试CDN转发"""
    print(f"CDN服务器: {CDN_SERVER}:{CDN_PORT}")

    session = create_cdn_session()

    try:
        resp = session.get('https://4.ipw.cn', timeout=10)
        print(f"出口IP: {resp.text.strip()}")
        return True
    except Exception as e:
        print(f"测试失败: {e}")
        return False


if __name__ == '__main__':
    test()
