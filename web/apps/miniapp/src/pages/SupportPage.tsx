import { BookOpen, ChevronRight, Inbox, LifeBuoy, Link2, MessageSquarePlus } from "lucide-react";
import { useState } from "react";
import { useSupportPolling } from "@xray/ui/hooks/useSupportPolling";
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
  const [showClosed, setShowClosed] = useState(false);
  const { data: tickets, error, reload } = useSupportPolling<TicketSummary[]>("support-list", () => api.get("/support/tickets"));

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
        <button className="home-row" onClick={() => navigate("/support/new?category=connection")}>
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
          <AlertTitle>{error}</AlertTitle><Button variant="ghost" onClick={() => void reload()}>{t("support.refresh")}</Button>
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

      {tickets && <div className="flex gap-2 mb-4"><Button size="sm" variant={!showClosed ? "default" : "outline"} onClick={() => setShowClosed(false)}>{t("support.active")} ({tickets.filter(t => t.status !== "closed").length})</Button><Button size="sm" variant={showClosed ? "default" : "outline"} onClick={() => setShowClosed(true)}>{t("support.archive")} ({tickets.filter(t => t.status === "closed").length})</Button></div>}
      {tickets &&
        tickets.filter(ticket => showClosed ? ticket.status === "closed" : ticket.status !== "closed").map((ticket) => (
          <TicketListItem
            key={ticket.id}
            ticket={ticket}
            onClick={() => navigate(`/support/${ticket.id}`)}
          />
        ))}

    </div>
  );
}
