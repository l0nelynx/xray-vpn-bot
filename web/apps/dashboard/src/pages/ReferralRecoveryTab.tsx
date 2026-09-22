import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@xray/ui/components/card";
import { Button } from "@xray/ui/components/button";
import { Checkbox } from "@xray/ui/components/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@xray/ui/components/table";
import ConfirmButton from "../components/ConfirmButton";
import { api } from "../api/client";

interface RecoveryRow {
  user_id: number; tg_id: number | null; username: string | null; promo_code: string;
  expected: number; automatic: number; paid: number; admin_grants: number;
  manual: number; spent: number; balance: number; missing: number; bonus: number; total: number;
  warnings: string[];
}
interface Snapshot {
  id: string;
  adjustments: Record<string, number>;
  plan: {
    rows: RecoveryRow[]; issues: { transaction_id: string; reason: string }[];
    rate: number; cap: number; purchases_checked: number; recipients: number;
    missing: number; bonus: number; total: number; manual: number;
  };
}
interface Report {
  status: string; snapshot: Snapshot | null;
  messages: Record<string, number>;
  message_details: { user_id: number; tg_id: number | null; status: string; error: string | null }[];
}
const endpoint = "/tg-admin/referral-recovery";
const number = (n: number) => n.toLocaleString("ru-RU");
const statuses: Record<string, string> = {
  sent: "Принято Telegram", pending: "В очереди", sending: "Отправляется",
  failed: "Отклонено Telegram", unknown: "Результат неизвестен", unavailable: "Нет Telegram ID",
};

