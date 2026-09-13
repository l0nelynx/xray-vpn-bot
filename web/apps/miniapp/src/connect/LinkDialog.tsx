import { useEffect, useRef, useState } from "react";
import { Copy } from "lucide-react";
import { Button } from "@xray/ui/components/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle } from "@xray/ui/components/dialog";
import { Spinner } from "@xray/ui/components/spinner";
import { useT } from "../i18n/LocaleContext";

export interface LinkResource {
  url: string;
  title: string;
  kind: "subscription" | "install" | "account" | "import" | "help";
  qr: boolean;
}

export default function LinkDialog({ resource, onClose, onCopy, returnFocus }: {
  resource: LinkResource | null;
  onClose: () => void;
  onCopy: (resource: LinkResource) => Promise<void>;
  returnFocus: React.RefObject<HTMLElement | null>;
}) {
  const { t } = useT();
  const [image, setImage] = useState("");
  const [failed, setFailed] = useState(false);
  const dialog = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let alive = true;
    setImage(""); setFailed(false);
    if (resource?.qr) {
      void import("qrcode").then(({ default: QRCode }) => QRCode.toDataURL(resource.url, {
        errorCorrectionLevel: "M", margin: 4, width: 720, color: { dark: "#000000", light: "#ffffff" },
      })).then((value) => { if (alive) setImage(value); }).catch(() => { if (alive) setFailed(true); });
    }
    return () => { alive = false; };
  }, [resource]);

  return <Dialog open={!!resource} onOpenChange={(open: boolean) => { if (!open) onClose(); }}>
    <DialogContent ref={dialog} tabIndex={-1} className="connect-link-dialog" overlayClassName="connect-modal-overlay" closeLabel={t("connect.closeDialog")} onOpenAutoFocus={(event: Event) => {
      // QR opens at its title, not scrolled down to the selectable URL field.
      if (resource?.qr) { event.preventDefault(); dialog.current?.focus({ preventScroll: true }); }
    }} onCloseAutoFocus={(event: Event) => {
      event.preventDefault(); returnFocus.current?.focus();
    }}>
      <DialogTitle>{resource?.title}</DialogTitle>
      <DialogDescription>{t(resource?.qr ? resource.kind === "subscription" ? "connect.qrSubscriptionHint" : "connect.qrExternalHint" : "connect.selectLinkHint")}</DialogDescription>
      {resource?.qr && <div className="connect-qr-image" aria-live="polite">
        {failed ? <p role="alert">{t("connect.qrFailed")}</p> : image ? <img src={image} alt={t("connect.qrAlt", { title: resource.title })} /> : <Spinner aria-label={t("connect.qrLoading")} />}
      </div>}
      {resource?.kind === "subscription" && resource.qr && <p className="connect-caption">{t("connect.personalLink")}</p>}
      <label className="connect-dialog-url">{t("connect.linkValue")}
        <textarea readOnly value={resource?.url ?? ""} onFocus={(event) => event.target.select()} rows={3} />
      </label>
      <Button variant="outline" onClick={() => { if (resource) void onCopy(resource); }}><Copy />{t("connect.copyLink")}</Button>
      <DialogClose asChild><Button variant="ghost">{t("connect.close")}</Button></DialogClose>
    </DialogContent>
  </Dialog>;
}
