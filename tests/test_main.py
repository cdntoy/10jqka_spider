"""
10jqka_spider 单元测试
"""
import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 尝试导入加密模块（可能缺少依赖）
try:
    from encrypt import rsa_enc, str_xor, pkcs1_v1_5_pad
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


@unittest.skipUnless(HAS_CRYPTO, "pycryptodome not installed")
class TestEncrypt(unittest.TestCase):
    """加密模块测试"""

    def test_rsa_enc_returns_bytes(self):
        """测试RSA加密返回bytes类型"""
        result = rsa_enc(b'test')
        self.assertIsInstance(result, bytes)

    def test_rsa_enc_not_empty(self):
        """测试RSA加密结果非空"""
        result = rsa_enc(b'hello')
        self.assertTrue(len(result) > 0)

    def test_str_xor_same_length(self):
        """测试XOR相同长度字符串"""
        result = str_xor('abc', 'xyz')
        self.assertEqual(len(result), 3)

    def test_str_xor_different_length(self):
        """测试XOR不同长度字符串"""
        result = str_xor('abcdef', 'xy')
        self.assertEqual(len(result), 6)

    def test_pkcs1_padding_length(self):
        """测试PKCS1填充后长度正确"""
        message = b'test'
        # 填充长度为 k-1 (不含前导0x00字节，由实际加密时补齐)
        result = pkcs1_v1_5_pad(message, 128)
        self.assertIn(len(result), [127, 128])

    def test_pkcs1_padding_format(self):
        """测试PKCS1填充格式正确"""
        message = b'test'
        result = pkcs1_v1_5_pad(message, 128)
        self.assertEqual(result[0], 0x02)  # 加密类型
        self.assertTrue(b'\x00' + message in result)


class TestPatterns(unittest.TestCase):
    """正则表达式测试 - 独立测试，不依赖外部库"""

    def test_date_pattern_match(self):
        """测试日期正则匹配"""
        import re
        date_pattern = re.compile(r'<td>([0-9-]{10})</td>')
        html = '<td>2025-01-15</td>'
        result = date_pattern.findall(html)
        self.assertEqual(result, ['2025-01-15'])

    def test_link_pattern_match(self):
        """测试链接正则匹配"""
        import re
        link_pattern = re.compile(r'<td>.+?href="(.+?)".+?>(.+?)</a></td>')
        # 正则要求href和>之间必须有内容
        html = '<td>xx<a href="http://example.com" xx>测试</a></td>'
        result = link_pattern.findall(html)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], 'http://example.com')
        self.assertEqual(result[0][1], '测试')

    def test_tbody_pattern(self):
        """测试tbody正则匹配"""
        import re
        tbody_pattern = re.compile(r'<tbody>([\w\W]+?)</tbody>')
        html = '<table><tbody><tr><td>data</td></tr></tbody></table>'
        result = tbody_pattern.findall(html)
        self.assertEqual(len(result), 1)
        self.assertIn('<tr>', result[0])

    def test_page_id_pattern(self):
        """测试页面ID正则"""
        import re
        page_id = re.compile(r'code/([0-9]+?)/')
        url = 'https://q.10jqka.com.cn/gn/detail/code/301234/'
        result = page_id.findall(url)
        self.assertEqual(result, ['301234'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
