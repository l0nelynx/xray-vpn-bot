import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Info } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@xray/ui/components/card";
import { Button } from "@xray/ui/components/button";
import { Input } from "@xray/ui/components/input";
import { Textarea } from "@xray/ui/components/textarea";
import { Switch } from "@xray/ui/components/switch";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@xray/ui/components/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@xray/ui/components/select";
import { cn } from "@xray/ui/lib/utils";
import { api } from "../../api/client";
import Collapsible from "../../components/Collapsible";
import type { ActionTypeMeta, CrmAction, CrmVariable, MessageTemplate } from "./types";

interface ActionsBuilderProps {
  actions: CrmAction[];
  onChange: (actions: CrmAction[]) => void;
  segmentId: string | null;
  templates?: MessageTemplate[];
  /** When "webhook", loads base + webhook-only template variables. */
  variablesContext?: "webhook" | null;
}

export default function ActionsBuilder({
  actions,
  onChange,
  segmentId,
  templates: templatesProp,
  variablesContext = null,
}: ActionsBuilderProps) {
  const [actionTypes, setActionTypes] = useState<ActionTypeMeta[]>([]);
  const [templates, setTemplates] = useState<MessageTemplate[]>(templatesProp || []);
  const [variablesOpen, setVariablesOpen] = useState(false);
  const [variables, setVariables] = useState<CrmVariable[]>([]);

  useEffect(() => {
    api.get<{ action_types: ActionTypeMeta[] }>("/crm/actions/types").then((r) => {
      setActionTypes(r.action_types);
    });
    const varsUrl =
      variablesContext === "webhook" ? "/crm/variables?context=webhook" : "/crm/variables";
    api.get<{ variables: CrmVariable[] }>(varsUrl).then((r) => {
      setVariables(r.variables);
    });
  }, [variablesContext]);

  useEffect(() => {
    if (templatesProp) {
      setTemplates(templatesProp);
      return;
    }
    if (!segmentId) {
      setTemplates([]);
      return;
    }
    api
      .get<{ templates: MessageTemplate[] }>(
        `/crm/templates?segment_id=${encodeURIComponent(segmentId)}`,
      )
      .then((r) => setTemplates(r.templates))
      .catch(() => setTemplates([]));
  }, [segmentId, templatesProp]);

  const updateAction = (type: string, patch: Partial<CrmAction>) => {
    onChange(actions.map((a) => (a.type === type ? { ...a, ...patch } : a)));
  };

  const applyTemplate = (templateId: string) => {
    const tpl = templates.find((t) => t.id === templateId);
    if (!tpl) return;
    onChange(
      actions.map((a) => {
        if (a.type === "send_message") {
          return { ...a, enabled: true, text: tpl.message_text };
        }
        if (a.type === "attach_button") {
          return { ...a, enabled: tpl.attach_button };
        }
        if (a.type === "rw_bonus_days" && tpl.suggested_bonus_days) {
          return { ...a, enabled: true, days: tpl.suggested_bonus_days };
        }
        if (a.type === "rw_bonus_traffic" && tpl.suggested_bonus_traffic_gb) {
          return { ...a, enabled: true, gb: tpl.suggested_bonus_traffic_gb };
        }
        return a;
      }),
    );
  };

  const copyVariable = async (key: string) => {
    try {
      await navigator.clipboard.writeText(`{{${key}}}`);
      toast.success(`Copied: {{${key}}}`);
    } catch {
      toast.error("Failed to copy");
    }
  };

  const telegramActions = actionTypes.filter((t) => t.category === "telegram");
  const rwActions = actionTypes.filter((t) => t.category === "remnawave");

  const renderAction = (meta: ActionTypeMeta) => {
    const act = actions.find((a) => a.type === meta.type);
    if (!act) return null;
    const disabled = meta.available === false;

    return (
      <Card key={meta.type} className={cn("mb-2", disabled && "opacity-50")}>
        <CardHeader className="flex-row items-center gap-2 space-y-0 py-2.5">
          <Switch
            checked={act.enabled && !disabled}
            disabled={disabled}
            onCheckedChange={(v: boolean) => updateAction(meta.type, { enabled: v })}
          />
          <span className="text-sm font-medium">{meta.label}</span>
        </CardHeader>
        {act.enabled && (
          <CardContent className="pt-0">
            {meta.type === "send_message" && (
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs text-muted-foreground">
                    HTML, variables {"{{username}}"}
                  </span>
                  <Button size="sm" variant="outline" onClick={() => setVariablesOpen(true)}>
                    <Info className="h-4 w-4" />
                    Variables
                  </Button>
                </div>
                <Textarea
                  rows={4}
                  value={act.text || ""}
                  onChange={(e) => updateAction(meta.type, { text: e.target.value })}
                  placeholder="Hi, {{username}}!"
                />
              </div>
            )}
            {meta.type === "attach_button" && (
              <Select
                value={act.button_type || "open_bot"}
                onValueChange={(v: string) => updateAction(meta.type, { button_type: v })}
              >
                <SelectTrigger className="w-full md:w-[220px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="open_bot">Open bot</SelectItem>
                  <SelectItem value="invite_friends">Invite friends</SelectItem>
                </SelectContent>
              </Select>
            )}
            {meta.type === "rw_bonus_days" && (
              <Input
                type="number"
                className="w-full md:w-[160px]"
                min={1}
                max={365}
                value={act.days ?? 1}
                onChange={(e) => updateAction(meta.type, { days: Number(e.target.value) || 1 })}
              />
            )}
            {meta.type === "rw_bonus_traffic" && (
              <Input
                type="number"
                className="w-full md:w-[160px]"
                min={1}
                max={1000}
                value={act.gb ?? 1}
                onChange={(e) => updateAction(meta.type, { gb: Number(e.target.value) || 1 })}
              />
            )}
            {meta.type === "rw_reset_traffic" && (
              <span className="text-sm text-muted-foreground">
                Resets the used traffic counter in Remnawave
              </span>
            )}
            {meta.type === "rw_set_status" && (
              <span className="text-sm text-muted-foreground">Coming soon</span>
            )}
          </CardContent>
        )}
      </Card>
    );
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">2. Actions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {templates.length > 0 && (
          <Select onValueChange={(v: string) => v && applyTemplate(v)}>
            <SelectTrigger>
              <SelectValue placeholder="Apply template" />
            </SelectTrigger>
            <SelectContent>
              {templates.map((t) => (
                <SelectItem key={t.id} value={t.id}>
                  {t.title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        <Collapsible title="Telegram" defaultOpen>
          {telegramActions.map(renderAction)}
        </Collapsible>
        <Collapsible title="Remnawave" defaultOpen>
          {rwActions.map(renderAction)}
        </Collapsible>
      </CardContent>

      <Dialog open={variablesOpen} onOpenChange={setVariablesOpen}>
        <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-[520px]">
          <DialogHeader>
            <DialogTitle>Variables</DialogTitle>
          </DialogHeader>
          <div className="space-y-1">
            {variables.map((row) => (
              <button
                key={row.key}
                type="button"
                onClick={() => copyVariable(row.key)}
                className="flex w-full flex-col items-start gap-0.5 rounded-md border border-border px-3 py-2 text-left hover:bg-white/5"
              >
                <code className="rounded bg-muted px-1 text-xs">{`{{${row.key}}}`}</code>
                <span className="text-xs text-muted-foreground">{row.label}</span>
              </button>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
