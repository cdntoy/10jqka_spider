from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.utils import cookiejar_from_dict, dict_from_cookiejar
from re import compile
from time import sleep
from json import loads, dumps
from cookies import _10jqka_Cookies, PATH, path_join, mkdir, exists, getpid
from datetime import datetime
from sqlite3 import connect
from csv import writer as csv_writer
from threading import Thread, Lock, Event, Semaphore
from random import randint, gauss, uniform
import signal
import sys
import toml
from database import Database
from socket_manager import SocketProxyManager

# 全局停止标志
shutdown_event = Event()
# 并发限制信号量 - 限制同时活跃的请求数
connection_semaphore = None
# 数据库和Socket管理器
db_instance = None
socket_manager = None
storage_mode = 'csv'  # 默认CSV模式
current_batch_id = None

def signal_handler(signum, frame):
    """处理Ctrl+C信号，优雅退出"""
    global db_instance, socket_manager, current_batch_id
    print('\n\033[93m正在停止爬虫，请稍候...\033[0m')
    shutdown_event.set()

    # 清理数据库中断数据
    if db_instance and current_batch_id:
        try:
            log('正在清理不完整的数据...', 'WARN')
            db_instance.rollback()
            db_instance.delete_batch_data(current_batch_id)
        except Exception as e:
            log(f'清理数据失败: {e}', 'ERROR')

    # 停止Socket代理
    if socket_manager:
        try:
            socket_manager.stop()
        except Exception as e:
            log(f'停止Socket代理失败: {e}', 'ERROR')

    # 不直接exit，让主线程自然退出以确保资源清理

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# 常量定义
VERSION = '1.7.3'
MAX_PAGE_RETRIES = 20  # 页面获取最大重试次数
MAX_CODE_RETRIES = 10  # 股票代码获取最大重试次数
MAX_LOGIN_ATTEMPTS = 6  # 登录最大尝试次数
MAX_ACCESS_DENIED_RETRIES = 16  # 访问拒绝最大重试次数
DEFAULT_INTERVAL = 1  # 默认请求间隔（秒）
DEFAULT_THREAD_COUNT = 16  # 默认线程数
DEFAULT_TIMEOUT = 10  # 默认超时时间（秒）

# 全局变量
total_count = 0
cur_count = 0
lock = Lock()
board_data: dict[str, list] = dict()  # 板块数据容器（原RESULT）
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

def random_sleep(base: float = None) -> None:
    """
    随机延迟，使用高斯分布模拟人工操作

    Args:
        base: 基础延迟时间（秒），默认使用全局interval值
    """
    if base is None:
        base = interval
    # 高斯分布: 均值=base, 标准差=base*0.3
    delay = max(0.1, gauss(base, base * 0.3))
    sleep(delay)

tbody_pattern = compile(r'<tbody>([\w\W]+?)</tbody>')
tr_pattern = compile(r'<tr>([\w\W]+?)</tr>')
date_pattern = compile(r'<td>([0-9-]{10})</td>')
link_pattern = compile(r'<td>.+?href="(.+?)".+?>(.+?)</a></td>')
total_pattern = compile(r'</td>[\w\W]+?<td>([0-9]+?)</td>')
page_info = compile(r'page_info.+?/([0-9]+?)<')
page_id = compile(r'code/([0-9]+?)/')
seq_pattern = compile(r'<td>([0-9]+?)</td>[\w\W]+?_blank')
code_name = compile(r'<td>.+?_blank">(.+?)</a>')
ths_pattern = compile(r'<td>[0-9]+?</td>[\w\W]+?href="(.+?)".+?>(.+?)</a>')
session = Session()

