from unittest.mock import patch
from fastapi.testclient import TestClient
from app.api.main import app
from app.db import get_db


def test_upload_validation_before_embedding():
    app.dependency_overrides[get_db] = lambda: None
    try:
        with TestClient(app) as client, patch('app.api.routes.ingest_text') as ingest:
            for filename, body, status in [('test.pdf', b'note', 422), ('../test.md', b'note', 422),
                                          ('test.md', b'x' * (65536 + 1), 413),
                                          ('test.md', b'\xff', 422), ('test.md', b' ', 422)]:
                assert client.post('/api/sources/upload', params={'filename': filename}, content=body).status_code == status
            ingest.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_upload_valid_file():
    app.dependency_overrides[get_db] = lambda: None
    try:
        with TestClient(app) as client, patch('app.api.routes.ingest_text', return_value=[]) as ingest:
            response = client.post('/api/sources/upload?filename=notes.md', content=b'# notes')
            assert response.status_code == 200
            assert response.json()['source'] == 'uploads/notes.md'
            ingest.assert_called_once_with(None, 'uploads/notes.md', '# notes', {'format': 'md'})
    finally:
        app.dependency_overrides.clear()


def test_raw_text_validation_and_save():
    app.dependency_overrides[get_db] = lambda: None
    try:
        with TestClient(app) as client, patch('app.api.routes.ingest_text', return_value=[]) as ingest:
            assert client.post('/api/sources/text?title=Test', content=b'hello').status_code == 200
            ingest.assert_called_once_with(None, 'notes/Test.txt', 'hello', {'format': 'text'})
            ingest.reset_mock()
            for title, body, status in [('Bad/path', b'note', 422), ('Good', b' ', 422), ('Good', b'\xff', 422), ('Good', b'x'*65537, 413)]:
                assert client.post('/api/sources/text', params={'title': title}, content=body).status_code == status
            ingest.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_delete_only_selected_source(db_session):
    from app.models import Chunk
    from app.core.embeddings import embedding_identity
    from sqlalchemy import select
    for source in ['notes/one.txt', 'notes/two.txt']:
        db_session.add(Chunk(source=source, chunk_index=0, content='test', source_metadata={},
                             embedding=[1.] + [0.] * 1535, embedding_model=embedding_identity()))
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as client:
            response = client.delete('/api/sources', params={'source': 'notes/one.txt'})
            assert response.status_code == 200 and response.json()['chunks_deleted'] == 1
            assert db_session.scalars(select(Chunk.source)).all() == ['notes/two.txt']
            assert client.delete('/api/sources', params={'source': 'notes/one.txt'}).status_code == 404
    finally:
        app.dependency_overrides.clear()
