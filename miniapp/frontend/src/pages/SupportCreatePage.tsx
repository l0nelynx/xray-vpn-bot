import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, TicketDetail } from "../api/client";

export default function SupportCreatePage() {
  const navigate = useNavigate();
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null);
    if (subject.trim().length < 1 || subject.trim().length > 200) {
      setError("Тема должна быть от 1 до 200 символов");
      return;
    }
    if (message.trim().length < 1 || message.trim().length > 4000) {
      setError("Сообщение должно быть от 1 до 4000 символов");
      return;
    }
    setSubmitting(true);
    try {
      const t = await api.post<TicketDetail>("/support/tickets", {
        subject: subject.trim(),
        message: message.trim(),
      });
      navigate(`/support/${t.id}`, { replace: true });
    } catch (e: any) {
      setError(e?.detail || String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page">
      <div className="page-title">Новое обращение</div>

      {error && <div className="error-banner">{error}</div>}

      <input
        className="input"
        placeholder="Тема"
        value={subject}
        maxLength={200}
        onChange={(e) => setSubject(e.target.value)}
      />
      <textarea
        className="textarea"
        placeholder="Опишите проблему"
        value={message}
        maxLength={4000}
        onChange={(e) => setMessage(e.target.value)}
      />

      <button className="btn" disabled={submitting} onClick={submit}>
        {submitting ? "Отправка…" : "Отправить"}
      </button>
      <button className="btn secondary" onClick={() => navigate(-1)}>
        Отмена
      </button>
    </div>
  );
}
