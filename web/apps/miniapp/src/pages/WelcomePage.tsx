import { Rocket } from "lucide-react";
import { Button } from "@xray/ui/components/button";
import { LinksInfo } from "../api/client";
import { useT } from "../i18n/LocaleContext";
import { openTelegramLink } from "../tg/webapp";

interface Props {
  links: LinksInfo;
}

function botStartUrl(botUrl: string): string {
  if (!botUrl) return "";

  const url = new URL(botUrl);
  url.searchParams.set("start", "");
  return url.toString();
}

export default function WelcomePage({ links }: Props) {
  const { t } = useT();
  return (
    <div className="page page-centered">
      <div style={{ textAlign: "center", maxWidth: 320 }}>
        <Rocket style={{ width: 56, height: 56, color: "#52C41A", margin: "0 auto 20px" }} />
        <div style={{ fontSize: 20, fontWeight: 700, color: "#FFFFFF", marginBottom: 10 }}>
          {t("welcome.title")}
        </div>
        <p style={{ color: "rgba(255,255,255,0.52)", marginBottom: 24, lineHeight: 1.5 }}>
          {t("welcome.body")}
        </p>
        <Button
          size="lg"
          className="w-full"
          onClick={() => openTelegramLink(botStartUrl(links.bot_url))}
        >
          {t("welcome.cta")}
        </Button>
      </div>
    </div>
  );
}
