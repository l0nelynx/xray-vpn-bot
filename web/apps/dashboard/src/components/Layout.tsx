import { useState, useEffect, useMemo } from "react";
import { Outlet, useNavigate, useLocation } from "react-router";
import {
  LayoutDashboard,
  Users,
  ArrowRightLeft,
  BarChart3,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  Menu as MenuIcon,
  ShoppingCart,
  LayoutGrid,
  Users2,
  Server,
  Store,
  MessageSquare,
  Smartphone,
  Gift,
  Headphones,
  Bot,
  Bell,
  Download,
  Trophy,
  ChevronDown,
  type LucideIcon,
} from "lucide-react";
import { Button } from "@xray/ui/components/button";
import { Sheet, SheetContent } from "@xray/ui/components/sheet";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@xray/ui/components/alert-dialog";
import { cn } from "@xray/ui/lib/utils";
import { api, clearToken } from "../api/client";
import useIsMobile from "../hooks/useIsMobile";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

const PAGE_TITLES: Record<string, string> = {
  "/": "Dashboard",
  "/users": "Users",
  "/transactions": "Transactions",
  "/stats": "Statistics",
  "/tariffs": "Tariffs",
  "/menus": "Bot Menus",
  "/squads": "Squads",
  "/telemt": "Telemt",
  "/store": "Store",
  "/support": "Support",
  "/promocodes": "Promocodes",
  "/giveaways": "Giveaways",
  "/webapp/tariffs": "Tariff Constructor",
  "/webapp/settings": "Settings",
  "/tg-admin": "TG Admin",
  "/crm": "CRM",
  "/push": "Push",
};

interface NavLeaf {
  key: string;
  label: string;
  icon?: LucideIcon;
}
interface NavGroup {
  label: string;
  children: NavLeaf[];
  /** collapsible submenu key (single expandable parent) */
  submenu?: { key: string; label: string; icon: LucideIcon };
}

