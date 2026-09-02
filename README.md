# Tezkor Kino Boti

Bu loyiha `aiogram 3.x` asosidagi asinxron Telegram kino boti. Kino kodi avval Redis’dan qidiriladi, ma'lumotlar PostgreSQL’da saqlanadi, majburiy obuna holati keshlanadi va ommaviy xabarlar alohida ishonchli navbat orqali yuboriladi.

## Ishga tushirish

1. Sozlama faylini yarating:

   ```bash
   cp .env.example .env
   ```

2. `.env` faylida quyidagilarni haqiqiy qiymatlar bilan to'ldiring:

   - `BOT_TOKEN` — BotFather bergan bot tokeni;
   - `ADMIN_IDS` — bosh adminning Telegram ID raqami;
   - `DATABASE_URL` va `REDIS_URL` — production muhitida xavfsiz parolli ulanish manzillari.

3. PostgreSQL va Redis servislarini ishga tushiring:

   ```bash
   docker compose up -d postgres redis
   ```

4. Ma'lumotlar bazasi jadvallarini bir marta yarating:

   ```bash
   docker compose exec -T postgres psql -U moviebot -d moviebot < migrations/001_initial.sql
   docker compose exec -T postgres psql -U moviebot -d moviebot < migrations/002_add_age_confirmation.sql
   docker compose exec -T postgres psql -U moviebot -d moviebot < migrations/003_user_discovery_features.sql
   docker compose exec -T postgres psql -U moviebot -d moviebot < migrations/004_movie_title_search_index.sql
   ```

5. Botni polling rejimida ishga tushiring:

   ```bash
   docker compose up --build bot
   ```

## Production va yuklama bo'yicha eslatmalar

- Kichik yoki bitta serverli loyiha uchun polling rejimida faqat **bitta** `bot` nusxasini ishga tushiring. Bitta Telegram tokeni uchun polling so'rovini bir vaqtning o'zida bir nechta nusxa o'qimasligi kerak.
- Katta yuklama uchun `.env` ichidagi `WEBHOOK_URL` ga ommaviy HTTPS manzilni yozing. Shunda bir nechta `bot` konteynerini load balancer ortida webhook rejimida ishga tushirish mumkin.
- `broadcaster` servisini faqat bitta nusxada qoldiring. U Redis qulfi va PostgreSQL’dagi `FOR UPDATE SKIP LOCKED` mexanizmi bilan xabarlarni takror yubormasdan, uzilishdan keyin davom ettira oladi.
- PostgreSQL pool limiti har bir jarayon uchun alohida. Masalan, 2 ta webhook boti va 1 ta broadcaster, har biri `DB_POOL_MAX_SIZE=20` bo'lsa, PostgreSQL’da jami 60 tagacha ulanish ochilishi mumkin. `max_connections` ni shunga moslang.

## Bot qanday ishlaydi

- Botga birinchi marta kirgan foydalanuvchi 18+ ogohlantirishini ko'radi. Faqat **Ha, 18 yoshdan o'tganman** tugmasi bosilgandan keyin kino qidirish va boshqa funksiyalar ishlaydi. Tasdiq PostgreSQL’da saqlanadi va Redis’da keshlanadi.
- Foydalanuvchi kino kodini yuboradi. Bot avval Redis’dagi `movie:v1:<code>` keshni tekshiradi, topilmasa PostgreSQL’dan oladi va keyingi so'rovlar uchun Redis’ga saqlaydi.
- Topilmagan kodlar ham 60 soniyaga keshlanadi. Bu noto'g'ri kodlarni qayta-qayta yuborish PostgreSQL’ga ortiqcha yuk bo'lmasligini ta'minlaydi.
- Kino Telegram `file_id` orqali yuboriladi. Video qayta yuklanmaydi, shu sabab javob tez bo'ladi.
- Majburiy obuna natijasi har bir foydalanuvchi va kanal uchun `SUBSCRIPTION_CACHE_TTL` vaqtiga keshlanadi (standart: 10 daqiqa). Foydalanuvchi **Tekshirish** tugmasini bosganda uning eski obuna keshi o'chiriladi va holat qayta tekshiriladi.
- Bot majburiy obuna kanallarida admin bo'lishi shart. Aks holda u a'zolikni tekshira olmaydi, join request’larni qabul qila olmaydi yoki tasdiqlay olmaydi.
- Broadcast barcha foydalanuvchilarga Redis orqali umumiy 25 ta xabar/sekund limit bilan yuboriladi. Botni bloklagan foydalanuvchilar belgilanadi, Telegram `RetryAfter` so'rasa xabar belgilangan vaqt kutib qayta yuboriladi.

## Admin paneldan foydalanish

`ADMIN_IDS` ichida turgan Telegram ID bilan botga `/admin` yuboring. Bu bosh admin hisoblanadi.

- **📊 Statistika** — jami, kunlik va oylik faol foydalanuvchilar soni.
- **🎬 Kinolar** — kod va video yuborib kino qo'shish. Kino o'chirish: `/delmovie KOD`.
- **🔐 Obuna kanallar** — kanal ID, nomi va invite/join-request havolasini kiritib majburiy obuna kanali qo'shish. O'chirish: `/delchannel CHAT_ID`.
- **✉️ Xabar yuborish** — yuborilgan xabardan broadcast yaratadi; holat xabari yuborish jarayonini ko'rsatadi.
- **⚙️ Sozlamalar** — `/start` buyrug'iga javob bo'ladigan matnni o'zgartiradi.
- **👤 Adminlar** — faqat bosh admin yangi admin qo'shishi yoki `/deladmin USER_ID` bilan o'chirishi mumkin. Bu oddiy adminlarning o'ziga yuqori huquq berib yuborishining oldini oladi.
