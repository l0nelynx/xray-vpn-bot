import { useState } from "react";
import { toast } from "sonner";
import { ScanLine, Send, Trash2, Ban } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@xray/ui/components/card";
import { Button } from "@xray/ui/components/button";
import { Textarea } from "@xray/ui/components/textarea";
import { Checkbox } from "@xray/ui/components/checkbox";
import { Badge } from "@xray/ui/components/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@xray/ui/components/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@xray/ui/components/table";
import { api } from "../api/client";
import ConfirmButton from "../components/ConfirmButton";

interface ScanUser {
  tg_id: number;
  username: string | null;
  rw_id?: number;
}

interface ScanResult {
  total_checked: number;
  to_disable?: ScanUser[];
  to_delete?: ScanUser[];
  errors: number;
}

interface ExecuteResult {
  disabled?: number;
  deleted?: number;
  notified: number;
  errors: number;
}

function ChannelPostTab() {
  const [text, setText] = useState("");
  const [attachButton, setAttachButton] = useState(true);
  const [loading, setLoading] = useState(false);

  const send = async () => {
    if (!text.trim()) {
      toast.warning("Введите текст поста");
      return;
    }
    setLoading(true);
    try {
      await api.post("/tg-admin/channel-post", { text, attach_button: attachButton });
      toast.success("Пост опубликован в канале");
      setText("");
    } catch {
      toast.error("Ошибка публикации в канале");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="max-w-[700px]">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Пост в канал</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Textarea
          rows={6}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Текст поста (HTML-разметка поддерживается)"
        />
        <label className="flex items-center gap-2 text-sm">
          <Checkbox
            checked={attachButton}
            onCheckedChange={(c: boolean | "indeterminate") => setAttachButton(c === true)}
          />
          Прикрепить кнопку «Открыть бота»
        </label>
        <ConfirmButton title="Опубликовать пост?" confirmText="Опубликовать" onConfirm={send}>
          <Button disabled={loading}>
            <Send className="h-4 w-4" />
            Опубликовать
          </Button>
        </ConfirmButton>
      </CardContent>
    </Card>
  );
}

interface CleanTabProps {
  title: string;
  scanEndpoint: string;
  executeEndpoint: string;
  listKey: "to_disable" | "to_delete";
  executeKey: "tg_ids" | "usernames";
  executeLabel: string;
  executeIcon: React.ReactNode;
  executeConfirm: string;
}

function CleanTab({
  title,
  scanEndpoint,
  executeEndpoint,
  listKey,
  executeKey,
  executeLabel,
  executeIcon,
  executeConfirm,
}: CleanTabProps) {
  const [scanning, setScanning] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [execResult, setExecResult] = useState<ExecuteResult | null>(null);

  const scan = async () => {
    setScanning(true);
    setScanResult(null);
    setExecResult(null);
    try {
      const res = await api.post<ScanResult>(scanEndpoint, {});
      setScanResult(res);
    } catch {
      toast.error("Ошибка сканирования");
    } finally {
      setScanning(false);
    }
  };

  const execute = async () => {
    if (!scanResult) return;
    const users = scanResult[listKey] ?? [];
    if (!users.length) return;

    const payload =
      executeKey === "tg_ids"
        ? { tg_ids: users.map((u) => u.tg_id) }
        : { usernames: users.map((u) => u.username).filter(Boolean) };

    setExecuting(true);
    try {
      const res = await api.post<ExecuteResult>(executeEndpoint, payload);
      setExecResult(res);
      setScanResult(null);
      toast.success("Операция завершена");
    } catch {
      toast.error("Ошибка выполнения");
    } finally {
      setExecuting(false);
    }
  };

  const users = scanResult?.[listKey] ?? [];

  const stat = (label: string, value: React.ReactNode) => (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="font-medium text-foreground/85">{value}</div>
    </div>
  );

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" disabled={scanning} onClick={scan}>
              <ScanLine className="h-4 w-4" />
              Сканировать
            </Button>
            {scanResult && users.length > 0 && (
              <ConfirmButton
                title={executeConfirm}
                description={`Пользователей: ${users.length}`}
                destructive
                confirmText="Выполнить"
                onConfirm={execute}
              >
                <Button variant="destructive" disabled={executing}>
                  {executeIcon}
                  {executeLabel} ({users.length})
                </Button>
              </ConfirmButton>
            )}
          </div>

          {scanResult && (
            <div className="mt-4">
              <div className="mb-3 flex flex-wrap gap-6">
                {stat("Проверено", scanResult.total_checked)}
                {stat(
                  "К обработке",
                  <Badge variant={users.length > 0 ? "warning" : "success"}>{users.length}</Badge>,
                )}
                {stat(
                  "Ошибок",
                  <Badge variant={scanResult.errors > 0 ? "destructive" : "outline"}>
                    {scanResult.errors}
                  </Badge>,
                )}
              </div>
              {users.length > 0 ? (
                <div className="max-h-72 overflow-auto rounded-lg border border-border">
                  <Table>
                    <TableHeader>
                      <TableRow className="hover:bg-transparent">
                        <TableHead>TG ID</TableHead>
                        <TableHead>Username</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {users.map((u) => (
                        <TableRow key={u.tg_id}>
                          <TableCell>{u.tg_id}</TableCell>
                          <TableCell>{u.username ?? "—"}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <span className="text-muted-foreground">Неподписанных пользователей не найдено.</span>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {execResult && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Результат</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-6">
              {execResult.disabled !== undefined && stat("Отключено", execResult.disabled)}
              {execResult.deleted !== undefined && stat("Удалено", execResult.deleted)}
              {stat("Уведомлено", execResult.notified)}
              {stat(
                "Ошибок",
                <Badge variant={execResult.errors > 0 ? "destructive" : "outline"}>
                  {execResult.errors}
                </Badge>,
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function TgAdminPage() {
  return (
    <div>
      <h1 className="mb-5 text-lg font-semibold text-foreground md:text-xl">TG Admin</h1>
      <Tabs defaultValue="channel">
        <TabsList className="mb-4 flex-wrap">
          <TabsTrigger value="channel">Пост в канал</TabsTrigger>
          <TabsTrigger value="subclean">FREE Sub Check</TabsTrigger>
          <TabsTrigger value="telemt">Telemt Clean</TabsTrigger>
        </TabsList>
        <TabsContent value="channel">
          <ChannelPostTab />
        </TabsContent>
        <TabsContent value="subclean">
          <CleanTab
            title="FREE users sub check — пользователи без подписки на канал"
            scanEndpoint="/tg-admin/sub-clean/scan"
            executeEndpoint="/tg-admin/sub-clean/execute"
            listKey="to_disable"
            executeKey="tg_ids"
            executeLabel="Отключить"
            executeIcon={<Ban className="h-4 w-4" />}
            executeConfirm="Отключить выбранных пользователей в RemnaWave и отправить уведомления?"
          />
        </TabsContent>
        <TabsContent value="telemt">
          <CleanTab
            title="Telemt Clean — удаление пользователей без подписки на канал"
            scanEndpoint="/tg-admin/telemt-clean/scan"
            executeEndpoint="/tg-admin/telemt-clean/execute"
            listKey="to_delete"
            executeKey="usernames"
            executeLabel="Удалить из Telemt"
            executeIcon={<Trash2 className="h-4 w-4" />}
            executeConfirm="Удалить выбранных пользователей из Telemt и отправить уведомления?"
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
