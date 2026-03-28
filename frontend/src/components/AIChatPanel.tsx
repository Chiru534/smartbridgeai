import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SendHorizontal, Bot, User, RefreshCw, Sparkles, AlertTriangle, Brain, ChevronDown, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { getToken } from "@/lib/auth";

export type Message = {
    id: string;
    role: "user" | "assistant";
    content: string;
    thoughts?: string;
    isStreaming?: boolean;
    timestamp?: number;
    citations?: Array<{
        source_type: string;
        label: string;
        document_id?: number | null;
        chunk_index?: number | null;
        score?: number | null;
    }>;
};

type UserProfile = {
    user_id: number;
    username: string;
    email: string;
    display_name: string;
    role: string;
    preferred_model?: string | null;
    preferred_tone?: string | null;
};

const FALLBACK_MODELS = [
    { id: "llama-3.3-70b-versatile", name: "Llama 3.3 70B Versatile" },
    { id: "llama-3.1-8b-instant", name: "Llama 3.1 8B Instant" },
    { id: "gemma2-9b-it", name: "Gemma 2 9B IT" },
];

const WELCOME_MESSAGE: Message = {
    id: "welcome",
    role: "assistant",
    content: "Welcome to Smartbridge AI! 👋 I can help you manage tasks, answer questions, and research the web. Try saying:\n\n• \"Create a task for Ananya to review the dashboard design\"\n• \"What is the current population of Hyderabad?\"\n• \"Help me plan the sprint\"",
    timestamp: Date.now(),
};

const SESSION_IDLE_TIMEOUT_MS = 60 * 60 * 1000;

