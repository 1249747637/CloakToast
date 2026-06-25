"""
Lightweight asyncio SOCKS5 chain proxy for CloakToast.

Traffic path: Chromium → local SOCKS5 (this module) → relay (mihomo) → target (cliproxy) → Internet

Pure Python stdlib, no external dependencies.
Each call to start_chain_proxy() launches a daemon thread with its own asyncio event loop.
"""
import asyncio
import logging
import struct
import threading
from urllib.parse import urlparse

logger = logging.getLogger("cloaktoast.chain_proxy")

# port → (asyncio.Server, asyncio.AbstractEventLoop)
_registry: dict[int, tuple] = {}

# SOCKS5 wire constants
_V5 = 0x05
_CMD_CONNECT = 0x01
_ATYP_IPV4 = 0x01
_ATYP_DOMAIN = 0x03
_ATYP_IPV6 = 0x04
_AUTH_NONE = 0x00
_AUTH_USERPASS = 0x02


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------

def _parse(url: str) -> dict:
    p = urlparse(url if "://" in url else f"socks5://{url}")
    scheme = p.scheme.lower()
    return {
        "scheme": scheme,
        "host": p.hostname or "",
        "port": p.port or (1080 if "socks" in scheme else 8080),
        "user": p.username or "",
        "pass": p.password or "",
    }


# ---------------------------------------------------------------------------
# Server side: accept SOCKS5 from Chromium
# ---------------------------------------------------------------------------

