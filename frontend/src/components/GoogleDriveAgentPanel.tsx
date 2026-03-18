import { useEffect, useMemo, useState } from "react";
import { FolderKanban, Link2, PlugZap, ShieldCheck, Unplug } from "lucide-react";
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
    service_account_configured: boolean;
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

export function GoogleDriveAgentPanel() {
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
            if (event.data?.type === "connector_connected" && event.data?.connector === "google_drive") {
                refreshData();
            }
            if (event.data?.type === "connector_error" && event.data?.connector === "google_drive") {
                toast.error("Google Drive connection failed", {
                    description: event.data?.message || "The Google OAuth flow could not be completed.",
                });
            }
        };
        window.addEventListener("message", handleMessage);
        return () => window.removeEventListener("message", handleMessage);
    }, []);

    const driveStatus = useMemo(
        () => statusRows.find((row) => row.server === "google_drive"),
        [statusRows],
    );
    const driveAccount = useMemo(
        () => accountRows.find((row) => row.connector_name === "google_drive"),
        [accountRows],
    );
    const usesServiceAccount = driveAccount?.auth_method === "service_account";
    const canStartOAuth = Boolean(
        driveStatus?.configured &&
        (driveStatus?.service_account_configured || driveStatus?.oauth_configured),
    );

    const handleConnect = () => {
        const token = getToken();
        if (!token || !canStartOAuth) return;
        const width = 640;
        const height = 760;
        const left = window.screenX + (window.outerWidth - width) / 2;
        const top = window.screenY + (window.outerHeight - height) / 2;
        const url = `${api.defaults.baseURL}/api/connectors/google/start?token=${encodeURIComponent(token)}`;
        window.open(url, "google-drive-connect", `width=${width},height=${height},left=${left},top=${top}`);
    };

    const handleDisconnect = async () => {
        setIsBusy(true);
        try {
            await api.delete("/api/connectors/google_drive");
            await refreshData();
        } finally {
            setIsBusy(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-muted/10 p-6 overflow-y-auto">
            <div className="mb-8 flex items-center gap-3">
                <div className="p-3 bg-primary/10 rounded-xl">
                    <FolderKanban className="w-6 h-6 text-primary" />
                </div>
                <div>
                    <h2 className="text-2xl font-bold tracking-tight text-foreground">Google Drive Agent</h2>
                    <p className="text-sm text-muted-foreground mt-1">Drive operations flow through a local MCP stdio subprocess and Groq tool calling.</p>
                </div>
            </div>
            <div className="rounded-2xl border border-border/40 bg-card px-4 py-4 text-sm text-muted-foreground mb-6 flex items-center justify-between gap-4">
                <div className="space-y-1">
                    <div className="flex items-center gap-2 text-foreground font-medium">
                        <PlugZap className="w-4 h-4 text-primary" />
                        Local MCP status
                    </div>
                    <p>
                        {driveStatus?.configured
                            ? `Google Drive MCP configured: ${driveStatus.command.join(" ")}`
                            : "Google Drive MCP command is not configured yet. Set GOOGLE_DRIVE_MCP_COMMAND in backend/.env to enable live tools."}
                    </p>
                    {driveStatus?.configured && driveStatus?.service_account_configured ? (
                        <p className="text-emerald-500">
                            Google Drive is configured in direct service-account mode. Share the target Drive folder with the configured service account email.
                        </p>
                    ) : null}
                    {driveStatus?.configured && !driveAccount?.connected && driveStatus?.setup_hint ? (
                        <p className="text-amber-500">
                            {driveStatus.setup_hint}
                        </p>
                    ) : null}
                </div>
                {driveAccount?.connected && !usesServiceAccount ? (
                    <Button variant="outline" onClick={handleDisconnect} disabled={isBusy} className="rounded-xl">
                        <Unplug className="w-4 h-4 mr-2" />
                        Disconnect
                    </Button>
                ) : !driveAccount?.connected ? (
                    <Button onClick={handleConnect} disabled={!canStartOAuth} className="rounded-xl">
                        <Link2 className="w-4 h-4 mr-2" />
                        {driveStatus?.service_account_configured ? "Activate Google Drive" : "Connect Google Drive"}
                    </Button>
                ) : null}
            </div>

            {driveAccount?.connected ? (
                <>
                    <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 text-sm text-muted-foreground mb-6">
                        <div className="flex items-center gap-2 text-foreground font-medium mb-1">
                            <ShieldCheck className="w-4 h-4 text-emerald-500" />
                            Connected as {driveAccount.display_name || driveAccount.login || driveAccount.email}
                        </div>
                        <p>
                            {usesServiceAccount
                                ? "The Google Drive workspace is using the configured service account directly. Share the target folder with that service account email to expose it to the local MCP server."
                                : "The user only needs to sign in with Google once. After that, the local MCP server reuses the stored refresh token."}
                        </p>
                    </div>
                    <div className="min-h-[720px] overflow-hidden rounded-2xl border border-border/40 bg-card shadow-sm">
                        <AIChatPanel mode="google_drive_agent" title="Google Drive Workspace Agent" />
                    </div>
                </>
            ) : (
                <div className="grid place-items-center min-h-[520px] rounded-2xl border border-dashed border-border/50 bg-card/80">
                    <div className="max-w-md text-center px-6">
                        <div className="w-16 h-16 rounded-2xl bg-primary/10 text-primary flex items-center justify-center mx-auto mb-5">
                            <FolderKanban className="w-8 h-8" />
                        </div>
                        <h3 className="text-xl font-semibold text-foreground mb-2">Connect Google Drive to continue</h3>
                        <p className="text-sm text-muted-foreground mb-6">
                            {driveStatus?.service_account_configured
                                ? "This workspace can connect directly through a configured Google service account. Share the target folder with that service account email, then activate the workspace."
                                : driveStatus?.setup_hint
                                    ? driveStatus.setup_hint
                                    : "The first time a user enters this workspace, they sign in with Google. The backend stores the refresh token locally so future Drive sessions reconnect automatically."}
                        </p>
                        {driveStatus?.oauth_redirect_uri ? (
                            <p className="text-xs text-muted-foreground mb-4">
                                OAuth callback: <span className="font-mono">{driveStatus.oauth_redirect_uri}</span>
                            </p>
                        ) : null}
                        <Button onClick={handleConnect} disabled={!canStartOAuth} className="rounded-xl">
                            <Link2 className="w-4 h-4 mr-2" />
                            {driveStatus?.service_account_configured ? "Use Service Account" : "Sign in with Google"}
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
}
