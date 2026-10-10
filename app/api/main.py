from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(title="AI Knowledge Platform")
app.include_router(router)
