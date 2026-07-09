# FB Live/Die Checker — Tác giả: @nhanxp | Hỗ trợ: Telegram/Facebook nhanxp
import httpx
import random

from . import config, db


USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 12; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.58 Mobile Safari/537.36",
]

import re

def extract_uid(link: str) -> str:
    link = (link or "").strip()
    if not link:
        return ""
    if "facebook.com" in link or "fb.com" in link:
        if "profile.php?id=" in link:
            match = re.search(r'id=(\d+)', link)
            if match: return match.group(1)
        else:
            match = re.search(r'(?:facebook\.com|fb\.com)/([^/?]+)', link)
            if match:
                # Tránh lấy nhầm các path mặc định của facebook
                if match.group(1).lower() not in ["home.php", "login.php", "watch", "groups", "marketplace"]:
                    return match.group(1)
    
    # Fallback cho trường hợp chỉ là UID thuần
    for sep in ("@", "?", "/", " ", "|"):
        if sep in link and not ("http" in link):
            link = link.split(sep)[0]
    return link.replace("https://", "").replace("http://", "").split("/")[0]


async def check_uid(uid: str) -> dict:
    uid = extract_uid(uid)
    result = {"uid": uid, "alive": False, "avatar_url": None, "ok": False}
    if not uid:
        return result

    # Dùng mbasic (giống v1.py) để vượt anti-bot và check chính xác
    url = f"https://mbasic.facebook.com/{uid}"
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            # allow_redirects=False -> httpx dùng follow_redirects=False
            r = await client.get(url, headers=headers)
            
            result["ok"] = True
            result["avatar_url"] = avatar_url(uid)
            
            html = r.text.lower()
            
            # Logic check mbasic giống v1.py
            if r.status_code == 200:
                die_indicators = ["không tìm thấy trang", "account disabled", "bị vô hiệu hóa", "checkpoint", "not found", "không khả dụng"]
                if any(ind in html for ind in die_indicators):
                    result["alive"] = False
                else:
                    result["alive"] = True
            elif r.status_code in [301, 302]:
                loc = r.headers.get("location", "").lower()
                if "login" in loc or "checkpoint" in loc:
                    result["alive"] = True
                else:
                    result["alive"] = False
            elif r.status_code == 404:
                result["alive"] = False
            else:
                result["alive"] = False
                
    except Exception as e:
        # Lỗi mạng
        pass

    return result


def avatar_url(uid: str, size: int = 500) -> str:
    uid = extract_uid(uid)
    token = db.get_setting("fb_avatar_token", config.DEFAULT_FB_AVATAR_TOKEN)
    base = f"{config.FB_GRAPH}/{uid}/picture?height={size}&width={size}"
    if token:
        base += f"&access_token={token}"
    return base
