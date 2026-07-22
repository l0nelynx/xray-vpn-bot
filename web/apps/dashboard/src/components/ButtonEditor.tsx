import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@xray/ui/components/dialog";
import { Input } from "@xray/ui/components/input";
import { Label } from "@xray/ui/components/label";
import { Switch } from "@xray/ui/components/switch";
import { Button } from "@xray/ui/components/button";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@xray/ui/components/select";
import type { MenuButton, MenuScreen } from "../api/types";
import { api } from "../api/client";

const KNOWN_CALLBACKS = [
  { value: "Premium", label: "Premium — Buy premium menu" },
  { value: "Extend_Month", label: "Extend_Month — Extend subscription" },
  { value: "Others", label: "Others — Instructions" },
  { value: "Free", label: "Free — Free version" },
  { value: "Sub_Info", label: "Sub_Info — Subscription info" },
  { value: "Devices", label: "Devices — Devices list" },
  { value: "Invite_Friends", label: "Invite_Friends — Referral" },
  { value: "Settings", label: "Settings — Settings menu" },
  { value: "Change_Language", label: "Change_Language — Language picker" },
  { value: "Agreement", label: "Agreement — User agreement" },
  { value: "Privacy", label: "Privacy — Privacy policy" },
  { value: "Main", label: "Main — Back to main menu" },
  { value: "Stars_Plans", label: "Stars_Plans — Stars tariffs" },
  { value: "Crypto_Plans", label: "Crypto_Plans — Crypto tariffs" },
  { value: "Crystal_plans", label: "Crystal_plans — Crystal tariffs" },
  { value: "SBP_Apay", label: "SBP_Apay — SBP/Apple Pay tariffs" },
  { value: "Enter_Promo", label: "Enter_Promo — Promo code input" },
  { value: "Migrate_RemnaWave", label: "Migrate_RemnaWave — Migration" },
  { value: "Telemt_Free", label: "Telemt_Free — Telemt free (channel sub)" },
];

const DEFAULTS: Partial<MenuButton> = {
  text_ru: "",
  text_en: "",
  callback_data: "",
  url: "",
  button_type: "callback",
  is_active: true,
  visibility_condition: "always",
};

interface ButtonEditorProps {
  open: boolean;
  button: Partial<MenuButton> | null;
  onSave: (values: Partial<MenuButton>) => void;
  onCancel: () => void;
}

export default function ButtonEditor({ open, button, onSave, onCancel }: ButtonEditorProps) {
  const [screens, setScreens] = useState<MenuScreen[]>([]);
  const [values, setValues] = useState<Partial<MenuButton>>(DEFAULTS);

  useEffect(() => {
    if (open) {
      api.get<MenuScreen[]>("/menus/screens").then(setScreens).catch(() => {});
    }
  }, [open]);

  useEffect(() => {
    if (open) setValues({ ...DEFAULTS, ...(button || {}) });
  }, [open, button]);

  const set = <K extends keyof MenuButton>(field: K, value: MenuButton[K]) =>
    setValues((v) => ({ ...v, [field]: value }));

  const buttonType = values.button_type;
  const isUrlType = buttonType === "url" || buttonType === "webapp";

  const handleOk = () => {
    if (!values.text_ru?.trim() || !values.text_en?.trim()) {
      toast.error("Text (RU) and Text (EN) are required");
      return;
    }
    if (isUrlType && !values.url?.trim()) {
      toast.error("URL is required");
      return;
    }
    onSave({ ...button, ...values });
  };

  return (
    <Dialog open={open} onOpenChange={(o: boolean) => !o && onCancel()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{button?.id ? "Edit Button" : "New Button"}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>Text (RU)</Label>
            <Input value={values.text_ru ?? ""} onChange={(e) => set("text_ru", e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>Text (EN)</Label>
            <Input value={values.text_en ?? ""} onChange={(e) => set("text_en", e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>Type</Label>
            <Select
              value={values.button_type ?? "callback"}
              onValueChange={(v: string) => set("button_type", v)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="callback">Callback</SelectItem>
                <SelectItem value="url">URL</SelectItem>
                <SelectItem value="webapp">WebApp</SelectItem>
                <SelectItem value="tariff">Tariff</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {!isUrlType && (
            <div className="space-y-1.5">
              <Label>Callback Data</Label>
              <Select
                value={values.callback_data || undefined}
                onValueChange={(v: string) => set("callback_data", v)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select handler or screen..." />
                </SelectTrigger>
                <SelectContent>
                  {screens.length > 0 && (
                    <SelectGroup>
                      <SelectLabel>Open Screen (dynamic)</SelectLabel>
                      {screens.map((s) => (
                        <SelectItem key={s.slug} value={`screen:${s.slug}`}>
                          {s.name} ({s.slug})
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  )}
                  <SelectGroup>
                    <SelectLabel>Bot Handlers (hardcoded)</SelectLabel>
                    {KNOWN_CALLBACKS.map((c) => (
                      <SelectItem key={c.value} value={c.value}>
                        {c.label}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
              <p className="text-[11px] text-muted-foreground">
                "Open Screen" items use prefix <code>screen:</code> — the bot renders them
                dynamically from the constructor.
              </p>
            </div>
          )}

          {isUrlType && (
            <div className="space-y-1.5">
              <Label>URL</Label>
              <Input
                placeholder="https://..."
                value={values.url ?? ""}
                onChange={(e) => set("url", e.target.value)}
              />
            </div>
          )}

          <div className="space-y-1.5">
            <Label>Visibility</Label>
            <Select
              value={values.visibility_condition ?? "always"}
              onValueChange={(v: string) => set("visibility_condition", v)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="always">Always</SelectItem>
                <SelectItem value="show_promo">Show Promo Only</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-2">
            <Switch
              checked={!!values.is_active}
              onCheckedChange={(v: boolean) => set("is_active", v)}
            />
            <Label>Active</Label>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={handleOk}>OK</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
