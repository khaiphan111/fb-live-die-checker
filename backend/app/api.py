# FB Live/Die Checker — Tác giả: @nhanxp | Hỗ trợ: Telegram/Facebook nhanxp
import secrets
import time

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from . import config, db, fb
from .bot import manager
from .poller import poller
from .util import now

router = APIRouter(prefix="/api")
_tokens = set()

DAY = 86400


def auth(authorization: str = Header(default="")):
    token = authorization.replace("Bearer ", "").strip()
    if token not in _tokens:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    return True


class LoginIn(BaseModel):
    password: str


class SettingsIn(BaseModel):
    bot_token: str | None = None
    price_1m: str | None = None
    poll_interval: str | None = None
    fb_avatar_token: str | None = None
    admin_password: str | None = None


class TokenIn(BaseModel):
    token: str


class AmountIn(BaseModel):
    amount: int


class MonthsIn(BaseModel):
    days: int


class UidIn(BaseModel):
    uid: str


def _row(r):
    return dict(r) if r else None


@router.post("/login")
def login(body: LoginIn):
    if body.password != db.get_setting("admin_password", "admin"):
        raise HTTPException(status_code=401, detail="Sai mật khẩu")
    tok = secrets.token_hex(24)
    _tokens.add(tok)
    return {"ok": True, "token": tok}


@router.get("/status")
def status(_=Depends(auth)):
    watches = db.all_watches()
    live = sum(1 for w in watches if w["last_status"] == "live")
    die = sum(1 for w in watches if w["last_status"] == "die")
    return {
        "app": config.APP_NAME,
        "version": config.APP_VERSION,
        "author": config.AUTHOR,
        "setup_done": db.get_setting("setup_done") == "1",
        "bot_running": manager.running,
        "poller_running": poller.running,
        "poller_last_run": poller.last_run,
        "users": len(db.list_users()),
        "watches_total": len(watches),
        "watches_live": live,
        "watches_die": die,
    }


@router.get("/settings")
def get_settings(_=Depends(auth)):
    s = db.all_settings()
    s.pop("admin_password", None)
    return s


@router.post("/settings")
async def save_settings(body: SettingsIn, _=Depends(auth)):
    restart_bot = False
    data = body.model_dump(exclude_none=True)
    for k, v in data.items():
        if k == "bot_token" and v != db.get_setting("bot_token"):
            restart_bot = True
        db.set_setting(k, v)
    if restart_bot:
        token = db.get_setting("bot_token")
        ok = await manager.start(token) if token else False
        if ok:
            db.set_setting("setup_done", "1")
            poller.start()
        return {"ok": True, "bot_running": manager.running, "bot_started": ok}
    return {"ok": True, "bot_running": manager.running}


@router.post("/verify-bot")
async def verify_bot(body: TokenIn, _=Depends(auth)):
    username = await manager.verify_token(body.token)
    if not username:
        raise HTTPException(status_code=400, detail="Token không hợp lệ")
    return {"ok": True, "username": username}


@router.get("/prereq")
async def prereq(_=Depends(auth)):
    out = {"telegram": False, "facebook": False, "bot_token": False}
    async with httpx.AsyncClient(timeout=10) as c:
        try:
            r = await c.get("https://api.telegram.org")
            out["telegram"] = r.status_code < 500
        except Exception:
            pass
        try:
            r = await c.get(f"{config.FB_GRAPH}/4/picture", params={"redirect": "false"})
            out["facebook"] = r.status_code < 500
        except Exception:
            pass
    token = db.get_setting("bot_token")
    if token:
        out["bot_token"] = bool(await manager.verify_token(token))
    return out


@router.get("/users")
def users(_=Depends(auth)):
    return [_row(u) for u in db.list_users()]


@router.post("/users/{tg_id}/topup")
def topup(tg_id: int, body: AmountIn, _=Depends(auth)):
    if not db.get_user(tg_id):
        raise HTTPException(status_code=404, detail="Không có user này")
    db.adjust_balance(tg_id, body.amount, "Admin nạp")
    db.add_log("topup", f"Admin nạp {body.amount}", tg_id)
    return {"ok": True, "user": _row(db.get_user(tg_id))}


@router.post("/users/{tg_id}/sub")
def grant_sub(tg_id: int, body: MonthsIn, _=Depends(auth)):
    user = db.get_user(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="Không có user này")
    base = max(now(), user["sub_until"] or 0)
    db.set_sub_until(tg_id, base + body.days * DAY)
    db.add_log("sub", f"Admin cấp {body.days} ngày", tg_id)
    return {"ok": True, "user": _row(db.get_user(tg_id))}


@router.get("/watches")
def watches(_=Depends(auth)):
    return [_row(w) for w in db.all_watches()]


@router.delete("/watches/{watch_id}")
def del_watch(watch_id: int, _=Depends(auth)):
    db.deactivate_watch(watch_id)
    return {"ok": True}


@router.get("/logs")
def logs(_=Depends(auth)):
    return [_row(l) for l in db.recent_logs(150)]


@router.post("/check")
async def manual_check(body: UidIn, _=Depends(auth)):
    res = await fb.check_uid(body.uid)
    return {
        "uid": res["uid"],
        "status": "live" if res["alive"] else ("die" if res["ok"] else "error"),
        "avatar_url": res["avatar_url"] or fb.avatar_url(res["uid"]),
    }
