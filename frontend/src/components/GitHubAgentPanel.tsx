import { useEffect, useMemo, useState } from "react";
import { Github, Link2, PlugZap, ShieldCheck, Unplug, Search, FileCode, Folder, X } from "lucide-react";
import { toast } from "sonner";

import api from "@/lib/api";
import { getToken } from "@/lib/auth";
import { AIChatPanel } from "./AIChatPanel";
import { Button } from "./ui/button";
import { Input } from "./ui/input";

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

type GithubFile = {
    path: string;
    type: string;
    size?: number;
};

type RepoStructure = {
    owner: string;
    repo: string;
    files: GithubFile[];
};

export function GitHubAgentPanel() {
    const [statusRows, setStatusRows] = useState<ConnectorStatus[]>([]);
    const [accountRows, setAccountRows] = useState<ConnectorAccount[]>([]);
    const [isBusy, setIsBusy] = useState(false);

    // New states for Repo analysis
    const [repoUrl, setRepoUrl] = useState("");
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [repoStructure, setRepoStructure] = useState<RepoStructure | null>(null);
    const [selectedFile, setSelectedFile] = useState<{ path: string; content: string } | null>(null);
    const [isFetchingFile, setIsFetchingFile] = useState(false);

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

    const handleAnalyzeRepo = async () => {
        if (!repoUrl.trim()) {
            toast.error("Please enter a GitHub repository URL");
            return;
        }

        setIsAnalyzing(true);
        setRepoStructure(null);
        setSelectedFile(null);
        try {
            const res = await api.post("/api/github/repo-structure", { repo_url: repoUrl });
            setRepoStructure(res.data);
            toast.success("Repository structure loaded");
        } catch (error: any) {
            toast.error("Failed to analyze repository", {
                description: error.response?.data?.detail || "Make sure the URL is correct and the repo is public or you have configured access.",
            });
        } finally {
            setIsAnalyzing(false);
        }
    };

    const handleViewFile = async (path: string) => {
        setIsFetchingFile(true);
        try {
            const res = await api.post("/api/github/file-content", { 
                repo_url: repoUrl,
                file_path: path 
            });
            setSelectedFile({ path, content: res.data.content });
        } catch (error: any) {
            toast.error("Failed to fetch file content", {
                description: error.response?.data?.detail || "Could not retrieve the file content.",
            });
        } finally {
            setIsFetchingFile(false);
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
                    <p className="text-sm text-muted-foreground mt-1">Repository analysis and live tool operations.</p>
                </div>
            </div>

            {/* Repo Link Input Section */}
            <div className="rounded-2xl border border-border/40 bg-card p-6 mb-6 shadow-sm">
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                    <Search className="w-5 h-5 text-primary" />
                    Analyze Repository
                </h3>
                <div className="flex gap-3">
                    <Input 
                        placeholder="https://github.com/owner/repository" 
                        value={repoUrl}
                        onChange={(e) => setRepoUrl(e.target.value)}
                        className="rounded-xl flex-1"
                        onKeyDown={(e) => e.key === 'Enter' && handleAnalyzeRepo()}
                    />
                    <Button 
                        onClick={handleAnalyzeRepo} 
                        disabled={isAnalyzing}
                        className="rounded-xl px-6"
                    >
                        {isAnalyzing ? "Analyzing..." : "Analyze"}
                    </Button>
                </div>
                <p className="text-xs text-muted-foreground mt-3 italic">
                    Enter any public repository link or your own linked account's repositories.
                </p>
            </div>

            <div className="rounded-2xl border border-border/40 bg-card px-4 py-4 text-sm text-muted-foreground mb-6 flex items-center justify-between gap-4">
                <div className="space-y-1">
                    <div className="flex items-center gap-2 text-foreground font-medium">
                        <PlugZap className="w-4 h-4 text-primary" />
                        Account connection status
                    </div>
                </div>
                {githubAccount?.connected && !usesSharedPat ? (
                    <Button variant="outline" onClick={handleDisconnect} disabled={isBusy} className="rounded-xl h-9">
                        <Unplug className="w-4 h-4 mr-2" />
                        Disconnect
                    </Button>
                ) : !githubAccount?.connected ? (
                    <Button variant="outline" onClick={handleConnect} disabled={!canStartOAuth} className="rounded-xl h-9">
                        <Link2 className="w-4 h-4 mr-2" />
                        Connect GitHub
                    </Button>
                ) : (
                    <div className="text-emerald-500 flex items-center gap-2 font-medium">
                        <ShieldCheck className="w-4 h-4" />
                        Connected as {githubAccount.display_name || "Shared PAT"}
                    </div>
                )}
            </div>

            {/* Repository Explorer */}
            {repoStructure && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
                    {/* File List Table */}
                    <div className="rounded-2xl border border-border/40 bg-card overflow-hidden shadow-sm flex flex-col max-h-[600px]">
                        <div className="p-4 border-b border-border/40 bg-muted/5 flex items-center justify-between sticky top-0 z-10">
                            <h4 className="font-semibold flex items-center gap-2">
                                <Folder className="w-4 h-4 text-amber-500" />
                                {repoStructure.owner}/{repoStructure.repo}
                            </h4>
                            <span className="text-xs bg-muted px-2 py-1 rounded-full">{repoStructure.files.length} items</span>
                        </div>
                        <div className="overflow-y-auto flex-1">
                            <table className="w-full text-left border-collapse">
                                <thead>
                                    <tr className="text-xs uppercase text-muted-foreground tracking-wider font-medium border-b border-border/20 bg-muted/10">
                                        <th className="px-4 py-3">File Name</th>
                                        <th className="px-4 py-3">Type</th>
                                        <th className="px-4 py-3">Size</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {repoStructure.files.map((file, idx) => (
                                        <tr key={idx} className="border-b border-border/10 hover:bg-muted/30 transition-colors group">
                                            <td className="px-4 py-3">
                                                {file.type === 'blob' ? (
                                                    <button 
                                                        onClick={() => handleViewFile(file.path)}
                                                        className="flex items-center gap-2 text-primary hover:underline font-medium text-sm text-left w-full"
                                                    >
                                                        <FileCode className="w-4 h-4 opacity-70" />
                                                        {file.path}
                                                    </button>
                                                ) : (
                                                    <div className="flex items-center gap-2 text-foreground font-medium text-sm opacity-80">
                                                        <Folder className="w-4 h-4 text-amber-500/70" />
                                                        {file.path}
                                                    </div>
                                                )}
                                            </td>
                                            <td className="px-4 py-3 text-xs opacity-60">
                                                {file.type === 'blob' ? 'File' : 'Dir'}
                                            </td>
                                            <td className="px-4 py-3 text-xs opacity-60">
                                                {file.size ? `${(file.size / 1024).toFixed(1)} KB` : '-'}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* File Content Viewer */}
                    <div className="rounded-2xl border border-border/40 bg-card overflow-hidden shadow-sm flex flex-col max-h-[600px]">
                        <div className="p-4 border-b border-border/40 bg-muted/5 flex items-center justify-between sticky top-0 z-10">
                            <h4 className="font-semibold flex items-center gap-2">
                                <FileCode className="w-4 h-4 text-primary" />
                                {selectedFile ? selectedFile.path : "Select a file to view content"}
                            </h4>
                            {selectedFile && (
                                <button onClick={() => setSelectedFile(null)} className="p-1 hover:bg-muted rounded-lg transition-colors">
                                    <X className="w-4 h-4" />
                                </button>
                            )}
                        </div>
                        <div className="overflow-auto flex-1 p-0 bg-[#1e1e1e]">
                            {isFetchingFile ? (
                                <div className="flex items-center justify-center h-full text-zinc-400 gap-3">
                                    <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                                    Loading content...
                                </div>
                            ) : selectedFile ? (
                                <pre className="p-4 text-sm font-mono text-zinc-300 leading-relaxed overflow-x-auto selection:bg-primary/30">
                                    <code>{selectedFile.content}</code>
                                </pre>
                            ) : (
                                <div className="flex flex-col items-center justify-center h-full text-zinc-500 gap-4 px-6 text-center">
                                    <div className="w-12 h-12 rounded-full bg-zinc-800/50 flex items-center justify-center">
                                        <FileCode className="w-6 h-6 opacity-20" />
                                    </div>
                                    <p className="text-sm">Click on a file name in the list to see its code here.</p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {githubAccount?.connected ? (
                <>
                    <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 text-sm text-muted-foreground mb-6">
                        <div className="flex items-center gap-2 text-foreground font-medium mb-1">
                            <ShieldCheck className="w-4 h-4 text-emerald-500" />
                            AI-Powered Workspace Agent
                        </div>
                        <p>
                            You can also chat with the AI about your repository or common GitHub tasks below.
                        </p>
                    </div>
                    <div className="min-h-[720px] overflow-hidden rounded-2xl border border-border/40 bg-card shadow-sm">
                        <AIChatPanel 
                            mode="github_agent" 
                            title="GitHub Workspace Agent" 
                            workspaceOptions={{
                                active_repo: repoUrl,
                                repo_structure: repoStructure ? {
                                    owner: repoStructure.owner,
                                    repo: repoStructure.repo,
                                    files: repoStructure.files.slice(0, 50).map(f => f.path)
                                } : null
                            }}
                        />
                    </div>
                </>
            ) : (
                <div className="grid place-items-center min-h-[420px] rounded-2xl border border-dashed border-border/50 bg-card/80 mt-6">
                    <div className="max-w-md text-center px-6">
                        <div className="w-16 h-16 rounded-2xl bg-primary/10 text-primary flex items-center justify-center mx-auto mb-5">
                            <Github className="w-8 h-8" />
                        </div>
                        <h3 className="text-xl font-semibold text-foreground mb-2">Connect for Workspace AI</h3>
                        <p className="text-sm text-muted-foreground mb-6">
                            Linking your account enables the agent to perform write operations, manage issues, and private PRs.
                        </p>
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
