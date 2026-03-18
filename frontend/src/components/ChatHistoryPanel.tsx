import { useState, useEffect } from "react";
import { format, isToday, isYesterday } from "date-fns";
import { MessageSquare, Calendar, ChevronRight, Search, X } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import api from "@/lib/api";

interface ChatSession {
    session_id: string;
    title: string;
    last_message_timestamp: string;
}

interface ChatHistoryPanelProps {
    onLoadSession: (sessionId: string) => void;
}

export function ChatHistoryPanel({ onLoadSession }: ChatHistoryPanelProps) {
    const [sessions, setSessions] = useState<ChatSession[]>([]);
    const [searchQuery, setSearchQuery] = useState("");
    const [sortOrder, setSortOrder] = useState<"newest" | "oldest">("newest");
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const fetchSessions = async () => {
            try {
                const res = await api.get("/api/chat/sessions");
                setSessions(res.data);
            } catch (err) {
                console.error("Failed to load chat sessions:", err);
            } finally {
                setIsLoading(false);
            }
        };
        fetchSessions();
    }, []);

    const normalizeTitle = (title: string) => {
        return title.replace(/^"+|"+$/g, "").replace(/\s+/g, " ").trim();
    };

    const buildPreview = (title: string) => {
        const cleaned = normalizeTitle(title);
        const firstLine = cleaned.split(/\r?\n/)[0] ?? cleaned;
        return firstLine.length > 60 ? `${firstLine.slice(0, 60)}...` : firstLine;
    };

    const filteredSessions = sessions
        .filter((session) =>
            normalizeTitle(session.title).toLowerCase().includes(searchQuery.trim().toLowerCase())
        )
        .sort((a, b) => {
            const timeA = new Date(a.last_message_timestamp).getTime();
            const timeB = new Date(b.last_message_timestamp).getTime();
            return sortOrder === "newest" ? timeB - timeA : timeA - timeB;
        });

    const formatSessionDate = (isoString: string) => {
        const d = new Date(isoString);
        if (isToday(d)) return "Today, " + format(d, "h:mm a");
        if (isYesterday(d)) return "Yesterday, " + format(d, "h:mm a");
        return format(d, "MMM d, h:mm a");
    };

    const isNewSession = (isoString: string) => {
        const sessionTime = new Date(isoString).getTime();
        if (!Number.isFinite(sessionTime)) return false;
        return Date.now() - sessionTime <= 24 * 60 * 60 * 1000;
    };

    const sectionTitle = sortOrder === "newest" ? "Recent Conversations" : "All History";

    return (
        <div className="flex flex-col h-full bg-gradient-to-b from-[#0b1220] to-[#0a0f1a]">
            {/* Header */}
            <div className="p-6 pb-5 border-b border-gray-800/90 bg-[#111827]/80 backdrop-blur-md z-10 sticky top-0 shadow-sm">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <h2 className="text-[28px] leading-tight font-medium tracking-tight text-white">Chat History</h2>
                        <p className="text-sm text-gray-400 mt-1">
                            {sessions.length} past conversations
                        </p>
                    </div>

                    <div className="w-full lg:w-auto flex flex-col gap-3 md:flex-row md:items-center">
                        <div className="relative w-full md:w-[440px]">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
                            <Input
                                placeholder="Search past conversations..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="h-11 rounded-lg border-gray-700/90 bg-gray-900/80 pl-9 pr-10 text-white placeholder:text-gray-500 focus-visible:ring-blue-500/60"
                            />
                            {searchQuery && (
                                <button
                                    type="button"
                                    onClick={() => setSearchQuery("")}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-1 text-gray-400 hover:bg-gray-800 hover:text-gray-200 transition-colors"
                                    aria-label="Clear search"
                                >
                                    <X className="h-3.5 w-3.5" />
                                </button>
                            )}
                        </div>

                        <div className="flex items-center gap-2">
                            <label htmlFor="history-sort" className="text-xs uppercase tracking-wide text-gray-400">
                                Sort
                            </label>
                            <select
                                id="history-sort"
                                value={sortOrder}
                                onChange={(e) => setSortOrder(e.target.value as "newest" | "oldest")}
                                className="h-11 rounded-lg border border-gray-700/90 bg-gray-900/80 px-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                            >
                                <option value="newest">Newest</option>
                                <option value="oldest">Oldest</option>
                            </select>
                        </div>
                    </div>
                </div>
            </div>

            {/* List */}
            <div className="flex-1 overflow-y-auto p-6 scroll-smooth custom-scrollbar">
                {isLoading ? (
                    <div className="space-y-3 max-w-4xl mx-auto">
                        {[1, 2, 3, 4].map(i => (
                            <div key={i} className="h-24 bg-gray-900/70 animate-pulse rounded-xl border border-gray-800/80" />
                        ))}
                    </div>
                ) : filteredSessions.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center text-gray-400">
                        <MessageSquare className="h-12 w-12 mb-4 opacity-25" />
                        <h3 className="text-lg font-medium text-white">No conversations found</h3>
                        <p className="text-sm mt-1">Start chatting with the AI to see your history here.</p>
                    </div>
                ) : (
                    <div className="max-w-4xl mx-auto pb-8">
                        <div className="rounded-2xl border border-gray-800/80 bg-[#111827]/55 shadow-sm overflow-hidden">
                            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-800/90">
                                <h3 className="text-sm font-medium text-white">{sectionTitle}</h3>
                                <span className="text-xs text-gray-400">{filteredSessions.length} conversations</span>
                            </div>

                            <div className="divide-y divide-gray-800/80">
                                {filteredSessions.map((session) => {
                                    const normalizedTitle = normalizeTitle(session.title) || "New conversation";
                                    const preview = buildPreview(session.title) || "Open this conversation to continue.";
                                    const isUnread = isNewSession(session.last_message_timestamp);

                                    return (
                                        <Card
                                            key={session.session_id}
                                            className="group cursor-pointer rounded-none border-0 bg-transparent shadow-none transition-transform duration-200 hover:bg-gray-800/80 hover:scale-[1.01]"
                                            onClick={() => onLoadSession(session.session_id)}
                                        >
                                            <div className="px-5 py-4 flex items-center gap-4">
                                                <div className="h-11 w-11 rounded-xl bg-blue-500/15 border border-blue-400/20 flex items-center justify-center flex-shrink-0">
                                                    <MessageSquare className="h-5 w-5 text-blue-300" />
                                                </div>

                                                <div className="min-w-0 flex-1">
                                                    <h4 className="font-medium text-white text-[15px] leading-tight truncate">
                                                        {normalizedTitle}
                                                    </h4>
                                                    <p className="text-sm text-gray-400 mt-1 truncate">
                                                        {preview}
                                                    </p>
                                                </div>

                                                <div className="flex items-center gap-3 flex-shrink-0">
                                                    <div className="text-right">
                                                        <div className="flex items-center justify-end gap-1.5 text-xs text-gray-300">
                                                            <Calendar className="h-3 w-3 text-gray-500" />
                                                            <span>{formatSessionDate(session.last_message_timestamp)}</span>
                                                        </div>
                                                        <div className="mt-1 flex items-center justify-end gap-1.5">
                                                            {isUnread && <span className="h-2 w-2 rounded-full bg-sky-400" aria-label="Unread conversation" />}
                                                            <span className="text-[11px] text-gray-500">{isUnread ? "New" : "Seen"}</span>
                                                        </div>
                                                    </div>
                                                    <ChevronRight className="h-4.5 w-4.5 text-gray-500 transition-transform group-hover:translate-x-0.5 group-hover:text-gray-300" />
                                                </div>
                                            </div>
                                        </Card>
                                    );
                                })}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
