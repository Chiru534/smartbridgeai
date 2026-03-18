import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SendHorizontal, Bot, User, RefreshCw, Sparkles, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";

export type Message = {
    id: string;
    role: "user" | "assistant";
    content: string;
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
    { id: "llama-3.3-70b-versatile", name: "Llama 3.3 70B Versatile – 70B" },
    { id: "llama-3.1-8b-instant", name: "Llama 3.1 8B Instant – 8B" },
    { id: "qwen-2.5-32b", name: "Qwen 2.5 32B" }
];

const WELCOME_MESSAGE: Message = {
    id: "welcome",
    role: "assistant",
    content: "Welcome to Smartbridge AI! 👋 I can help you manage tasks, answer questions, and research the web. Try saying:\n\n• \"Create a task for Ananya to review the dashboard design\"\n• \"What is the current population of Hyderabad?\"\n• \"Help me plan the sprint\"",
    timestamp: Date.now(),
};
const SESSION_IDLE_TIMEOUT_MS = 60 * 60 * 1000; // 60 minutes

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
        return raw
            .split(/\s+/)
            .map(part => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
            .join(" ");
    }
    return null;
}

function getStoredSessionId(mode: string): string | undefined {
    try {
        const value = localStorage.getItem(getActiveSessionKey(mode));
        return value || undefined;
    } catch {
        return undefined;
    }
}

function persistActiveSession(sessionId: string | undefined, mode: string) {
    try {
        const activeSessionKey = getActiveSessionKey(mode);
        if (sessionId) {
            localStorage.setItem(activeSessionKey, sessionId);
        } else {
            localStorage.removeItem(activeSessionKey);
        }
    } catch {
        // no-op
    }
}

function markSessionActivity(mode: string) {
    try {
        localStorage.setItem(getLastActivityKey(mode), Date.now().toString());
    } catch {
        // no-op
    }
}

function isSessionIdleExpired(mode: string): boolean {
    try {
        const raw = localStorage.getItem(getLastActivityKey(mode));
        if (!raw) return false;
        const lastActivity = Number(raw);
        if (!Number.isFinite(lastActivity) || lastActivity <= 0) return false;
        return Date.now() - lastActivity > SESSION_IDLE_TIMEOUT_MS;
    } catch {
        return false;
    }
}

