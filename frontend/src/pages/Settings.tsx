// FB Live/Die Checker — Tác giả: @nhanxp | Hỗ trợ: Telegram/Facebook nhanxp
import { IconCircleCheck, IconCircleX, IconDeviceFloppy, IconPlugConnected } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { Button, Card, CardContent, CardHeader, CardTitle, Input, Label } from "../components/ui";
import { api } from "../lib/api";
import { vnd } from "../lib/utils";

function Check({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      {ok ? (
        <IconCircleCheck size={18} className="text-live" />
      ) : (
        <IconCircleX size={18} className="text-die" />
      )}
      {label}
    </div>
  );
}

export default function Settings({ onSaved }: { onSaved: () => void }) {
  const [s, setS] = useState<any>(null);
  const [prereq, setPrereq] = useState<any>(null);
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      setS(await api("/api/settings"));
      setPrereq(await api("/api/prereq"));
    } catch (e: any) {
      toast.error(e.message);
    }
  }
  useEffect(() => {
    load();
  }, []);

  function up(k: string, v: string) {
    setS((p: any) => ({ ...p, [k]: v }));
  }

  async function save() {
    setSaving(true);
    try {
      const r = await api("/api/settings", { method: "POST", body: JSON.stringify(s) });
      toast.success(r.bot_started ? "Đã lưu & khởi động bot" : "Đã lưu cấu hình");
      await load();
      onSaved();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setSaving(false);
    }
  }

  if (!s) return <div className="text-muted-foreground">Đang tải...</div>;
  const p1 = Number(s.price_1m) || 0;

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      <h1 className="text-2xl font-semibold">Cấu hình</h1>

      <Card>
        <CardHeader>
          <CardTitle>Điều kiện hoạt động</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {prereq ? (
            <>
              <Check ok={prereq.telegram} label="Kết nối tới Telegram API" />
              <Check ok={prereq.facebook} label="Kết nối tới Facebook Graph" />
              <Check ok={prereq.bot_token} label="Bot Token hợp lệ" />
            </>
          ) : (
            <span className="text-sm text-muted-foreground">Đang kiểm tra...</span>
          )}
          <Button variant="outline" size="sm" className="self-start mt-1" onClick={load}>
            <IconPlugConnected size={16} /> Kiểm tra lại
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Bot Telegram</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label>Bot Token</Label>
            <Input
              value={s.bot_token || ""}
              onChange={(e) => up("bot_token", e.target.value)}
              placeholder="123456:ABC-..."
            />
            <p className="text-xs text-muted-foreground">
              Lấy token từ @BotFather. Lưu xong bot tự khởi động và tạo menu.
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Giá gói & theo dõi</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label>Giá 1 tháng (VNĐ)</Label>
            <Input
              type="number"
              value={s.price_1m || ""}
              onChange={(e) => up("price_1m", e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Tự nhân: 2 tháng = {vnd(p1 * 2)} · 3 tháng = {vnd(p1 * 3)}
            </p>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Chu kỳ quét (giây)</Label>
            <Input
              type="number"
              value={s.poll_interval || ""}
              onChange={(e) => up("poll_interval", e.target.value)}
            />
            <p className="text-xs text-muted-foreground">Tối thiểu 15 giây.</p>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Token avatar Facebook (công khai)</Label>
            <Input
              value={s.fb_avatar_token || ""}
              onChange={(e) => up("fb_avatar_token", e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Bảo mật</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-1.5">
          <Label>Mật khẩu quản trị mới</Label>
          <Input
            type="password"
            value={s.admin_password || ""}
            onChange={(e) => up("admin_password", e.target.value)}
            placeholder="Để trống nếu không đổi"
          />
        </CardContent>
      </Card>

      <Button onClick={save} disabled={saving} className="self-start">
        <IconDeviceFloppy size={18} />
        {saving ? "Đang lưu..." : "Lưu cấu hình"}
      </Button>
    </div>
  );
}
