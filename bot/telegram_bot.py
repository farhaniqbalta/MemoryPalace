import httpx
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, CommandHandler, filters

from app.config import settings

API_BASE_URL = settings.api_base_url


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/ingest",
            json={"source_type": "telegram", "content": text},
            timeout=60,
        )
    if response.status_code != 200:
        await update.message.reply_text(f"Couldn't save that: {response.text}")
        return
    card = response.json()
    await update.message.reply_text(
        f"Saved as [{card['type']}] {card['title']}\nTags: {', '.join(card['tags'])}"
    )


async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = " ".join(context.args)
    if not question:
        await update.message.reply_text("Usage: /ask <question>")
        return
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/ask", json={"question": question}, timeout=60
        )
    if response.status_code != 200:
        await update.message.reply_text(f"Couldn't answer that: {response.text}")
        return
    data = response.json()
    titles = ", ".join(c["title"] for c in data["cited_cards"]) or "none"
    await update.message.reply_text(f"{data['answer']}\n\nSources: {titles}")


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Usage: /search <query>")
        return
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/search", json={"query": query}, timeout=60
        )
    if response.status_code != 200:
        await update.message.reply_text(f"Search failed: {response.text}")
        return
    results = response.json()
    if not results:
        await update.message.reply_text("No matches found.")
        return
    lines = [f"- {r['card']['title']} ({r['score']:.2f})" for r in results]
    await update.message.reply_text("\n".join(lines))


def build_app() -> Application:
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("ask", ask))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return application


if __name__ == "__main__":
    build_app().run_polling()
