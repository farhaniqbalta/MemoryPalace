from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api.routes import router

app = FastAPI(title="AI Knowledge Platform")
app.include_router(router)

static_dir = Path(__file__).resolve().parents[1] / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
def web_preview():
    return FileResponse(static_dir / "index.html")


# Return useful errors without exposing credentials, SQL, or submitted documents.
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
import anthropic
from google.genai.errors import APIError as GeminiAPIError
from openai import OpenAIError


@app.exception_handler(SQLAlchemyError)
async def database_error(request, error):
    return JSONResponse(status_code=503, content={'detail': 'The database is unavailable. Start PostgreSQL and check the local database configuration.'})


@app.exception_handler(anthropic.APIError)
@app.exception_handler(GeminiAPIError)
@app.exception_handler(OpenAIError)
async def provider_error(request, error):
    return JSONResponse(status_code=502, content={'detail': 'The AI provider request failed. Check API credentials, model availability, and quota, then try again.'})


@app.exception_handler(ValueError)
async def operation_error(request, error):
    return JSONResponse(status_code=502, content={'detail': 'The operation could not complete. Check provider configuration or retry the request.'})
