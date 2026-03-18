import { useEffect, useMemo, useState } from "react";
import { Github, Link2, PlugZap, ShieldCheck, Unplug } from "lucide-react";
import { toast } from "sonner";

import api from "@/lib/api";
import { getToken } from "@/lib/auth";
import { AIChatPanel } from "./AIChatPanel";
import { Button } from "./ui/button";

type ConnectorStatus = {
    server: string;
    configured: boolean;
    command: string[];
    oauth_configured: boolean;
    pat_configured: boolean;
    auth_flow?: string | null;
    oauth_redirect_uri?: string | null;
    setup_hint?: string | null;
    last_error?: string | null;
};

type ConnectorAccount = {
    connector_name: string;
    connected: boolean;
    auth_method?: string | null;
    display_name?: string | null;
    login?: string | null;
    email?: string | null;
};

export function GitHubAgentPanel() {
    const [statusRows, setStatusRows] = useState<ConnectorStatus[]>([]);
    const [accountRows, setAccountRows] = useState<ConnectorAccount[]>([]);
    const [isBusy, setIsBusy] = useState(false);

    const refreshData = async () => {
        try {
            const [statusRes, accountsRes] = await Promise.all([
                api.get("/api/connectors/status"),
                api.get("/api/connectors/accounts"),
            ]);
            setStatusRows(Array.isArray(statusRes.data) ? statusRes.data : []);
            setAccountRows(Array.isArray(accountsRes.data) ? accountsRes.data : []);
        } catch {
            setStatusRows([]);
            setAccountRows([]);
        }
    };

    useEffect(() => {
        refreshData();
    }, []);

    useEffect(() => {
        const backendOrigin = new URL(api.defaults.baseURL || window.location.origin).origin;
        const handleMessage = (event: MessageEvent) => {
            if (event.origin !== backendOrigin) return;
            if (event.data?.type === "connector_connected" && event.data?.connector === "github") {
                refreshData();
            }
            if (event.data?.type === "connector_error" && event.data?.connector === "github") {
                toast.error("GitHub connection failed", {
                    description: event.data?.message || "The GitHub OAuth flow could not be completed.",
                });
            }
        };
        window.addEventListener("message", handleMessage);
        return () => window.removeEventListener("message", handleMessage);
    }, []);

    const githubStatus = useMemo(
        () => statusRows.find((row) => row.server === "github"),
        [statusRows],
    );
    const githubAccount = useMemo(
        () => accountRows.find((row) => row.connector_name === "github"),
        [accountRows],
    );
    const usesSharedPat = githubAccount?.auth_method === "pat_env";
    const canStartOAuth = Boolean(githubStatus?.configured && githubStatus?.oauth_configured);

    const handleConnect = () => {
        const token = getToken();
        if (!token || !canStartOAuth) return;
        const width = 640;
        const height = 760;
        const left = window.screenX + (window.outerWidth - width) / 2;
        const top = window.screenY + (window.outerHeight - height) / 2;
        const url = `${api.defaults.baseURL}/api/connectors/github/start?token=${encodeURIComponent(token)}`;
        window.open(url, "github-connect", `width=${width},height=${height},left=${left},top=${top}`);
    };

    const handleDisconnect = async () => {
        setIsBusy(true);
        try {
            await api.delete("/api/connectors/github");
            await refreshData();
        } finally {
            setIsBusy(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-muted/10 p-6 overflow-y-auto">
            <div className="mb-8 flex items-center gap-3">
                <div className="p-3 bg-primary/10 rounded-xl">
                    <Github className="w-6 h-6 text-primary" />
                </div>
                <div>
                    <h2 className="text-2xl font-bold tracking-tight text-foreground">GitHub Agent</h2>
                    <p className="text-sm text-muted-foreground mt-1">Repository operations flow through a local MCP stdio subprocess and Groq tool calling.</p>
                </div>
            </div>
            <div className="rounded-2xl border border-border/40 bg-card px-4 py-4 text-sm text-muted-foreground mb-6 flex items-center justify-between gap-4">
                <div className="space-y-1">
                    <div className="flex items-center gap-2 text-foreground font-medium">
                        <PlugZap className="w-4 h-4 text-primary" />
                        Local MCP status
                    </div>
                    <p>
                        {githubStatus?.configured
                            ? `GitHub MCP configured: ${githubStatus.command.join(" ")}`
                            : "GitHub MCP command is not configured yet. Set GITHUB_MCP_COMMAND in backend/.env to enable live tools."}
                    </p>
                    {githubStatus?.configured && githubStatus?.pat_configured ? (
                        <p className="text-emerald-500">
                            Shared GitHub PAT detected in the backend. The agent can use GitHub without the OAuth popup.
                        </p>
                    ) : null}
                    {githubStatus?.configured && !githubStatus?.oauth_configured && !githubStatus?.pat_configured ? (
                        <p className="text-amber-500">
                            GitHub OAuth is not configured yet. {githubStatus.setup_hint}
                        </p>
                    ) : null}
                </div>
                {githubAccount?.connected && !usesSharedPat ? (
                    <Button variant="outline" onClick={handleDisconnect} disabled={isBusy} className="rounded-xl">
                        <Unplug className="w-4 h-4 mr-2" />
                        Disconnect
                    </Button>
                ) : !githubAccount?.connected ? (
                    <Button onClick={handleConnect} disabled={!canStartOAuth} className="rounded-xl">
                        <Link2 className="w-4 h-4 mr-2" />
                        Connect GitHub
                    </Button>
                ) : null}
            </div>

            {githubAccount?.connected ? (
                <>
                    <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 text-sm text-muted-foreground mb-6">
                        <div className="flex items-center gap-2 text-foreground font-medium mb-1">
                            <ShieldCheck className="w-4 h-4 text-emerald-500" />
                            Connected as {githubAccount.display_name || githubAccount.login || githubAccount.email}
                        </div>
                        <p>
                            {usesSharedPat
                                ? "The agent is using the shared GITHUB_PAT from the backend environment through the local MCP subprocess."
                                : "The agent can now use your GitHub account through the local MCP subprocess."}
                        </p>
                    </div>
                    <div className="min-h-[720px] overflow-hidden rounded-2xl border border-border/40 bg-card shadow-sm">
                        <AIChatPanel mode="github_agent" title="GitHub Workspace Agent" />
                    </div>
                </>
            ) : (
                <div className="grid place-items-center min-h-[520px] rounded-2xl border border-dashed border-border/50 bg-card/80">
                    <div className="max-w-md text-center px-6">
                        <div className="w-16 h-16 rounded-2xl bg-primary/10 text-primary flex items-center justify-center mx-auto mb-5">
                            <Github className="w-8 h-8" />
                        </div>
                        <h3 className="text-xl font-semibold text-foreground mb-2">Connect GitHub to continue</h3>
                        <p className="text-sm text-muted-foreground mb-6">
                            You can either sign in with GitHub through OAuth or configure a shared GITHUB_PAT in the backend for local stdio MCP access.
                        </p>
                        {githubStatus?.oauth_redirect_uri ? (
                            <p className="text-xs text-muted-foreground mb-4">
                                OAuth callback: <span className="font-mono">{githubStatus.oauth_redirect_uri}</span>
                            </p>
                        ) : null}
                        <Button onClick={handleConnect} disabled={!canStartOAuth} className="rounded-xl">
                            <Link2 className="w-4 h-4 mr-2" />
                            Sign in with GitHub
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
}