async def _socks5_accept(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> tuple[str, int]:
    """Complete SOCKS5 server handshake, return (dest_host, dest_port)."""
    import socket as _socket

    hdr = await reader.readexactly(2)
    if hdr[0] != _V5:
        raise ValueError(f"not SOCKS5 (ver={hdr[0]:#x})")
    await reader.readexactly(hdr[1])            # consume method list
    writer.write(bytes([_V5, _AUTH_NONE]))       # we only offer no-auth
    await writer.drain()

    req = await reader.readexactly(4)
    if req[0] != _V5 or req[1] != _CMD_CONNECT:
        raise ValueError(f"unsupported cmd {req[1]:#x}")
    atyp = req[3]
    if atyp == _ATYP_IPV4:
        host = _socket.inet_ntoa(await reader.readexactly(4))
    elif atyp == _ATYP_DOMAIN:
        host = (await reader.readexactly((await reader.readexactly(1))[0])).decode()
    elif atyp == _ATYP_IPV6:
        host = _socket.inet_ntop(_socket.AF_INET6, await reader.readexactly(16))
    else:
        raise ValueError(f"unknown ATYP {atyp:#x}")
    port = struct.unpack("!H", await reader.readexactly(2))[0]
    return host, port


def _socks5_reply(success: bool) -> bytes:
    rep = 0x00 if success else 0x01
    return bytes([_V5, rep, 0x00, _ATYP_IPV4, 0, 0, 0, 0, 0, 0])


# ---------------------------------------------------------------------------
# Client side: speak SOCKS5 to relay or target
# ---------------------------------------------------------------------------

async def _socks5_connect(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    host: str,
    port: int,
    user: str,
    passwd: str,
) -> None:
    import socket as _socket

    methods = bytes([_AUTH_NONE, _AUTH_USERPASS]) if user else bytes([_AUTH_NONE])
    writer.write(bytes([_V5, len(methods)]) + methods)
    await writer.drain()

    resp = await reader.readexactly(2)
    if resp[0] != _V5:
        raise ConnectionError(f"bad SOCKS5 version from server: {resp[0]:#x}")
    method = resp[1]

    if method == _AUTH_USERPASS:
        eu, ep = user.encode(), passwd.encode()
        writer.write(bytes([0x01, len(eu)]) + eu + bytes([len(ep)]) + ep)
        await writer.drain()
        ar = await reader.readexactly(2)
        if ar[1] != 0x00:
            raise ConnectionError(f"SOCKS5 auth rejected ({ar[1]:#x})")
    elif method != _AUTH_NONE:
        raise ConnectionError(f"server chose unknown auth method {method:#x}")

    hb = host.encode()
    writer.write(
        bytes([_V5, _CMD_CONNECT, 0x00, _ATYP_DOMAIN, len(hb)])
        + hb
        + struct.pack("!H", port)
    )
    await writer.drain()

    rh = await reader.readexactly(4)
    if rh[0] != _V5 or rh[1] != 0x00:
        raise ConnectionError(f"SOCKS5 CONNECT refused (REP={rh[1]:#x})")
    # drain bound address
    atyp = rh[3]
    if atyp == _ATYP_IPV4:
        await reader.readexactly(4)
    elif atyp == _ATYP_DOMAIN:
        await reader.readexactly((await reader.readexactly(1))[0])
    elif atyp == _ATYP_IPV6:
        await reader.readexactly(16)
    await reader.readexactly(2)  # bound port


# ---------------------------------------------------------------------------
# Client side: HTTP CONNECT to relay or target
# ---------------------------------------------------------------------------

async def _http_connect(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    host: str,
    port: int,
    user: str,
    passwd: str,
) -> None:
    import base64
    auth = (
        f"Proxy-Authorization: Basic {base64.b64encode(f'{user}:{passwd}'.encode()).decode()}\r\n"
        if user
        else ""
    )
    writer.write(
        f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n{auth}\r\n".encode()
    )
    await writer.drain()

    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = await reader.read(4096)
        if not chunk:
            raise ConnectionError("HTTP CONNECT: server closed before response")
        buf += chunk

    first = buf.split(b"\r\n", 1)[0].decode(errors="replace")
    parts = first.split(" ", 2)
    if len(parts) < 2 or parts[1] != "200":
        raise ConnectionError(f"HTTP CONNECT failed: {first!r}")


async def _proxy_connect(reader, writer, proxy: dict, host: str, port: int) -> None:
    """Connect through proxy (relay or target) to reach host:port."""
    if proxy["scheme"] == "socks5":
        await _socks5_connect(reader, writer, host, port, proxy["user"], proxy["pass"])
    else:
        await _http_connect(reader, writer, host, port, proxy["user"], proxy["pass"])


# ---------------------------------------------------------------------------
# Bidirectional pipe
# ---------------------------------------------------------------------------

async def _pipe(src: asyncio.StreamReader, dst: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await src.read(65536)
            if not data:
                break
            dst.write(data)
            await dst.drain()
    except Exception:
        pass
    finally:
        try:
            dst.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Per-connection handler
# ---------------------------------------------------------------------------

async def _handle(
    cr: asyncio.StreamReader,
    cw: asyncio.StreamWriter,
    relay: dict,
    target: dict,
) -> None:
    rw: asyncio.StreamWriter | None = None
    try:
        dest_host, dest_port = await _socks5_accept(cr, cw)

        # Open TCP to relay
        rr, rw = await asyncio.open_connection(relay["host"], relay["port"])

        # Relay → target (cliproxy)
        await _proxy_connect(rr, rw, relay, target["host"], target["port"])

        # Target (cliproxy) → final destination
        await _proxy_connect(rr, rw, target, dest_host, dest_port)

        # Tell Chromium the tunnel is ready
        cw.write(_socks5_reply(success=True))
        await cw.drain()

        await asyncio.gather(_pipe(cr, rw), _pipe(rr, cw), return_exceptions=True)

    except Exception as exc:
        logger.debug("chain_proxy connection error: %s", exc)
        try:
            cw.write(_socks5_reply(success=False))
            await cw.drain()
        except Exception:
            pass
    finally:
        try:
            cw.close()
        except Exception:
            pass
        if rw is not None:
            try:
                rw.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_chain_proxy(relay_url: str, target_url: str) -> int:
    """Start a background SOCKS5 chain proxy. Returns the local listening port."""
    relay = _parse(relay_url)
    target = _parse(target_url)

    ready = threading.Event()
    port_holder: list[int] = []

    def _run() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _serve() -> None:
            server = await asyncio.start_server(
                lambda r, w: _handle(r, w, relay, target),
                host="127.0.0.1",
                port=0,  # OS picks a free port
            )
            port = server.sockets[0].getsockname()[1]
            _registry[port] = (server, loop)
            port_holder.append(port)
            ready.set()
            async with server:
                await server.serve_forever()

        loop.run_until_complete(_serve())

    threading.Thread(target=_run, daemon=True, name="chain-proxy").start()

    if not ready.wait(timeout=5):
        raise RuntimeError("chain_proxy: server did not start within 5 s")
    return port_holder[0]


def stop_chain_proxy(port: int) -> None:
    """Gracefully stop the chain proxy on the given port (best-effort)."""
    entry = _registry.pop(port, None)
    if not entry:
        return
    server, loop = entry
    if loop.is_running():
        loop.call_soon_threadsafe(server.close)