# 完整的Chrome浏览器请求头（按标准顺序排列）
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
    从全局board_data准备板块和股票数据

    Returns:
        (boards, stocks) 元组
        - boards: 板块信息列表
        - stocks: 股票信息列表
    """
    global board_data

    boards = []
    stocks = []
    for key, value in board_data.items():
        board = {
            'board_name': key,
            'source_url': value[1] if len(value) > 1 else None,
            'driving_event': value[2] if len(value) > 2 and value[2] != '--' else None,
            'stock_count': value[3] if len(value) > 3 and value[3] != '--' else None
        }
        boards.append(board)

        # 股票数据
        if len(value) > 4:
            for stock in value[4]:
                stocks.append({
                    'board_name': key,
                    'sequence_num': stock[0],
                    'stock_code': stock[1],
                    'stock_name': stock[2]
                })

    return boards, stocks


def save_to_mysql(boards: list[dict], stocks: list[dict], board_type: str) -> None:
    """
    保存数据到MySQL数据库

    Args:
        boards: 板块信息列表
        stocks: 股票信息列表
        board_type: 板块类型（thshy/gn/dy）
    """
    global db_instance, current_batch_id

    if not (storage_mode == 'mysql' and db_instance):
        return

    scrape_date = datetime.now().strftime("%Y-%m-%d")

    try:
        with db_instance.transaction():
            # 插入板块和股票数据
            db_instance.insert_boards(current_batch_id, boards, board_type, scrape_date)
            db_instance.insert_stocks(current_batch_id, stocks, scrape_date)

            # 更新批次状态
            db_instance.update_batch_status(
                current_batch_id,
                'success',
                total_boards=len(boards),
                total_stocks=len(stocks)
            )

        # 生成变化统计
        db_instance.generate_change_summary(current_batch_id, board_type)

        log(f'✓ MySQL保存成功: {len(boards)} 个板块, {len(stocks)} 只股票')

    except Exception as e:
        log(f'MySQL保存失败: {e}', 'ERROR')
        if current_batch_id:
            try:
                db_instance.update_batch_status(current_batch_id, 'failed', error_message=str(e))
            except:
                pass


def save_to_csv(name: str, config: dict) -> None:
    """
    保存数据到CSV文件

    Args:
        name: 板块名称（如"同花顺行业"）
        config: 配置字典
    """
    global today, today_date, board_data

    if not (config['scraper']['enable_csv_backup'] or storage_mode == 'csv'):
        return

    _path = path_join(PATH, 'result')
    if not exists(_path):
        mkdir(_path)

    _path = path_join(PATH, 'result', today_date)
    if not exists(_path):
        mkdir(_path)

    info_path = path_join(_path, f'{today}_{name}板块信息.csv')
    code_path = path_join(_path, f'{today}_{name}板块代码.csv')

    # 检查文件是否存在，决定是否写入头行
    info_exists = exists(info_path)
    code_exists = exists(code_path)

    with open(info_path, 'a', encoding='utf-8') as i_f, \
         open(code_path, 'a', encoding='utf-8') as c_f:
        info = csv_writer(i_f)
        code = csv_writer(c_f)

        if not info_exists:
            info.writerow(['日期', '板块名称', '来源链接', '驱动事件', '成分股量'])
        if not code_exists:
            code.writerow(['原始序号', '板块名称', '代码', '名称'])

        info_arr = []
        code_arr = []
        for key, value in board_data.items():
            arr = [value[0], key, value[1], value[2], value[3]]
            info_arr.append(arr)
            for v in value[4]:
                code_arr.append([v[0], key, v[1], v[2]])

        info.writerows(info_arr)
        code.writerows(code_arr)

    log(f'✓ CSV保存成功: {info_path}')


def store(name: str, board_type: str, config: dict) -> None:
    """
    保存数据到MySQL和/或CSV（协调器函数）

    Args:
        name: 板块名称（如"同花顺行业"）
        board_type: 板块类型（thshy/gn/dy）
        config: 配置字典
    """
    # 1. 准备数据
    boards, stocks = prepare_board_data()

    # 2. 保存到MySQL
    save_to_mysql(boards, stocks, board_type)

    # 3. 保存到CSV
    save_to_csv(name, config)

def fetch(index: int, plate: str, max_retries: int = MAX_PAGE_RETRIES) -> None:
    """
    获取板块列表页的基本信息

    Args:
        index: 页码索引
        plate: 板块类型（gn/thshy/dy）
        max_retries: 最大重试次数
    """
    global session, board_data, interval, lock, cookies_obj

    print(f'\x1b[2K\rFetch {index} page.')

    data = None
    url = ''
    match plate:
        case 'gn':
            url = f'https://q.10jqka.com.cn/gn/index/field/addtime/order/desc/page/{index}/ajax/1/'
        case 'thshy':
            url = f'https://q.10jqka.com.cn/thshy/index/field/199112/order/desc/page/{index}/ajax/1/'
        case 'dy':
            url = f'https://q.10jqka.com.cn/dy/index/field/199112/order/desc/page/{index}/ajax/1/'
        case _:
            raise ValueError(f"Unknown plate type: {plate}")

    # 获取板块信息（添加最大重试限制）
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
                random_sleep()
        except (ConnectionError, TimeoutError) as e:
            print(f'\x1b[2K\r\x1b[91mNetwork error (retry {retry+1}/{max_retries}): {e}\x1b[0m')
            random_sleep()
        except Exception as e:
            print(f'\x1b[2K\r\x1b[91mUnexpected error (retry {retry+1}/{max_retries}): {e}\x1b[0m')
            random_sleep()
    else:
        print(f'\x1b[2K\r\x1b[91mFetch page {index} failed after {max_retries} retries\x1b[0m')
        return

    tr = tr_pattern.findall(data[0])

    # 解析板块信息
    for td in tr:
        # [Link, Name]
        link = link_pattern.findall(td)
        if len(link) == 0: continue

        # 板块名称
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

            # 日期
            date = date_pattern.findall(td)
            if len(date) == 1:
                board_data[name].append(date[0])
            else:
                board_data[name].append('--')

            # 链接
            board_data[name].append(link[0][0])

            # 描述
            if len(link) == 2:
                board_data[name].append(link[1][1])
            else:
                # 没有描述就将其置为默认值
                board_data[name].append('--')

            # 旗下页面总数
            pages = total_pattern.findall(td)
            if len(pages) == 1:
                board_data[name].append(pages[0])
            else:
                board_data[name].append('--')

def fetch_code(name: str, prefix: str) -> list[list[str]]:
    """
    获取指定板块的成分股代码和名称

    Args:
        name: 板块名称
        prefix: 板块类型前缀（gn/thshy/dy）

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

    match prefix:
        case 'gn':
            url_prefix = 'q.10jqka.com.cn/gn/detail/field/199112/order/desc/page'
        case 'thshy':
            url_prefix = 'q.10jqka.com.cn/thshy/detail/field/199112/order/desc/page'
        case 'dy':
            url_prefix = 'q.10jqka.com.cn/dy/detail/field/199112/order/desc/page'
        case _:
            raise ValueError(f"Unknown prefix type: {prefix}")

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
        random_sleep()
        sub_count += 1

        print(
            f'\x1b[2K\r总共需要获取: {total_count}\t'
            f'失败项: [{', '.join(failed_items)}]\t'
            f'Sub count: {sub_count}', end = ''
        )

        # 添加最大重试限制
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
                random_sleep()
                continue
            else:
                break
        else:
            continue  # 重试耗尽，跳过此页

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

