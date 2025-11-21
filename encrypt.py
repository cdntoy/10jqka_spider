from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5, AES
from Crypto.Util.number import long_to_bytes, bytes_to_long
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
from urllib.parse import quote
from base64 import b64encode, b64decode
from hashlib import md5, sha256
from os import urandom, mkdir, getpid
from os.path import dirname, join as path_join, exists
import hmac

PATH = dirname(__file__)

pub_key = '''\
-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCxS7QTSCoGWPJxn+Ye1NNxwcXKKv4GnO8cWFB8lsHPJWNuHS3BoktZ24uboq0/IMK9kb/yxgyN5aBHrRkTBKOBWIkSN3kZ8GuK1tjiYxbnkWN66cR8KsWL4xM6WDdgnt4XBNHLIdT6c2O+23a+bQFpw2USuJpyDshRwofwQb4VcwIDAQAB
-----END PUBLIC KEY-----
'''
n = int(
    'CB99A3A4891FFECEDD94F455C5C486B936D'
    '0A37247D750D299D66A711F5F7C1EF8C17E'
    'AFD2E1552081DFFD1F78966593D81A499B8'
    '02B18B0D76EF1D74F217E3FD98E8E05A906'
    '245BEDD810557DFB8F653118E59293A08C1'
    'E51DDCFA2CC13251A5BE301B080A0C93A58'
    '7CB71BAED18AEF9F1E27DA6877AFED6BC56'
    '49DB12DD021',
    16
)
e = 0x10001

key = get_random_bytes(16)

rsa_cipher = PKCS1_v1_5.new(RSA.import_key(pub_key))
aes_cipher = AES.new(key, AES.MODE_ECB)

def get_id() -> str:
    enc = rsa_cipher.encrypt(key)
    with open(path_join(PATH, 'origin.txt'), 'rb') as f:
        device_info = f.read()
    
    _1 = b64encode(enc)
    _2 = b64encode(aes_cipher.encrypt(pad(device_info, AES.block_size)))

    return quote(_1 + b'#' + _2)

def pkcs1_v1_5_pad(message: bytes, k: int) -> bytes:
    """
    Apply PKCS#1 v1.5 padding (encryption type: 0x02).
    :param message: The message to pad (must be <= k - 11 bytes)
    :param k: Key length in bytes (e.g., 256 for 2048-bit RSA)
    :return: Padded message of length k
    """
    if len(message) > k - 11:
        raise ValueError("Message too long for PKCS#1 v1.5 padding.")

    # Generate non-zero padding bytes
    ps_len = k - len(message) - 3
    ps = bytearray()
    while len(ps) < ps_len:
        new_bytes = urandom(1) #ps_len - len(ps))
        ps.extend(b for b in new_bytes if b != 0x00)

    return b'\x02' + bytes(ps) + b'\x00' + message

def rsa_enc(plain: bytes, key_size: int = 128) -> bytes:
    m = int.from_bytes(pkcs1_v1_5_pad(plain, key_size), byteorder = 'big')
    c = pow(m, e, n)
    return b64encode(c.to_bytes(key_size, byteorder = 'big'))

def str_xor(src, dst) -> str:
    ret = ''
    for i in range(len(src)):
        i = i % len(dst)
        ret += chr(ord(src[i]) ^ ord(dst[i]))

    return ret

def passwd_salt(dsk, ssv, dsv, crnd, passwd: bytes) -> bytes:
    key = str_xor(
        b64decode(ssv).decode('UTF-8'),
        sha256((crnd + dsk).encode('UTF-8')).hexdigest()
    ).split('$')[2].split('=')[1].encode('UTF-8')

    return rsa_enc(b64encode(str_xor(
        hmac.new(key, md5(passwd).hexdigest().encode('UTF-8'), sha256).hexdigest(),
        sha256(dsv.encode('UTF-8')).hexdigest()
    ).encode('UTF-8')))

