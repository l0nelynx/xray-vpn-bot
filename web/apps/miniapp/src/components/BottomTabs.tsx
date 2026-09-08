import { CircleHelp, Home, Link2, ShoppingBag } from "lucide-react";
import { useLocation, useNavigate } from "react-router";
import { api, TicketSummary } from "../api/client";
import { useSupportPolling } from "@xray/ui/hooks/useSupportPolling";
import { useEffect } from "react";
import { useT } from "../i18n/LocaleContext";

const TABS = [
  { path: "/", icon: <Home />, labelKey: "tabs.home" },
  { path: "/connect", icon: <Link2 />, labelKey: "tabs.connect" },
  { path: "/buy", icon: <ShoppingBag />, labelKey: "tabs.buy" },
  { path: "/support", icon: <CircleHelp />, labelKey: "tabs.help" },
] as const;

export default function BottomTabs() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { t } = useT();
  const { data: tickets, reload } = useSupportPolling<TicketSummary[]>("support-badge", () => api.get("/support/tickets"), 15000);
  const unread = tickets?.filter(ticket => ticket.unread).length || 0;
  useEffect(() => { const update = () => { void reload(); }; window.addEventListener("support-read", update); return () => window.removeEventListener("support-read", update); }, [reload]);

  const isActive = (path: string) => {
    if (path === "/") return pathname === "/";
    return pathname.startsWith(path);
  };

  return (
    <nav className="bottom-tabs">
      {TABS.map((tab) => (
        <button
          key={tab.path}
          className={isActive(tab.path) ? "active" : ""}
          onClick={() => navigate(tab.path)}
        >
          <span className="icon">{tab.icon}</span>
          <span className="label">{t(tab.labelKey)}{tab.path === "/support" && unread > 0 && <strong className="ml-1" aria-label={t("support.newReply")}>({unread})</strong>}</span>
        </button>
      ))}
    </nav>
  );
}
