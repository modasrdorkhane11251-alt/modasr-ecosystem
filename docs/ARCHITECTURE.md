# معماری (مونولیت ماژولار — طبق دستور، بدون میکروسرویس غیرضروری)

```
packages/core/
  config.py            بارگذاری/اعتبارسنجی env، بدون مقدار پیش‌فرض خطرناک
  database.py           SQLite + مهاجرت نسخه‌دار (user_version)؛ هویت = (platform, platform_user_id)
  platform_adapter.py    اینترفیس انتزاعی مشترک همه‌ی پیام‌رسان‌ها
  ai/openrouter.py        کلاینت OpenRouter؛ ارائه‌دهنده‌ی اصلی و تنها نقطه‌ی تماس فعلی با هوش مصنوعی
  ai/gemini.py             کلاینت Gemini؛ نگه‌داشته‌شده به‌عنوان ارائه‌دهنده‌ی اختیاری/غیرفعال (هیچ رباتی صدایش نمی‌زند)

apps/telegram-bot/
  adapter.py              پیاده‌سازی PlatformAdapter برای تلگرام (Bot API + requests)
  main.py                 حلقه‌ی polling واقعی؛ تنها «سیم‌کشی»، بدون منطق کسب‌وکار

apps/bale-bot/
  adapter.py              پیاده‌سازی PlatformAdapter برای بله (tapi.bale.ai)

apps/rubika-bot/
  adapter.py               اسکلت؛ عمداً NotImplementedError
```

## چرا این‌طور
- منطق AI و دیتابیس هیچ‌وقت مستقیم با SDK یک پیام‌رسان کار نمی‌کند؛ فقط از پشت `PlatformAdapter`.
  همین الان اثبات شده: `main.py` تلگرام هیچ importی از Bale ندارد و برعکس.
- هویت کاربر بر اساس `(platform, platform_user_id)` است، نه فقط یک ID خام — چون دو پلتفرم
  می‌توانند یک ID عددی مشابه داشته باشند و این‌ها نباید به‌اشتباه یک نفر حساب شوند.
  اتصال صریح حساب‌ها (account linking) عمداً هنوز اضافه نشده.
- `requests` به‌جای `httpx`/کتابخانه‌های سنگین پیام‌رسان، چون این محیط توسعه اینترنت نداشت
  و نصب پکیج جدید ممکن نبود؛ تعویض به کتابخانه‌ی رسمی بعداً، پشت همین اینترفیس، بی‌خطر است.

## ارائه‌دهنده‌ی هوش مصنوعی (تصمیم فعلی پروژه)
- **OpenRouter ارائه‌دهنده‌ی اصلی و فعال است.** `apps/telegram-bot/main.py` و
  `apps/bale-bot/main.py` هر دو از همان یک ماژول مشترک `packages/core/ai/openrouter.py`
  استفاده می‌کنند (نه کپی جدا در هر ربات).
- API مصرفی: `POST https://openrouter.ai/api/v1/chat/completions` (فرمت سازگار با OpenAI).
- `packages/core/ai/gemini.py` حذف نشد؛ به‌عنوان ارائه‌دهنده‌ی اختیاری/غیرفعال برای آینده
  نگه‌داشته شده (تست‌هایش هم همچنان پاس می‌شوند)، اما **هیچ ربات فعلی آن را فرانمی‌خواند**.
- اگر در آینده ارائه‌دهنده‌ی سومی اضافه شود، باید مثل این دو، یک آداپتور مستقل در
  `packages/core/ai/` با همان امضای `generate(history, prompt, system_instruction)` باشد؛
  OpenRouter همچنان پیش‌فرض باقی می‌ماند مگر تصمیم صریح دیگری گرفته شود.
- جزئیات پیاده‌سازی و نتایج تست مهاجرت در `docs/TEST_REPORT.md` (بخش «مهاجرت به OpenRouter»).

## وضعیت لایه‌های آینده (طبق MASTER_PROJECT_DIRECTIVE، هنوز شروع نشده)
وب‌اپ، پنل ادمین، اشتراک/لایسنس/پرداخت — در فازهای F به بعد. وارد کردن آن‌ها حالا فقط
حجم کد را بالا می‌برد بدون اینکه هسته تثبیت شده باشد؛ طبق دستور صریح خودِ مستند راهنما
("Do not generate thousands of lines of unverified code in one pass").
