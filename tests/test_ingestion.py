from unittest.mock import patch

import pytest
import tiktoken
from sqlalchemy import select

from app.core.ingestion import chunk_text, ingest_text, normalize_source
from app.models import Chunk

VECTOR = [1.0] + [0.0] * 1535


def test_chunk_limits_and_unicode():
    content = ('Notes about PostgreSQL. 中文🙂\n\n' * 300)
    chunks = chunk_text(content)
    enc = tiktoken.get_encoding('cl100k_base')
    assert len(chunks) > 1
    assert all(len(enc.encode(c)) <= 500 and len(c.encode('utf-8')) <= 2048 for c in chunks)
    assert all('�' not in c for c in chunks)
    assert chunks[0].startswith('Notes')
    assert chunks[-1].endswith('中文🙂\n\n')


def test_empty_and_overlap():
    assert chunk_text(' \n') == []
    content = ' abc' * 1000
    chunks = chunk_text(content)
    assert len(chunks) > 1
    assert chunks[0][-100:] in chunks[1]
    with pytest.raises(ValueError):
        chunk_text(content, 75, 75)


@pytest.mark.parametrize('source', ['/a.md', '../a.md', 'a.pdf', '.', ''])
def test_invalid_sources(source):
    with pytest.raises(ValueError):
        normalize_source(source)


@patch('app.core.ingestion.embed_text', return_value=VECTOR)
def test_reingest_and_failed_embeddings_preserve_source(mock_embed, db_session):
    ingest_text(db_session, 'docs/test.md', 'old content', {'format': 'md'})
    ingest_text(db_session, 'docs/test.md', 'new content')
    rows = db_session.scalars(select(Chunk).where(Chunk.source == 'docs/test.md')).all()
    assert len(rows) == 1 and rows[0].content == 'new content'
    assert rows[0].embedding_model.startswith(('gemini:', 'openai:'))
    mock_embed.side_effect = RuntimeError('provider failed')
    with pytest.raises(RuntimeError):
        ingest_text(db_session, 'docs/test.md', 'updated again')
    assert db_session.scalars(select(Chunk)).one().content == 'new content'
    assert ingest_text(db_session, 'docs/test.md', '  ') == []
    assert db_session.scalars(select(Chunk)).one().content == 'new content'


@patch('app.core.ingestion.embed_text', return_value=VECTOR)
def test_database_failure_rolls_back_replacement(mock_embed, db_session):
    ingest_text(db_session, 'docs/test.md', 'original')
    with patch.object(db_session, 'commit', side_effect=RuntimeError('commit failure')):
        with pytest.raises(RuntimeError):
            ingest_text(db_session, 'docs/test.md', 'replacement')
    assert db_session.scalars(select(Chunk)).one().content == 'original'


def test_cli_reads_folder_and_skips_empty(tmp_path, monkeypatch, capsys):
    from scripts import ingest
    (tmp_path / 'note.md').write_text('note', encoding='utf-8')
    (tmp_path / 'empty.txt').write_text('', encoding='utf-8')
    (tmp_path / 'ignore.pdf').write_text('unsupported', encoding='utf-8')
    monkeypatch.setattr('sys.argv', ['ingest', str(tmp_path), '--root', str(tmp_path)])
    with patch.object(ingest, 'SessionLocal'), patch.object(ingest, 'ingest_text', side_effect=lambda db, source, content, metadata: [object()] if content else []) as mocked:
        assert ingest.main() == 0
    assert mocked.call_count == 2
    assert 'Files saved: 1; skipped: 1; failed: 0' in capsys.readouterr().out
