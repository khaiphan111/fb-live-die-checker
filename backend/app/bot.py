# FB Live/Die Checker — Tác giả: @nhanxp | Hỗ trợ: Telegram/Facebook nhanxp
import asyncio
from typing import Optional

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    URLInputFile,
)

from . import config, db, fb
from .util import now, parse_check_args, vnd

router = Router()

DAY = 86400

MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="/check"), KeyboardButton(text="/list")],
        [KeyboardButton(text="/balance"), KeyboardButton(text="/sub")],
        [KeyboardButton(text="/menu"), KeyboardButton(text="/help")],
    ],
    resize_keyboard=True,
)

COMMANDS = [
    BotCommand(command="start", description="Kết nối & xem tài khoản"),
    BotCommand(command="check", description="Thêm UID theo dõi live/die"),
    BotCommand(command="list", description="Danh sách UID đang theo dõi"),
    BotCommand(command="remove", description="Bỏ theo dõi 1 UID"),
    BotCommand(command="balance", description="Xem số dư"),
    BotCommand(command="sub", description="Mua / gia hạn gói"),
    BotCommand(command="menu", description="Hiện menu"),
    BotCommand(command="help", description="Hướng dẫn"),
]


def _sub_active(user) -> bool:
    return user and user["sub_until"] and user["sub_until"] > now()


def _sub_text(user) -> str:
    if _sub_active(user):
        days_left = (user["sub_until"] - now()) // DAY
        return f"Còn hạn ({days_left} ngày)"
    return "Chưa có / đã hết hạn"


def status_caption(status: str, note: Optional[str], price, header: str = "") -> str:
    icon = "🟢" if status == "live" else "🔴"
    word = "LIVE" if status == "live" else "DIE"
    lines = []
    if header:
        lines.append(header)
    lines.append(f"{icon} Tài khoản đang <b>{word}</b>")
    if note:
        lines.append(f"Ghi chú: {note}")
    if price:
        lines.append(f"Giá: {vnd(price)}")
    return "\n".join(lines)


async def _send_card(bot: Bot, chat_id: int, uid: str, status: str, note, price,
                     avatar: Optional[str], header: str = ""):
    caption = status_caption(status, note, price, header)
    if avatar:
        try:
            await bot.send_photo(chat_id, photo=URLInputFile(avatar), caption=caption)
            return
        except Exception:
            pass
    await bot.send_message(chat_id, caption)


@router.message(CommandStart())
async def on_start(msg: Message):
    u = msg.from_user
    user = db.upsert_user(u.id, u.username or "", u.full_name or "")
    db.add_log("system", f"/start {u.id} @{u.username}", u.id)
    text = (
        f"Xin chào <b>{u.full_name}</b>!\n"
        f"Đã kết nối tài khoản của bạn.\n\n"
        f"Số dư: <b>{vnd(user['balance'])}</b>\n"
        f"Gói: <b>{_sub_text(user)}</b>\n\n"
        f"Dùng /check để thêm UID theo dõi, /sub để mua gói.\n"
        f"Hỗ trợ: Telegram @{config.SUPPORT_TELEGRAM} • Facebook {config.SUPPORT_FACEBOOK}"
    )
    await msg.answer(text, reply_markup=MENU)


@router.message(Command("menu"))
async def on_menu(msg: Message):
    await msg.answer("Menu đã sẵn sàng.", reply_markup=MENU)


@router.message(Command("help"))
async def on_help(msg: Message):
    text = (
        "<b>Hướng dẫn</b>\n"
        "/check {uid} [ghi chú] [giá] [số ngày]\n"
        "Ví dụ: /check 123 Mở khoá cho anh D 50000 7\n"
        "→ theo dõi UID 123, ghi chú \"Mở khoá cho anh D\", giá 50.000, trong 7 ngày.\n\n"
        "Quy tắc: phần nào không điền thì bỏ qua. Hai số ở cuối là [giá] [số ngày]; "
        "nếu chỉ có một số thì hiểu là số ngày.\n\n"
        "/list xem danh sách • /remove {uid} bỏ theo dõi\n"
        "/balance xem số dư • /sub mua/gia hạn gói\n\n"
        f"Hỗ trợ: Telegram @{config.SUPPORT_TELEGRAM} • Facebook {config.SUPPORT_FACEBOOK}"
    )
    await msg.answer(text)


@router.message(Command("balance"))
async def on_balance(msg: Message):
    user = db.get_user(msg.from_user.id)
    if not user:
        await msg.answer("Bạn chưa /start. Gõ /start trước nhé.")
        return
    await msg.answer(
        f"Số dư: <b>{vnd(user['balance'])}</b>\nGói: <b>{_sub_text(user)}</b>"
    )


@router.message(Command("sub"))
async def on_sub(msg: Message):
    p1 = int(db.get_setting("price_1m", "0") or 0)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"1 tháng - {vnd(p1)}", callback_data="sub:1")],
            [InlineKeyboardButton(text=f"2 tháng - {vnd(p1 * 2)}", callback_data="sub:2")],
            [InlineKeyboardButton(text=f"3 tháng - {vnd(p1 * 3)}", callback_data="sub:3")],
        ]
    )
    await msg.answer("Chọn gói muốn mua / gia hạn:", reply_markup=kb)


