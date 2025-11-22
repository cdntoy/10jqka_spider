#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Socket代理进程管理模块
提供Socket代理的启动、监控、重启、清理功能
"""

import os
import subprocess
import socket
import time
import signal
import logging
from threading import Thread, Event
from typing import Optional

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SocketProxyManager:
    """Socket代理进程管理器"""

    def __init__(self, config: dict):
        """
        初始化Socket代理管理器

        Args:
            config: 配置字典，包含socket_proxy和path配置
        """
        self.config = config['socket_proxy']
        self.path_config = config['path']

        self.port = self.config.get('port', 8080)
        self.server_ip = self.config.get('server_ip', '110.242.70.68')
        self.server_port = self.config.get('server_port', 443)
        self.daemon_mode = self.config.get('daemon_mode', True)
        self.auto_restart = self.config.get('auto_restart', True)
        self.health_check_interval = self.config.get('health_check_interval', 5)
        self.startup_timeout = self.config.get('startup_timeout', 10)

        self.socket_binary = self.path_config.get('socket_binary', './socket/thread_socket')
        self.pid_file = self.path_config.get('socket_pid_file', 'socket_proxy.pid')

        self.process: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None
        self.monitor_thread: Optional[Thread] = None
        self.shutdown_event = Event()

    def check_port_available(self) -> bool:
        """
        检查端口是否可用

        Returns:
            True: 端口未被占用
            False: 端口已被占用
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('127.0.0.1', self.port))
                return True
        except OSError:
            return False

    def find_process_by_port(self) -> Optional[int]:
        """
        通过端口查找进程PID

        Returns:
            PID或None
        """
        try:
            # 使用lsof查找占用端口的进程
            result = subprocess.run(
                ['lsof', '-ti', f':{self.port}'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                pid = int(result.stdout.strip().split('\n')[0])
                logger.debug(f"找到占用端口 {self.port} 的进程: PID {pid}")
                return pid
        except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
            pass

        return None

    def kill_existing_proxy(self):
        """清理已存在的Socket代理进程"""
        # 1. 尝试从PID文件读取
        if os.path.exists(self.pid_file):
            try:
                with open(self.pid_file, 'r') as f:
                    pid = int(f.read().strip())
                    if self._is_process_alive(pid):
                        logger.info(f"从PID文件找到进程 {pid}，正在终止...")
                        self._kill_process(pid)
                os.remove(self.pid_file)
            except (ValueError, FileNotFoundError, PermissionError) as e:
                logger.warning(f"清理PID文件失败: {e}")

        # 2. 通过端口查找进程
        pid = self.find_process_by_port()
        if pid:
            logger.info(f"端口 {self.port} 被进程 {pid} 占用，正在终止...")
            self._kill_process(pid)

        # 3. 等待端口释放
        max_wait = 5
        for i in range(max_wait):
            if self.check_port_available():
                logger.info(f"✓ 端口 {self.port} 已释放")
                return
            time.sleep(1)

        logger.warning(f"端口 {self.port} 仍被占用")

    def _is_process_alive(self, pid: int) -> bool:
        """检查进程是否存活"""
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _kill_process(self, pid: int):
        """终止进程"""
        try:
            # 先尝试SIGTERM（优雅退出）
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)

            # 如果还活着，使用SIGKILL强制终止
            if self._is_process_alive(pid):
                os.kill(pid, signal.SIGKILL)
                time.sleep(0.5)

            logger.info(f"✓ 进程 {pid} 已终止")
        except ProcessLookupError:
            logger.debug(f"进程 {pid} 已不存在")
        except PermissionError:
            logger.error(f"无权限终止进程 {pid}")

    def start(self):
        """启动Socket代理"""
        if not self.config.get('enabled', True):
            logger.info("Socket代理已禁用，跳过启动")
            return

        logger.info("正在启动Socket代理...")

        # 1. 清理已存在的进程
        self.kill_existing_proxy()

        # 2. 检查可执行文件
        if not os.path.exists(self.socket_binary):
            raise FileNotFoundError(f"Socket代理程序不存在: {self.socket_binary}")

        # 3. 构建启动命令
        cmd = [
            self.socket_binary,
            '-r', self.server_ip,
            '-p', str(self.port),
        ]

        if self.daemon_mode:
            cmd.append('-d')

        # 4. 启动进程
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # 5. 等待进程启动（检查PID）
            if self.daemon_mode:
                # 守护进程模式：需要从输出中获取PID
                time.sleep(0.5)
                # 通过端口查找真实PID
                self.pid = self.find_process_by_port()
            else:
                self.pid = self.process.pid

            # 6. 验证启动
            if not self._wait_for_startup():
                raise RuntimeError("Socket代理启动超时")

            # 7. 保存PID到文件
            if self.pid:
                with open(self.pid_file, 'w') as f:
                    f.write(str(self.pid))

            logger.info(f"✓ Socket代理已启动 (PID: {self.pid}, 端口: {self.port})")

            # 8. 启动监控线程
            if self.auto_restart:
                self.monitor_thread = Thread(target=self._monitor_loop, daemon=True)
                self.monitor_thread.start()
                logger.debug("Socket代理监控线程已启动")

        except Exception as e:
            logger.error(f"启动Socket代理失败: {e}")
            raise

    def _wait_for_startup(self) -> bool:
        """等待Socket代理启动完成"""
        start_time = time.time()

        while time.time() - start_time < self.startup_timeout:
            # 检查端口是否开始监听
            if not self.check_port_available():
                logger.info(f"✓ Socket代理端口 {self.port} 已就绪")
                return True
            time.sleep(0.5)

        return False

    def _monitor_loop(self):
        """监控循环（后台线程）"""
        logger.debug("进入监控循环")

        while not self.shutdown_event.is_set():
            time.sleep(self.health_check_interval)

            if self.shutdown_event.is_set():
                break

            # 检查进程是否存活
            if not self.is_alive():
                logger.warning("⚠ Socket代理进程异常退出，正在重启...")
                try:
                    self.restart()
                except Exception as e:
                    logger.error(f"重启Socket代理失败: {e}")
                    break

        logger.debug("退出监控循环")

    def is_alive(self) -> bool:
        """
        检查Socket代理是否存活

        Returns:
            True: 进程存活
            False: 进程已退出
        """
        if self.pid is None:
            return False

        # 检查进程
        if not self._is_process_alive(self.pid):
            return False

        # 检查端口
        if self.check_port_available():
            return False

        return True

    def restart(self):
        """重启Socket代理"""
        logger.info("正在重启Socket代理...")
        self.stop()
        time.sleep(1)
        self.start()

    def stop(self):
        """停止Socket代理"""
        logger.info("正在停止Socket代理...")

        # 1. 停止监控线程
        self.shutdown_event.set()
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)

        # 2. 终止进程
        if self.pid:
            self._kill_process(self.pid)
            self.pid = None

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
            except Exception as e:
                logger.warning(f"终止进程时出错: {e}")
            finally:
                self.process = None

        # 3. 删除PID文件
        if os.path.exists(self.pid_file):
            try:
                os.remove(self.pid_file)
            except Exception as e:
                logger.warning(f"删除PID文件失败: {e}")

        logger.info("✓ Socket代理已停止")

    def __del__(self):
        """析构函数：确保资源清理"""
        if hasattr(self, 'shutdown_event') and not self.shutdown_event.is_set():
            self.stop()
