#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
10jqka板块爬虫 v2.0.0
完全重构版本：3数据库架构 + 全中文化 + 可选抓取
"""

from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.utils import cookiejar_from_dict, dict_from_cookiejar
from re import compile
from time import sleep, time
from json import loads, dumps
from cookies import _10jqka_Cookies, PATH, path_join, mkdir, exists, getpid
from datetime import datetime
from csv import writer as csv_writer
from threading import Thread, Lock, Event, Semaphore
from random import gauss
import signal
import sys
import toml
from database import Database, BOARD_CONFIGS
from socket_manager import SocketProxyManager

# 全局停止标志
shutdown_event = Event()
# 并发限制信号量
connection_semaphore = None
# 数据库实例字典（每个板块类型一个）
db_instances: dict[str, Database] = {}
socket_manager = None
storage_mode = 'csv'
# 当前批次ID字典
current_batch_ids: dict[str, int] = {}

def signal_handler(signum, frame):
    """处理Ctrl+C信号，优雅退出"""
    global db_instances, socket_manager, current_batch_ids
    print('\n\033[93m正在停止爬虫，请稍候...\033[0m')
    shutdown_event.set()

    # 清理各数据库中断数据
    for board_type, db in db_instances.items():
        if board_type in current_batch_ids:
            try:
                log(f'正在清理 {board_type} 的不完整数据...', 'WARN')
                db.rollback()
                db.delete_batch_data(current_batch_ids[board_type])
            except Exception as e:
                log(f'清理 {board_type} 数据失败: {e}', 'ERROR')

    # 停止Socket代理
    if socket_manager:
        try:
            socket_manager.stop()
        except Exception as e:
            log(f'停止Socket代理失败: {e}', 'ERROR')

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# 常量定义
VERSION = '2.0.1'
MAX_PAGE_RETRIES = 20
MAX_CODE_RETRIES = 10
MAX_LOGIN_ATTEMPTS = 6
MAX_ACCESS_DENIED_RETRIES = 16
DEFAULT_INTERVAL = 1
DEFAULT_THREAD_COUNT = 16
DEFAULT_TIMEOUT = 10

# 板块编号映射
BOARD_NUMBER_MAP = {
    1: '同花顺行业',
    2: '概念',
    3: '地域'
}

# 全局变量
total_count = 0
cur_count = 0
lock = Lock()
board_data: dict[str, list] = dict()
failed_items: list[str] = []

today = datetime.now().strftime("%Y%m%d%H%M%S")
today_date = datetime.now().strftime("%Y%m%d")

interval = DEFAULT_INTERVAL
user = b''
pwd = b''
thread_count = DEFAULT_THREAD_COUNT
timeout = DEFAULT_TIMEOUT

def log(msg: str, level: str = 'INFO') -> None:
    """带时间戳的日志输出"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{timestamp}] [{level}] {msg}')

def random_sleep(base: float = None) -> bool:
    """
    随机延迟，使用高斯分布模拟人工操作

    支持响应shutdown_event，可被Ctrl+C中断

    Args:
        base: 基础延迟时间（秒），默认使用全局interval值

    Returns:
        bool: True表示正常完成，False表示被shutdown_event中断
    """
    if base is None:
        base = interval
    delay = max(0.1, gauss(base, base * 0.3))

    elapsed = 0.0
    step = 0.05
    while elapsed < delay:
        if shutdown_event.is_set():
            return False
        sleep(min(step, delay - elapsed))
        elapsed += step
    return True

# 正则表达式模式
tbody_pattern = compile(r'<tbody>([\w\W]+?)</tbody>')
tr_pattern = compile(r'<tr>([\w\W]+?)</tr>')
date_pattern = compile(r'<td>([0-9-]{10})</td>')
link_pattern = compile(r'<td>.+?href="(.+?)".+?>(.+?)</a></td>')
total_pattern = compile(r'</td>[\w\W]+?<td>([0-9]+?)</td>')
page_info = compile(r'page_info.+?/([0-9]+?)<')
page_id = compile(r'code/([0-9]+?)/')
seq_pattern = compile(r'<td>([0-9]+?)</td>[\w\W]+?_blank')
code_name = compile(r'<td>.+?_blank">(.+?)</a>')

