import { useState } from "react";
import { useNavigate } from "react-router";
import { Alert, AlertTitle } from "@xray/ui/components/alert";
import { Button } from "@xray/ui/components/button";
import { Input } from "@xray/ui/components/input";
import { Label } from "@xray/ui/components/label";
import { Textarea } from "@xray/ui/components/textarea";
import { api, TicketDetail } from "../api/client";
import { useT } from "../i18n/LocaleContext";

const SUBJECT_MAX = 200;
const MESSAGE_MAX = 4000;

export default function SupportCreatePage() {
  const navigate = useNavigate();
  const { t } = useT();
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const submit = async () => {
    const trimmedSubject = subject.trim();
    const trimmedMessage = message.trim();
    if (!trimmedSubject) {
      setFormError(t("supportCreate.error.subject"));
      return;
    }
    if (!trimmedMessage) {
      setFormError(t("supportCreate.error.message"));
      return;
    }
    setFormError(null);
    setError(null);
    setSubmitting(true);
    try {
      const ticket = await api.post<TicketDetail>("/support/tickets", {
        subject: trimmedSubject,
        message: trimmedMessage,
      });
      navigate(`/support/${ticket.id}`, { replace: true });
    } catch (e: any) {
      setError(e?.detail || String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page">
      <div className="text-xl font-bold text-foreground mb-5">
        {t("supportCreate.title")}
      </div>

      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertTitle>{error}</AlertTitle>
        </Alert>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="flex flex-col gap-4"
      >
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="subject">{t("supportCreate.subjectLabel")}</Label>
          <Input
            id="subject"
            placeholder={t("supportCreate.subjectPlaceholder")}
            value={subject}
            onChange={(e) => setSubject(e.target.value.slice(0, SUBJECT_MAX))}
            maxLength={SUBJECT_MAX}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="message">{t("supportCreate.messageLabel")}</Label>
          <Textarea
            id="message"
            placeholder={t("supportCreate.messagePlaceholder")}
            rows={6}
            value={message}
            onChange={(e) => setMessage(e.target.value.slice(0, MESSAGE_MAX))}
            maxLength={MESSAGE_MAX}
          />
          <span className="text-xs text-muted-foreground text-right">
            {message.length}/{MESSAGE_MAX}
          </span>
        </div>

        {formError && <span className="text-destructive text-[13px]">{formError}</span>}

        <div className="flex flex-col gap-3 w-full">
          <Button size="lg" className="w-full" type="submit" disabled={submitting}>
            {submitting ? t("supportCreate.submitting") : t("supportCreate.submit")}
          </Button>
          <Button size="lg" variant="outline" className="w-full" type="button" onClick={() => navigate(-1)}>
            {t("supportCreate.cancel")}
          </Button>
        </div>
      </form>
    </div>
  );
}
