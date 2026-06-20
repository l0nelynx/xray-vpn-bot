import { Button, Col, Row, Space, Typography } from "antd";
import {
  LockOutlined,
  RocketOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  SafetyCertificateOutlined,
  GlobalOutlined,
} from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import BrandLogo from "../components/BrandLogo";
import { BRAND_NAME } from "../branding";

const { Title, Paragraph, Text } = Typography;

const FEATURES = [
  {
    icon: <LockOutlined style={{ fontSize: 28, color: "#06D6A0" }} />,
    title: "Zero-Trust Access",
    desc: "Every connection authenticated, encrypted and isolated. No implicit trust, no perimeter exposure.",
  },
  {
    icon: <GlobalOutlined style={{ fontSize: 28, color: "#06D6A0" }} />,
    title: "Global Infrastructure",
    desc: "High-availability nodes across multiple regions. 99.9% SLA with automatic failover and load balancing.",
  },
  {
    icon: <TeamOutlined style={{ fontSize: 28, color: "#06D6A0" }} />,
    title: "Team Connectivity",
    desc: "Centralised access policies, device management and role-based controls for organisations of any size.",
  },
  {
    icon: <ThunderboltOutlined style={{ fontSize: 28, color: "#06D6A0" }} />,
    title: "High Throughput",
    desc: "Optimised routing protocols deliver low-latency, high-bandwidth connections for demanding workloads.",
  },
  {
    icon: <SafetyCertificateOutlined style={{ fontSize: 28, color: "#06D6A0" }} />,
    title: "Compliance Ready",
    desc: "Traffic isolation, audit logging and data-residency controls built for regulated industries.",
  },
  {
    icon: <RocketOutlined style={{ fontSize: 28, color: "#06D6A0" }} />,
    title: "Instant Deployment",
    desc: "Connect in minutes. Cross-platform clients for Windows, macOS, Linux, iOS and Android.",
  },
];

