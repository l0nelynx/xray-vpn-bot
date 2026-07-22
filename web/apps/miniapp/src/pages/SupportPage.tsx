import { Inbox, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { Alert, AlertTitle } from "@xray/ui/components/alert";
import { Button } from "@xray/ui/components/button";
import { Spinner } from "@xray/ui/components/spinner";
import { api, TicketSummary } from "../api/client";
import TicketListItem from "../components/TicketListItem";
import { useT } from "../i18n/LocaleContext";

export default function SupportPage() {
  const navigate = useNavigate();
  const { t } = useT();
  const [tickets, setTickets] = useState<TicketSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<TicketSummary[]>("/support/tickets")
      .then(setTickets)
      .catch((e) => setError(e?.detail || String(e)));
  }, []);

  return (
    <div className="page">
      <div className="text-xl font-bold text-foreground mb-5">
        {t("support.title")}
      </div>

      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertTitle>{error}</AlertTitle>
        </Alert>
      )}

      {tickets === null && !error && (
        <div className="spinner-wrap">
          <Spinner />
        </div>
      )}

      {tickets && tickets.length === 0 && (
        <div className="text-center py-10 text-muted-foreground">
          <Inbox className="w-8 h-8 mx-auto mb-3 opacity-60" />
          <div style={{ whiteSpace: "pre-line" }}>
            {t("support.empty")}
          </div>
        </div>
      )}

      {tickets &&
        tickets.map((ticket) => (
          <TicketListItem
            key={ticket.id}
            ticket={ticket}
            onClick={() => navigate(`/support/${ticket.id}`)}
          />
        ))}

      <Button
        size="icon"
        className="rounded-full fixed right-6 shadow-lg"
        style={{ bottom: 88, width: 52, height: 52 }}
        onClick={() => navigate("/support/new")}
        aria-label={t("support.newAria")}
      >
        <Plus className="w-[22px] h-[22px]" />
      </Button>
    </div>
  );
}
