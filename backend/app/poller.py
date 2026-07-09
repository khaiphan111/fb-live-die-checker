# FB Live/Die Checker — Tác giả: @nhanxp | Hỗ trợ: Telegram/Facebook nhanxp
import asyncio

from . import bot as botmod
from . import db, fb
from .util import now


class Poller:
    def __init__(self):
        self._task = None
        self.last_run = 0

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self):
        if not self.running:
            self._task = asyncio.create_task(self._loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    async def _loop(self):
        while True:
            try:
                await self._tick()
            except Exception as e:
                db.add_log("system", f"Lỗi poller: {e}")
            interval = int(db.get_setting("poll_interval", "60") or 60)
            await asyncio.sleep(max(15, interval))

    async def _tick(self):
        self.last_run = now()
        for w in db.active_watches():
            if w["expire_at"] and now() > w["expire_at"]:
                db.deactivate_watch(w["id"])
                db.add_log("system", f"Hết hạn theo dõi UID {w['uid']}", w["tg_id"], w["uid"])
                continue

            res = await fb.check_uid(w["uid"])
            if not res["ok"]:
                continue
            new_status = "live" if res["alive"] else "die"
            avatar = res["avatar_url"] or w["avatar_url"] or fb.avatar_url(w["uid"])
            old = w["last_status"]
            db.update_watch_status(w["id"], new_status, avatar)

            if old and old != new_status:
                db.add_log(
                    "change",
                    f"UID {w['uid']}: {old} → {new_status}",
                    w["tg_id"],
                    w["uid"],
                )
                await self._notify(w, new_status, avatar)
            await asyncio.sleep(0.3)

    async def _notify(self, w, status, avatar):
        bot = botmod.manager.bot
        if not bot:
            return
        try:
            await botmod._send_card(
                bot, w["tg_id"], w["uid"], status, w["note"], w["price"],
                avatar, header="Thay đổi trạng thái:",
            )
        except Exception as e:
            db.add_log("system", f"Lỗi gửi thông báo {w['tg_id']}: {e}")


poller = Poller()
