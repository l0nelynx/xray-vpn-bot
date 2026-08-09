import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router";
import { Button } from "@xray/ui/components/button";
import { useT } from "../i18n/LocaleContext";

export default function StackPageHeader({
  title,
  backTo,
  action,
}: {
  title: string;
  backTo?: string;
  action?: ReactNode;
}) {
  const navigate = useNavigate();
  const { t } = useT();

  return (
    <header className="stack-page-header">
      <Button
        size="icon"
        variant="ghost"
        onClick={() => backTo ? navigate(backTo) : navigate(-1)}
        aria-label={t("common.back")}
      >
        <ArrowLeft />
      </Button>
      <h1>{title}</h1>
      <div className="stack-page-header__action">{action}</div>
    </header>
  );
}