export default function ReferralRecoveryTab() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [adjustments, setAdjustments] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [reviewed, setReviewed] = useState(false);
  const [error, setError] = useState("");
  const executed = report?.status === "executed";

  useEffect(() => {
    let active = true;
    let first = true;
    const refresh = async () => {
      try {
        const result = await api.get<Report>(endpoint);
        if (!active) return;
        setReport(result);
        if (first || result.status === "executed") {
          setSnapshot(result.snapshot);
          setAdjustments(result.snapshot?.adjustments ?? {});
        }
        first = false;
      } catch {
        if (active) setError("Не удалось загрузить отчёт. Обновите страницу для проверки результата.");
      }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  async function scan() {
    setBusy(true); setError(""); setReviewed(false);
    try {
      setSnapshot(await api.post<Snapshot>(`${endpoint}/preview`, { manual_adjustments: adjustments }));
      setDirty(false);
    } catch {
      setDirty(true);
      setError("Расчёт не выполнен. Проверьте суммы ручной компенсации: от 0 до разницы между положенным и уже начисленным.");
    } finally { setBusy(false); }
  }

  async function execute() {
    if (!snapshot || !reviewed || dirty) return;
    setBusy(true); setError("");
    try {
      await api.post(`${endpoint}/execute`, { preview_id: snapshot.id, reviewed });
      setReport(await api.get<Report>(endpoint));
      toast.success("Баллы начислены. Сообщения поставлены в очередь.");
    } catch {
      // A timeout may happen after commit. Fetch persisted state before
      // suggesting another attempt; the server also guards repeated requests.
      try {
        const latest = await api.get<Report>(endpoint);
        setReport(latest);
        if (latest.status === "executed") { setSnapshot(latest.snapshot); return; }
      } catch { /* The durable report can be loaded again after reconnect. */ }
      setDirty(true); setReviewed(false);
      setError("Выдача не подтверждена. Возможно, данные изменились после расчёта. Обновите отчёт и пересчитайте перед повтором.");
    } finally { setBusy(false); }
  }

  async function retryMessages() {
    setBusy(true);
    try {
      await api.post(`${endpoint}/retry-messages`, {});
      setReport(await api.get<Report>(endpoint));
    } catch { setError("Не удалось повторить отправку."); }
    finally { setBusy(false); }
  }

  const plan = snapshot?.plan;
  return <Card>
    <CardHeader><CardTitle>Восстановление реферальных наград</CardTitle></CardHeader>
    <CardContent className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Однократная сверка завершённых покупок, включая оплату баллами. Из положенной награды вычитаются
        уже начисленные награды и подтверждённая ручная компенсация. К остатку добавляется 10% с округлением вверх каждому получателю.
      </p>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {!executed && <Button onClick={scan} disabled={busy || !report || report.status === "uninitialized"} variant="outline">
        {busy ? "Подождите…" : "Рассчитать пропущенные награды"}
      </Button>}
      {report?.status === "uninitialized" && <p role="alert">Сначала примените миграции базы данных.</p>}
      {plan && <>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {[
            ["Покупок проверено", plan.purchases_checked],
            ["Получателей доплаты", plan.recipients],
            ["Пропущенные баллы", plan.missing], ["Компенсация 10%", plan.bonus],
            [executed ? "Всего начислено баллов" : "Всего к выдаче", plan.total],
            ["Зачтено вручную", plan.manual],
          ].map(([label, value]) => <div key={label}>
            <div className="text-xs text-muted-foreground">{label}</div>
            <div className="text-xl font-semibold">{number(Number(value))}</div>
          </div>)}
        </div>
        <p className="text-sm">Расчёт по текущим настройкам: {number(plan.rate)} баллов за каждые 30 дней,
          лимит {number(plan.cap)} на промокод. История изменений ставки не хранится.</p>
        {!executed && <p className="text-sm text-muted-foreground">В графе «Зачесть вручную» предложены положительные начисления администратора.
          Если среди них были другие подарки, уменьшите сумму и пересчитайте. Расходы и текущий баланс показаны для сверки и повторно не вычитаются.</p>}
        {executed && <p className="text-sm text-muted-foreground">Таблица сохраняет утверждённые значения до начисления.</p>}
        <div className="max-h-96 overflow-auto rounded-lg border border-border">
          <Table>
            <TableHeader><TableRow>
              {["Получатель", "Положено", "Учтено наград", "Выдано админом", "Зачесть вручную", "Потрачено", "Баланс", "Не выдано", "+10%", "Итого"].map(h => <TableHead key={h}>{h}</TableHead>)}
            </TableRow></TableHeader>
            <TableBody>{plan.rows.map(row => <TableRow key={row.promo_code}>
              <TableCell>
                <div>{row.username || row.tg_id || `User ${row.user_id}`}</div>
                <div className="text-xs text-muted-foreground">{row.tg_id ?? "Нет Telegram"} · {row.promo_code}</div>
                {row.warnings.map(w => <div key={w} className="max-w-64 text-xs text-amber-600">{w}</div>)}
              </TableCell>
              <TableCell>{number(row.expected)}</TableCell><TableCell>{number(row.paid)}</TableCell>
              <TableCell>{number(row.admin_grants)}</TableCell>
              <TableCell><input type="number" min={0} max={Math.max(0, row.expected - row.paid)} step={1}
                aria-label={`Ручная компенсация ${row.user_id}`} disabled={busy || executed}
                className="w-24 rounded border border-border bg-background p-2"
                value={adjustments[String(row.user_id)] ?? row.manual}
                onChange={e => { setAdjustments({ ...adjustments, [String(row.user_id)]: Number(e.target.value) }); setDirty(true); setReviewed(false); }} /></TableCell>
              <TableCell>{number(row.spent)}</TableCell><TableCell>{number(row.balance)}</TableCell>
              <TableCell>{number(row.missing)}</TableCell><TableCell>{number(row.bonus)}</TableCell><TableCell>{number(row.total)}</TableCell>
            </TableRow>)}</TableBody>
          </Table>
        </div>
        {plan.issues.length > 0 && <div role="alert" className="text-sm text-destructive">
          Выдача заблокирована: {plan.issues.length} покупок требуют проверки исходных данных.
          <ul>{plan.issues.map(i => <li key={i.transaction_id}>{i.transaction_id}: {i.reason}</li>)}</ul>
        </div>}
        {!executed && <>
          {dirty && <p className="text-sm text-amber-600">Пересчитайте суммы перед подтверждением.</p>}
          <label className="flex items-start gap-2 text-sm"><Checkbox checked={reviewed}
            disabled={dirty || busy} onCheckedChange={(v: boolean | "indeterminate") => setReviewed(v === true)} />
            Проверил ставку, лимит, расхождения и ручные начисления. Подтверждаю расчёт по текущим настройкам и отправку извинений получателям доплаты.
          </label>
          <ConfirmButton title="Начислить пропущенные награды и отправить извинения?"
            description={`${plan.recipients} получателей. Награды: ${number(plan.missing)}, бонус: ${number(plan.bonus)}, всего: ${number(plan.total)} баллов. Операция выполняется один раз.`}
            confirmText="Начислить и отправить" cancelText="Отмена" onConfirm={execute}>
            <Button disabled={!reviewed || dirty || busy || plan.issues.length > 0 || !plan.rows.length}>Подтвердить выдачу</Button>
          </ConfirmButton>
          <details className="text-sm"><summary>Текст сообщения получателю</summary>
            <p className="mt-2">Мы восстановили ваши реферальные баллы. Из-за ошибки часть наград за покупки приглашённых вами пользователей не начислилась вовремя.
              Извините за задержку — мы исправили ошибку. В сообщении будут указаны пропущенная сумма, компенсация +10% и общая сумма пополнения.</p>
          </details>
        </>}
      </>}
      {executed && report && <div className="space-y-3">
        <p className="font-medium">Начисление завершено и сохранено. Повторная выдача заблокирована.</p>
        <p className="text-sm">Статусы обновляются каждые 5 секунд. «Принято Telegram» означает успешную отправку, а не прочтение.</p>
        <div className="flex flex-wrap gap-4">{Object.entries(statuses).map(([key, label]) =>
          <span key={key}>{label}: <b>{report.messages[key] ?? 0}</b></span>)}</div>
        {!!report.messages.failed && <Button disabled={busy} variant="outline" onClick={retryMessages}>Повторить отклонённые сообщения</Button>}
        {!!report.messages.unknown && <p className="text-sm text-amber-600">Для сообщений с неизвестным результатом автоматический повтор отключён, чтобы не отправлять дубликаты. Нужна ручная проверка.</p>}
        <ul className="text-sm">{report.message_details.filter(n => ["failed", "unknown", "unavailable"].includes(n.status)).map(n =>
          <li key={n.user_id}>{n.tg_id ?? `User ${n.user_id}`}: {statuses[n.status]} {n.error && `— ${n.error}`}</li>)}</ul>
      </div>}
    </CardContent>
  </Card>;
}
