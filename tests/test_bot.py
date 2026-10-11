from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from bot import telegram_bot as bot


@pytest.fixture
def update(monkeypatch):
    monkeypatch.setattr(bot.settings, 'telegram_owner_id', 123)
    monkeypatch.setattr(bot.settings, 'api_base_url', 'http://test-api')
    message = SimpleNamespace(text='Why PostgreSQL?', reply_text=AsyncMock())
    return SimpleNamespace(effective_user=SimpleNamespace(id=123), effective_message=message,
                           effective_chat=SimpleNamespace(type='private'))


@pytest.mark.asyncio
@pytest.mark.parametrize('handler', [bot.ask, bot.search, bot.handle_message])
@pytest.mark.parametrize('kind', ['other-user', 'no-owner', 'group', 'no-user'])
async def test_reject_before_api(update, monkeypatch, handler, kind):
    if kind == 'other-user': update.effective_user.id = 999
    if kind == 'no-owner': monkeypatch.setattr(bot.settings, 'telegram_owner_id', None)
    if kind == 'group': update.effective_chat.type = 'group'
    if kind == 'no-user': update.effective_user = None
    with respx.mock(assert_all_called=False) as mock:
        await handler(update, SimpleNamespace(args=['question']))
        assert len(mock.calls) == 0
    update.effective_message.reply_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_owner_plain_text_question(update):
    with respx.mock() as mock:
        route = mock.post('http://test-api/ask').respond(200, json={'answer': 'Because pgvector.', 'sources': ['docs/prd.md']})
        await bot.handle_message(update, SimpleNamespace(args=[]))
    assert route.called
    assert 'Sources: docs/prd.md' in update.effective_message.reply_text.call_args.args[0]


@pytest.mark.asyncio
async def test_search_chunks(update):
    with respx.mock() as mock:
        mock.post('http://test-api/search').respond(200, json=[{'chunk': {'source': 'a.md', 'chunk_index': 0, 'content': 'notes'}, 'score': .9}])
        await bot.search(update, SimpleNamespace(args=['notes']))
    assert 'a.md (chunk 0, 0.90)' in update.effective_message.reply_text.call_args.args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [409, 422, 500])
async def test_api_failure(update, status):
    with respx.mock() as mock:
        mock.post('http://test-api/ask').respond(status, text='private internal details')
        await bot.ask(update, SimpleNamespace(args=['question']))
    assert 'private internal details' not in update.effective_message.reply_text.call_args.args[0]


@pytest.mark.asyncio
async def test_timeout(update):
    with respx.mock() as mock:
        mock.post('http://test-api/ask').mock(side_effect=httpx.ReadTimeout('timeout'))
        await bot.ask(update, SimpleNamespace(args=['question']))
    assert 'unavailable' in update.effective_message.reply_text.call_args.args[0]


@pytest.mark.asyncio
async def test_long_unicode_reply(update):
    text = '🙂' * 5000
    await bot.reply(update, text)
    pieces = [call.args[0] for call in update.effective_message.reply_text.call_args_list]
    assert ''.join(pieces) == text
    assert all(len(piece.encode('utf-16-le')) // 2 <= 4000 for piece in pieces)


def test_requires_owner(monkeypatch):
    monkeypatch.setattr(bot.settings, 'telegram_owner_id', None)
    with pytest.raises(ValueError, match='TELEGRAM_OWNER_ID'):
        bot.build_app()
