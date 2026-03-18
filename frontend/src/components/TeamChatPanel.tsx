import React, { useState, useEffect, useRef } from 'react';
import { getUser } from '../lib/auth';
import { TEAM_MEMBERS, getMemberColor, getMemberInitials } from '../lib/team';
import { Send, MessageSquare } from 'lucide-react';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Avatar, AvatarFallback } from './ui/avatar';

interface TeamMessage {
    id: number | string;
    sender_id: string;
    receiver_id: string;
    content: string;
    timestamp: string;
    is_read: boolean;
}

const IST_TIMEZONE = 'Asia/Kolkata';
const HAS_EXPLICIT_TZ = /(?:Z|[+-]\d{2}:\d{2})$/i;

const parseUtcTimestamp = (rawTimestamp: string): Date => {
    const normalized = rawTimestamp.includes(' ') ? rawTimestamp.replace(' ', 'T') : rawTimestamp;
    const withTimezone = HAS_EXPLICIT_TZ.test(normalized) ? normalized : `${normalized}Z`;
    return new Date(withTimezone);
};

const formatTimeInIST = (rawTimestamp: string): string => {
    return new Intl.DateTimeFormat('en-GB', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
        timeZone: IST_TIMEZONE
    }).format(parseUtcTimestamp(rawTimestamp));
};

const formatDateInIST = (rawTimestamp: string): string => {
    return new Intl.DateTimeFormat('en-IN', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        timeZone: IST_TIMEZONE
    }).format(parseUtcTimestamp(rawTimestamp));
};

