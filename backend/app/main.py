# FB Live/Die Checker — Tác giả: @nhanxp | Hỗ trợ: Telegram/Facebook nhanxp
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, db
from .api import router as api_router
from .bot import manager
from .poller import poller

app = FastAPI(title=config.APP_NAME)
app.include_router(api_router)


@app.on_event("startup")
async def on_startup():
    db.init_db()
    token = db.get_setting("bot_token")
    if token and db.get_setting("setup_done") == "1":
        if await manager.start(token):
            poller.start()


@app.on_event("shutdown")
async def on_shutdown():
    await poller.stop()
    await manager.stop()


@app.get("/api/health")
def health():
    return {"ok": True, "app": config.APP_NAME, "version": config.APP_VERSION}


if os.path.isdir(config.STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(config.STATIC_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        index = os.path.join(config.STATIC_DIR, "index.html")
        if os.path.isfile(index):
            return FileResponse(index)
        return JSONResponse({"detail": "Frontend chưa build"}, status_code=404)
