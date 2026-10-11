"""Owner-only Telegram interface to the chunk RAG API."""
import math

import httpx
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, CommandHandler, filters

from app.config import settings


def allowed(update: Update) -> bool:
    return bool(settings.telegram_owner_id and update.effective_user
                and update.effective_user.id == settings.telegram_owner_id
                and update.effective_message and update.effective_chat
                and update.effective_chat.type == 'private')


async def reply(update: Update, text: str) -> None:
    # Telegram counts UTF-16 units; this also keeps emoji-heavy replies in bounds.
    pieces, current, units = [], [], 0
    for character in text:
        width = len(character.encode('utf-16-le')) // 2
        if units + width > 4000:
            pieces.append(''.join(current))
            current, units = [], 0
        current.append(character)
        units += width
    if current:
        pieces.append(''.join(current))
    for piece in pieces:
        await update.effective_message.reply_text(piece)


async def request(update: Update, endpoint: str, payload):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f'{settings.api_base_url}/{endpoint}', json=payload, timeout=120)
        if response.status_code == 409:
            await reply(update, 'The stored embeddings need re-embedding for the configured model.')
            return None
        if response.status_code == 422:
            await reply(update, 'Please use a nonempty question or query of at most 8000 characters.')
            return None
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        await reply(update, 'The knowledge API is unavailable or returned an invalid response. Please try again later.')
        return None


async def answer(update: Update, question: str) -> None:
    data = await request(update, 'ask', {'question': question})
    if data is None:
        return
    if (not isinstance(data, dict) or not isinstance(data.get('answer'), str)
            or not data['answer'].strip() or not isinstance(data.get('sources'), list)
            or not all(isinstance(source, str) for source in data['sources'])):
        await reply(update, 'The knowledge API returned an invalid answer.')
        return
    sources = ', '.join(data['sources']) or 'none'
    await reply(update, f"{data['answer']}\n\nSources: {sources}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update):
        return
    await answer(update, update.effective_message.text or '')


async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update):
        return
    question = ' '.join(context.args).strip()
    if not question:
        await reply(update, 'Usage: /ask <question>')
        return
    await answer(update, question)


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update):
        return
    query = ' '.join(context.args).strip()
    if not query:
        await reply(update, 'Usage: /search <query>')
        return
    results = await request(update, 'search', {'query': query})
    if results is None:
        return
    try:
        if not isinstance(results, list):
            raise ValueError('Invalid results')
        lines = []
        for result in results:
            chunk = result['chunk']
            if not isinstance(chunk['source'], str) or not isinstance(chunk['content'], str):
                raise ValueError('Invalid chunk')
            score = float(result['score'])
            if not math.isfinite(score):
                raise ValueError('Invalid score')
            lines.append(f"- {chunk['source']} (chunk {chunk['chunk_index']}, {score:.2f})\n{chunk['content'][:300]}")
    except (KeyError, TypeError, ValueError):
        await reply(update, 'The knowledge API returned invalid search results.')
        return
    await reply(update, '\n\n'.join(lines) if lines else 'No matches found.')


def build_app() -> Application:
    if settings.telegram_owner_id is None:
        raise ValueError('Set TELEGRAM_OWNER_ID to your numeric Telegram user ID before starting the bot')
    if not settings.telegram_bot_token.strip():
        raise ValueError('Set TELEGRAM_BOT_TOKEN before starting the bot')
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler('ask', ask))
    application.add_handler(CommandHandler('search', search))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return application


if __name__ == '__main__':
    build_app().run_polling()
