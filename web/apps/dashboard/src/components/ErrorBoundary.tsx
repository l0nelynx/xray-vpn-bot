import { Component, type ReactNode } from "react";
import { Card, CardContent } from "@xray/ui/components/card";
import { Button } from "@xray/ui/components/button";

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
        <div className="flex min-h-[60vh] items-center justify-center p-4">
          <Card className="max-w-sm text-center">
            <CardContent className="flex flex-col items-center gap-3 p-6">
              <h3 className="text-lg font-semibold text-foreground">Something went wrong</h3>
              <p className="text-sm text-muted-foreground">
                An unexpected error occurred. Please reload the page.
              </p>
              <Button onClick={() => window.location.reload()}>Reload</Button>
            </CardContent>
          </Card>
        </div>
      );
    }

    return this.props.children;
  }
}