export function TeamChatPanel() {
    const user = getUser();
    const token = user?.token;
    const [messages, setMessages] = useState<TeamMessage[]>([]);
    const [newMessage, setNewMessage] = useState('');
    const [selectedUser, setSelectedUser] = useState<string | null>(null);
    const [unreadCounts, setUnreadCounts] = useState<Record<string, number>>({});
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // List of users avoiding current logged in user
    const chatUsers = TEAM_MEMBERS.filter(m => m.name.toLowerCase() !== user?.displayName.toLowerCase());

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    const fetchMessages = async (targetId: string) => {
        if (!token) return;
        try {
            const response = await fetch(`http://localhost:8000/api/chat/messages/${encodeURIComponent(targetId)}`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            if (response.ok) {
                const data = await response.json();
                setMessages(
                    [...data].sort((a, b) => parseUtcTimestamp(a.timestamp).getTime() - parseUtcTimestamp(b.timestamp).getTime())
                );
                scrollToBottom();
            }
        } catch (error) {
            console.error('Failed to fetch messages:', error);
        }
    };

    const fetchUnreadCounts = async () => {
        if (!token) return;
        try {
            const response = await fetch('http://localhost:8000/api/team-chat/unread', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                setUnreadCounts(data);
            }
        } catch (error) {
            console.error('Failed to fetch unread counts:', error);
        }
    };

    const markAsRead = async (targetId: string) => {
        if (!token) return;
        try {
            await fetch(`http://localhost:8000/api/team-chat/${encodeURIComponent(targetId)}/read`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            setUnreadCounts(prev => ({ ...prev, [targetId.toLowerCase()]: 0 }));
        } catch (error) {
            console.error('Failed to mark read:', error);
        }
    };

    useEffect(() => {
        if (token) {
            fetchUnreadCounts();
        }
    }, [token]);

    useEffect(() => {
        if (selectedUser && token) {
            fetchMessages(selectedUser);
            markAsRead(selectedUser);

            // Add polling fallback as requested
            const interval = setInterval(() => {
                fetchMessages(selectedUser);
            }, 5000);
            return () => clearInterval(interval);
        }
    }, [selectedUser, token]);

    useEffect(() => {
        // SSE Listener
        if (!token) return;
        const source = new EventSource(`http://localhost:8000/api/events?token=${token}`);

        source.onmessage = (event) => {
            const payload = JSON.parse(event.data);
            if (payload.type === 'team_message') {
                const msg = payload.payload as TeamMessage;
                const selectedUsername = selectedUser?.toLowerCase();
                const currentUsername = user?.username?.toLowerCase();
                const messageSender = msg.sender_id.toLowerCase();
                const messageReceiver = msg.receiver_id.toLowerCase();

                // If message is for currently open chat
                if (
                    selectedUsername &&
                    currentUsername &&
                    ((messageSender === selectedUsername && messageReceiver === currentUsername) ||
                        (messageSender === currentUsername && messageReceiver === selectedUsername))
                ) {
                    setMessages(prev => {
                        // Avoid duplicates if polling also fetched it
                        if (prev.some(m => m.id === msg.id)) return prev;
                        return [...prev, msg].sort((a, b) => parseUtcTimestamp(a.timestamp).getTime() - parseUtcTimestamp(b.timestamp).getTime());
                    });
                    if (messageReceiver === currentUsername) {
                        markAsRead(selectedUsername);
                    }
                    scrollToBottom();
                } else if (currentUsername && messageReceiver === currentUsername) {
                    // Update unread count
                    setUnreadCounts(prev => ({
                        ...prev,
                        [messageSender]: (prev[messageSender] || 0) + 1
                    }));
                }
            }
        };

        return () => source.close();
    }, [token, selectedUser, user]);

    const handleSendMessage = async (e: React.FormEvent) => {
        e.preventDefault();
        const content = newMessage.trim();
        if (!content || !selectedUser || !user) return;
        const selectedUsername = selectedUser.toLowerCase();

        // Optimistic UI update
        const tempId = `temp-${Date.now()}`;
        const optimisticMsg: TeamMessage = {
            id: tempId,
            sender_id: user.username.toLowerCase(),
            receiver_id: selectedUsername,
            content: content,
            timestamp: new Date().toISOString(),
            is_read: false
        };

        setMessages(prev => [...prev, optimisticMsg]);
        setNewMessage('');
        scrollToBottom();

        try {
            const response = await fetch('http://localhost:8000/api/chat/send', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    receiver_id: selectedUsername,
                    content: content
                })
            });

            if (response.ok) {
                const confirmedMsg = await response.json();
                // Replace optimistic message with confirmed one to get real ID
                setMessages(prev => prev.map(m => m.id === tempId ? confirmedMsg : m));
            } else {
                // If failed, remove optimistic message or show error
                setMessages(prev => prev.filter(m => m.id !== tempId));
                console.error('Failed to send message');
            }
        } catch (error) {
            setMessages(prev => prev.filter(m => m.id !== tempId));
            console.error('Failed to send message:', error);
        }
    };

    // Auto sort unique dates
    const groupMessagesByDate = (msgs: TeamMessage[]) => {
        const groups: Record<string, TeamMessage[]> = {};
        msgs.forEach(msg => {
            const date = formatDateInIST(msg.timestamp);
            if (!groups[date]) groups[date] = [];
            groups[date].push(msg);
        });
        return groups;
    };

    return (
        <div className="flex h-full bg-background overflow-hidden relative">
            {/* Sidebar Users List */}
            <div className="w-1/3 max-w-sm bg-card border-r border-border overflow-y-auto">
                <div className="p-4 border-b border-border sticky top-0 bg-card/95 backdrop-blur z-10">
                    <h2 className="font-semibold text-lg text-foreground flex items-center gap-2">
                        <MessageSquare className="w-5 h-5" /> Team Chat
                    </h2>
                </div>
                <div className="p-3 flex flex-col gap-1">
                    {chatUsers.map(member => (
                        <button
                            key={member.id}
                            onClick={() => setSelectedUser(member.username)}
                            className={`flex items-center justify-between p-3 rounded-xl transition-all group ${selectedUser === member.username ? 'bg-primary/10 border border-primary/20' : 'hover:bg-muted/50 border border-transparent'
                                }`}
                        >
                            <div className="flex items-center gap-3">
                                <Avatar className="h-10 w-10 border border-slate-200 shadow-sm">
                                    <AvatarFallback className={`${member.color} text-white font-medium`}>
                                        {member.initials}
                                    </AvatarFallback>
                                </Avatar>
                                <div className="text-left">
                                    <p className="font-medium text-foreground text-sm leading-tight group-hover:text-primary transition-colors">{member.name}</p>
                                    <p className="text-xs text-muted-foreground mt-0.5 group-hover:text-primary/80 transition-colors uppercase tracking-tight">{member.role}</p>
                                </div>
                            </div>
                            {unreadCounts[member.username.toLowerCase()] > 0 && (
                                <Badge className="bg-rose-500 hover:bg-rose-600 rounded-full h-5 w-5 p-0 flex items-center justify-center">
                                    {unreadCounts[member.username.toLowerCase()]}
                                </Badge>
                            )}
                        </button>
                    ))}
                </div>
            </div>

            {/* Chat Area */}
            <div className="flex-1 flex flex-col bg-slate-50 h-full relative">
                {selectedUser ? (
                    <>
                        <div className="p-4 px-6 bg-card border-b border-border shadow-sm relative z-10 flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <Avatar className="h-9 w-9">
                                    <AvatarFallback className={`${getMemberColor(selectedUser)} text-white`}>
                                        {getMemberInitials(selectedUser)}
                                    </AvatarFallback>
                                </Avatar>
                                <div>
                                    <h3 className="font-semibold text-foreground capitalize">{selectedUser}</h3>
                                </div>
                            </div>
                        </div>

                        <div className="flex-1 overflow-y-auto p-6 space-y-6">
                            {Object.entries(groupMessagesByDate(messages)).map(([date, dateMessages]) => (
                                <div key={date}>
                                    <div className="flex justify-center mb-4">
                                        <Badge variant="outline" className="bg-card/50 text-foreground font-medium rounded-full px-3">
                                            {date}
                                        </Badge>
                                    </div>
                                    <div className="space-y-4">
                                        {dateMessages.map(msg => {
                                            const isMe = msg.sender_id === user?.username;
                                            return (
                                                <div key={msg.id} className={`flex ${isMe ? 'justify-end' : 'justify-start'}`}>
                                                    <div className={`max-w-[75%] rounded-2xl px-4 py-2.5 ${isMe ? 'bg-primary text-primary-foreground rounded-br-sm shadow-sm' : 'bg-card border border-border text-card-foreground rounded-bl-sm shadow-sm'}`}>
                                                        <p className="text-[15px] whitespace-pre-wrap">{msg.content}</p>
                                                        <span className={`text-[10px] mt-1 block font-medium ${isMe ? 'opacity-80' : 'text-muted-foreground'}`}>
                                                            {formatTimeInIST(msg.timestamp)}
                                                        </span>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            ))}
                            <div ref={messagesEndRef} />
                        </div>

                        <div className="p-4 bg-card border-t border-border">
                            <form onSubmit={handleSendMessage} className="flex gap-3 max-w-4xl mx-auto">
                                <input
                                    type="text"
                                    value={newMessage}
                                    onChange={(e) => setNewMessage(e.target.value)}
                                    placeholder="Type your message..."
                                    className="flex-1 bg-slate-100 dark:bg-slate-800 border-none rounded-full px-5 py-2.5 focus:ring-2 focus:ring-indigo-500 focus:bg-white dark:focus:bg-slate-700 transition-colors text-slate-900 dark:text-white placeholder:text-slate-400"
                                />
                                <Button
                                    type="submit"
                                    disabled={!newMessage.trim()}
                                    className="rounded-full w-11 h-11 p-0 bg-indigo-600 hover:bg-indigo-700 shadow-md group border-none"
                                >
                                    <Send className="h-4 w-4 ml-0.5 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                                </Button>
                            </form>
                        </div>
                    </>
                ) : (
                    <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground p-8 text-center space-y-4">
                        <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-2">
                            <MessageSquare className="w-8 h-8 text-muted-foreground/50" />
                        </div>
                        <h3 className="text-xl font-medium text-foreground">Your Messages</h3>
                        <p className="max-w-sm text-sm">Select a colleague from the sidebar to view your private conversation or start a new one.</p>
                    </div>
                )}
            </div>
        </div>
    );
}