def fetch_detail(name: str, prefix: str, max_retries: int = MAX_CODE_RETRIES) -> None:
    """
    获取板块详细信息（成分股列表）并处理重试逻辑

    Args:
        name: 板块名称
        prefix: 板块类型前缀（gn/thshy/dy）
        max_retries: 最大重试次数
    """
    global board_data, lock, failed_items, connection_semaphore

    for attempt in range(max_retries):
        # 使用信号量限制并发连接数
        if connection_semaphore:
            connection_semaphore.acquire()
        try:
            result = fetch_code(name, prefix)
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
            random_sleep(interval * 2)  # 失败后等待更久
        finally:
            if connection_semaphore:
                connection_semaphore.release()

    print(f'\x1b[2K\r\x1b[91m{name} failed after {max_retries} attempts\x1b[0m')

def check_cookies_valid() -> None:
    """
    检查并刷新cookies有效性

    如果cookies失效，会自动重新登录获取新的cookies
    如果遇到访问拒绝（403/401），会等待IP切换并重试
    """
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
            sleep(2)
            # 获取新IP并显示
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

def start_thread(Fn, args, plate) -> None:
    """
    启动多线程执行任务

    Args:
        Fn: 要执行的函数
        args: 参数列表
        plate: 板块类型（会作为第二个参数传递给Fn）
    """
    global thread_count

    threads = []
    for i in args:
        threads.append(Thread(
            target = Fn,
            args = (i, plate)
        ))

    started_threads = list()
    for i in range(len(threads) // thread_count):
        for j in range(thread_count):
            thread = threads.pop()
            thread.start()
            started_threads.append(thread)

        for j in range(len(started_threads)):
            thread = started_threads.pop()
            thread.join()

    for i in range(len(threads)):
        thread = threads.pop()
        thread.start()
        started_threads.append(thread)

    for i in started_threads:
        i.join()

def fetch_pages(plate: str, url: str, config: dict) -> None:
    """
    爬取指定板块类型的所有数据

    Args:
        plate: 板块类型（gn/thshy/dy）
        url: 起始URL
        config: 配置字典
    """
    global board_data, session, page_info, cookies_obj, total_count, cur_count

    name = ''
    match plate:
        case 'gn':
            name = '概念'
        case 'thshy':
            name = '同花顺行业'
        case 'dy':
            name = '地域'
        case _:
            raise ValueError(f"Unknown plate type: {plate}")

    board_data = dict()
    end_page = 1
    session.cookies.set('v', cookies_obj.get_v())
    resp = session.get(
        url = url, # 'https://q.10jqka.com.cn/dy/index/field/199112/order/desc/page/1/ajax/1/',
        allow_redirects = False
    )
    data = page_info.findall(resp.content.decode('gbk', errors='ignore'))
    if len(data) == 1:
        end_page = int(data[0])

    print(f'爬取 {name} 板块，总共: {end_page} 页')
    start_thread(fetch, range(1, end_page + 1), plate)

    total_count = len(board_data.keys())
    cur_count = 0

    start_thread(fetch_detail, list(board_data.keys()), plate)
    store(name, plate, config)


if '__main__' == __name__:
    with open(path_join(PATH, 'PID'), 'w') as f:
        f.write(str(getpid()))

    import argparse
    parser = argparse.ArgumentParser(
        description=f'同花顺板块数据爬虫 v{VERSION}',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例: python3 main.py -u 用户名 -p 密码\n配置文件: config.toml'
    )
    parser.add_argument('-u', '--user', type=str, default='', help='登录用户名', metavar='用户名')
    parser.add_argument('-p', '--password', type=str, default='', help='登录密码', metavar='密码')
    parser.add_argument('-b', '--interval', type=int, help='请求间隔秒数（覆盖配置文件）', metavar='秒')
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
            'thread_count': 32
        }
    if not config.get('path'):
        config['path'] = {
            'result_dir': 'result',
            'socket_binary': './socket/thread_socket',
            'socket_pid_file': 'socket_proxy.pid'
        }

    args = parser.parse_args()

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

    # 初始化Socket代理管理器
    if config['socket_proxy']['enabled']:
        try:
            socket_manager = SocketProxyManager(config)
            socket_manager.start()
        except Exception as e:
            log(f'Socket代理启动失败: {e}', 'ERROR')
            log('降级到本地直连模式', 'WARN')
            config['socket_proxy']['enabled'] = False

    # 初始化MySQL数据库
    if config['database']['enabled']:
        try:
            db_instance = Database(config['database'])
            db_instance.test_connection()
            storage_mode = 'mysql'
            log('✓ MySQL连接成功，使用MySQL存储模式')

            # 清理僵尸批次
            db_instance.cleanup_stale_batches()
        except Exception as e:
            log(f'⚠ MySQL连接失败: {e}', 'WARN')
            log('降级到CSV存储模式')
            storage_mode = 'csv'
            db_instance = None
    else:
        log('MySQL已禁用，使用CSV存储模式')
        storage_mode = 'csv'

    # 初始化并发连接限制
    max_concurrent = min(thread_count, 64)
    connection_semaphore = Semaphore(max_concurrent)
    log(f'并发连接限制: {max_concurrent}')

    # 配置网络适配器
    if config['socket_proxy']['enabled']:
        # Socket代理模式：使用本地socket代理
        proxy_port = config['socket_proxy'].get('port', 8080)
        proxy_url = f'http://127.0.0.1:{proxy_port}'
        session.proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        log(f'Socket代理模式: 127.0.0.1:{proxy_port}')
    else:
        # 本地直连模式
        log('⚠ 本地直连模式（仅限测试）', 'WARN')
        log('⚠ 生产环境推荐使用Socket代理模式', 'WARN')

    # 测试网络连接
    if config['socket_proxy']['enabled']:
        # Socket模式需要测试出口IP
        try:
            ip = session.get(url='https://4.ipw.cn', timeout=10).text
            log(f'出口IP: {ip.strip()}')
        except Exception as e:
            log(f'网络连接测试失败: {e}', 'WARN')

    try:
        cookies_obj = _10jqka_Cookies(session, user, pwd)
        check_cookies_valid()

        # 同花顺行业
        if storage_mode == 'mysql' and db_instance:
            current_batch_id = db_instance.create_batch('thshy')

        log('开始爬取: 同花顺行业')
        fetch_pages(
            'thshy',
            'https://q.10jqka.com.cn/thshy/index/field/199112/order/desc/page/1/ajax/1/',
            config
        )
        current_batch_id = None  # 重置

        # 概念
        if storage_mode == 'mysql' and db_instance:
            current_batch_id = db_instance.create_batch('gn')

        log('开始爬取: 概念板块')
        fetch_pages(
            'gn',
            'https://q.10jqka.com.cn/gn/index/field/addtime/order/desc/page/30/ajax/1/',
            config
        )
        current_batch_id = None  # 重置

        # 地域
        if storage_mode == 'mysql' and db_instance:
            current_batch_id = db_instance.create_batch('dy')

        log('开始爬取: 地域板块')
        fetch_pages(
            'dy',
            'https://q.10jqka.com.cn/dy/index/field/199112/order/desc/page/1/ajax/1/',
            config
        )
        current_batch_id = None  # 重置

        log('✓ 所有爬取任务完成')
    except KeyboardInterrupt:
        log('\n用户中断，程序退出', 'WARN')
    except Exception as e:
        log(f'爬取失败: {e}', 'ERROR')
        raise
    finally:
        # 确保关闭所有资源
        try:
            session.close()
            if db_instance:
                db_instance.close()
            if socket_manager:
                socket_manager.stop()
        except Exception as e:
            log(f'资源清理时出错: {e}', 'ERROR')
