import { useEffect, useMemo, useState } from "react";
import { Slack, Link2, PlugZap, ShieldCheck, Unplug } from "lucide-react";
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

export function SlackAgentPanel() {
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
            if (event.data?.type === "connector_connected" && event.data?.connector === "slack") {
                refreshData();
            }
            if (event.data?.type === "connector_error" && event.data?.connector === "slack") {
                toast.error("Slack connection failed", {
                    description: event.data?.message || "The Slack OAuth flow could not be completed.",
                });
            }
        };
        window.addEventListener("message", handleMessage);
        return () => window.removeEventListener("message", handleMessage);
    }, []);

    const slackStatus = useMemo(
        () => statusRows.find((row) => row.server === "slack"),
        [statusRows],
    );
    const slackAccount = useMemo(
        () => accountRows.find((row) => row.connector_name === "slack"),
        [accountRows],
    );
    const canStartOAuth = Boolean(slackStatus?.configured && slackStatus?.oauth_configured);

    const handleConnect = () => {
        const token = getToken();
        if (!token || !canStartOAuth) return;
        const width = 640;
        const height = 800;
        const left = window.screenX + (window.outerWidth - width) / 2;
        const top = window.screenY + (window.outerHeight - height) / 2;
        const url = `${api.defaults.baseURL}/api/connectors/slack/start?token=${encodeURIComponent(token)}`;
        window.open(url, "slack-connect", `width=${width},height=${height},left=${left},top=${top}`);
    };

    const handleDisconnect = async () => {
        setIsBusy(true);
        try {
            await api.delete("/api/connectors/slack");
            await refreshData();
        } finally {
            setIsBusy(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-muted/10 p-6 overflow-y-auto">
            <div className="mb-8 flex items-center gap-3">
                <div className="p-3 bg-[#4A154B]/10 rounded-xl">
                    <Slack className="w-6 h-6 text-[#4A154B]" />
                </div>
                <div>
                    <h2 className="text-2xl font-bold tracking-tight text-foreground">Slack Agent</h2>
                    <p className="text-sm text-muted-foreground mt-1">Manage channels, search messages, and post updates via local MCP integration.</p>
                </div>
            </div>
            
            <div className="rounded-2xl border border-border/40 bg-card px-4 py-4 text-sm text-muted-foreground mb-6 flex items-center justify-between gap-4 shadow-sm">
                <div className="space-y-1">
                    <div className="flex items-center gap-2 text-foreground font-medium">
                        <PlugZap className="w-4 h-4 text-primary" />
                        Slack Integration Status
                    </div>
                    <p>
                        {slackStatus?.configured
                            ? `Slack MCP service is enabled.`
                            : "Slack integration is disabled. Set SLACK_CLIENT_ID and SLACK_CLIENT_SECRET in backend/.env."}
                    </p>
                    {!slackStatus?.oauth_configured && slackStatus?.configured && (
                         <p className="text-amber-500 text-xs">
                         {slackStatus.setup_hint || "OAuth redirect URI mismatch or missing credentials."}
                     </p>
                    )}
                </div>
                {slackAccount?.connected ? (
                    <Button variant="outline" onClick={handleDisconnect} disabled={isBusy} className="rounded-xl">
                        <Unplug className="w-4 h-4 mr-2" />
                        Disconnect
                    </Button>
                ) : (
                    <Button onClick={handleConnect} disabled={!canStartOAuth} className="rounded-xl bg-[#4A154B] hover:bg-[#3b113c] text-white border-none shadow-md">
                        <Link2 className="w-4 h-4 mr-2" />
                        Connect Slack
                    </Button>
                )}
            </div>

            {slackAccount?.connected ? (
                <>
                    <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 text-sm text-muted-foreground mb-6">
                        <div className="flex items-center gap-2 text-foreground font-medium mb-1">
                            <ShieldCheck className="w-4 h-4 text-emerald-500" />
                            Connected as {slackAccount.display_name || slackAccount.email || "Slack Workspace"}
                        </div>
                        <p>The agent can now interact with your Slack workspace through secure localized MCP tools.</p>
                    </div>
                    <div className="min-h-[720px] overflow-hidden rounded-2xl border border-border/40 bg-card shadow-md">
                        <AIChatPanel mode="slack_agent" title="Slack Communication Agent" />
                    </div>
                </>
            ) : (
                <div className="grid place-items-center min-h-[520px] rounded-2xl border border-dashed border-border/50 bg-card/80">
                    <div className="max-w-md text-center px-6">
                        <div className="w-16 h-16 rounded-2xl bg-[#4A154B]/10 text-[#4A154B] flex items-center justify-center mx-auto mb-5 shadow-sm">
                            <Slack className="w-8 h-8" />
                        </div>
                        <h3 className="text-xl font-semibold text-foreground mb-2">Connect Slack to continue</h3>
                        <p className="text-sm text-muted-foreground mb-6">
                            Sign in with your Slack workspace to grant the agent permission to help you manage your communication.
                        </p>
                        {slackStatus?.oauth_redirect_uri ? (
                            <div className="bg-muted p-3 rounded-lg mb-6 border border-border/40">
                                <p className="text-[10px] uppercase tracking-wider font-bold text-muted-foreground mb-1">Required Callback URL</p>
                                <code className="text-xs break-all text-primary font-mono">{slackStatus.oauth_redirect_uri}</code>
                            </div>
                        ) : null}
                        <Button onClick={handleConnect} disabled={!canStartOAuth} className="rounded-xl w-full py-6 text-base font-semibold bg-[#4A154B] hover:bg-[#3b113c] text-white border-none shadow-lg transition-transform hover:scale-[1.02] active:scale-[0.98]">
                            <Link2 className="w-5 h-5 mr-2" />
                            Add to Slack
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
}
