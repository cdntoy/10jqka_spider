from requests import Session
from requests.utils import cookiejar_from_dict, dict_from_cookiejar
from encrypt import get_id, rsa_enc, passwd_salt, md5, sha256, PATH, path_join, mkdir, exists, getpid
from time import time
from json import loads, dumps
import execjs
import random
import ddddocr

class _10jqka_Cookies:
    def __init__(self, session: Session, user: bytes, pwd: bytes) -> None:
        self.js_ctx = None
        self.user = user
        self.pwd = pwd
        self.session = session

        with open(path_join(PATH, 'v_new.js'), 'r') as f:
            self.js_ctx = execjs.compile(f.read())

        self.session.cookies.set('v', self.get_v())
        self.det = ddddocr.DdddOcr(ocr = False, det = False)


    def get_v(self) -> str:
        return self.js_ctx.call('get_v') # type: ignore

    def get_crnd(self):
        return ''.join(random.choices('0123456789abcdefghijklmnopqrstuvwxyz', k=8)) + ''.join(
            random.choices('0123456789abcdefghijklmnopqrstuvwxyz', k=8))

    def get_gs(self, crnd: str, uname: str) -> dict:
        return self.session.post(
            url = 'https://upass.10jqka.com.cn/user/getGS',
            data = {
                'uname': uname,
                'rsa_version': "default_4",
                'crnd': crnd
            }
        ).json()

    def generate(self, token: str) -> dict:
        return self.session.post(
            url = 'https://hawkeye.10jqka.com.cn/v1/hawkeye/generate',
            data = 'pass_code=&user_id=null&source_type=web&collections=' +
                token +
                '&protocol=fingerprint_1',
            # data = {
            #     'pass_code': '',
            #     'user_id': 'null',
            #     'source_type': 'web',
            #     'collections': token,
            #     'protocol': 'fingerprint_1'
            # },
            allow_redirects = False
        ).json()


    def get_ticket(self):
        resp = dict()
        captcha_resp = dict()
        phrase = ''

        for i in range(10):
            try:
                resp = self.session.get(
                    url = 'https://captcha.10jqka.com.cn/getPreHandle',
                    params = {
                        'captcha_type': 4,
                        'appid': 'registernew',
                        'random': time() * 2,
                        'callback': 'PreHandle'
                    }
                )
                captcha_resp = loads(resp.text[10:-1])
                c_background = self.session.get(
                    url = f'https://captcha.10jqka.com.cn/getImg?{captcha_resp['data']['urlParams']}',
                    params = {
                        'iuk': captcha_resp['data']['imgs'][0]
                    }
                ).content
                c_target = self.session.get(
                    url = f'https://captcha.10jqka.com.cn/getImg?{captcha_resp['data']['urlParams']}',
                    params = {
                        'iuk': captcha_resp['data']['imgs'][1]
                    }
                ).content
                self.session.cookies.set('v', self.get_v())

                det_res = self.det.slide_match(target_bytes = c_target, background_bytes = c_background, simple_target = True)
                # 滑块验证码位置校正系数 (根据实际验证码图片尺寸调整)
                X_SCALE = 0.908        # X轴缩放比例
                Y_SCALE = 0.9323 - 1e-9  # Y轴缩放比例
                CAPTCHA_WIDTH = 309    # 验证码背景宽度
                CAPTCHA_HEIGHT = 177.22058823529412  # 验证码背景高度
                phrase = f'{int(det_res["target"][0]) * X_SCALE};' \
                    f'{det_res["target"][1] * Y_SCALE};' \
                    f'{CAPTCHA_WIDTH};{CAPTCHA_HEIGHT}'

                resp = self.session.get(
                    url = f'https://captcha.10jqka.com.cn/getTicket?{captcha_resp['data']['urlParams']}',
                    params = {
                        'phrase': phrase,
                        'callback': 'verify'
                    }
                )
                resp = loads(resp.text[7:-1])
                if resp.get('ticket') != None:
                    break
            except Exception as e:
                print(f'获取验证码失败，重试: {i}: {e}')

            if i == 9:
                return '', '', ''

        ticket = resp['ticket']
        signature = captcha_resp['data']['sign']

        return signature, phrase, ticket

    def get_cookies(self) -> dict:
        token = self.generate(get_id())
        pass_code = token['data']['pass_code']
        device_code = token['data']['device_code']
        expires_time = token['data']['expires_time']
        resp = self.session.post(
            url = 'https://upass.10jqka.com.cn/common/setDeviceCookie',
            data = {
                'u_dpass': pass_code,
                'u_did': device_code,
                'u_uver': '1.0.0',
                'expires_time': expires_time
            },
            allow_redirects = False
        )

        self.session.cookies.set('v', self.get_v())

        crnd = self.get_crnd()
        gs = self.get_gs(crnd, rsa_enc(self.user).decode('UTF-8'))

        resp = self.session.post(
            url = 'https://upass.10jqka.com.cn/login/dologinreturnjson2',
            data = {
                "uname": rsa_enc(self.user),
                "passwd": rsa_enc(md5(self.pwd).hexdigest().encode('UTF-8')),
                "saltLoginTimes": "1",
                "longLogin": "on",
                "rsa_version": "default_4",
                "source": "pc_web",
                "request_type": "login",
                "captcha_type": "4",
                "upwd_score": 55,
                "ignore_upwd_score": "",
                "passwdSalt": passwd_salt(gs['dsk'], gs['ssv'], gs['dsv'], crnd, self.pwd),
                "dsk": gs['dsk'],
                "crnd": crnd,
                "ttype": "WEB",
                "sdtis": "C22",
                "timestamp": int(time())
            },
            allow_redirects = False
        )

        # print(resp.json())

        signature, phrase, ticket = self.get_ticket()

        resp = self.session.post(
            url = 'https://upass.10jqka.com.cn/login/dologinreturnjson2',
            data = {
                "uname": rsa_enc(self.user),
                "passwd": rsa_enc(md5(self.pwd).hexdigest().encode('UTF-8')),
                "saltLoginTimes": "1",
                "longLogin": "on",
                "rsa_version": "default_4",
                "source": "pc_web",
                "request_type": "login",
                "captcha_type": "4",
                "captcha_phrase": phrase,
                "captcha_ticket": ticket,
                "captcha_signature": signature,
                "upwd_score": 55,
                "ignore_upwd_score": "",
                "passwdSalt": passwd_salt(gs['dsk'], gs['ssv'], gs['dsv'], crnd, self.pwd),
                "dsk": gs['dsk'],
                "crnd": crnd,
                "ttype": "WEB",
                "sdtis": "C22",
                "timestamp": int(time())
            },
            allow_redirects = False
        )

        if resp.json()['errorcode'] == 0:
            return dict_from_cookiejar(self.session.cookies)
        else:
            return dict()
