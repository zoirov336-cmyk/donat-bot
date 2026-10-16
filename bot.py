import asyncio
import html
import logging
import re

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import catalog
import config
import db
import rcon

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("shop")

router = Router()
NICK_RE = re.compile(r"^\.?[A-Za-z0-9_]{3,16}$")

STATUS_UZ = {
    "pending": "⏳ Kutilmoqda",
    "processing": "⚙️ Berilmoqda",
    "done": "✅ Bajarildi",
    "rejected": "❌ Rad etildi",
    "failed": "⚠️ Xatolik (admin ko'radi)",
}


class Order(StatesGroup):
    nick = State()
    confirm = State()
    proof = State()


def esc(s) -> str:
    return html.escape(str(s or ""))


# ───────────────────────── klaviaturalar ─────────────────────────
def menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for c in catalog.CATEGORIES:
        b.button(text=c["title"], callback_data=f"cat:{c['id']}")
    b.button(text="📋 Buyurtmalarim", callback_data="myorders")
    b.adjust(1)
    return b.as_markup()


def cat_kb(cat) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for it in cat["items"]:
        b.button(text=f"{it['title']} — {catalog.money(it['price'])}", callback_data=f"item:{it['id']}")
    b.button(text="⬅️ Orqaga", callback_data="menu")
    b.adjust(1)
    return b.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="❌ Bekor qilish", callback_data="cancel")
    return b.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Ha, to'g'ri", callback_data="nick_ok")
    b.button(text="✏️ O'zgartirish", callback_data="nick_edit")
    b.button(text="❌ Bekor qilish", callback_data="cancel")
    b.adjust(1)
    return b.as_markup()