function normalizeModeStorageKey(mode: string): string {
    return (mode || "standard_chat").replace(/[^a-z0-9]+/gi, "_").toLowerCase();
}
function getActiveSessionKey(mode: string): string {
    return `smartbridge_active_chat_session_${normalizeModeStorageKey(mode)}`;
}
function getLastActivityKey(mode: string): string {
    return `smartbridge_chat_last_activity_${normalizeModeStorageKey(mode)}`;
}
function extractDisplayNameFromMessage(input: string): string | null {
    const patterns = [
        /\bmy name is\s+([A-Za-z][A-Za-z\s'-]{0,49})/i,
        /\bi am\s+([A-Za-z][A-Za-z\s'-]{0,49})/i,
        /\bcall me\s+([A-Za-z][A-Za-z\s'-]{0,49})/i,
    ];
    const text = input.trim();
    for (const pattern of patterns) {
        const match = text.match(pattern);
        if (!match) continue;
        const raw = (match[1] || "").trim().replace(/[.,!?;:]+$/, "");
        if (raw.length < 2) continue;
        return raw.split(/\s+/).map(p => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase()).join(" ");
    }
    return null;
}
function getStoredSessionId(mode: string): string | undefined {
    try { return localStorage.getItem(getActiveSessionKey(mode)) || undefined; } catch { return undefined; }
}
function persistActiveSession(sessionId: string | undefined, mode: string) {
    try {
        if (sessionId) localStorage.setItem(getActiveSessionKey(mode), sessionId);
        else localStorage.removeItem(getActiveSessionKey(mode));
    } catch { /* no-op */ }
}
function markSessionActivity(mode: string) {
    try { localStorage.setItem(getLastActivityKey(mode), Date.now().toString()); } catch { /* no-op */ }
}
function isSessionIdleExpired(mode: string): boolean {
    try {
        const raw = localStorage.getItem(getLastActivityKey(mode));
        if (!raw) return false;
        const last = Number(raw);
        return Number.isFinite(last) && last > 0 && Date.now() - last > SESSION_IDLE_TIMEOUT_MS;
    } catch { return false; }
}
function createSessionId(): string {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
    return `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/** Renders clean final AI message text */
function renderContent(content: string) {
    if (!content) return null;
    if (content.includes("⚠️")) {
        return (
            <span className="flex items-start gap-2">
                <AlertTriangle size={14} className="text-amber-500 mt-0.5 flex-shrink-0" />
                <span>{content.replace("⚠️ ", "")}</span>
            </span>
        );
    }
    return <div className="whitespace-pre-wrap text-sm leading-relaxed">{content}</div>;
}

/** Collapsible Thinking Process box — shown above the final message while streaming */
function ThinkingBox({ thoughts, isStreaming }: { thoughts: string; isStreaming?: boolean }) {
    const [isOpen, setIsOpen] = useState(true);
    return (
        <div className="mb-2 rounded-xl border border-gray-700/60 bg-gray-800/50 overflow-hidden text-xs">
            <button
                className="w-full flex items-center gap-2 px-3 py-2 text-gray-400 hover:text-gray-200 hover:bg-gray-700/40 transition-colors"
                onClick={() => setIsOpen(o => !o)}
            >
                {isStreaming ? (
                    <span className="flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse" />
                        <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse delay-75" />
                        <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse delay-150" />
                    </span>
                ) : (
                    <Brain size={12} className="text-purple-400 flex-shrink-0" />
                )}
                <span className="font-medium text-purple-300">
                    {isStreaming ? "Thinking..." : "Thinking Process"}
                </span>
                <span className="ml-auto">
                    {isOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                </span>
            </button>
            {isOpen && (
                <div className="px-3 pb-3 pt-1 text-gray-400 whitespace-pre-wrap border-t border-gray-700/40 max-h-48 overflow-y-auto">
                    {thoughts || (isStreaming ? "..." : "")}
                </div>
            )}
        </div>
    );
}

// Skeleton loader
function ChatSkeleton() {
    return (
        <div className="space-y-6 p-6">
            {[1, 2, 3].map(i => (
                <div key={i} className={`flex ${i % 2 === 0 ? "justify-end" : "justify-start"} w-full`}>
                    <div className={`flex items-end gap-3 max-w-[70%] ${i % 2 === 0 ? "flex-row-reverse" : "flex-row"}`}>
                        <div className="w-9 h-9 rounded-full bg-muted animate-skeleton flex-shrink-0" />
                        <div className={`rounded-2xl bg-muted animate-skeleton ${i % 2 === 0 ? "rounded-br-sm" : "rounded-bl-sm"}`}
                            style={{ width: `${120 + i * 60}px`, height: "48px" }} />
                    </div>
                </div>
            ))}
        </div>
    );
}

type AIChatPanelProps = {
    onTaskCreated?: () => void;
    sessionId?: string;
    onNewChat?: () => void;
    mode?: string;
    workspaceOptions?: Record<string, unknown>;
    title?: string;
};

export function AIChatPanel({
    onTaskCreated,
    sessionId,
    onNewChat,
    mode = "standard_chat",
    workspaceOptions = {},
    title = "AI Chat Assistant",
}: AIChatPanelProps) {
    const [availableModels, setAvailableModels] = useState(FALLBACK_MODELS);
    const [isFetchingModels, setIsFetchingModels] = useState(false);
    const [model, setModel] = useState(FALLBACK_MODELS[0].id);
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [isInitialized, setIsInitialized] = useState(false);
    const [cooldownTime, setCooldownTime] = useState(0);
    const [cacheAgeStr, setCacheAgeStr] = useState<string | null>(null);
    const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
    const [currentSessionId, setCurrentSessionId] = useState<string | undefined>(() => sessionId ?? getStoredSessionId(mode));
    const scrollRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Cooldown timer
    useEffect(() => {
        if (cooldownTime > 0) {
            const timer = setTimeout(() => setCooldownTime(c => c - 1), 1000);
            return () => clearTimeout(timer);
        }
    }, [cooldownTime]);

    // Keep idle timer accurate
    useEffect(() => {
        const handleActivity = () => markSessionActivity(mode);
        const events: Array<keyof WindowEventMap> = ["click", "keydown", "mousemove", "touchstart"];
        events.forEach(ev => window.addEventListener(ev, handleActivity, { passive: true }));
        return () => events.forEach(ev => window.removeEventListener(ev, handleActivity));
    }, [mode]);

    // Auto-close stale session context
    useEffect(() => {
        const idleCheck = setInterval(() => {
            if (document.visibilityState !== "visible") return;
            if (!isSessionIdleExpired(mode)) return;
            if (sessionId) return;
            const freshSessionId = createSessionId();
            setMessages([WELCOME_MESSAGE]);
            setCurrentSessionId(freshSessionId);
            persistActiveSession(freshSessionId, mode);
            markSessionActivity(mode);
        }, 60_000);
        return () => clearInterval(idleCheck);
    }, [mode, sessionId]);

    // Fetch user profile
    useEffect(() => {
        let isCancelled = false;
        api.get("/api/user/profile").then(res => {
            if (isCancelled || !res?.data) return;
            setUserProfile(res.data as UserProfile);
            if (res.data.preferred_model) setModel(res.data.preferred_model);
        }).catch(() => { /* Keep chat functional */ });
        return () => { isCancelled = true; };
    }, []);

    // Load history
    useEffect(() => {
        const fetchHistory = async () => {
            setIsLoading(true);
            try {
                const idleExpired = isSessionIdleExpired(mode);
                let resolvedSessionId = sessionId ?? getStoredSessionId(mode);

                if (mode === "standard_chat" && !resolvedSessionId && !idleExpired) {
                    const sessionsRes = await api.get("/api/chat/sessions");
                    if (Array.isArray(sessionsRes.data) && sessionsRes.data.length > 0) {
                        resolvedSessionId = sessionsRes.data[0].session_id;
                    }
                }

                if (!resolvedSessionId || (idleExpired && !sessionId)) {
                    const fresh = createSessionId();
                    setCurrentSessionId(fresh);
                    persistActiveSession(fresh, mode);
                    markSessionActivity(mode);
                    setMessages([WELCOME_MESSAGE]);
                    return;
                }

                const res = await api.get(`/api/chat/history?session_id=${encodeURIComponent(resolvedSessionId)}`);
                if (res.data && res.data.length > 0) {
                    setMessages(res.data.map((msg: any) => ({
                        id: `db-msg-${msg.id}`,
                        role: msg.role,
                        content: msg.content,
                        timestamp: new Date(msg.timestamp).getTime()
                    })));
                } else {
                    setMessages([WELCOME_MESSAGE]);
                }
                setCurrentSessionId(resolvedSessionId);
                persistActiveSession(resolvedSessionId, mode);
                markSessionActivity(mode);
            } catch {
                setMessages([WELCOME_MESSAGE]);
                const fallback = sessionId ?? getStoredSessionId(mode) ?? createSessionId();
                setCurrentSessionId(fallback);
                persistActiveSession(fallback, mode);
            } finally {
                setIsInitialized(true);
                setIsLoading(false);
            }
        };
        fetchHistory();
    }, [mode, sessionId]);

    // Model fetching with cache
    const CACHE_KEY = "smartbridge_models_cache_v1";
    const CACHE_TTL = 45 * 60 * 1000;

    const updateCacheAgeDisplay = (timestamp: number) => {
        const ageMs = Date.now() - timestamp;
        setCacheAgeStr(ageMs < 60000 ? "Just now" : `${Math.floor(ageMs / 60000)} min ago`);
    };

    const fetchModels = useCallback(async (forceRefresh = false) => {
        setIsFetchingModels(true);
        try {
            if (!forceRefresh) {
                const cached = localStorage.getItem(CACHE_KEY);
                if (cached) {
                    const { models, timestamp } = JSON.parse(cached);
                    if (Date.now() - timestamp < CACHE_TTL && Array.isArray(models) && models.length > 0) {
                        setAvailableModels(models);
                        if (!models.find((m: any) => m.id === model)) setModel(models[0].id);
                        updateCacheAgeDisplay(timestamp);
                        return;
                    }
                }
            }
            const res = await api.get("/api/available-models");
            if (res.data.models && res.data.models.length > 0) {
                const newModels = res.data.models;
                setAvailableModels(newModels);
                const now = Date.now();
                localStorage.setItem(CACHE_KEY, JSON.stringify({ models: newModels, timestamp: now }));
                updateCacheAgeDisplay(now);
                if (!newModels.find((m: any) => m.id === model)) setModel(newModels[0].id);
                if (forceRefresh) toast.success("Models refreshed", { description: `${newModels.length} models available` });
            }
        } catch {
            if (forceRefresh) toast.error("Failed to fetch models", { description: "Using fallback model list" });
        } finally {
            setIsFetchingModels(false);
        }
    }, [model]);

    useEffect(() => { fetchModels(); }, []);

    // Tab visibility auto-fetch
    useEffect(() => {
        const handleVisibilityChange = () => {
            if (document.visibilityState === "visible") {
                const cached = localStorage.getItem(CACHE_KEY);
                if (cached) {
                    try { if (Date.now() - JSON.parse(cached).timestamp < CACHE_TTL) return; } catch { /* */ }
                }
                fetchModels();
            }
        };
        document.addEventListener("visibilitychange", handleVisibilityChange);
        return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
    }, [fetchModels]);

    // Auto-scroll
    useEffect(() => {
        if (scrollRef.current) requestAnimationFrame(() => { scrollRef.current!.scrollTop = scrollRef.current!.scrollHeight; });
    }, [messages, isLoading]);

    const handleSend = async () => {
        const trimmed = input.trim();
        if (!trimmed || isLoading) return;
        if (cooldownTime > 0) { toast.error(`Please wait ${cooldownTime} seconds before next message`); return; }

        const userMsg: Message = { id: `msg-${Date.now()}`, role: "user", content: trimmed, timestamp: Date.now() };
        setMessages(prev => [...prev, userMsg]);
        setInput("");
        setIsLoading(true);
        textareaRef.current?.focus();

        // Detect display name (non-blocking)
        const detectedName = extractDisplayNameFromMessage(trimmed);
        if (detectedName && (!userProfile || userProfile.display_name.toLowerCase() !== detectedName.toLowerCase())) {
            api.patch("/api/user/profile", { display_name: detectedName })
                .then(res => setUserProfile(res.data as UserProfile))
                .catch(() => { /* non-blocking */ });
        }

        const sessionForSend = currentSessionId ?? createSessionId();
        if (!currentSessionId) { setCurrentSessionId(sessionForSend); persistActiveSession(sessionForSend, mode); }

        const context = messages.filter(m => m.id !== "welcome").slice(-20)
            .map(m => ({ role: m.role, content: m.content }))
            .concat({ role: "user", content: trimmed });

        // Create a placeholder message for streaming
        const assistantMsgId = `msg-${Date.now()}-assistant`;
        setMessages(prev => [...prev, {
            id: assistantMsgId, role: "assistant", content: "", thoughts: "", isStreaming: true, timestamp: Date.now(),
        }]);

        try {
            const token = getToken() || "";
            const response = await fetch(`${api.defaults.baseURL}/api/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
                body: JSON.stringify({ model, messages: context, session_id: sessionForSend, mode, workspace_options: workspaceOptions }),
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData?.detail || `HTTP ${response.status}`);
            }
            if (!response.body) throw new Error("No response body");

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const parts = buffer.split("\n\n");
                buffer = parts.pop() ?? "";

                for (const part of parts) {
                    const line = part.trim();
                    if (!line.startsWith("data: ")) continue;
                    try {
                        const event = JSON.parse(line.slice(6));
                        const evType: string = event.type;
                        const evContent: string = event.content ?? "";

                        if (evType === "thought") {
                            setMessages(prev => prev.map(m =>
                                m.id === assistantMsgId ? { ...m, thoughts: (m.thoughts ?? "") + evContent } : m
                            ));
                        } else if (evType === "message") {
                            setMessages(prev => prev.map(m =>
                                m.id === assistantMsgId ? { ...m, content: (m.content ?? "") + evContent } : m
                            ));
                        } else if (evType === "error") {
                            setMessages(prev => prev.map(m =>
                                m.id === assistantMsgId ? { ...m, content: `⚠️ ${evContent}`, isStreaming: false } : m
                            ));
                        } else if (evType === "done") {
                            setMessages(prev => prev.map(m =>
                                m.id === assistantMsgId ? { ...m, isStreaming: false } : m
                            ));
                            setCurrentSessionId(sessionForSend);
                            persistActiveSession(sessionForSend, mode);
                            markSessionActivity(mode);
                            if (onTaskCreated) onTaskCreated();
                        }
                    } catch { /* malformed SSE line */ }
                }
            }
            // Ensure streaming is marked done
            setMessages(prev => prev.map(m => m.id === assistantMsgId && m.isStreaming ? { ...m, isStreaming: false } : m));

        } catch (error: any) {
            const errorMessage = error?.message || "Failed to connect to AI service.";
            toast.error("Chat Error", { description: errorMessage, duration: 5000 });
            setMessages(prev => prev.map(m =>
                m.id === assistantMsgId ? { ...m, content: `⚠️ ${errorMessage}`, isStreaming: false } : m
            ));
        } finally {
            setIsLoading(false);
            setCooldownTime(3);
        }
    };

    const clearHistory = () => {
        const freshSessionId = createSessionId();
        setMessages([WELCOME_MESSAGE]);
        setCurrentSessionId(freshSessionId);
        persistActiveSession(freshSessionId, mode);
        markSessionActivity(mode);
        if (onNewChat) onNewChat();
        toast.success("New chat started");
    };

    if (!isInitialized) return <ChatSkeleton />;

    return (
        <div className="flex flex-col h-full bg-muted/10 relative">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-3.5 bg-card/80 backdrop-blur-md border-b border-border/50 z-10 sticky top-0 shadow-sm">
                <div className="flex items-center gap-3">
                    <h2 className="font-semibold text-foreground flex items-center gap-2.5 text-base">
                        <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                            <Bot className="text-primary w-4.5 h-4.5" />
                        </div>
                        {title}
                    </h2>
                    {userProfile?.display_name && (
                        <span className="text-xs text-muted-foreground">You: {userProfile.display_name}</span>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" className="h-8 text-xs text-muted-foreground hover:text-foreground gap-1.5"
                        onClick={clearHistory} aria-label="Start new chat">
                        New Chat
                    </Button>
                    <div className="w-px h-5 bg-border/50" />
                    {cacheAgeStr && (
                        <span className="text-[10px] text-muted-foreground mr-1 whitespace-nowrap">Last updated: {cacheAgeStr}</span>
                    )}
                    <Button variant="ghost" size="icon"
                        className={`h-8 w-8 border border-border/50 bg-background text-muted-foreground hover:text-foreground shadow-sm hover:bg-muted/50 rounded-lg ${isFetchingModels ? "opacity-50 cursor-not-allowed" : ""}`}
                        onClick={() => fetchModels(true)} disabled={isFetchingModels} title="Refresh models" aria-label="Refresh available models">
                        <RefreshCw size={14} className={isFetchingModels ? "animate-spin" : ""} />
                    </Button>
                    <Select value={model} onValueChange={setModel}>
                        <SelectTrigger className={`w-[260px] h-8 text-xs bg-background border-border/50 shadow-sm hover:bg-muted/50 transition-colors rounded-lg ${isFetchingModels ? "opacity-50" : ""}`} aria-label="Select AI model">
                            <SelectValue placeholder="Select Model" />
                        </SelectTrigger>
                        <SelectContent className="border-border shadow-lg rounded-xl max-h-[300px]">
                            {availableModels.map(m => (
                                <SelectItem key={m.id} value={m.id} className="text-xs cursor-pointer py-2">
                                    <span className="font-medium">{m.name}</span>
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-6 space-y-5 scroll-smooth custom-scrollbar" ref={scrollRef}>
                {messages.map((m) => (
                    <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"} w-full animate-fade-up`}>
                        <div className={`max-w-[80%] flex items-end gap-2.5 ${m.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
                            {m.role === "assistant" ? (
                                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-blue-600 text-primary-foreground flex items-center justify-center shadow-md flex-shrink-0">
                                    <Sparkles size={14} />
                                </div>
                            ) : (
                                <div className="w-8 h-8 rounded-full bg-secondary/20 text-secondary flex items-center justify-center shadow-sm flex-shrink-0 border border-secondary/30">
                                    <User size={14} />
                                </div>
                            )}
                            <div className={`px-4 py-3 text-sm leading-relaxed shadow-sm transition-all duration-200 w-full overflow-hidden ${m.role === "user"
                                ? "bg-primary text-primary-foreground rounded-2xl rounded-br-md max-w-fit"
                                : "bg-card text-card-foreground border border-border/40 rounded-2xl rounded-bl-md"
                                }`}>
                                {/* Thinking box ABOVE the message, only for assistant */}
                                {m.role === "assistant" && m.thoughts && (
                                    <ThinkingBox thoughts={m.thoughts} isStreaming={m.isStreaming} />
                                )}
                                {m.role === "assistant" ? renderContent(m.content) : m.content}
                                {/* Show typing dots while streaming and no content yet */}
                                {m.role === "assistant" && m.isStreaming && !m.content && !m.thoughts && (
                                    <span className="flex items-center gap-1.5 text-muted-foreground">
                                        <span className="w-1.5 h-1.5 rounded-full bg-primary/60 typing-dot-1"></span>
                                        <span className="w-1.5 h-1.5 rounded-full bg-primary/60 typing-dot-2"></span>
                                        <span className="w-1.5 h-1.5 rounded-full bg-primary/60 typing-dot-3"></span>
                                    </span>
                                )}
                                {m.role === "assistant" && Array.isArray(m.citations) && m.citations.length > 0 && (
                                    <div className="mt-3 pt-3 border-t border-border/40 flex flex-wrap gap-2">
                                        {m.citations.map((citation, index) => (
                                            <span key={`${m.id}-citation-${index}`}
                                                className="inline-flex items-center rounded-full border border-primary/20 bg-primary/5 px-2.5 py-1 text-[11px] text-muted-foreground">
                                                {citation.label}
                                                {typeof citation.chunk_index === "number" ? ` #${citation.chunk_index}` : ""}
                                            </span>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                ))}

                {/* Typing indicator (shown while loading but before any streaming message appears) */}
                {isLoading && messages.every(m => !m.isStreaming) && (
                    <div className="flex justify-start w-full animate-fade-up">
                        <div className="flex items-end gap-2.5">
                            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-blue-600 text-primary-foreground flex items-center justify-center shadow-md flex-shrink-0">
                                <Sparkles size={14} />
                            </div>
                            <div className="px-5 py-3.5 rounded-2xl bg-card border border-border/40 rounded-bl-md text-muted-foreground text-sm flex items-center gap-1.5">
                                <span className="w-1.5 h-1.5 rounded-full bg-primary/60 typing-dot-1"></span>
                                <span className="w-1.5 h-1.5 rounded-full bg-primary/60 typing-dot-2"></span>
                                <span className="w-1.5 h-1.5 rounded-full bg-primary/60 typing-dot-3"></span>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Input */}
            <div className="p-4 bg-card/80 backdrop-blur-md border-t border-border/50 shadow-[0_-4px_20px_-10px_rgba(0,0,0,0.08)]">
                <div className="relative flex items-center shadow-sm rounded-xl bg-background border border-border/60 focus-within:ring-2 focus-within:ring-primary/40 focus-within:border-primary/30 transition-all group overflow-hidden">
                    <Textarea
                        ref={textareaRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                        placeholder="Message Smartbridge AI..."
                        className="pr-14 pl-4 py-3 resize-none h-[52px] min-h-[52px] max-h-[150px] bg-transparent border-0 focus-visible:ring-0 shadow-none text-sm text-foreground placeholder:text-muted-foreground/60 dark:text-white"
                        aria-label="Chat message input"
                    />
                    <Button size="icon" onClick={handleSend} disabled={!input.trim() || isLoading || cooldownTime > 0}
                        className={`absolute right-2 bottom-1.5 h-9 w-9 rounded-lg transition-all duration-200 ${input.trim() && !isLoading && cooldownTime === 0
                            ? "bg-primary hover:bg-primary/90 text-primary-foreground shadow-md hover:shadow-lg hover:scale-105 active:scale-95"
                            : "bg-muted text-muted-foreground cursor-not-allowed"}`}
                        aria-label="Send message">
                        <SendHorizontal size={16} />
                    </Button>
                </div>
                <p className="text-[11px] text-center text-muted-foreground/60 mt-2.5 font-medium">
                    Smartbridge AI • Press <kbd className="px-1.5 py-0.5 bg-muted rounded text-[10px] font-mono">Enter</kbd> to send, <kbd className="px-1.5 py-0.5 bg-muted rounded text-[10px] font-mono">Shift+Enter</kbd> for new line
                </p>
            </div>
        </div>
    );
}
