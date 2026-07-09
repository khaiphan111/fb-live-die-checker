// FB Live/Die Checker — Tác giả: @nhanxp | Hỗ trợ: Telegram/Facebook nhanxp
import { IconCoin, IconRefresh, IconCalendarPlus } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { Badge, Button, Card, CardContent, Input } from "../components/ui";
import { api } from "../lib/api";
import { fromNow, vnd } from "../lib/utils";

export default function Users() {
  const [users, setUsers] = useState<any[]>([]);
  const [amount, setAmount] = useState<Record<number, string>>({});
  const [days, setDays] = useState<Record<number, string>>({});

  async function load() {
    try {
      setUsers(await api("/api/users"));
    } catch (e: any) {
      toast.error(e.message);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function topup(id: number) {
    const v = Number(amount[id]);
    if (!v) return toast.error("Nhập số tiền");
    try {
      await api(`/api/users/${id}/topup`, { method: "POST", body: JSON.stringify({ amount: v }) });
      toast.success("Đã nạp số dư");
      setAmount((p) => ({ ...p, [id]: "" }));
      load();
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function grant(id: number) {
    const v = Number(days[id]);
    if (!v) return toast.error("Nhập số ngày");
    try {
      await api(`/api/users/${id}/sub`, { method: "POST", body: JSON.stringify({ days: v }) });
      toast.success("Đã cấp gói");
      setDays((p) => ({ ...p, [id]: "" }));
      load();
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  const now = Date.now() / 1000;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Người dùng Telegram</h1>
        <Button variant="outline" size="sm" onClick={load}>
          <IconRefresh size={16} /> Làm mới
        </Button>
      </div>

      {users.length === 0 && (
        <Card>
          <CardContent className="text-sm text-muted-foreground">
            Chưa có người dùng. Khi ai đó gõ /start trong bot, họ sẽ xuất hiện ở đây.
          </CardContent>
        </Card>
      )}

      <div className="flex flex-col gap-3">
        {users.map((u) => {
          const active = u.sub_until > now;
          return (
            <Card key={u.tg_id}>
              <CardContent className="flex flex-wrap items-center gap-4">
                <div className="min-w-44">
                  <div className="font-medium">{u.name || "—"}</div>
                  <div className="text-sm text-muted-foreground">
                    @{u.username || u.tg_id}
                  </div>
                </div>
                <div className="min-w-32">
                  <div className="text-xs text-muted-foreground">Số dư</div>
                  <div className="font-medium">{vnd(u.balance)}</div>
                </div>
                <div className="min-w-40">
                  <div className="text-xs text-muted-foreground">Gói</div>
                  <Badge status={active ? "live" : "neutral"}>
                    {active ? `Đến ${fromNow(u.sub_until)}` : "Chưa có"}
                  </Badge>
                </div>
                <div className="flex items-center gap-2 ml-auto">
                  <Input
                    className="w-28"
                    placeholder="Số tiền"
                    value={amount[u.tg_id] || ""}
                    onChange={(e) => setAmount((p) => ({ ...p, [u.tg_id]: e.target.value }))}
                  />
                  <Button size="sm" variant="outline" onClick={() => topup(u.tg_id)}>
                    <IconCoin size={16} /> Nạp
                  </Button>
                  <Input
                    className="w-20"
                    placeholder="Ngày"
                    value={days[u.tg_id] || ""}
                    onChange={(e) => setDays((p) => ({ ...p, [u.tg_id]: e.target.value }))}
                  />
                  <Button size="sm" variant="outline" onClick={() => grant(u.tg_id)}>
                    <IconCalendarPlus size={16} /> Cấp gói
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
