import { BookOpen, ChevronRight, Inbox, LifeBuoy, Link2, MessageSquarePlus } from "lucide-react";
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
        {t("support.helpTitle")}
      </div>

      <div className="help-actions">
        <button className="home-row" onClick={() => navigate("/connect?source=help")}>
          <span className="home-row__icon"><Link2 /></span><span><strong>{t("support.connectGuide")}</strong><small>{t("support.connectGuideBody")}</small></span><ChevronRight />
        </button>
        <button className="home-row" onClick={() => navigate("/onboarding?replay=1")}>
          <span className="home-row__icon"><BookOpen /></span><span><strong>{t("support.replayOnboarding")}</strong><small>{t("support.replayOnboardingBody")}</small></span><ChevronRight />
        </button>
        <button className="home-row" onClick={() => navigate("/support/new")}>
          <span className="home-row__icon"><LifeBuoy /></span><span><strong>{t("support.problem")}</strong><small>{t("support.problemBody")}</small></span><ChevronRight />
        </button>
      </div>

      <div className="support-tickets-header">
        <div className="section-label">{t("support.ticketsTitle")}</div>
        <Button size="sm" variant="outline" onClick={() => navigate("/support/new")}>
          <MessageSquarePlus />
          {t("support.newTicket")}
        </Button>
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

    </div>
  );
}
