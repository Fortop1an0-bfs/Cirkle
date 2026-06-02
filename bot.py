"""Cirkle — бот для подсчёта кружков.

Идея: пересылаешь боту видео-кружок (video_note) — он считает.
Команда /stats показывает, сколько кружков ДОЛЖНО было прийти к этому
моменту (по интервалу 30 мин с точки отсчёта) и сколько РЕАЛЬНО пришло.
"""
import asyncio
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from dotenv import load_dotenv

import db

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
INTERVAL_MIN = int(os.getenv("INTERVAL_MINUTES", "30"))
INTERVAL_SEC = INTERVAL_MIN * 60
TZ = ZoneInfo(os.getenv("TZ", "Europe/Moscow"))

dp = Dispatcher()


def human_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, _ = divmod(rem, 60)
    if h and m:
        return f"{h} ч {m} мин"
    if h:
        return f"{h} ч"
    return f"{m} мин"


def fmt_time(ts: float) -> str:
    return datetime.fromtimestamp(ts, TZ).strftime("%d.%m %H:%M")


@dp.message(Command("start"))
async def cmd_start(msg: Message):
    await msg.answer(
        "Привет! Я считаю кружочки 🟢\n\n"
        "• Пересылай мне сюда кружок — я его засчитаю.\n"
        "• /go — начать отсчёт с этого момента\n"
        "• /go_today — отсчёт с 00:00 сегодня\n"
        "• /stats — статистика: должна / прислала / долг\n"
        "• /add N — вручную добавить N кружков\n"
        "• /sub N — убрать N кружков (если ошибся)\n"
        "• /set N — задать точное число присланных\n"
        "• /reset — обнулить всё\n\n"
        f"Интервал: каждые {INTERVAL_MIN} мин, режим 24/7.\n"
        "Начни с /go 👇"
    )


@dp.message(Command("go"))
async def cmd_go(msg: Message):
    ts = await db.set_start(msg.chat.id)
    await msg.answer(
        f"⏱ Отсчёт пошёл с {fmt_time(ts)}.\n"
        f"Жду кружок каждые {INTERVAL_MIN} минут. Погнали!"
    )


@dp.message(Command("go_today"))
async def cmd_go_today(msg: Message):
    midnight = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    ts = midnight.timestamp()
    await db.set_start(msg.chat.id, ts)
    await msg.answer(
        f"⏱ Отсчёт установлен на 00:00 сегодня ({fmt_time(ts)}).\n"
        f"Кружки «капают» каждые {INTERVAL_MIN} мин с полуночи. /stats покажет долг."
    )


def _parse_n(command: CommandObject, default: int = 1) -> int | None:
    """Достать число из аргумента команды. None — если аргумент кривой."""
    if not command.args:
        return default
    arg = command.args.strip().split()[0]
    if not arg.lstrip("+-").isdigit():
        return None
    return int(arg)


@dp.message(Command("add"))
@dp.edited_message(Command("add"))
async def cmd_add(msg: Message, command: CommandObject):
    n = _parse_n(command, default=1)
    if n is None or n <= 0:
        await msg.answer("Формат: /add N — добавить N кружков. Например: /add 3")
        return
    await db.add_events(msg.chat.id, n)
    total = await db.count_events(msg.chat.id)
    await msg.answer(f"➕ Добавил {n} в {fmt_time(time.time())}. Всего кружков: {total}")


@dp.message(Command("sub"))
@dp.edited_message(Command("sub"))
async def cmd_sub(msg: Message, command: CommandObject):
    n = _parse_n(command, default=1)
    if n is None or n <= 0:
        await msg.answer("Формат: /sub N — убрать N кружков. Например: /sub 2")
        return
    removed = await db.delete_latest(msg.chat.id, n)
    total = await db.count_events(msg.chat.id)
    await msg.answer(f"➖ Убрал {removed}. Всего кружков: {total}")


@dp.message(Command("set"))
@dp.edited_message(Command("set"))
async def cmd_set(msg: Message, command: CommandObject):
    n = _parse_n(command, default=None)
    if n is None or n < 0:
        await msg.answer("Формат: /set N — задать точное число. Например: /set 40")
        return
    await db.clear_events(msg.chat.id)
    if n > 0:
        await db.add_events(msg.chat.id, n)
    await msg.answer(f"📝 Поставил счётчик ровно на {n}.")


@dp.message(Command("reset"))
async def cmd_reset(msg: Message):
    await db.reset(msg.chat.id)
    await msg.answer("🧹 Всё обнулил. /go чтобы начать заново.")


@dp.message(Command("stats"))
async def cmd_stats(msg: Message):
    chat_id = msg.chat.id
    start = await db.get_start(chat_id)
    if start is None:
        await msg.answer("Отсчёт ещё не начат. Жми /go.")
        return

    now = time.time()
    elapsed = now - start
    expected = int(elapsed // INTERVAL_SEC)
    actual = await db.count_events(chat_id, since=start)
    diff = actual - expected
    last = await db.last_event_ts(chat_id)

    if diff < 0:
        verdict = f"🔴 Долг: {-diff} круж."
    elif diff == 0:
        verdict = "🟢 Идём ровно по графику!"
    else:
        verdict = f"🟣 Перевыполнение: +{diff} круж."

    last_line = (
        f"🕓 Последний: {fmt_time(last)} ({human_duration(now - last)} назад)"
        if last else "🕓 Кружков пока не было"
    )

    await msg.answer(
        f"⏰ Прошло: {human_duration(elapsed)} "
        f"({expected} интервалов по {INTERVAL_MIN} мин)\n"
        f"📊 Должна была: {expected}\n"
        f"✅ Прислала: {actual}\n"
        f"{verdict}\n"
        f"{last_line}"
    )


@dp.message(F.video_note)
async def on_video_note(msg: Message):
    chat_id = msg.chat.id
    if await db.get_start(chat_id) is None:
        # авто-старт при первом кружке, если отсчёт не начат
        await db.set_start(chat_id)
    await db.add_event(chat_id)
    total = await db.count_events(chat_id)
    try:
        await msg.delete()
        note = ""
    except Exception:
        # не удалось удалить (например, прошло >48 ч) — не страшно
        note = " (удалить не вышло)"
    await msg.answer(f"🟢 Засчитано в {fmt_time(time.time())}! Всего кружков: {total}{note}")


async def main():
    await db.init()
    bot = Bot(BOT_TOKEN)
    print("Cirkle bot started.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
