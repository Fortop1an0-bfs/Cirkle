"""Хранилище на SQLite. Один файл, ноль настройки."""
import time
import aiosqlite

DB_PATH = "cirkle.db"


async def init():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """CREATE TABLE IF NOT EXISTS counters (
                chat_id  INTEGER PRIMARY KEY,
                start_ts REAL NOT NULL
            )"""
        )
        await db.execute(
            """CREATE TABLE IF NOT EXISTS events (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                ts      REAL NOT NULL
            )"""
        )
        await db.commit()


async def set_start(chat_id: int, ts: float | None = None) -> float:
    """Зафиксировать точку отсчёта. Возвращает использованный ts."""
    ts = ts if ts is not None else time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO counters(chat_id, start_ts) VALUES(?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET start_ts=excluded.start_ts",
            (chat_id, ts),
        )
        await db.commit()
    return ts


async def get_start(chat_id: int) -> float | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT start_ts FROM counters WHERE chat_id=?", (chat_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def add_event(chat_id: int, ts: float | None = None) -> None:
    ts = ts if ts is not None else time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO events(chat_id, ts) VALUES(?, ?)", (chat_id, ts)
        )
        await db.commit()


async def add_events(chat_id: int, n: int, ts: float | None = None) -> None:
    """Добавить сразу N событий (ручной ввод)."""
    ts = ts if ts is not None else time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(
            "INSERT INTO events(chat_id, ts) VALUES(?, ?)",
            [(chat_id, ts)] * n,
        )
        await db.commit()


async def delete_latest(chat_id: int, n: int) -> int:
    """Удалить N последних событий. Возвращает, сколько реально удалено."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id FROM events WHERE chat_id=? ORDER BY ts DESC, id DESC LIMIT ?",
            (chat_id, n),
        ) as cur:
            ids = [r[0] for r in await cur.fetchall()]
        if ids:
            qmarks = ",".join("?" * len(ids))
            await db.execute(
                f"DELETE FROM events WHERE id IN ({qmarks})", ids
            )
            await db.commit()
        return len(ids)


async def clear_events(chat_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM events WHERE chat_id=?", (chat_id,))
        await db.commit()


async def count_events(chat_id: int, since: float | None = None) -> int:
    q = "SELECT COUNT(*) FROM events WHERE chat_id=?"
    args: list = [chat_id]
    if since is not None:
        q += " AND ts >= ?"
        args.append(since)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(q, args) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def last_event_ts(chat_id: int) -> float | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT MAX(ts) FROM events WHERE chat_id=?", (chat_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row and row[0] is not None else None


async def reset(chat_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM events WHERE chat_id=?", (chat_id,))
        await db.execute("DELETE FROM counters WHERE chat_id=?", (chat_id,))
        await db.commit()
