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

# 全局停止标志
shutdown_event = Event()
# 并发限制信号量 - 限制同时活跃的请求数
connection_semaphore = None

def signal_handler(signum, frame):
    """处理Ctrl+C信号，优雅退出"""
    print('\n\033[93m正在停止爬虫，请稍候...\033[0m')
    shutdown_event.set()
    # 不直接exit，让主线程自然退出以确保资源清理

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

total_count = 0
cur_count = 0
lock = Lock()
RESULT: dict[str, list] = dict()
failed_items: list[str] = []

today = datetime.now().strftime("%Y%m%d%H%M%S")
today_date = datetime.now().strftime("%Y%m%d")

interval = 1  # 默认请求间隔1秒
user = b''
pwd = b''
thread_count = 16  # 默认16线程
VERSION = '1.7.0'
timeout = 10  # 默认超时10秒

def log(msg: str, level: str = 'INFO') -> None:
    """带时间戳的日志输出"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{timestamp}] [{level}] {msg}')

def random_sleep(base: float = None) -> None:
    """随机延迟，使用高斯分布模拟人工操作"""
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



def store(name: str) -> None:
    global today, today_date, RESULT

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

    with open(info_path, 'a') as i_f, open(code_path, 'a') as c_f:
        info = csv_writer(i_f)
        code = csv_writer(c_f)

        if not info_exists:
            info.writerow(['日期', '板块名称', '来源链接', '驱动事件', '成分股量'])
        if not code_exists:
            code.writerow(['原始序号', '板块名称', '代码', '名称'])

        info_arr = []
        code_arr = []
        for key,value in RESULT.items():
            arr = [value[0], key, value[1], value[2], value[3]]
            info_arr.append(arr)
            for v in value[4]:
                code_arr.append([v[0], key, v[1], v[2]])

        info.writerows(info_arr)
        code.writerows(code_arr)

def fetch(index: int, plate: str, max_retries: int = 20) -> None:
    global session, RESULT, interval, lock, cookies_obj

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
            if RESULT.get(name) is None:
                RESULT[name] = []
            else:
                if len(RESULT[name]) != 4:
                    print('Unknown data')
                    quit(3)
                else:
                    continue

            # 日期
            date = date_pattern.findall(td)
            if len(date) == 1:
                RESULT[name].append(date[0])
            else:
                RESULT[name].append('--')

            # 链接
            RESULT[name].append(link[0][0])

            # 描述
            if len(link) == 2:
                RESULT[name].append(link[1][1])
            else:
                # 没有描述就将其置为默认值
                RESULT[name].append('--')

            # 旗下页面总数
            pages = total_pattern.findall(td)
            if len(pages) == 1:
                RESULT[name].append(pages[0])
            else:
                RESULT[name].append('--')

def fetch_code(name: str, prefix: str) -> list[list[str]]:
    global session, RESULT, total_count, cur_count, failed_items, lock, cookies_obj, code_name

    if name not in RESULT or len(RESULT[name]) < 2:
        print(f'[警告] {name} 数据结构不完整')
        return []
    page_ids = page_id.findall(RESULT[name][1])
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
        for code_retry in range(10):
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

def fetch_detail(name: str, prefix: str, max_retries: int = 10) -> None:
    global RESULT, lock, failed_items, connection_semaphore

    for attempt in range(max_retries):
        # 使用信号量限制并发连接数
        if connection_semaphore:
            connection_semaphore.acquire()
        try:
            result = fetch_code(name, prefix)
            with lock:
                RESULT[name].append(result)
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
    global session, cookies_obj, timeout

    count = 0
    while True:
        session.cookies.set('v', cookies_obj.get_v())
        resp = session.get(
            url = 'https://q.10jqka.com.cn/gn/index/field/addtime/order/desc/page/30/ajax/1/',
            allow_redirects = False,
            timeout = timeout
        )

        if resp.status_code == 302:
            print('Need to login')
            if count > 6:
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
            print(f'Access denied (重试 {count}/16，新IP: {new_ip})')
            if count > 16:
                print('Access denied达到最大尝试次数')
                quit(1)
            continue
        elif resp.status_code == 200:
            print('Cookies valid!')
            break

def start_thread(Fn, args, plate) -> None:
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

def fetch_pages(plate: str, url: str) -> None:
    global RESULT, session, page_info, cookies_obj, total_count, cur_count

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

    RESULT = dict()
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

    total_count = len(RESULT.keys())
    cur_count = 0

    start_thread(fetch_detail, list(RESULT.keys()), plate)
    store(name)


if '__main__' == __name__:
    with open(path_join(PATH, 'PID'), 'w') as f:
        f.write(str(getpid()))

    import argparse
    parser = argparse.ArgumentParser(
        description=f'同花顺板块数据爬虫 v{VERSION}',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例: python3 main.py -u 用户名 -p 密码'
    )
    parser.add_argument('-u', '--user', type=str, default='', help='登录用户名', metavar='用户名')
    parser.add_argument('-p', '--password', type=str, default='', help='登录密码', metavar='密码')
    parser.add_argument('-b', '--interval', type=int, default=1, help='请求间隔秒数 (默认: 1)', metavar='秒')
    parser.add_argument('-H', '--threads', type=int, default=16, help='并发线程数 (默认: 16)', metavar='数量')
    parser.add_argument('-t', '--timeout', type=int, default=10, help='请求超时秒数 (默认: 10)', metavar='秒')
    parser.add_argument('-d', '--direct', action='store_true', help='本地直连模式（仅限测试，不使用CDN代理）')
    parser.add_argument('-v', '--version', action='version', version=f'%(prog)s v{VERSION}')

    args = parser.parse_args()

    # 参数验证
    if not args.user or not args.password:
        print('错误: 必须提供用户名(-u)和密码(-p)')
        sys.exit(1)
    if args.interval < 0:
        print('错误: 请求间隔不能为负数')
        sys.exit(1)
    if args.threads < 1 or args.threads > 256:
        print('错误: 线程数必须在1-256之间')
        sys.exit(1)
    if args.timeout < 1:
        print('错误: 超时时间必须大于0')
        sys.exit(1)

    user = args.user.encode('UTF-8')
    pwd = args.password.encode('UTF-8')
    interval = args.interval
    thread_count = args.threads
    timeout = args.timeout

    log(f'同花顺板块爬虫 v{VERSION}')

    log(f'线程数: {thread_count}, 间隔: {interval}s, 超时: {timeout}s')

    # 初始化并发连接限制
    max_concurrent = min(thread_count, 64)
    connection_semaphore = Semaphore(max_concurrent)
    log(f'并发连接限制: {max_concurrent}')

    # 配置网络适配器
    if args.direct:
        # 测试模式：本地直连
        log('⚠️  本地直连模式（仅限测试）', 'WARN')
        log('⚠️  生产环境必须使用CDN代理', 'WARN')
    else:
        # 默认模式：通过百度CDN代理轮换IP
        from cdn_adapter import CdnAdapter, CDN_SERVER
        adapter = CdnAdapter(
            pool_connections=64,
            pool_maxsize=64
        )
        session.mount('https://', adapter)
        log(f'CDN转发: {CDN_SERVER}')

    # 测试CDN是否可用
    try:
        ip = session.get(url='https://4.ipw.cn', timeout=10).text
        log(f'出口IP: {ip.strip()}')
    except Exception as e:
        log(f'CDN连接失败: {e}', 'ERROR')
        sys.exit(1)

    try:
        cookies_obj = _10jqka_Cookies(session, user, pwd)
        check_cookies_valid()

        # 同花顺行业
        log('开始爬取: 同花顺行业')
        fetch_pages(
            'thshy',
            'https://q.10jqka.com.cn/thshy/index/field/199112/order/desc/page/1/ajax/1/'
        )

        # 概念
        log('开始爬取: 概念板块')
        fetch_pages(
            'gn',
            'https://q.10jqka.com.cn/gn/index/field/addtime/order/desc/page/30/ajax/1/'
        )

        # 地域
        log('开始爬取: 地域板块')
        fetch_pages(
            'dy',
            'https://q.10jqka.com.cn/dy/index/field/199112/order/desc/page/1/ajax/1/'
        )

        log('爬取任务完成')
    except Exception as e:
        log(f'爬取失败: {e}', 'ERROR')
        raise
    finally:
        # 确保关闭session释放资源
        session.close()
