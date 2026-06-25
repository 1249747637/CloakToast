"""
chain_proxy 单元测试：URL 解析、SOCKS5 协议握手、服务器启停。
"""
import asyncio
import struct
import socket
import pytest
from backend.services.chain_proxy import (
    _parse, _socks5_accept, _socks5_connect, _socks5_reply,
    start_chain_proxy, stop_chain_proxy,
)


# ---------------------------------------------------------------------------
# URL 解析
# ---------------------------------------------------------------------------

def test_parse_socks5_with_credentials():
    p = _parse("socks5://alice:pass@1.2.3.4:7897")
    assert p["scheme"] == "socks5"
    assert p["host"] == "1.2.3.4"
    assert p["port"] == 7897
    assert p["user"] == "alice"
    assert p["pass"] == "pass"


def test_parse_http_no_credentials():
    p = _parse("http://proxy.lan:8080")
    assert p["scheme"] == "http"
    assert p["host"] == "proxy.lan"
    assert p["port"] == 8080
    assert p["user"] == ""
    assert p["pass"] == ""


def test_parse_socks5_no_scheme():
    """裸 host:port 应默认为 socks5。"""
    p = _parse("127.0.0.1:1080")
    assert p["scheme"] == "socks5"
    assert p["host"] == "127.0.0.1"
    assert p["port"] == 1080


def test_parse_default_ports():
    assert _parse("socks5://x.com")["port"] == 1080
    assert _parse("http://x.com")["port"] == 8080


# ---------------------------------------------------------------------------
# 辅助工具
# ---------------------------------------------------------------------------

class _BytesWriter:
    """asyncio.StreamWriter 最小替代，捕获写入字节。"""
    def __init__(self):
        self.buf = bytearray()

    def write(self, data: bytes):
        self.buf.extend(data)

    async def drain(self):
        pass

    def close(self):
        pass


def _make_reader(data: bytes) -> asyncio.StreamReader:
    r = asyncio.StreamReader()
    r.feed_data(data)
    r.feed_eof()
    return r


# ---------------------------------------------------------------------------
# SOCKS5 服务端握手 (_socks5_accept)
# ---------------------------------------------------------------------------

def _build_socks5_connect_request(host: str, port: int) -> bytes:
    """构造 Chromium → 本地代理的 SOCKS5 请求帧（domain 类型）。"""
    hb = host.encode()
    handshake = bytes([0x05, 0x01, 0x00])  # VER=5, NMETHODS=1, METHOD=0x00(no-auth)
    connect = (
        bytes([0x05, 0x01, 0x00, 0x03, len(hb)])  # VER CMD RSV ATYP LEN
        + hb
        + struct.pack("!H", port)
    )
    return handshake + connect


def test_socks5_accept_domain():
    async def _run():
        data = _build_socks5_connect_request("www.example.com", 443)
        reader = _make_reader(data)
        writer = _BytesWriter()
        host, port = await _socks5_accept(reader, writer)
        assert host == "www.example.com"
        assert port == 443
        # 服务端应回复 no-auth 选择（05 00）
        assert writer.buf[:2] == bytes([0x05, 0x00])

    asyncio.run(_run())


def test_socks5_accept_ipv4():
    async def _run():
        ip_bytes = socket.inet_aton("93.184.216.34")
        handshake = bytes([0x05, 0x01, 0x00])
        connect = (
            bytes([0x05, 0x01, 0x00, 0x01])  # ATYP=IPv4
            + ip_bytes
            + struct.pack("!H", 80)
        )
        reader = _make_reader(handshake + connect)
        writer = _BytesWriter()
        host, port = await _socks5_accept(reader, writer)
        assert host == "93.184.216.34"
        assert port == 80

    asyncio.run(_run())


def test_socks5_reply_success():
    reply = _socks5_reply(True)
    assert reply[0] == 0x05
    assert reply[1] == 0x00  # REP=success
    assert len(reply) == 10


def test_socks5_reply_failure():
    reply = _socks5_reply(False)
    assert reply[1] == 0x01  # REP=general failure


# ---------------------------------------------------------------------------
# 服务器启停集成测试
# ---------------------------------------------------------------------------

def test_start_stop_chain_proxy():
    """start_chain_proxy 应在随机端口上监听，stop 后端口不再可用。"""
    relay_url = "socks5://127.0.0.1:9999"  # 不会真正连，只测端口分配
    target_url = "socks5://127.0.0.1:8888"

    port = start_chain_proxy(relay_url, target_url)
    assert isinstance(port, int)
    assert 1024 <= port <= 65535

    # 端口应处于监听状态
    with socket.create_connection(("127.0.0.1", port), timeout=2) as s:
        assert s.fileno() != -1

    stop_chain_proxy(port)


def test_start_chain_proxy_unique_ports():
    """两次调用应分配不同端口（OS 保证 port=0 分配唯一）。"""
    p1 = start_chain_proxy("socks5://127.0.0.1:9991", "socks5://127.0.0.1:8881")
    p2 = start_chain_proxy("socks5://127.0.0.1:9992", "socks5://127.0.0.1:8882")
    try:
        assert p1 != p2
    finally:
        stop_chain_proxy(p1)
        stop_chain_proxy(p2)
