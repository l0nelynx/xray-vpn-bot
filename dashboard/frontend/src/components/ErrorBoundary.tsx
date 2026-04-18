import { Component, type ReactNode } from "react";
import { Card, Button } from "antd";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "60vh" }}>
          <Card style={{ maxWidth: 400, textAlign: "center" }}>
            <h3 style={{ color: "rgba(255,255,255,0.85)" }}>Something went wrong</h3>
            <p style={{ color: "rgba(255,255,255,0.55)" }}>
              An unexpected error occurred. Please reload the page.
            </p>
            <Button type="primary" onClick={() => window.location.reload()}>
              Reload
            </Button>
          </Card>
        </div>
      );
    }

    return this.props.children;
  }
}
