# TuronCraft Telegram donat bot

Xaridor: bo'lim → mahsulot → Minecraft nik → to'lov cheki (rasm).
Admin: chekni ko'radi → **✅ Pul tushdi** bosadi → bot RCON orqali serverda avtomatik beradi.

Ishlatiladigan buyruqlar (sizning pluginlaringizga mos):
- Rank: `lp user <nik> parent set <rank>` (LuckPerms)
- Case key: `articases givekey <nik> <token|resource> <son>` (ArtiCases)
- Token: `points give <nik> <son>` (PlayerPoints)

## 1. Serverda RCON yoqing
`server.properties`:
```
enable-rcon=true
rcon.port=25575
rcon.password=KUCHLI_PAROL
```
Serverni qayta ishga tushiring. RCON port o'yin portidan (20810) **boshqa** bo'ladi.

## 2. Telegram tomoni
- @BotFather → /newbot → **token** oling.
- @userinfobot orqali o'zingizning **Telegram ID** ingizni bilib oling (admin uchun).
- Admin botga bir marta /start bosishi shart (aks holda bot unga xabar yubora olmaydi).

## 3. Railway
1. Fayllarni GitHub repoga yuklang → Railway → New Project → Deploy from GitHub.
2. **Variables** bo'limida:

| Nomi | Qiymati |
|---|---|
| `BOT_TOKEN` | BotFather tokeni |
| `ADMIN_IDS` | `111111111,222222222` |
| `RCON_HOST` | server hosti |
| `RCON_PORT` | RCON porti |
| `RCON_PASSWORD` | RCON paroli |
| `PAYMENT_TEXT` | karta raqami va ism (qator uchun `\n` yozing) |
| `SUPPORT_CONTACT` | masalan `@admin` (ixtiyoriy) |
| `DB_PATH` | `/data/bot.db` |

3. **Volume** qo'shing va uni `/data` ga ulang. Bo'lmasa, Railway qayta ishga tushganda buyurtmalar bazasi o'chib ketadi.
4. Faqat **bitta** nusxa (replica) ishlasin.

Bot ishga tushganda adminlarga "RCON ulandi / ulanmadi" xabarini yuboradi. Keyinroq `/rcontest` bilan tekshirish mumkin.

## 4. Narxlar va mahsulotlar
`catalog.json` ichidagi **narxlar namuna**. O'zingiznikiga almashtiring. Yangi mahsulot qo'shish uchun mavjudini nusxalab, `id`, `title`, `price` va `commands` ni o'zgartiring (`{nick}` o'rniga xaridor niki qo'yiladi).

## 5. Admin buyruqlari
- `/pending` — kutayotgan buyurtmalar
- `/rcontest` — RCON tekshiruvi
- Xatolik bo'lsa tugmalar: **🔁 Qayta urinish** (faqat bajarilmagan buyruqlarni takrorlaydi), **✅ Qo'lda berdim**, **❌ Rad etish**.

## Eslatmalar
- Birinchi marta o'zingizning nikingiz bilan arzon mahsulotni sinab ko'ring.
- `parent set` o'yinchining eski rankini almashtiradi. Kichik rank sotib olgan yuqori rankli o'yinchi pasayib qoladi, shuning uchun chekda nikni tekshiring.
- ArtiCases/PlayerPoints oflayn o'yinchiga berishni qo'llasa-qo'llamasligini sinab ko'ring. Xato bo'lsa, bot admin ga server javobini ko'rsatadi.
- RCON parolini hech kimga bermang va oddiy parol qo'ymang.