def admin_kb(order_id: int, failed: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if failed:
        b.button(text="🔁 Qayta urinish", callback_data=f"ok:{order_id}")
        b.button(text="✅ Qo'lda berdim", callback_data=f"manual:{order_id}")
    else:
        b.button(text="✅ Pul tushdi", callback_data=f"ok:{order_id}")
    b.button(text="❌ Rad etish", callback_data=f"no:{order_id}")
    b.adjust(1)
    return b.as_markup()


async def safe_edit(call: CallbackQuery, text: str, kb: InlineKeyboardMarkup | None = None):
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        await call.message.answer(text, reply_markup=kb)


def welcome_text() -> str:
    return "🎮 <b>TuronCraft do'koniga xush kelibsiz!</b>\n\nKerakli bo'limni tanlang:"


# ───────────────────────── xaridor oqimi ─────────────────────────
@router.message(CommandStart())
async def cmd_start(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(welcome_text(), reply_markup=menu_kb())


@router.callback_query(F.data == "menu")
async def cb_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit(call, welcome_text(), menu_kb())
    await call.answer()


@router.callback_query(F.data == "cancel")
async def cb_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit(call, "Bekor qilindi.\n\n" + welcome_text(), menu_kb())
    await call.answer()


@router.callback_query(F.data.startswith("cat:"))
async def cb_cat(call: CallbackQuery, state: FSMContext):
    await state.clear()
    cid = call.data.split(":", 1)[1]
    cat = next((c for c in catalog.CATEGORIES if c["id"] == cid), None)
    if not cat:
        return await call.answer("Bo'lim topilmadi", show_alert=True)
    await safe_edit(call, f"<b>{esc(cat['title'])}</b>\n\nMahsulotni tanlang:", cat_kb(cat))
    await call.answer()


@router.callback_query(F.data.startswith("item:"))
async def cb_item(call: CallbackQuery, state: FSMContext):
    item = catalog.ITEMS.get(call.data.split(":", 1)[1])
    if not item:
        return await call.answer("Mahsulot topilmadi", show_alert=True)
    if db.count_pending(call.from_user.id) >= config.MAX_PENDING_PER_USER:
        return await call.answer(
            "Sizda tasdiqlanmagan buyurtmalar ko'p. Avval ular yakunlansin.", show_alert=True
        )
    await state.set_state(Order.nick)
    await state.update_data(item_id=item["id"])
    await safe_edit(
        call,
        f"🛒 <b>{esc(item['title'])}</b>\n"
        f"💰 Narxi: <b>{catalog.money(item['price'])}</b>\n"
        f"📝 {esc(item.get('desc', ''))}\n\n"
        "🎮 Endi <b>Minecraft nikingizni</b> yozing (aynan serverdagidek, katta-kichik harf bilan):",
        cancel_kb(),
    )
    await call.answer()


@router.message(Order.nick, F.text, ~F.text.startswith("/"))
async def got_nick(m: Message, state: FSMContext):
    nick = m.text.strip()
    if not NICK_RE.fullmatch(nick):
        return await m.answer(
            "❗ Nik noto'g'ri. Faqat lotin harflari, raqam va _ bo'lishi, 3–16 belgi bo'lishi kerak. "
            "Qaytadan yozing:",
            reply_markup=cancel_kb(),
        )
    await state.update_data(nick=nick)
    await state.set_state(Order.confirm)
    data = await state.get_data()
    item = catalog.ITEMS[data["item_id"]]
    await m.answer(
        f"🎮 Nik: <b>{esc(nick)}</b>\n📦 {esc(item['title'])} — {catalog.money(item['price'])}\n\n"
        "Nik to'g'rimi? Xato yozilsa, mahsulot boshqa o'yinchiga ketib qoladi!",
        reply_markup=confirm_kb(),
    )


@router.callback_query(Order.confirm, F.data == "nick_edit")
async def cb_nick_edit(call: CallbackQuery, state: FSMContext):
    await state.set_state(Order.nick)
    await safe_edit(call, "🎮 Nikingizni qaytadan yozing:", cancel_kb())
    await call.answer()


@router.callback_query(Order.confirm, F.data == "nick_ok")
async def cb_nick_ok(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    item = catalog.ITEMS[data["item_id"]]
    await state.set_state(Order.proof)
    await safe_edit(
        call,
        f"💳 <b>To'lov</b>\n\n📦 {esc(item['title'])}\n💰 Summa: <b>{catalog.money(item['price'])}</b>\n"
        f"🎮 Nik: <b>{esc(data['nick'])}</b>\n\n"
        f"{esc(config.PAYMENT_TEXT)}\n\n"
        "📸 To'lovni qilgach, <b>chek rasmini (skrinshot)</b> shu yerga yuboring.",
        cancel_kb(),
    )
    await call.answer()


def _proof_from(m: Message):
    if m.photo:
        p = m.photo[-1]
        return p.file_id, p.file_unique_id, "photo"
    if m.document and (m.document.mime_type or "").startswith("image/"):
        return m.document.file_id, m.document.file_unique_id, "document"
    return None


@router.message(Order.proof, ~F.text.startswith("/"))
async def got_proof(m: Message, state: FSMContext, bot: Bot):
    proof = _proof_from(m)
    if not proof:
        return await m.answer("📸 Iltimos, to'lov chekining <b>rasmini</b> yuboring.", reply_markup=cancel_kb())

    data = await state.get_data()
    item = catalog.ITEMS.get(data.get("item_id", ""))
    nick = data.get("nick")
    if not item or not nick:
        await state.clear()
        return await m.answer("Sessiya tugadi. /start bosing.")
    if db.count_pending(m.from_user.id) >= config.MAX_PENDING_PER_USER:
        await state.clear()
        return await m.answer("Sizda tasdiqlanmagan buyurtmalar ko'p. Avval ular yakunlansin.")

    file_id, uid, kind = proof
    dup = db.proof_used_before(uid)
    order_id = db.create_order(m.from_user, item, nick, file_id, uid, kind)
    await state.clear()

    await m.answer(
        f"✅ Buyurtma <b>#{order_id}</b> qabul qilindi!\n"
        "Admin to'lovni tekshirgach, mahsulot serverda avtomatik beriladi. Natijani shu yerda xabar qilaman.",
        reply_markup=menu_kb(),
    )

    order = db.get(order_id)
    caption = admin_caption(order, extra="⚠️ <b>DIQQAT: bu chek rasmi avval ham yuborilgan!</b>" if dup else "")
    for admin_id in config.ADMIN_IDS:
        try:
            if kind == "photo":
                sent = await bot.send_photo(admin_id, file_id, caption=caption, reply_markup=admin_kb(order_id))
            else:
                sent = await bot.send_document(admin_id, file_id, caption=caption, reply_markup=admin_kb(order_id))
            db.add_admin_msg(order_id, admin_id, sent.message_id)
        except Exception as e:
            log.warning("Adminga (%s) yuborib bo'lmadi: %s", admin_id, e)


@router.message(Order.nick, ~F.text.startswith("/"))
@router.message(Order.confirm, ~F.text.startswith("/"))
async def wrong_input(m: Message):
    await m.answer("Iltimos, tugmalardan foydalaning yoki nikingizni matn ko'rinishida yozing.", reply_markup=cancel_kb())


@router.message(F.photo)
async def stray_photo(m: Message):
    await m.answer("Avval /start bosib, mahsulotni tanlang.")


@router.callback_query(F.data == "myorders")
async def cb_myorders(call: CallbackQuery):
    await safe_edit(call, orders_text(call.from_user.id), menu_kb())
    await call.answer()


@router.message(Command("orders"))
async def cmd_orders(m: Message):
    await m.answer(orders_text(m.from_user.id), reply_markup=menu_kb())


def orders_text(user_id: int) -> str:
    rows = db.user_orders(user_id)
    if not rows:
        return "Sizda hali buyurtma yo'q."
    lines = ["📋 <b>Oxirgi buyurtmalaringiz:</b>\n"]
    for o in rows:
        status = STATUS_UZ.get(o["status"], o["status"])
        if o["status"] == "failed":
            status = "⏳ Admin ko'rib chiqmoqda"
        lines.append(f"#{o['id']} • {esc(o['item_title'])} • {esc(o['nick'])} • {status}")
    return "\n".join(lines)


# ───────────────────────── admin oqimi ─────────────────────────
def admin_caption(o, extra: str = "") -> str:
    who = esc(o["full_name"])
    if o["username"]:
        who += f" (@{esc(o['username'])})"
    text = (
        f"🆕 <b>Buyurtma #{o['id']}</b>\n"
        f"👤 {who} • ID: <code>{o['user_id']}</code>\n"
        f"🎮 Nik: <code>{esc(o['nick'])}</code>\n"
        f"📦 {esc(o['item_title'])}\n"
        f"💰 {catalog.money(o['price'])}\n"
        f"📌 Holat: {STATUS_UZ.get(o['status'], o['status'])}"
    )
    if extra:
        text += f"\n\n{extra}"
    return text


async def refresh_admin_msgs(bot: Bot, order_id: int, extra: str = "", kb: InlineKeyboardMarkup | None = None):
    o = db.get(order_id)
    for row in db.admin_msgs(order_id):
        try:
            await bot.edit_message_caption(
                chat_id=row["chat_id"], message_id=row["message_id"],
                caption=admin_caption(o, extra), reply_markup=kb,
            )
        except TelegramBadRequest as e:
            if "not modified" not in str(e):
                log.warning("Admin xabarini yangilab bo'lmadi: %s", e)
        except Exception as e:
            log.warning("Admin xabarini yangilab bo'lmadi: %s", e)


def render_commands(item: dict, nick: str) -> list[str]:
    return [c.format(nick=nick) for c in item["commands"]]


async def deliver(order_id: int) -> tuple[bool, str]:
    o = db.get(order_id)
    item = catalog.ITEMS.get(o["item_id"])
    if not item:
        return False, f"Mahsulot katalogda topilmadi: {o['item_id']}"
    if not NICK_RE.fullmatch(o["nick"]):
        return False, "Nik formati noto'g'ri"
    cmds = render_commands(item, o["nick"])
    for i in range(o["done_cmds"], len(cmds)):
        try:
            resp = await rcon.run_one(config.RCON_HOST, config.RCON_PORT, config.RCON_PASSWORD, cmds[i])
        except rcon.RconError as e:
            return False, str(e)
        log.info("Order #%s cmd %r -> %r", order_id, cmds[i], resp)
        if rcon.looks_failed(resp):
            return False, f"Buyruq: {cmds[i]}\nServer javobi: {resp}"
        db.set_progress(order_id, i + 1)
    return True, ""


def is_admin(call: CallbackQuery) -> bool:
    return call.from_user.id in config.ADMIN_IDS


@router.callback_query(F.data.startswith("ok:"))
async def adm_ok(call: CallbackQuery, bot: Bot):
    if not is_admin(call):
        return await call.answer("Ruxsat yo'q", show_alert=True)
    order_id = int(call.data.split(":", 1)[1])
    if not db.claim(order_id):
        return await call.answer("Bu buyurtma allaqachon ishlangan yoki jarayonda.", show_alert=True)
    await call.answer("Serverga yuborilmoqda...")
    await refresh_admin_msgs(bot, order_id, extra="⚙️ Serverga yuborilmoqda...")

    ok, err = await deliver(order_id)
    o = db.get(order_id)
    if ok:
        db.set_status(order_id, "done")
        await refresh_admin_msgs(bot, order_id, extra=f"✅ Berildi (tasdiqladi: {esc(call.from_user.full_name)})")
        await notify_user(bot, o["user_id"],
                          f"✅ Buyurtma <b>#{order_id}</b> bajarildi!\n"
                          f"📦 {esc(o['item_title'])} — <b>{esc(o['nick'])}</b> hisobiga berildi.\n"
                          "Serverga kirib tekshiring. Rahmat! 🎉")
    else:
        db.set_status(order_id, "failed", err)
        await refresh_admin_msgs(
            bot, order_id,
            extra=f"⚠️ <b>Berib bo'lmadi:</b>\n<code>{esc(err)}</code>",
            kb=admin_kb(order_id, failed=True),
        )


@router.callback_query(F.data.startswith("manual:"))
async def adm_manual(call: CallbackQuery, bot: Bot):
    if not is_admin(call):
        return await call.answer("Ruxsat yo'q", show_alert=True)
    order_id = int(call.data.split(":", 1)[1])
    if not db.mark_manual_done(order_id):
        return await call.answer("Holat mos emas.", show_alert=True)
    o = db.get(order_id)
    await call.answer("Belgilandi")
    await refresh_admin_msgs(bot, order_id, extra=f"✅ Qo'lda berildi ({esc(call.from_user.full_name)})")
    await notify_user(bot, o["user_id"],
                      f"✅ Buyurtma <b>#{order_id}</b> bajarildi!\n"
                      f"📦 {esc(o['item_title'])} — <b>{esc(o['nick'])}</b> hisobiga berildi.")


@router.callback_query(F.data.startswith("no:"))
async def adm_no(call: CallbackQuery, bot: Bot):
    if not is_admin(call):
        return await call.answer("Ruxsat yo'q", show_alert=True)
    order_id = int(call.data.split(":", 1)[1])
    if not db.reject(order_id):
        return await call.answer("Bu buyurtma allaqachon ishlangan yoki jarayonda.", show_alert=True)
    o = db.get(order_id)
    await call.answer("Rad etildi")
    await refresh_admin_msgs(bot, order_id, extra=f"❌ Rad etildi ({esc(call.from_user.full_name)})")
    contact = f" Savol bo'lsa: {esc(config.SUPPORT_CONTACT)}" if config.SUPPORT_CONTACT else ""
    await notify_user(bot, o["user_id"],
                      f"❌ Buyurtma <b>#{order_id}</b> uchun to'lov tasdiqlanmadi.{contact}")


async def notify_user(bot: Bot, user_id: int, text: str):
    try:
        await bot.send_message(user_id, text)
    except Exception as e:
        log.warning("Foydalanuvchiga (%s) xabar yuborib bo'lmadi: %s", user_id, e)


@router.message(Command("pending"))
async def cmd_pending(m: Message):
    if m.from_user.id not in config.ADMIN_IDS:
        return
    rows = db.pending_orders()
    if not rows:
        return await m.answer("Kutayotgan buyurtma yo'q ✅")
    lines = ["⏳ <b>Kutayotgan buyurtmalar:</b>\n"]
    for o in rows:
        lines.append(f"#{o['id']} • {esc(o['nick'])} • {esc(o['item_title'])} • {STATUS_UZ.get(o['status'])}")
    await m.answer("\n".join(lines))


@router.message(Command("rcontest"))
async def cmd_rcontest(m: Message):
    if m.from_user.id not in config.ADMIN_IDS:
        return
    try:
        resp = await rcon.run_one(config.RCON_HOST, config.RCON_PORT, config.RCON_PASSWORD, "list")
        await m.answer(f"✅ RCON ishlayapti:\n<code>{esc(resp)}</code>")
    except rcon.RconError as e:
        await m.answer(f"❌ RCON xato: {esc(e)}")


# ───────────────────────── ishga tushirish ─────────────────────────
async def main():
    db.recover_stuck()
    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    try:
        resp = await rcon.run_one(config.RCON_HOST, config.RCON_PORT, config.RCON_PASSWORD, "list")
        status = f"✅ RCON ulandi: {resp}"
    except rcon.RconError as e:
        status = f"❌ RCON ulanmadi: {e}"
    log.info(status)
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"🤖 Bot ishga tushdi.\n{esc(status)}")
        except Exception as e:
            log.warning("Adminga (%s) start xabari ketmadi (botga /start bosganmisiz?): %s", admin_id, e)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
