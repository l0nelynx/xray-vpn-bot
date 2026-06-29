import { ArrowLeftOutlined } from "@ant-design/icons";
import { Button, Typography } from "antd";
import { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

interface Props {
  title: string;
  children: ReactNode;
}

export default function LegalLayout({ title, children }: Props) {
  const navigate = useNavigate();
  return (
    <div className="page legal-page">
      <Button
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate(-1)}
        type="text"
        style={{ marginBottom: 12 }}
      >
        Назад
      </Button>

      <Typography.Title level={3} className="legal-title">
        {title}
      </Typography.Title>

      <div className="legal-content">{children}</div>
    </div>
  );
}
