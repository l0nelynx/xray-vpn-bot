import { ArrowLeft } from "lucide-react";
import { ReactNode } from "react";
import { useNavigate } from "react-router";
import { Button } from "@xray/ui/components/button";
import { useT } from "../i18n/LocaleContext";

interface Props {
  title: string;
  children: ReactNode;
}

export default function LegalLayout({ title, children }: Props) {
  const navigate = useNavigate();
  const { t } = useT();
  return (
    <div className="page legal-page">
      <Button variant="ghost" onClick={() => navigate(-1)} style={{ marginBottom: 12 }}>
        <ArrowLeft />
        {t("legal.back")}
      </Button>

      <h1 className="legal-title">{title}</h1>

      <div className="legal-content">{children}</div>
    </div>
  );
}
