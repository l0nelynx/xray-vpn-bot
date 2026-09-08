import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { Button } from "@xray/ui/components/button";
import { Input } from "@xray/ui/components/input";
import { Textarea } from "@xray/ui/components/textarea";
import { SupportImages } from "@xray/ui/components/support-images";
import { useSupportDraft } from "@xray/ui/hooks/useSupportDraft";
import { useSupportPolling } from "@xray/ui/hooks/useSupportPolling";
import { api, TicketDetail } from "../api/client";
import { useT } from "../i18n/LocaleContext";

type Context = {
  subscriptions: { id: number; label: string }[];
  payments: { id: string; label: string }[];
};
export default function SupportCreatePage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { locale } = useT();
  const ru = locale === "ru";
  const [draft, setDraft] = useSupportDraft("miniapp:new");
  const initial = (() => {
    try {
      return JSON.parse(draft || "{}");
    } catch {
      return {};
    }
  })();
  const requestedCategory = params.get("category") || initial.category;
  const [category, setCategory] = useState(
    ["connection", "speed", "payment", "subscription", "other"].includes(
      requestedCategory,
    )
      ? requestedCategory
      : "connection",
  );
  const [platform, setPlatform] = useState(initial.platform || "");
  const [message, setMessage] = useState(initial.message || "");
  const [subject, setSubject] = useState(initial.subject || "");
  const [subscription, setSubscription] = useState(initial.subscription || "");
  const [payment, setPayment] = useState(initial.payment || "");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data: context } = useSupportPolling<Context>(
    "context",
    () => api.get("/support/context"),
    60000,
  );
  const options = ru
    ? {
        connection: "Подключение",
        speed: "Скорость",
        payment: "Оплата",
        subscription: "Подписка",
        other: "Другое",
      }
    : {
        connection: "Connection",
        speed: "Speed",
        payment: "Payment",
        subscription: "Subscription",
        other: "Other",
      };
  const hints: Record<string, string> = ru
    ? {
        connection:
          "Что происходит при подключении? Какое приложение используете? Приложите скриншот ошибки.",
        speed:
          "На каком устройстве и в какой сети падает скорость? Когда это началось?",
        payment: "Когда вы оплатили подписку? Что произошло после оплаты?",
        subscription: "Что нужно изменить или проверить в подписке?",
        other: "Расскажите, что произошло и какая помощь нужна.",
      }
    : {
        connection:
          "What happens when you connect? Which VPN app do you use? Attach a screenshot of the error.",
        speed: "Which device and network are affected? When did it start?",
        payment: "When did you pay? What happened after payment?",
        subscription: "What would you like us to check or change?",
        other: "Tell us what happened and how we can help.",
      };
  const save = (values: Record<string, string>) =>
    setDraft(
      JSON.stringify({
        category,
        platform,
        message,
        subject,
        subscription,
        payment,
        ...values,
      }),
    );
  const submit = async () => {
    if (busy) return;
    if (!message.trim()) {
      setError(ru ? "Опишите проблему" : "Describe the issue");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("category", category);
      form.append("platform", platform);
      form.append("message", message.trim());
      form.append(
        "subject",
        subject.trim() ||
          `${options[category as keyof typeof options]}${platform ? ` · ${platform}` : ""}`,
      );
      if (subscription) form.append("subscription_id", subscription);
      if (payment) form.append("payment_id", payment);
      files.forEach((f) => form.append("images", f));
      const ticket = await api.postForm<TicketDetail>(
        "/support/tickets/create",
        form,
      );
      setDraft("");
      navigate(`/support/${ticket.id}?created=1`, { replace: true });
    } catch (e) {
      setError(
        ru
          ? `Не удалось отправить обращение. ${(e as Error).message}`
          : (e as Error).message,
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="page">
      <h1 className="text-xl font-bold mb-2">
        {ru ? "Чем помочь?" : "How can we help?"}
      </h1>
      <p className="text-sm text-muted-foreground mb-5">
        {ru
          ? "Выберите тему и расскажите о проблеме."
          : "Choose a topic and tell us what happened."}
      </p>
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <fieldset disabled={busy} className="flex flex-col gap-4">
          <div
            className="flex flex-wrap gap-2"
            role="group"
            aria-label={ru ? "Тема" : "Topic"}
          >
            {Object.entries(options).map(([k, v]) => (
              <Button
                type="button"
                key={k}
                variant={category === k ? "default" : "outline"}
                size="sm"
                onClick={() => {
                  setCategory(k);
                  save({ category: k });
                }}
              >
                {v}
              </Button>
            ))}
          </div>
          {(category === "connection" || category === "speed") && (
            <label className="text-sm">
              {ru ? "Устройство" : "Device"}
              <select
                className="support-form-select"
                value={platform}
                onChange={(e) => {
                  setPlatform(e.target.value);
                  save({ platform: e.target.value });
                }}
              >
                <option value="">
                  {ru ? "Выберите устройство" : "Select a device"}
                </option>
                {[
                  "Android",
                  "iPhone / iPad",
                  "Windows",
                  "macOS",
                  "Linux",
                  "TV / Router",
                ].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
          )}
          {!!context?.subscriptions.length && (
            <label className="text-sm">
              {ru ? "Подписка" : "Subscription"}
              <select
                className="support-form-select"
                value={subscription}
                onChange={(e) => {
                  setSubscription(e.target.value);
                  save({ subscription: e.target.value });
                }}
              >
                <option value="">
                  {ru
                    ? "Не относится к конкретной подписке"
                    : "No specific subscription"}
                </option>
                {context.subscriptions.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
          )}
          {category === "payment" && !!context?.payments.length && (
            <label className="text-sm">
              {ru ? "Платёж" : "Payment"}
              <select
                className="support-form-select"
                value={payment}
                onChange={(e) => {
                  setPayment(e.target.value);
                  save({ payment: e.target.value });
                }}
              >
                <option value="">
                  {ru
                    ? "Выберите платёж (необязательно)"
                    : "Select a payment (optional)"}
                </option>
                {context.payments.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="text-sm">
            {ru ? "Что случилось?" : "What happened?"}
            <Textarea
              className="mt-2"
              rows={5}
              maxLength={4000}
              value={message}
              onChange={(e) => {
                setMessage(e.target.value);
                save({ message: e.target.value });
              }}
              placeholder={hints[category]}
            />
          </label>
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>
              {message ? (ru ? "Черновик сохранён" : "Draft saved") : ""}
            </span>
            <span>{message.length}/4000</span>
          </div>
          <SupportImages
            files={files}
            onChange={setFiles}
            onError={setError}
            label={ru ? "Скриншот" : "Screenshot"}
            disabled={busy}
          />
          <details className="text-sm text-muted-foreground">
            <summary>{ru ? "Уточнить заголовок" : "Customize subject"}</summary>
            <Input
              className="mt-2"
              aria-label={ru ? "Заголовок" : "Subject"}
              maxLength={200}
              value={subject}
              onChange={(e) => {
                setSubject(e.target.value);
                save({ subject: e.target.value });
              }}
            />
          </details>
          <p className="text-xs text-muted-foreground">
            {ru
              ? "Выбранные устройство, подписка и платёж будут видны поддержке. Фотографии нужно выбрать заново после выхода из формы."
              : "Support can see the selected device, subscription and payment. Reselect photos if you leave this form."}
          </p>
          {error && (
            <div role="alert" className="text-sm text-destructive">
              {error}
            </div>
          )}
          <Button type="submit" size="lg" disabled={busy}>
            {busy
              ? ru
                ? "Отправляем…"
                : "Sending…"
              : ru
                ? "Отправить обращение"
                : "Send request"}
          </Button>
          <Button
            variant="outline"
            type="button"
            onClick={() => navigate("/support")}
          >
            {ru ? "Назад" : "Back"}
          </Button>
        </fieldset>
      </form>
    </div>
  );
}
