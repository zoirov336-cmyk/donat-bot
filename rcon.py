"""Minecraft RCON klienti (qo'shimcha kutubxonasiz)."""
import asyncio
import re
import struct

_AUTH = 3
_COMMAND = 2
_COLOR_RE = re.compile(r"§.")


class RconError(Exception):
    pass


def _pack(req_id: int, ptype: int, body: str) -> bytes:
    payload = struct.pack("<ii", req_id, ptype) + body.encode("utf-8") + b"\x00\x00"
    return struct.pack("<i", len(payload)) + payload


async def _read_packet(reader: asyncio.StreamReader):
    raw_len = await reader.readexactly(4)
    (length,) = struct.unpack("<i", raw_len)
    if length < 10 or length > 8192:
        raise RconError(f"Noto'g'ri RCON paket uzunligi: {length}")
    data = await reader.readexactly(length)
    req_id, ptype = struct.unpack("<ii", data[:8])
    body = data[8:-2].decode("utf-8", "replace")
    return req_id, ptype, body


async def _run(host: str, port: int, password: str, commands: list[str]) -> list[str]:
    reader, writer = await asyncio.open_connection(host, port)
    try:
        writer.write(_pack(1, _AUTH, password))
        await writer.drain()
        while True:
            req_id, ptype, _ = await _read_packet(reader)
            if ptype == _COMMAND or req_id == -1:  # auth javobi
                if req_id == -1:
                    raise RconError("RCON parol noto'g'ri")
                break
        out = []
        for i, cmd in enumerate(commands, start=100):
            writer.write(_pack(i, _COMMAND, cmd))
            await writer.drain()
            while True:
                rid, _, body = await _read_packet(reader)
                if rid == i:
                    out.append(_COLOR_RE.sub("", body).strip())
                    break
        return out
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


_lock = asyncio.Lock()


async def run_commands(host: str, port: int, password: str, commands: list[str], timeout: float = 15) -> list[str]:
    """Buyruqlarni ketma-ket bajaradi va har birining javobini qaytaradi."""
    async with _lock:
        try:
            return await asyncio.wait_for(_run(host, port, password, commands), timeout)
        except RconError:
            raise
        except asyncio.TimeoutError:
            raise RconError("RCON javob bermadi (timeout)")
        except (OSError, asyncio.IncompleteReadError) as e:
            raise RconError(f"RCON ulanish xatosi: {e}")


async def run_one(host: str, port: int, password: str, command: str) -> str:
    return (await run_commands(host, port, password, [command]))[0]


_FAIL_MARKERS = (
    "topilmadi", "noto'g'ri", "noto‘g‘ri", "huquqi yo", "unknown", "usage:",
    "does not exist", "could not", "unable", "error", "xatolik", "not found",
    "no such", "incorrect", "invalid", "no permission", "player-only",
)


def looks_failed(response: str) -> bool:
    low = response.lower()
    return any(m in low for m in _FAIL_MARKERS)
