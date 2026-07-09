# FB Live/Die Checker — Tác giả: @nhanxp | Hỗ trợ: Telegram/Facebook nhanxp
import httpx

from . import config, db


def _first_part(uid: str) -> str:
    uid = (uid or "").strip()
    for sep in ("@", "?", "/", " "):
        if sep in uid:
            uid = uid.split(sep)[0]
    return uid


async def check_uid(uid: str) -> dict:
    uid = _first_part(uid)
    result = {"uid": uid, "alive": False, "avatar_url": None, "ok": False}
    if not uid:
        return result

    url = f"{config.FB_GRAPH}/{uid}/picture"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, params={"redirect": "false"})
            data = r.json()
    except Exception:
        return result

    result["ok"] = True
    if isinstance(data, dict) and data.get("data") and data["data"].get("height"):
        result["alive"] = True
        result["avatar_url"] = avatar_url(uid)
    return result


def avatar_url(uid: str, size: int = 500) -> str:
    uid = _first_part(uid)
    token = db.get_setting("fb_avatar_token", config.DEFAULT_FB_AVATAR_TOKEN)
    base = f"{config.FB_GRAPH}/{uid}/picture?height={size}&width={size}"
    if token:
        base += f"&access_token={token}"
    return base
