import os
import sys


def _need(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        print(f"XATO: '{name}' o'zgaruvchisi kiritilmagan (Railway -> Variables).", file=sys.stderr)
        sys.exit(1)
    return value


BOT_TOKEN = _need("BOT_TOKEN")

try:
    ADMIN_IDS = {int(x) for x in _need("ADMIN_IDS").replace(" ", "").split(",") if x}
except ValueError:
    print("XATO: ADMIN_IDS faqat raqamlardan iborat bo'lishi kerak (vergul bilan ajrating).", file=sys.stderr)
    sys.exit(1)

RCON_HOST = _need("RCON_HOST")
try:
    RCON_PORT = int(_need("RCON_PORT"))
except ValueError:
    print("XATO: RCON_PORT raqam bo'lishi kerak.", file=sys.stderr)
    sys.exit(1)
RCON_PASSWORD = _need("RCON_PASSWORD")

PAYMENT_TEXT = os.getenv(
    "PAYMENT_TEXT",
    "💳 To'lov rekvizitlari hali kiritilmagan. Admin bilan bog'laning.",
).replace("\\n", "\n")
SUPPORT_CONTACT = os.getenv("SUPPORT_CONTACT", "").strip()
DB_PATH = os.getenv("DB_PATH", "bot.db").strip() or "bot.db"

MAX_PENDING_PER_USER = 5
