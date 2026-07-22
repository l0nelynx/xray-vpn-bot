import { Laptop, Smartphone, RefreshCw, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Alert, AlertTitle } from "@xray/ui/components/alert";
import { Badge } from "@xray/ui/components/badge";
import { Button } from "@xray/ui/components/button";
import { Spinner } from "@xray/ui/components/spinner";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@xray/ui/components/alert-dialog";
import { api, DeviceItem, DevicesResponse } from "../api/client";
import { useT } from "../i18n/LocaleContext";

function platformIcon(platform: string | null) {
  if (!platform) return <Laptop />;
  const p = platform.toLowerCase();
  if (p.includes("android") || p.includes("ios") || p.includes("iphone") || p.includes("mobile")) {
    return <Smartphone />;
  }
  return <Laptop />;
}

export default function DevicesPage() {
  const { t, dateLocale } = useT();
  const [devices, setDevices] = useState<DeviceItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const [confirmHwid, setConfirmHwid] = useState<string | null>(null);

  const formatDate = (value: string | null): string => {
    if (!value) return t("common.emDash");
    try {
      return new Date(value).toLocaleString(dateLocale, {
        day: "numeric",
        month: "short",
        year: "numeric",
      });
    } catch {
      return value;
    }
  };

  const load = () => {
    setDevices(null);
    setError(null);
    api
      .get<DevicesResponse>("/devices")
      .then((res) => setDevices(res.devices))
      .catch((e) => setError(e?.detail || String(e)));
  };

  useEffect(() => { load(); }, []);

  const handleDelete = async (hwid: string) => {
    setRemoving(hwid);
    try {
      await api.delete<void>(`/devices/${encodeURIComponent(hwid)}`);
      setDevices((prev) => (prev ? prev.filter((d) => d.hwid !== hwid) : prev));
      toast.success(t("devices.toast.deleted"));
    } catch (e: any) {
      toast.error(t("devices.toast.deleteFailed"), { description: e?.detail || String(e) });
    } finally {
      setRemoving(null);
      setConfirmHwid(null);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <span style={{ fontSize: 22, fontWeight: 700, color: "#FFFFFF", letterSpacing: "-0.3px" }}>
          {t("devices.title")}
        </span>
        <Button
          className="refresh-fab"
          size="icon"
          variant="outline"
          onClick={load}
          aria-label={t("devices.refreshAria")}
        >
          <RefreshCw />
        </Button>
      </div>

      {error && (
        <Alert variant="destructive" style={{ marginBottom: 16 }}>
          <AlertTitle>{error}</AlertTitle>
        </Alert>
      )}

      {devices === null && !error && (
        <div className="spinner-wrap">
          <Spinner />
        </div>
      )}

      {devices && devices.length === 0 && (
        <div style={{ textAlign: "center", padding: "40px 0", color: "rgba(255,255,255,0.38)" }}>
          {t("devices.empty")}
        </div>
      )}

      {devices && devices.map((d) => (
        <div key={d.hwid} className="device-card">
          <div className="device-card__icon">
            {platformIcon(d.platform)}
          </div>

          <div className="device-card__body">
            <div className="device-card__name">
              {d.device_model || d.platform || t("devices.fallbackName")}
              {d.platform && (
                <Badge style={{ marginLeft: 8, fontSize: 11, verticalAlign: "middle" }}>
                  {d.platform}
                </Badge>
              )}
            </div>
            {d.os_version && (
              <div className="device-card__meta">{t("devices.os", { version: d.os_version })}</div>
            )}
            <div className="device-card__meta" style={{ marginTop: 4 }}>
              {t("devices.added", { date: formatDate(d.created_at) })}
            </div>
            <div className="device-card__meta" style={{ opacity: 0.6, marginTop: 2, fontSize: 11 }}>
              {d.hwid}
            </div>
          </div>

          <div className="device-card__actions">
            <Button
              variant="destructive"
              size="icon"
              className="rounded-full"
              onClick={() => setConfirmHwid(d.hwid)}
              disabled={removing === d.hwid}
            >
              {removing === d.hwid ? <Spinner /> : <Trash2 />}
            </Button>
          </div>
        </div>
      ))}

      <AlertDialog open={!!confirmHwid} onOpenChange={(open: boolean) => !open && setConfirmHwid(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("devices.confirm.title")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("devices.confirm.body")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("devices.confirm.cancel")}</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => confirmHwid && handleDelete(confirmHwid)}
            >
              {t("devices.confirm.delete")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