# HTTP会话配置
session = Session()
adapter = HTTPAdapter(
    pool_connections=64,
    pool_maxsize=64,
    max_retries=Retry(
        total=3,
        backoff_factor=0.3,
        status_forcelist=[500, 502, 503, 504]
    )
)
session.mount('http://', adapter)
session.mount('https://', adapter)

session.headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Origin': 'https://upass.10jqka.com.cn',
    'Referer': 'https://upass.10jqka.com.cn/'
}
cookies_obj = None

with open(path_join(PATH, 'cookies.json'), 'r') as f:
    session.cookies = cookiejar_from_dict(loads(f.read()))


def prepare_board_data() -> tuple[list[dict], list[dict]]:
    """
    从全局board_data准备板块和股票数据,并进行去重处理

    Returns:
        (boards, stocks) 元组
    """
    global board_data

    boards = []
    stocks = []
    seen_boards = set()

    for key, value in board_data.items():
        if key in seen_boards:
            continue
        seen_boards.add(key)

        board = {
            'board_name': key,
            'source_url': value[1] if len(value) > 1 else None,
            'driving_event': value[2] if len(value) > 2 and value[2] != '--' else None,
            'stock_count': value[3] if len(value) > 3 and value[3] != '--' else None
        }
        boards.append(board)

        if len(value) > 4:
            seen_stocks = set()
            for stock in value[4]:
                stock_code = stock[1]

                if stock_code in seen_stocks:
                    continue
                seen_stocks.add(stock_code)

                stocks.append({
                    'board_name': key,
                    'sequence_num': stock[0],
                    'stock_code': stock_code,
                    'stock_name': stock[2]
                })

    return boards, stocks


def save_to_mysql(boards: list[dict], stocks: list[dict], board_type: str, batch_id: int, db: Database) -> None:
    """
    保存数据到MySQL数据库（v2.0.0新架构）

    Args:
        boards: 板块信息列表
        stocks: 股票信息列表
        board_type: 板块类型（同花顺行业/概念/地域）
        batch_id: 批次ID
        db: Database实例
    """
    try:
        with db.transaction():
            # 插入板块和股票数据（使用中文字段名）
            db.insert_boards(batch_id, boards)
            db.insert_stocks(batch_id, stocks)

        # 数据完整性校验
        is_valid, error_msg = db.validate_batch_integrity(batch_id)
        if not is_valid:
            log(f'✗ {board_type} 数据完整性校验失败: {error_msg}', 'ERROR')
            db.delete_batch_data(batch_id)
            raise ValueError(f"数据完整性校验失败: {error_msg}")

        log(f'✓ {board_type} MySQL保存成功: {len(boards)} 个板块, {len(stocks)} 只股票')

    except Exception as e:
        log(f'{board_type} MySQL保存失败: {e}', 'ERROR')
        raise


def save_to_csv(board_type: str, config: dict) -> None:
    """
    保存数据到CSV文件（v2.0.0新文件夹结构）

    Args:
        board_type: 板块类型（同花顺行业/概念/地域）
        config: 配置字典
    """
    global today, today_date, board_data

    if not (config['scraper']['enable_csv_backup'] or storage_mode == 'csv'):
        return

    # 新的CSV文件夹结构: result/同花顺行业板块/20251123/
    result_base = path_join(PATH, 'result')
    if not exists(result_base):
        mkdir(result_base)

    board_folder = path_join(result_base, BOARD_CONFIGS[board_type]['database'])
    if not exists(board_folder):
        mkdir(board_folder)

    date_folder = path_join(board_folder, today_date)
    if not exists(date_folder):
        mkdir(date_folder)

    info_path = path_join(date_folder, f'板块信息_{today}.csv')
    code_path = path_join(date_folder, f'成分股_{today}.csv')

    info_exists = exists(info_path)
    code_exists = exists(code_path)

    with open(info_path, 'a', encoding='utf-8') as i_f, \
         open(code_path, 'a', encoding='utf-8') as c_f:
        info = csv_writer(i_f)
        code = csv_writer(c_f)

        if not info_exists:
            info.writerow(['日期', '板块名称', '来源链接', '驱动事件', '成分股量'])
        if not code_exists:
            code.writerow(['原始序号', '板块名称', '股票代码', '股票名称'])

        info_arr = []
        code_arr = []
        for key, value in board_data.items():
            arr = [value[0], key, value[1], value[2], value[3]]
            info_arr.append(arr)
            for v in value[4]:
                code_arr.append([v[0], key, v[1], v[2]])

        info.writerows(info_arr)
        code.writerows(code_arr)

    log(f'✓ {board_type} CSV保存成功: {info_path}')