@router.callback_query(F.data.startswith("sub:"))
async def on_sub_pick(cb: CallbackQuery):
    months = int(cb.data.split(":")[1])
    p1 = int(db.get_setting("price_1m", "0") or 0)
    cost = p1 * months
    user = db.get_user(cb.from_user.id)
    if not user:
        await cb.answer("Bạn chưa /start.", show_alert=True)
        return
    if user["balance"] < cost:
        await cb.answer(
            f"Số dư không đủ. Cần {vnd(cost)}, bạn có {vnd(user['balance'])}.",
            show_alert=True,
        )
        return
    db.adjust_balance(cb.from_user.id, -cost, f"Mua gói {months} tháng")
    base = max(now(), user["sub_until"] or 0)
    db.set_sub_until(cb.from_user.id, base + months * 30 * DAY)
    db.add_log("sub", f"Mua {months} tháng (-{cost})", cb.from_user.id)
    u2 = db.get_user(cb.from_user.id)
    await cb.message.answer(
        f"Đã kích hoạt gói <b>{months} tháng</b>.\n"
        f"Số dư còn: <b>{vnd(u2['balance'])}</b>\nGói: <b>{_sub_text(u2)}</b>"
    )
    await cb.answer("Thành công")


@router.message(Command("list"))
async def on_list(msg: Message):
    rows = db.user_watches(msg.from_user.id)
    if not rows:
        await msg.answer("Bạn chưa theo dõi UID nào. Dùng /check để thêm.")
        return
    lines = ["<b>Danh sách đang theo dõi</b>"]
    for w in rows:
        st = w["last_status"] or "?"
        icon = "🟢" if st == "live" else ("🔴" if st == "die" else "⚪")
        extra = f" — {w['note']}" if w["note"] else ""
        lines.append(f"{icon} {w['uid']}{extra}")
    await msg.answer("\n".join(lines))


@router.message(Command("remove"))
async def on_remove(msg: Message):
    parts = (msg.text or "").split()
    if len(parts) < 2:
        await msg.answer("Cú pháp: /remove {uid}")
        return
    n = db.remove_watch(msg.from_user.id, parts[1].strip())
    await msg.answer("Đã bỏ theo dõi." if n else "Không tìm thấy UID này.")


@router.message(Command("check"))
async def on_check(msg: Message):
    user = db.get_user(msg.from_user.id)
    if not user:
        await msg.answer("Bạn chưa /start. Gõ /start trước nhé.")
        return
    if not _sub_active(user):
        await msg.answer("Bạn cần có gói còn hạn để dùng /check. Gõ /sub để mua gói.")
        return

    uid, note, price, days = parse_check_args(msg.text or "")
    if not uid:
        await msg.answer("Cú pháp: /check {uid} [ghi chú] [giá] [số ngày]")
        return

    res = await fb.check_uid(uid)
    status = "live" if res["alive"] else "die"
    avatar = res["avatar_url"] or fb.avatar_url(uid)
    expire_at = now() + days * DAY if days else 0
    wid = db.add_watch(msg.from_user.id, res["uid"], note or "", price or 0, expire_at)
    db.update_watch_status(wid, status, avatar)
    db.add_log("add", f"Thêm UID {res['uid']} ({status})", msg.from_user.id, res["uid"])

    header = "Đã thêm theo dõi:"
    if days:
        header += f" trong {days} ngày"
    await _send_card(msg.bot, msg.chat.id, res["uid"], status, note, price, avatar, header)


@router.message(F.text & ~F.text.startswith("/"))
async def on_other(msg: Message):
    await msg.answer("Gõ /menu để xem các chức năng, hoặc /help để được hướng dẫn.", reply_markup=MENU)


class BotManager:
    def __init__(self):
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self._task: Optional[asyncio.Task] = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self, token: str) -> bool:
        await self.stop()
        if not token:
            return False
        self.bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        try:
            me = await self.bot.get_me()
        except Exception:
            self.bot = None
            return False
        try:
            await self.bot.delete_webhook(drop_pending_updates=True)
        except Exception:
            pass
        self.dp = Dispatcher()
        self.dp.include_router(router)
        await self.bot.set_my_commands(COMMANDS)
        self._task = asyncio.create_task(self.dp.start_polling(self.bot, handle_signals=False))
        db.add_log("system", f"Bot khởi động: @{me.username}")
        return True

    async def stop(self):
        if self.dp:
            try:
                await self.dp.stop_polling()
            except Exception:
                pass
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        if self.bot:
            try:
                await self.bot.session.close()
            except Exception:
                pass
            self.bot = None
        self.dp = None

    async def verify_token(self, token: str) -> Optional[str]:
        if not token:
            return None
        b = Bot(token=token)
        try:
            me = await b.get_me()
            return me.username
        except Exception:
            return None
        finally:
            await b.session.close()


manager = BotManager()