function createSessionId(): string {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
        return crypto.randomUUID();
    }
    return `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function renderMarkdown(content: string) {
    if (!content) return null;

    // Check if it's an error message
    if (content.includes("⚠️")) {
        return (
            <span className="flex items-start gap-2">
                <AlertTriangle size={14} className="text-amber-500 mt-0.5 flex-shrink-0" />
                <span>{content.replace("⚠️ ", "")}</span>
            </span>
        );
    }

    // Completely strip out known internal blocks using regex before rendering.
    // 1. Strip <think>...</think> blocks
    let cleanedContent = content.replace(/<think>[\s\S]*?<\/think>/g, '');

    // 2. Strip **Thinking:** blocks up to the next heading or **Output:**
    cleanedContent = cleanedContent.replace(/\*\*Thinking:\*\*[\s\S]*?(?=\*\*Action:\*\*|\*\*Observation:\*\*|\*\*Output:\*\*|$)/g, '');

    // 3. Strip **Action:** blocks up to the next heading or **Output:**
    cleanedContent = cleanedContent.replace(/\*\*Action:\*\*[\s\S]*?(?=\*\*Thinking:\*\*|\*\*Observation:\*\*|\*\*Output:\*\*|$)/g, '');

    // 4. Strip **Observation:** blocks up to the next heading or **Output:**
    cleanedContent = cleanedContent.replace(/\*\*Observation:\*\*[\s\S]*?(?=\*\*Thinking:\*\*|\*\*Action:\*\*|\*\*Output:\*\*|$)/g, '');

    // 5. Remove the "**Output:**" prefix itself if it exists, leaving just the text
    cleanedContent = cleanedContent.replace(/\*\*Output:\*\*/g, '').trim();

    if (!cleanedContent) {
        // If content was only actions/thoughts (e.g. intermediate step) don't render an empty bubble
        return null;
    }

    return (
        <div className="flex flex-col gap-2 w-full text-sm">
            <div className="mt-2 whitespace-pre-wrap text-foreground font-medium">{cleanedContent}</div>
        </div>
    );
}

// Session continuity keys are intentionally persisted to preserve chat context across refreshes.

// Skeleton loader for chat area
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

    // Keep idle timer accurate while the user interacts with the chat UI.
    useEffect(() => {
        const handleActivity = () => markSessionActivity(mode);
        const events: Array<keyof WindowEventMap> = ["click", "keydown", "mousemove", "touchstart"];
        events.forEach((eventName) => window.addEventListener(eventName, handleActivity, { passive: true }));
        return () => events.forEach((eventName) => window.removeEventListener(eventName, handleActivity));
    }, [mode]);

    // Auto-close stale session context after prolonged inactivity.
    useEffect(() => {
        const idleCheck = setInterval(() => {
            if (document.visibilityState !== "visible") return;
            if (!isSessionIdleExpired(mode)) return;
            if (sessionId) return; // Don't override an explicitly selected history session.

            const freshSessionId = createSessionId();
            setMessages([WELCOME_MESSAGE]);
            setCurrentSessionId(freshSessionId);
            persistActiveSession(freshSessionId, mode);
            markSessionActivity(mode);
        }, 60_000);

        return () => clearInterval(idleCheck);
    }, [mode, sessionId]);

    useEffect(() => {
        let isCancelled = false;
        const fetchProfile = async () => {
            try {
                const res = await api.get("/api/user/profile");
                if (isCancelled || !res?.data) return;
                setUserProfile(res.data as UserProfile);
                if (res.data.preferred_model) {
                    setModel(res.data.preferred_model);
                }
            } catch {
                // Keep chat functional even if profile endpoint fails.
            }
        };
        fetchProfile();
        return () => {
            isCancelled = true;
        };
    }, []);

    // Load history on mount or when sessionId changes
    useEffect(() => {
        const fetchHistory = async () => {
            setIsLoading(true);
            try {
                const idleExpired = isSessionIdleExpired(mode);
                let resolvedSessionId = sessionId ?? getStoredSessionId(mode);

                // If no explicit/local session, recover the latest persisted session from DB.
                if (mode === "standard_chat" && !resolvedSessionId && !idleExpired) {
                    const sessionsRes = await api.get("/api/chat/sessions");
                    if (Array.isArray(sessionsRes.data) && sessionsRes.data.length > 0) {
                        resolvedSessionId = sessionsRes.data[0].session_id;
                    }
                }

                // Long idle: close old local session context and start fresh.
                if (!resolvedSessionId || (idleExpired && !sessionId)) {
                    const freshSessionId = createSessionId();
                    setCurrentSessionId(freshSessionId);
                    persistActiveSession(freshSessionId, mode);
                    markSessionActivity(mode);
                    setMessages([WELCOME_MESSAGE]);
                    setIsInitialized(true);
                    setIsLoading(false);
                    return;
                }

                const res = await api.get(`/api/chat/history?session_id=${encodeURIComponent(resolvedSessionId)}`);
                if (res.data && res.data.length > 0) {
                    const formattedHistory = res.data.map((msg: any) => ({
                        id: `db-msg-${msg.id}`,
                        role: msg.role,
                        content: msg.content,
                        timestamp: new Date(msg.timestamp).getTime()
                    }));
                    setMessages(formattedHistory);

                    setCurrentSessionId(resolvedSessionId);
                    persistActiveSession(resolvedSessionId, mode);
                    markSessionActivity(mode);
                } else {
                    setMessages([WELCOME_MESSAGE]);
                    setCurrentSessionId(resolvedSessionId);
                    persistActiveSession(resolvedSessionId, mode);
                    markSessionActivity(mode);
                }
            } catch (err) {
                console.error("Failed to load chat history", err);
                setMessages([WELCOME_MESSAGE]);
                const fallbackSessionId = sessionId ?? getStoredSessionId(mode) ?? createSessionId();
                setCurrentSessionId(fallbackSessionId);
                persistActiveSession(fallbackSessionId, mode);
            } finally {
                setIsInitialized(true);
                setIsLoading(false);
            }
        };
        fetchHistory();
    }, [mode, sessionId]);


    // Model caching constants
    const CACHE_KEY = "smartbridge_models_cache_v1";
    const CACHE_TTL = 45 * 60 * 1000; // 45 minutes

    const updateCacheAgeDisplay = (timestamp: number) => {
        const ageMs = Date.now() - timestamp;
        if (ageMs < 60000) {
            setCacheAgeStr("Just now");
        } else {
            const mins = Math.floor(ageMs / 60000);
            setCacheAgeStr(`${mins} min ago`);
        }
    };

    const fetchModels = useCallback(async (forceRefresh = false) => {
        setIsFetchingModels(true);
        try {
            // Check cache first
            if (!forceRefresh) {
                const cachedData = localStorage.getItem(CACHE_KEY);
                if (cachedData) {
                    try {
                        const { models, timestamp } = JSON.parse(cachedData);
                        if (Date.now() - timestamp < CACHE_TTL && Array.isArray(models) && models.length > 0) {
                            setAvailableModels(models);
                            if (!models.find((m: any) => m.id === model)) {
                                setModel(models[0].id);
                            }
                            updateCacheAgeDisplay(timestamp);
                            setIsFetchingModels(false);
                            return; // Use cache
                        }
                    } catch (e) {
                        console.error("Failed to parse cached models", e);
                    }
                }
            }

            const res = await api.get("/api/available-models");
            if (res.data.models && res.data.models.length > 0) {
                const newModels = res.data.models;

                // Compare with cache if we had one
                const cachedDataStr = localStorage.getItem(CACHE_KEY);
                if (cachedDataStr) {
                    try {
                        const cachedData = JSON.parse(cachedDataStr);
                        if (cachedData && Array.isArray(cachedData.models)) {
                            const oldIds = cachedData.models.map((m: any) => m.id).sort().join(',');
                            const newIds = newModels.map((m: any) => m.id).sort().join(',');

                            if (oldIds !== newIds && forceRefresh === false) {
                                // Only notify if it happened automatically (not force refresh)
                                toast.info("Groq updated available models");
                            }
                        }
                    } catch (e) {
                        // ignore error
                    }
                }

                setAvailableModels(newModels);

                const now = Date.now();
                // Save to cache
                localStorage.setItem(CACHE_KEY, JSON.stringify({
                    models: newModels,
                    timestamp: now
                }));
                updateCacheAgeDisplay(now);

                if (!newModels.find((m: any) => m.id === model)) {
                    setModel(newModels[0].id);
                }

                if (forceRefresh) {
                    toast.success("Models refreshed", { description: `${newModels.length} models available` });
                }
            }
        } catch {
            if (forceRefresh) {
                toast.error("Failed to fetch models", { description: "Using fallback model list" });
            }
            // If fetch fails and we don't have valid models yet, fall back to default
            if (availableModels === FALLBACK_MODELS) {
                setAvailableModels(FALLBACK_MODELS);
            }
        } finally {
            setIsFetchingModels(false);
        }
    }, [model, availableModels]);

    useEffect(() => {
        fetchModels();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Tab visibility auto-fetch
    useEffect(() => {
        const handleVisibilityChange = () => {
            if (document.visibilityState === 'visible') {
                const cachedData = localStorage.getItem(CACHE_KEY);
                let shouldFetch = true;
                if (cachedData) {
                    try {
                        const { timestamp } = JSON.parse(cachedData);
                        if (Date.now() - timestamp < CACHE_TTL) {
                            shouldFetch = false;
                        }
                    } catch (e) { }
                }
                if (shouldFetch) {
                    fetchModels();
                }
            }
        };

        document.addEventListener("visibilitychange", handleVisibilityChange);
        return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
    }, [fetchModels]);

    // Auto-scroll to bottom
    useEffect(() => {
        if (scrollRef.current) {
            requestAnimationFrame(() => {
                scrollRef.current!.scrollTop = scrollRef.current!.scrollHeight;
            });
        }
    }, [messages, isLoading]);

    const handleSend = async () => {
        const trimmed = input.trim();
        if (!trimmed || isLoading) return;

        if (cooldownTime > 0) {
            toast.error(`Please wait ${cooldownTime} seconds before next message`);
            return;
        }

        const userMsg: Message = {
            id: `msg-${Date.now()}`,
            role: "user",
            content: trimmed,
            timestamp: Date.now(),
        };
        setMessages(prev => [...prev, userMsg]);
        setInput("");
        setIsLoading(true);

        // Refocus textarea
        textareaRef.current?.focus();

        try {
            const detectedName = extractDisplayNameFromMessage(trimmed);
            if (
                detectedName &&
                (!userProfile || userProfile.display_name.toLowerCase() !== detectedName.toLowerCase())
            ) {
                try {
                    const profileRes = await api.patch("/api/user/profile", { display_name: detectedName });
                    setUserProfile(profileRes.data as UserProfile);
                } catch {
                    // Non-blocking: chat should continue even if profile update fails.
                }
            }

            const sessionForSend = currentSessionId ?? createSessionId();
            if (!currentSessionId) {
                setCurrentSessionId(sessionForSend);
                persistActiveSession(sessionForSend, mode);
            }

            const context = messages
                .filter(m => m.id !== "welcome")
                .slice(-20) // keep last 20 messages for context
                .map(m => ({ role: m.role, content: m.content }))
                .concat({ role: "user", content: trimmed });

            const res = await api.post("/api/chat", {
                model,
                messages: context,
                session_id: sessionForSend,
                mode,
                workspace_options: workspaceOptions,
            });

            const replyText = res.data.reply;
            if (res.data.session_id) {
                setCurrentSessionId(res.data.session_id);
                persistActiveSession(res.data.session_id, mode);
                markSessionActivity(mode);
            }

            setMessages(prev => [...prev, {
                id: `msg-${Date.now()}`,
                role: "assistant",
                content: replyText,
                timestamp: Date.now(),
                citations: Array.isArray(res.data.citations) ? res.data.citations : [],
            }]);

            if (onTaskCreated) onTaskCreated();

        } catch (error: any) {
            let errorMessage = "Failed to connect to AI service.";
            let errorDescription = "Please check if the backend server is running.";

            const status = error?.response?.status;
            if (status) {
                if (status === 429) {
                    errorMessage = "Rate limit reached";
                    errorDescription = "Too many requests. Please wait a moment and try again.";
                } else if (status === 404) {
                    errorMessage = "Model not found";
                    errorDescription = `The model "${model}" may no longer be available. Try a different model.`;
                } else if (status === 400) {
                    errorMessage = "Invalid request";
                    errorDescription = "The selected model may not support this request format.";
                } else if (status >= 500) {
                    errorMessage = "Server error";
                    errorDescription = error?.response?.data?.detail || "The backend failed while processing this request.";
                }
            } else if (error?.request) {
                errorMessage = "Network error";
                errorDescription = "Cannot reach the backend server. Make sure it's running on port 8000.";
            }

            toast.error(errorMessage, { description: errorDescription, duration: 5000 });

            setMessages(prev => [...prev, {
                id: `msg-${Date.now()}`,
                role: "assistant",
                content: `⚠️ ${errorMessage}. ${errorDescription}`,
                timestamp: Date.now(),
            }]);
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

    if (!isInitialized) {
        return <ChatSkeleton />;
    }

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
                        <span className="text-xs text-muted-foreground">
                            You: {userProfile.display_name}
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 text-xs text-muted-foreground hover:text-foreground gap-1.5"
                        onClick={clearHistory}
                        aria-label="Start new chat"
                    >
                        New Chat
                    </Button>
                    <div className="w-px h-5 bg-border/50" />
                    {cacheAgeStr && (
                        <span className="text-[10px] text-muted-foreground mr-1 whitespace-nowrap">
                            Last updated: {cacheAgeStr}
                        </span>
                    )}
                    <Button
                        variant="ghost"
                        size="icon"
                        className={`h-8 w-8 border border-border/50 bg-background text-muted-foreground hover:text-foreground shadow-sm hover:bg-muted/50 rounded-lg ${isFetchingModels ? 'opacity-50 cursor-not-allowed' : ''}`}
                        onClick={() => fetchModels(true)}
                        disabled={isFetchingModels}
                        title="Refresh available models"
                        aria-label="Refresh available models"
                    >
                        <RefreshCw size={14} className={isFetchingModels ? "animate-spin" : ""} />
                    </Button>
                    <Select value={model} onValueChange={setModel}>
                        <SelectTrigger
                            className={`w-[260px] h-8 text-xs bg-background border-border/50 shadow-sm hover:bg-muted/50 transition-colors rounded-lg ${isFetchingModels ? 'opacity-50' : ''}`}
                            aria-label="Select AI model"
                        >
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
                    <div
                        key={m.id}
                        className={`flex ${m.role === "user" ? "justify-end" : "justify-start"} w-full animate-fade-up`}
                    >
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
                            <div
                                className={`px-4 py-3 text-sm leading-relaxed shadow-sm transition-all duration-200 w-full overflow-hidden ${m.role === "user"
                                    ? "bg-primary text-primary-foreground rounded-2xl rounded-br-md max-w-fit"
                                    : "bg-card text-card-foreground border border-border/40 rounded-2xl rounded-bl-md"
                                    }`}
                            >
                                {m.role === "assistant" ? renderMarkdown(m.content) : m.content}
                                {m.role === "assistant" && Array.isArray(m.citations) && m.citations.length > 0 && (
                                    <div className="mt-3 pt-3 border-t border-border/40 flex flex-wrap gap-2">
                                        {m.citations.map((citation, index) => (
                                            <span
                                                key={`${m.id}-citation-${index}`}
                                                className="inline-flex items-center rounded-full border border-primary/20 bg-primary/5 px-2.5 py-1 text-[11px] text-muted-foreground"
                                            >
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

                {/* Typing indicator */}
                {isLoading && (
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

            {/* Input — always sticky at the bottom */}
            <div className="p-4 bg-card/80 backdrop-blur-md border-t border-border/50 shadow-[0_-4px_20px_-10px_rgba(0,0,0,0.08)]">
                <div className="relative flex items-center shadow-sm rounded-xl bg-background border border-border/60 focus-within:ring-2 focus-within:ring-primary/40 focus-within:border-primary/30 transition-all group overflow-hidden">
                    <Textarea
                        ref={textareaRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey) {
                                e.preventDefault();
                                handleSend();
                            }
                        }}
                        placeholder="Message Smartbridge AI..."
                        className="pr-14 pl-4 py-3 resize-none h-[52px] min-h-[52px] max-h-[150px] bg-transparent border-0 focus-visible:ring-0 shadow-none text-sm text-foreground placeholder:text-muted-foreground/60 dark:text-white"
                        aria-label="Chat message input"
                    />
                    <Button
                        size="icon"
                        onClick={handleSend}
                        disabled={!input.trim() || isLoading || cooldownTime > 0}
                        className={`absolute right-2 bottom-1.5 h-9 w-9 rounded-lg transition-all duration-200 ${input.trim() && !isLoading && cooldownTime === 0
                            ? "bg-primary hover:bg-primary/90 text-primary-foreground shadow-md hover:shadow-lg hover:scale-105 active:scale-95"
                            : "bg-muted text-muted-foreground cursor-not-allowed"
                            }`}
                        aria-label="Send message"
                    >
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