def store(board_type: str, config: dict) -> None:
    """
    保存数据到MySQL和/或CSV（v2.0.0版本）

    Args:
        board_type: 板块类型（同花顺行业/概念/地域）
        config: 配置字典
    """
    global db_instances, current_batch_ids

    boards, stocks = prepare_board_data()

    # MySQL存储
    if storage_mode == 'mysql' and board_type in db_instances:
        batch_id = current_batch_ids.get(board_type)
        if batch_id:
            save_to_mysql(boards, stocks, board_type, batch_id, db_instances[board_type])

    # CSV存储
    save_to_csv(board_type, config)


def fetch(index: int, url_type: str, max_retries: int = MAX_PAGE_RETRIES) -> None:
    """
    获取板块列表页的基本信息

    Args:
        index: 页码索引
        url_type: URL类型（thshy/gn/dy）
        max_retries: 最大重试次数
    """
    global session, board_data, interval, lock, cookies_obj

    print(f'\x1b[2K\rFetch {index} page.')

    data = None
    url = ''
    match url_type:
        case 'gn':
            url = f'https://q.10jqka.com.cn/gn/index/field/addtime/order/desc/page/{index}/ajax/1/'
        case 'thshy':
            url = f'https://q.10jqka.com.cn/thshy/index/field/199112/order/desc/page/{index}/ajax/1/'
        case 'dy':
            url = f'https://q.10jqka.com.cn/dy/index/field/199112/order/desc/page/{index}/ajax/1/'
        case _:
            raise ValueError(f"Unknown url_type: {url_type}")

    for retry in range(max_retries):
        if shutdown_event.is_set():
            return
        with lock:
            session.cookies.set('v', cookies_obj.get_v())
        try:
            resp = session.get(
                url = url,
                allow_redirects = False,
                timeout = timeout
            )

            data = tbody_pattern.findall(resp.content.decode('gbk', errors='ignore'))
            if len(data) == 1:
                break
            else:
                if not random_sleep():
                    return
        except (ConnectionError, TimeoutError) as e:
            print(f'\x1b[2K\r\x1b[91mNetwork error (retry {retry+1}/{max_retries}): {e}\x1b[0m')
            if not random_sleep():
                return
        except Exception as e:
            print(f'\x1b[2K\r\x1b[91mUnexpected error (retry {retry+1}/{max_retries}): {e}\x1b[0m')
            if not random_sleep():
                return
    else:
        print(f'\x1b[2K\r\x1b[91mFetch page {index} failed after {max_retries} retries\x1b[0m')
        return

    tr = tr_pattern.findall(data[0])

    for td in tr:
        link = link_pattern.findall(td)
        if len(link) == 0: continue

        name = link[0][1]

        with lock:
            if board_data.get(name) is None:
                board_data[name] = []
            else:
                if len(board_data[name]) != 4:
                    print('Unknown data')
                    quit(3)
                else:
                    continue

            date = date_pattern.findall(td)
            if len(date) == 1:
                board_data[name].append(date[0])
            else:
                board_data[name].append('--')

            board_data[name].append(link[0][0])

            if len(link) == 2:
                board_data[name].append(link[1][1])
            else:
                board_data[name].append('--')

            pages = total_pattern.findall(td)
            if len(pages) == 1:
                board_data[name].append(pages[0])
            else:
                board_data[name].append('--')


