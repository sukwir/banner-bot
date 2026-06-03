import os
import json
import asyncio
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

NAME, URL, PRICE, COMMENTS = range(4)

user_data_store = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привіт! Я генерую промпти для рекламних банерів.\n\n"
        "Надішли мені назву товару щоб почати:"
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("🔗 Тепер надішли посилання на сайт конкурента:")
    return URL

async def get_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['url'] = update.message.text
    await update.message.reply_text("💰 Яка твоя ціна? (тільки число, наприклад: 899)")
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['price'] = update.message.text
    await update.message.reply_text(
        "💬 Є додаткові побажання? (стиль, акцент на характеристиці тощо)\n\n"
        "Або надішли /skip щоб пропустити:"
    )
    return COMMENTS

async def skip_comments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['comments'] = ''
    return await generate_prompts(update, context)

async def get_comments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['comments'] = update.message.text
    return await generate_prompts(update, context)

async def generate_prompts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data.get('name', '')
    url = context.user_data.get('url', '')
    price = context.user_data.get('price', '')
    comments = context.user_data.get('comments', '')

    msg = await update.message.reply_text("⏳ Генерую промпти... Зачекай 20-30 секунд")

    notes = f"Додаткові побажання: {comments}" if comments else ""

    prompt = f"""Товар: "{name}"
Посилання на сайт конкурента (для контексту): {url}
Ціна: {price} грн
{notes}

Згенеруй JSON з такою структурою:
{{
  "utp": ["6-8 коротких УТП по 3-5 слів, конкретні факти"],
  "site_prompts": [
    {{"index": 1, "task": "ГОЛОВНИЙ ЕКРАН", "prompt": "...детальний промпт..."}},
    {{"index": 2, "task": "КОМПЛЕКТАЦІЯ", "prompt": "..."}},
    {{"index": 3, "task": "ГОЛОВНА ФУНКЦІЯ", "prompt": "..."}},
    {{"index": 4, "task": "СЦЕНАРІЇ ВИКОРИСТАННЯ", "prompt": "..."}},
    {{"index": 5, "task": "ФІНАЛЬНИЙ ЗАКЛИК", "prompt": "..."}}
  ],
  "creative_prompts": [
    {{"index": 1, "headline": "ДЛЯ ІДЕАЛЬНОГО ВІДПОЧИНКУ!", "prompt": "..."}},
    {{"index": 2, "headline": "ТВІЙ КОМФОРТ — НАШ ПРІОРИТЕТ!", "prompt": "..."}},
    {{"index": 3, "headline": "ЗАМОВ І ВІДЧУЙ РІЗНИЦЮ!", "prompt": "..."}}
  ]
}}

Правила для промптів:
- КОЖЕН промпт починається з: CRITICAL — ZERO WATERMARKS. No ChatGPT/OpenAI/DALL-E text anywhere.
- site_prompts: вертикальний формат 4:5 (1080x1350px), стиль Rozetka/Wildberries
- creative_prompts: вертикальний формат 3:4 (1080x1440px), яскравий рекламний стиль як українські e-commerce банери
- Назва товару "{name}" — найбільший текст на банері
- Ціна {price} грн — завжди присутня
- Кнопка ЗАМОВЛЯЙ ЗАРАЗ → — завжди присутня на creative_prompts
- Весь текст на банері українською мовою
- УТП різні на кожному банері

Відповідай ТІЛЬКИ JSON без markdown."""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 4000,
                    "system": "Ти генеруєш промпти для рекламних зображень. Відповідай ТІЛЬКИ валідним JSON без markdown і backtick.",
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                data = await response.json()
                text = ''.join(b.get('text', '') for b in data.get('content', []))
                text = text.replace('```json', '').replace('```', '').strip()
                result = json.loads(text)

        await msg.delete()

        # Send UTP
        utp_text = "✅ *Дані витягнуто*\n\n*УТП товару:*\n" + "\n".join(f"• {u}" for u in result.get('utp', []))
        await update.message.reply_text(utp_text, parse_mode='Markdown')

        # Send site prompts
        await update.message.reply_text("📄 *ФОТО ДЛЯ САЙТУ (5 карток, формат 4:5)*", parse_mode='Markdown')
        for p in result.get('site_prompts', []):
            text = f"*Картка {p['index']} — {p['task']}*\n\n`{p['prompt']}`"
            await update.message.reply_text(text, parse_mode='Markdown')
            await asyncio.sleep(0.3)

        # Send creative prompts
        await update.message.reply_text("🎯 *БАНЕРИ ДЛЯ КРЕАТИВІВ (3 банери, формат 3:4)*", parse_mode='Markdown')
        for p in result.get('creative_prompts', []):
            text = f"*Банер {p['index']} — {p['headline']}*\n\n`{p['prompt']}`"
            await update.message.reply_text(text, parse_mode='Markdown')
            await asyncio.sleep(0.3)

        await update.message.reply_text(
            "✦ Готово! Копіюй промпти і вставляй в ChatGPT (вкладка Зображення)\n\n"
            "Для нового товару натисни /start"
        )

    except Exception as e:
        await msg.delete()
        await update.message.reply_text(
            f"❌ Помилка: {str(e)}\n\nСпробуй ще раз — натисни /start"
        )

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Скасовано. Натисни /start щоб почати знову.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_url)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_price)],
            COMMENTS: [
                CommandHandler('skip', skip_comments),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_comments)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    app.add_handler(conv_handler)
    print("Bot started...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