const STATS = [
  { value: "99.9%", label: "Uptime SLA" },
  { value: "50+", label: "Network Nodes" },
  { value: "10 Gbps", label: "Peak Throughput" },
  { value: "24/7", label: "Support" },
];

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div style={{ background: "#0B0B14", minHeight: "100vh", color: "rgba(255,255,255,0.92)" }}>
      {/* ── Navigation ─────────────────────────────────────────────────────── */}
      <nav
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "18px 48px",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          position: "sticky",
          top: 0,
          zIndex: 100,
          background: "rgba(11,11,20,0.85)",
          backdropFilter: "blur(20px)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <BrandLogo size={34} />
          <Text strong style={{ fontSize: 18, color: "#fff", letterSpacing: "-0.3px" }}>
            {BRAND_NAME}
          </Text>
        </div>

        <Space size={12}>
          <Button
            type="text"
            style={{ color: "rgba(255,255,255,0.65)" }}
            onClick={() => document.getElementById("features")?.scrollIntoView({ behavior: "smooth" })}
          >
            Solutions
          </Button>
          <Button
            type="text"
            style={{ color: "rgba(255,255,255,0.65)" }}
            onClick={() => document.getElementById("stats")?.scrollIntoView({ behavior: "smooth" })}
          >
            Platform
          </Button>
          <Button
            style={{
              background: "rgba(6,214,160,0.15)",
              borderColor: "rgba(6,214,160,0.4)",
              color: "#06D6A0",
            }}
            onClick={() => navigate("/login")}
          >
            Client Portal
          </Button>
        </Space>
      </nav>

      {/* ── Hero ───────────────────────────────────────────────────────────── */}
      <section
        style={{
          textAlign: "center",
          padding: "120px 24px 100px",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Decorative gradient glow */}
        <div
          style={{
            position: "absolute",
            top: "20%",
            left: "50%",
            transform: "translateX(-50%)",
            width: 700,
            height: 400,
            background:
              "radial-gradient(ellipse, rgba(6,214,160,0.12) 0%, transparent 70%)",
            pointerEvents: "none",
          }}
        />

        <div style={{ position: "relative", maxWidth: 800, margin: "0 auto" }}>
          <div
            style={{
              display: "inline-block",
              padding: "4px 14px",
              borderRadius: 20,
              border: "1px solid rgba(6,214,160,0.35)",
              background: "rgba(6,214,160,0.08)",
              marginBottom: 24,
            }}
          >
            <Text style={{ fontSize: 13, color: "#06D6A0", letterSpacing: "0.5px" }}>
              Enterprise Network Infrastructure
            </Text>
          </div>

          <Title
            level={1}
            style={{
              color: "#fff",
              fontSize: "clamp(36px, 5vw, 64px)",
              fontWeight: 700,
              lineHeight: 1.15,
              margin: "0 0 20px",
              letterSpacing: "-1px",
            }}
          >
            Private Connectivity
            <br />
            <span
              style={{
                background: "linear-gradient(135deg, #06D6A0, #0096C7)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              Built for Modern Teams
            </span>
          </Title>

          <Paragraph
            style={{
              fontSize: 18,
              color: "rgba(255,255,255,0.6)",
              maxWidth: 560,
              margin: "0 auto 40px",
              lineHeight: 1.7,
            }}
          >
            Secure, high-performance network access for distributed teams.
            Zero-trust architecture, global infrastructure, enterprise-grade reliability.
          </Paragraph>

          <Space size={16} wrap style={{ justifyContent: "center" }}>
            <Button
              type="primary"
              size="large"
              style={{
                background: "linear-gradient(135deg, #06D6A0, #0096C7)",
                border: "none",
                height: 50,
                padding: "0 32px",
                fontSize: 16,
                fontWeight: 600,
                borderRadius: 12,
              }}
              onClick={() => navigate("/register")}
            >
              Get Started
            </Button>
            <Button
              size="large"
              style={{
                background: "rgba(255,255,255,0.06)",
                border: "1px solid rgba(255,255,255,0.16)",
                color: "rgba(255,255,255,0.85)",
                height: 50,
                padding: "0 32px",
                fontSize: 16,
                borderRadius: 12,
              }}
              onClick={() => navigate("/login")}
            >
              Sign In
            </Button>
          </Space>
        </div>
      </section>

      {/* ── Stats bar ──────────────────────────────────────────────────────── */}
      <section
        id="stats"
        style={{
          borderTop: "1px solid rgba(255,255,255,0.06)",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
          padding: "40px 48px",
          background: "rgba(255,255,255,0.02)",
        }}
      >
        <Row justify="center" gutter={[48, 24]}>
          {STATS.map((s) => (
            <Col key={s.label} style={{ textAlign: "center", minWidth: 140 }}>
              <div style={{ fontSize: 32, fontWeight: 700, color: "#06D6A0", lineHeight: 1 }}>
                {s.value}
              </div>
              <div style={{ fontSize: 13, color: "rgba(255,255,255,0.5)", marginTop: 6 }}>
                {s.label}
              </div>
            </Col>
          ))}
        </Row>
      </section>

      {/* ── Features ───────────────────────────────────────────────────────── */}
      <section id="features" style={{ padding: "100px 48px", maxWidth: 1200, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 64 }}>
          <Title
            level={2}
            style={{ color: "#fff", fontWeight: 700, fontSize: 36, marginBottom: 12 }}
          >
            Everything your team needs
          </Title>
          <Paragraph style={{ color: "rgba(255,255,255,0.55)", fontSize: 16 }}>
            A complete private network platform — from access control to compliance.
          </Paragraph>
        </div>

        <Row gutter={[24, 24]}>
          {FEATURES.map((f) => (
            <Col key={f.title} xs={24} sm={12} lg={8}>
              <div
                style={{
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(255,255,255,0.09)",
                  borderRadius: 16,
                  padding: 28,
                  height: "100%",
                  transition: "border-color 0.2s",
                }}
                onMouseEnter={(e) =>
                  ((e.currentTarget as HTMLDivElement).style.borderColor =
                    "rgba(6,214,160,0.3)")
                }
                onMouseLeave={(e) =>
                  ((e.currentTarget as HTMLDivElement).style.borderColor =
                    "rgba(255,255,255,0.09)")
                }
              >
                <div style={{ marginBottom: 16 }}>{f.icon}</div>
                <Title level={4} style={{ color: "#fff", marginBottom: 8, fontSize: 17 }}>
                  {f.title}
                </Title>
                <Paragraph style={{ color: "rgba(255,255,255,0.55)", margin: 0, lineHeight: 1.6 }}>
                  {f.desc}
                </Paragraph>
              </div>
            </Col>
          ))}
        </Row>
      </section>

      {/* ── CTA banner ─────────────────────────────────────────────────────── */}
      <section
        style={{
          margin: "0 48px 80px",
          borderRadius: 20,
          background: "linear-gradient(135deg, rgba(6,214,160,0.12), rgba(0,150,199,0.12))",
          border: "1px solid rgba(6,214,160,0.2)",
          padding: "60px 40px",
          textAlign: "center",
        }}
      >
        <Title level={2} style={{ color: "#fff", marginBottom: 12 }}>
          Ready to connect your team?
        </Title>
        <Paragraph style={{ color: "rgba(255,255,255,0.6)", fontSize: 16, marginBottom: 32 }}>
          Access requires an invitation code from an existing client or partner.
        </Paragraph>
        <Button
          type="primary"
          size="large"
          style={{
            background: "linear-gradient(135deg, #06D6A0, #0096C7)",
            border: "none",
            height: 50,
            padding: "0 40px",
            fontSize: 16,
            fontWeight: 600,
            borderRadius: 12,
          }}
          onClick={() => navigate("/register")}
        >
          Create Account
        </Button>
      </section>

      {/* ── Footer ─────────────────────────────────────────────────────────── */}
      <footer
        style={{
          borderTop: "1px solid rgba(255,255,255,0.07)",
          padding: "32px 48px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <BrandLogo size={26} />
          <Text style={{ color: "rgba(255,255,255,0.4)", fontSize: 13 }}>
            © {new Date().getFullYear()} {BRAND_NAME}. All rights reserved.
          </Text>
        </div>
        <Text style={{ color: "rgba(255,255,255,0.25)", fontSize: 12 }}>
          Secure · Private · Reliable
        </Text>
      </footer>
    </div>
  );
}