def fetch_code(name: str, url_type: str) -> list[list[str]]:
    """
    获取指定板块的成分股代码和名称

    Args:
        name: 板块名称
        url_type: URL类型（thshy/gn/dy）

    Returns:
        成分股列表，每个元素为[序号, 代码, 名称]
    """
    global session, board_data, total_count, cur_count, failed_items, lock, cookies_obj, code_name

    if name not in board_data or len(board_data[name]) < 2:
        print(f'[警告] {name} 数据结构不完整')
        return []
    page_ids = page_id.findall(board_data[name][1])
    if not page_ids:
        print(f'[警告] {name} 无法获取板块代码')
        return []
    code = page_ids[0]
    _result: list[list[str]] = []
    sub_count = 0
    url_prefix = ''

    match url_type:
        case 'gn':
            url_prefix = 'q.10jqka.com.cn/gn/detail/field/199112/order/desc/page'
        case 'thshy':
            url_prefix = 'q.10jqka.com.cn/thshy/detail/field/199112/order/desc/page'
        case 'dy':
            url_prefix = 'q.10jqka.com.cn/dy/detail/field/199112/order/desc/page'
        case _:
            raise ValueError(f"Unknown url_type: {url_type}")

    session.cookies.set('v', cookies_obj.get_v())
    resp = session.get(
        url = f'https://{url_prefix}/1/ajax/1/code/{code}/',
        allow_redirects = False,
        timeout = timeout
    )
    data = page_info.findall(resp.content.decode('gbk', errors='ignore'))
    pages = 0
    if len(data) == 0:
        pages = 1
    else:
        pages = int(data[0])

    for page in range(1, pages + 1):
        if not random_sleep():
            return []
        sub_count += 1

        print(
            f'\x1b[2K\r总共需要获取: {total_count}\t'
            f'失败项: [{', '.join(failed_items)}]\t'
            f'Sub count: {sub_count}', end = ''
        )

        for code_retry in range(MAX_CODE_RETRIES):
            if shutdown_event.is_set():
                return []
            session.cookies.set('v', cookies_obj.get_v())
            resp = session.get(
                url = f'https://{url_prefix}/{page}/ajax/1/code/{code}/',
                timeout = timeout,
                allow_redirects = False
            )

            if resp.status_code == 302:
                check_cookies_valid()

            if resp.status_code == 401 or resp.status_code == 403:
                if not random_sleep():
                    return []
                continue
            else:
                break
        else:
            continue

        tbody = tbody_pattern.findall(resp.content.decode('gbk', errors='ignore'))
        if len(tbody) == 0:
            continue
        tr = tr_pattern.findall(tbody[0])
        for td in tr:
            c_name = code_name.findall(td)
            if len(c_name) < 2: continue
            seq_results = seq_pattern.findall(td)
            if not seq_results: continue
            __result = []
            __result.append(seq_results[0])
            __result.append(c_name[0])
            __result.append(c_name[1])

            _result.append(__result)

    with lock:
        cur_count += 1
        if name in failed_items:
            failed_items.remove(name)

    print(f'\x1b[2K\r\x1b[92m{cur_count}. {name} fetch done.\x1b[0m')
    return _result


def fetch_detail(name: str, url_type: str, max_retries: int = MAX_CODE_RETRIES) -> None:
    """
    获取板块详细信息（成分股列表）并处理重试逻辑

    Args:
        name: 板块名称
        url_type: URL类型（thshy/gn/dy）
        max_retries: 最大重试次数
    """
    global board_data, lock, failed_items, connection_semaphore

    for attempt in range(max_retries):
        if connection_semaphore:
            connection_semaphore.acquire()
        try:
            result = fetch_code(name, url_type)
            with lock:
                board_data[name].append(result)
                if name in failed_items:
                    failed_items.remove(name)
            return
        except Exception as e:
            with lock:
                if name not in failed_items:
                    failed_items.append(name)
            print(f'\x1b[2K\r\x1b[91m{name} retry {attempt + 1}/{max_retries}: {e}\x1b[0m')
            if not random_sleep(interval * 2):
                return
        finally:
            if connection_semaphore:
                connection_semaphore.release()

    print(f'\x1b[2K\r\x1b[91m{name} failed after {max_retries} attempts\x1b[0m')


def check_cookies_valid() -> None:
    """检查并刷新cookies有效性"""
    global session, cookies_obj, timeout

    count = 0
    while True:
        if shutdown_event.is_set():
            return
        session.cookies.set('v', cookies_obj.get_v())
        resp = session.get(
            url = 'https://q.10jqka.com.cn/gn/index/field/addtime/order/desc/page/30/ajax/1/',
            allow_redirects = False,
            timeout = timeout
        )

        if resp.status_code == 302:
            print('Need to login')
            if count > MAX_LOGIN_ATTEMPTS:
                print('获取登录令牌达到最大尝试次数')
                quit(1)

            try:
                cookies = cookies_obj.get_cookies()
            except Exception as e:
                print(f'获取cookies失败: {e}')
                count += 1
                continue

            if cookies == dict():
                print('Get cookies failed')
                count += 1
                continue

            with open(path_join(PATH, 'cookies.json'), 'w') as f:
                f.write(dumps(cookies))

            session.cookies = cookiejar_from_dict(cookies)
            break
        elif resp.status_code > 400:
            count += 1
            if not random_sleep(2):
                return
            try:
                ip_resp = session.get('https://4.ipw.cn', timeout=10)
                new_ip = ip_resp.text.strip()
            except Exception as e:
                new_ip = f'获取失败({e})'
            print(f'Access denied (重试 {count}/{MAX_ACCESS_DENIED_RETRIES}，新IP: {new_ip})')
            if count > MAX_ACCESS_DENIED_RETRIES:
                print('Access denied达到最大尝试次数')
                quit(1)
            continue
        elif resp.status_code == 200:
            print('Cookies valid!')
            break


