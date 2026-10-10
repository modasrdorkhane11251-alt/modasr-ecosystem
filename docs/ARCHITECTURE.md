# معماری (مونولیت ماژولار — طبق دستور، بدون میکروسرویس غیرضروری)

```
packages/core/
  config.py            بارگذاری/اعتبارسنجی env، بدون مقدار پیش‌فرض خطرناک
  database.py           SQLite + مهاجرت نسخه‌دار (user_version)؛ هویت = (platform, platform_user_id)
  platform_adapter.py    اینترفیس انتزاعی مشترک همه‌ی پیام‌رسان‌ها
  ai/gemini.py           کلاینت Gemini؛ تنها نقطه‌ی تماس با هوش مصنوعی

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

## وضعیت لایه‌های آینده (طبق MASTER_PROJECT_DIRECTIVE، هنوز شروع نشده)
وب‌اپ، پنل ادمین، اشتراک/لایسنس/پرداخت — در فازهای F به بعد. وارد کردن آن‌ها حالا فقط
حجم کد را بالا می‌برد بدون اینکه هسته تثبیت شده باشد؛ طبق دستور صریح خودِ مستند راهنما
("Do not generate thousands of lines of unverified code in one pass").
