import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { AlertCircle, RefreshCw } from "lucide-react";

interface Props {
    children?: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
    public state: State = {
        hasError: false,
        error: null
    };

    public static getDerivedStateFromError(error: Error): State {
        // Update state so the next render will show the fallback UI.
        return { hasError: true, error };
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error("Uncaught error:", error, errorInfo);
    }

    public render() {
        if (this.state.hasError) {
            return (
                <div className="flex flex-col items-center justify-center min-h-full p-8 text-center bg-background text-foreground z-50">
                    <div className="p-4 bg-destructive/10 rounded-full mb-6">
                        <AlertCircle className="w-12 h-12 text-destructive" />
                    </div>
                    <h1 className="text-2xl font-bold tracking-tight mb-2">Something went wrong</h1>
                    <p className="text-muted-foreground max-w-md mb-8">
                        The application encountered an unexpected error. Please try refreshing the page.
                    </p>
                    <div className="bg-muted p-4 rounded-xl text-left max-w-2xl w-full overflow-auto mb-8 text-sm font-mono text-muted-foreground border border-border">
                        {this.state.error?.toString()}
                    </div>
                    <button
                        className="flex items-center gap-2 group bg-primary hover:bg-primary/90 text-primary-foreground px-6 py-2.5 rounded-xl font-medium transition-colors cursor-pointer"
                        onClick={() => window.location.reload()}
                    >
                        <RefreshCw className="w-4 h-4 group-hover:rotate-180 transition-transform duration-500" />
                        Reload Application
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}