function buildMenuGroups(legacyEnabled: boolean): NavGroup[] {
  const groups: NavGroup[] = [
    {
      label: "Overview",
      children: [
        { key: "/", icon: LayoutDashboard, label: "Dashboard" },
        { key: "/users", icon: Users, label: "Users" },
        { key: "/transactions", icon: ArrowRightLeft, label: "Transactions" },
        { key: "/stats", icon: BarChart3, label: "Statistics" },
      ],
    },
  ];

  if (legacyEnabled) {
    groups.push({
      label: "Bot Constructor",
      children: [
        { key: "/tariffs", icon: ShoppingCart, label: "Tariffs" },
        { key: "/menus", icon: LayoutGrid, label: "Bot Menus" },
        { key: "/squads", icon: Users2, label: "Squads" },
      ],
    });
  }

  groups.push({
    label: "Services",
    children: [
      { key: "/telemt", icon: Server, label: "Telemt" },
      { key: "/store", icon: Store, label: "Store" },
      { key: "/support", icon: MessageSquare, label: "Support" },
      { key: "/promocodes", icon: Gift, label: "Promocodes" },
      { key: "/giveaways", icon: Trophy, label: "Giveaways" },
      { key: "/crm", icon: Headphones, label: "CRM" },
      { key: "/push", icon: Bell, label: "Push" },
      { key: "/tg-admin", icon: Bot, label: "TG Admin" },
    ],
  });

  groups.push({
    label: "WebApp",
    submenu: { key: "webapp", label: "WebApp", icon: Smartphone },
    children: [
      { key: "/webapp/tariffs", label: "Tariff Constructor" },
      { key: "/webapp/settings", label: "Settings" },
    ],
  });

  return groups;
}

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [legacyEnabled, setLegacyEnabled] = useState<boolean>(true);
  const [installPrompt, setInstallPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const isMobile = useIsMobile();

  useEffect(() => {
    api
      .get<{ legacy_bot_constructor: boolean }>("/settings/features")
      .then((r) => setLegacyEnabled(r.legacy_bot_constructor))
      .catch(() => setLegacyEnabled(true));
  }, []);

  useEffect(() => {
    const onBeforeInstall = (e: Event) => {
      e.preventDefault();
      setInstallPrompt(e as BeforeInstallPromptEvent);
    };
    const onInstalled = () => setInstallPrompt(null);
    window.addEventListener("beforeinstallprompt", onBeforeInstall);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstall);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  const handleInstall = async () => {
    if (!installPrompt) return;
    await installPrompt.prompt();
    await installPrompt.userChoice;
    setInstallPrompt(null);
  };

  const groups = useMemo(() => buildMenuGroups(legacyEnabled), [legacyEnabled]);

  const [webappOpen, setWebappOpen] = useState<boolean>(() =>
    location.pathname.startsWith("/webapp"),
  );

  useEffect(() => {
    if (location.pathname.startsWith("/webapp")) setWebappOpen(true);
  }, [location.pathname]);

  const handleLogout = () => {
    clearToken();
    navigate("/login");
  };

  const go = (key: string) => {
    navigate(key);
    if (isMobile) setMobileMenuOpen(false);
  };

  const pageTitle = PAGE_TITLES[location.pathname] ?? "Dashboard";
  const showLabels = !collapsed || isMobile;

  const navBtnClass = (active: boolean) =>
    cn(
      "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
      active
        ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-sm"
        : "text-sidebar-foreground/75 hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
      !showLabels && "justify-center px-0",
    );

  const sidebarContent = (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex h-16 flex-shrink-0 items-center gap-3 border-b border-sidebar-border px-4">
        <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-primary text-xs font-semibold text-primary-foreground">
          VP
        </div>
        {showLabels && (
          <span className="truncate text-sm font-semibold tracking-tight">VPN Admin</span>
        )}
      </div>

      <nav className="flex-1 space-y-6 overflow-auto px-3 py-4">
        {groups.map((group) => (
          <div key={group.label} className="space-y-1.5">
            {showLabels && (
              <div className="px-3 pb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                {group.label}
              </div>
            )}
            <div className="space-y-1">
              {group.submenu ? (
                <>
                  <button
                    type="button"
                    onClick={() => setWebappOpen((v) => !v)}
                    className={navBtnClass(location.pathname.startsWith("/webapp"))}
                  >
                    <group.submenu.icon className="h-4 w-4 flex-shrink-0" />
                    {showLabels && (
                      <>
                        <span className="flex-1 text-left">{group.submenu.label}</span>
                        <ChevronDown
                          className={cn("h-4 w-4 transition-transform", webappOpen && "rotate-180")}
                        />
                      </>
                    )}
                  </button>
                  {webappOpen &&
                    showLabels &&
                    group.children.map((item) => (
                      <button
                        key={item.key}
                        type="button"
                        onClick={() => go(item.key)}
                        className={cn(navBtnClass(location.pathname === item.key), "pl-10")}
                      >
                        <span className="text-left">{item.label}</span>
                      </button>
                    ))}
                </>
              ) : (
                group.children.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => go(item.key)}
                    className={navBtnClass(location.pathname === item.key)}
                    title={!showLabels ? item.label : undefined}
                  >
                    {item.icon && <item.icon className="h-4 w-4 flex-shrink-0" />}
                    {showLabels && <span className="text-left">{item.label}</span>}
                  </button>
                ))
              )}
            </div>
          </div>
        ))}
      </nav>

      <div className="flex flex-shrink-0 flex-col gap-2 border-t border-sidebar-border p-3">
        {installPrompt && (
          <Button
            variant="outline"
            onClick={handleInstall}
            aria-label="Install app"
            className={cn("w-full justify-start", !showLabels && "justify-center px-0")}
          >
            <Download className="h-4 w-4" />
            {showLabels && "Install app"}
          </Button>
        )}
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button
              variant="outline"
              aria-label="Logout"
              className={cn(
                "w-full justify-start text-muted-foreground",
                !showLabels && "justify-center px-0",
              )}
            >
              <LogOut className="h-4 w-4" />
              {showLabels && "Logout"}
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Log out?</AlertDialogTitle>
              <AlertDialogDescription>You will need to sign in again.</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={handleLogout}>Logout</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen bg-background">
      {!isMobile && (
        <aside
          className="sticky top-0 h-screen flex-shrink-0 overflow-hidden border-r border-sidebar-border transition-all"
          style={{ width: collapsed ? 68 : 260 }}
        >
          {sidebarContent}
        </aside>
      )}

      {isMobile && (
        <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
          <SheetContent side="left" className="w-72 border-sidebar-border bg-sidebar p-0">
            {sidebarContent}
          </SheetContent>
        </Sheet>
      )}

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="sticky top-0 z-10 flex h-16 flex-shrink-0 items-center border-b border-border bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60 md:px-8">
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="icon"
              className="h-9 w-9"
              aria-label={
                isMobile ? "Open navigation menu" : collapsed ? "Expand sidebar" : "Collapse sidebar"
              }
              onClick={isMobile ? () => setMobileMenuOpen(true) : () => setCollapsed(!collapsed)}
            >
              {isMobile ? (
                <MenuIcon className="h-4 w-4" />
              ) : collapsed ? (
                <PanelLeftOpen className="h-4 w-4" />
              ) : (
                <PanelLeftClose className="h-4 w-4" />
              )}
            </Button>
            <h1 className="text-base font-semibold tracking-tight">{pageTitle}</h1>
          </div>
        </header>

        <main className="min-h-[calc(100vh-4rem)] overflow-auto p-4 md:p-8">
          <div className="mx-auto w-full max-w-[1600px]">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