def start_thread(Fn, args, url_type) -> None:
    """
    启动多线程执行任务

    Args:
        Fn: 要执行的函数
        args: 参数列表
        url_type: URL类型（thshy/gn/dy）
    """
    global thread_count

    threads = []
    for i in args:
        threads.append(Thread(
            target = Fn,
            args = (i, url_type)
        ))

    started_threads = list()
    for i in range(len(threads) // thread_count):
        for j in range(thread_count):
            thread = threads.pop()
            thread.start()
            started_threads.append(thread)

        for j in range(len(started_threads)):
            thread = started_threads.pop()
            while thread.is_alive():
                thread.join(timeout=0.1)
                if shutdown_event.is_set():
                    return

    for i in range(len(threads)):
        thread = threads.pop()
        thread.start()
        started_threads.append(thread)

    for i in started_threads:
        while i.is_alive():
            i.join(timeout=0.1)
            if shutdown_event.is_set():
                return


def fetch_pages(board_type: str, config: dict) -> None:
    """
    爬取指定板块类型的所有数据（v2.0.0版本）

    Args:
        board_type: 板块类型（同花顺行业/概念/地域）
        config: 配置字典
    """
    global board_data, session, page_info, cookies_obj, total_count, cur_count
    global db_instances, current_batch_ids

    # 从配置获取URL和url_type
    board_config = BOARD_CONFIGS[board_type]
    url = board_config['url']
    url_type = board_config['url_type']

    board_data = dict()
    start_time = time()

    # 创建批次
    batch_id = None
    if storage_mode == 'mysql' and board_type in db_instances:
        batch_id = db_instances[board_type].create_batch()
        current_batch_ids[board_type] = batch_id

    # 获取总页数
    end_page = 1
    session.cookies.set('v', cookies_obj.get_v())
    resp = session.get(url = url, allow_redirects = False)
    data = page_info.findall(resp.content.decode('gbk', errors='ignore'))
    if len(data) == 1:
        end_page = int(data[0])

    log(f'开始爬取: {board_type}，总共 {end_page} 页')
    start_thread(fetch, range(1, end_page + 1), url_type)

    total_count = len(board_data.keys())
    cur_count = 0

    start_thread(fetch_detail, list(board_data.keys()), url_type)

    # 计算耗时
    elapsed = time() - start_time

    # 保存数据
    store(board_type, config)

    # 更新批次状态（包含耗时）
    if batch_id and board_type in db_instances:
        boards, stocks = prepare_board_data()
        db_instances[board_type].update_batch_status(
            batch_id,
            '成功',
            total_boards=len(boards),
            total_stocks=len(stocks),
            elapsed_seconds=elapsed
        )
        del current_batch_ids[board_type]

    log(f'✓ {board_type} 完成，耗时 {elapsed:.2f} 秒')


if '__main__' == __name__:
    with open(path_join(PATH, 'PID'), 'w') as f:
        f.write(str(getpid()))

    import argparse
    parser = argparse.ArgumentParser(
        description=f'同花顺板块数据爬虫 v{VERSION}',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''板块类型编号:
  1 = 同花顺行业板块
  2 = 概念板块
  3 = 地域板块

使用示例:
  抓取全部板块:
    python3 main.py -u 用户名 -p 密码 -s

  只抓取概念板块:
    python3 main.py -u 用户名 -p 密码 -s -B 2

  只抓取行业板块:
    python3 main.py -u 用户名 -p 密码 -s -B 1

  抓取多个板块（概念+地域）:
    python3 main.py -u 用户名 -p 密码 -s -B 2 3

配置文件: config.toml
'''
    )
    parser.add_argument('-u', '--user', type=str, default='', help='登录用户名', metavar='用户名')
    parser.add_argument('-p', '--password', type=str, default='', help='登录密码', metavar='密码')
    parser.add_argument('-b', '--interval', type=int, help='请求间隔秒数（覆盖配置文件）', metavar='秒')
    parser.add_argument('-B', '--boards', type=int, nargs='+',
                        choices=[1, 2, 3],
                        help='指定板块: 1=同花顺行业 2=概念 3=地域（可多选）', metavar='板块')
    parser.add_argument('-H', '--threads', type=int, help='并发线程数（覆盖配置文件）', metavar='数量')
    parser.add_argument('-t', '--timeout', type=int, help='请求超时秒数（覆盖配置文件）', metavar='秒')
    parser.add_argument('-s', '--socket', action='store_true', help='Socket代理模式（覆盖配置文件）')
    parser.add_argument('-P', '--proxy-port', type=int, help='Socket代理端口（覆盖配置文件）', metavar='端口')
    parser.add_argument('-d', '--direct', action='store_true', help='本地直连模式（仅限测试，不使用代理）')
    parser.add_argument('-c', '--config', type=str, default='config.toml', help='配置文件路径', metavar='路径')
    parser.add_argument('-v', '--version', action='version', version=f'%(prog)s v{VERSION}')

    args = parser.parse_args()

    # 加载配置文件
    config = {}
    config_file = path_join(PATH, args.config)
    if exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = toml.load(f)
            log(f'✓ 加载配置文件: {config_file}')
        except Exception as e:
            log(f'警告: 配置文件加载失败，使用默认配置: {e}', 'WARN')
    else:
        log(f'警告: 配置文件不存在 ({config_file})，使用默认配置', 'WARN')

    # 设置默认配置
    if not config.get('database'):
        config['database'] = {'enabled': False}
    if not config.get('socket_proxy'):
        config['socket_proxy'] = {'enabled': True, 'port': 8080}
    if not config.get('scraper'):
        config['scraper'] = {
            'enable_csv_backup': True,
            'interval_seconds': 1,
            'max_retries': 20,
            'thread_count': 32,
            'enabled_boards': ['同花顺行业', '概念', '地域']  # 默认全部启用
        }
    if not config.get('path'):
        config['path'] = {
            'result_dir': 'result',
            'socket_binary': './socket/thread_socket',
            'socket_pid_file': 'socket_proxy.pid'
        }

    # 确保enabled_boards配置存在
    if 'enabled_boards' not in config['scraper']:
        config['scraper']['enabled_boards'] = ['同花顺行业', '概念', '地域']

    # 参数验证
    if not args.user or not args.password:
        print('错误: 必须提供用户名(-u)和密码(-p)')
        sys.exit(1)
    if args.socket and args.direct:
        print('错误: -s (socket代理) 和 -d (直连) 不能同时使用')
        sys.exit(1)

    # 命令行参数覆盖配置文件
    if args.interval is not None:
        config['scraper']['interval_seconds'] = args.interval
    if args.threads is not None:
        config['scraper']['thread_count'] = args.threads
    if args.timeout is not None:
        timeout = args.timeout
    else:
        timeout = DEFAULT_TIMEOUT
    if args.socket:
        config['socket_proxy']['enabled'] = True
    if args.direct:
        config['socket_proxy']['enabled'] = False
    if args.proxy_port is not None:
        config['socket_proxy']['port'] = args.proxy_port
    if args.boards is not None:
        # 将数字转换为板块名称
        board_names = [BOARD_NUMBER_MAP[num] for num in args.boards]
        config['scraper']['enabled_boards'] = board_names
        board_list = ', '.join([f'{num}={BOARD_NUMBER_MAP[num]}' for num in args.boards])
        log(f'命令行指定板块: {board_list}')

    # 参数范围验证
    if config['scraper']['interval_seconds'] < 0:
        print('错误: 请求间隔不能为负数')
        sys.exit(1)
    if config['scraper']['thread_count'] < 1 or config['scraper']['thread_count'] > 256:
        print('错误: 线程数必须在1-256之间')
        sys.exit(1)
    if timeout < 1:
        print('错误: 超时时间必须大于0')
        sys.exit(1)
    if config['socket_proxy'].get('port', 8080) < 1 or config['socket_proxy'].get('port', 8080) > 65535:
        print('错误: 代理端口必须在1-65535之间')
        sys.exit(1)

    user = args.user.encode('UTF-8')
    pwd = args.password.encode('UTF-8')
    interval = config['scraper']['interval_seconds']
    thread_count = config['scraper']['thread_count']

    log(f'同花顺板块爬虫 v{VERSION}')
    log(f'线程数: {thread_count}, 间隔: {interval}s, 超时: {timeout}s')

    # 显示板块类型映射
    enabled_boards = config['scraper']['enabled_boards']
    log('━' * 50)
    log('板块类型说明:')
    log('  1 = 同花顺行业板块')
    log('  2 = 概念板块')
    log('  3 = 地域板块')
    log('━' * 50)
    board_display = ', '.join(enabled_boards)
    log(f'本次抓取板块: {board_display}')
    log('━' * 50)

    # 初始化Socket代理管理器
    if config['socket_proxy']['enabled']:
        try:
            socket_manager = SocketProxyManager(config)
            socket_manager.start()
        except Exception as e:
            log(f'Socket代理启动失败: {e}', 'ERROR')
            log('降级到本地直连模式', 'WARN')
            config['socket_proxy']['enabled'] = False

    # 初始化MySQL数据库（为每个启用的板块类型创建Database实例）
    enabled_boards = config['scraper']['enabled_boards']
    if config['database']['enabled']:
        try:
            for board_type in enabled_boards:
                if board_type not in BOARD_CONFIGS:
                    log(f'警告: 未知的板块类型 {board_type}，跳过', 'WARN')
                    continue

                db = Database(config['database'], board_type)
                if db.test_connection():
                    db_instances[board_type] = db
                    log(f'✓ {board_type} MySQL连接成功')

            if db_instances:
                storage_mode = 'mysql'
                log(f'✓ 已连接 {len(db_instances)} 个数据库，使用MySQL存储模式')
            else:
                log('⚠ 所有MySQL连接失败', 'WARN')
                log('降级到CSV存储模式')
                storage_mode = 'csv'
        except Exception as e:
            log(f'⚠ MySQL连接失败: {e}', 'WARN')
            log('降级到CSV存储模式')
            storage_mode = 'csv'
    else:
        log('MySQL已禁用，使用CSV存储模式')
        storage_mode = 'csv'

    # 初始化并发连接限制
    max_concurrent = min(thread_count, 64)
    connection_semaphore = Semaphore(max_concurrent)
    log(f'并发连接限制: {max_concurrent}')

    # 配置网络适配器
    if config['socket_proxy']['enabled']:
        proxy_port = config['socket_proxy'].get('port', 8080)
        proxy_url = f'http://127.0.0.1:{proxy_port}'
        session.proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        log(f'Socket代理模式: 127.0.0.1:{proxy_port}')
    else:
        log('⚠ 本地直连模式（仅限测试）', 'WARN')
        log('⚠ 生产环境推荐使用Socket代理模式', 'WARN')

    # 测试网络连接
    if config['socket_proxy']['enabled']:
        try:
            ip = session.get(url='https://4.ipw.cn', timeout=10).text
            log(f'出口IP: {ip.strip()}')
        except Exception as e:
            log(f'网络连接测试失败: {e}', 'WARN')

    try:
        cookies_obj = _10jqka_Cookies(session, user, pwd)
        check_cookies_valid()

        # 根据配置抓取启用的板块类型
        total_start = time()
        for board_type in enabled_boards:
            if board_type not in BOARD_CONFIGS:
                log(f'跳过未知的板块类型: {board_type}', 'WARN')
                continue

            if shutdown_event.is_set():
                log('用户中断，停止抓取', 'WARN')
                break

            fetch_pages(board_type, config)

        total_elapsed = time() - total_start
        log(f'✓ 所有爬取任务完成，总耗时 {total_elapsed:.2f} 秒')

    except KeyboardInterrupt:
        log('\n用户中断，程序退出', 'WARN')
    except Exception as e:
        log(f'爬取失败: {e}', 'ERROR')
        raise
    finally:
        # 确保关闭所有资源
        try:
            session.close()
            for db in db_instances.values():
                db.close()
            if socket_manager:
                socket_manager.stop()
        except Exception as e:
            log(f'资源清理时出错: {e}', 'ERROR')
