import { useState } from "react";
import { TEAM_MEMBERS } from "@/lib/team";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Mail, Phone, Search, ExternalLink, X, Briefcase } from "lucide-react";

interface TeamDirectoryPanelProps {
    onViewMemberTasks?: (memberName: string) => void;
}

export function TeamDirectoryPanel({ onViewMemberTasks }: TeamDirectoryPanelProps) {
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedMember, setSelectedMember] = useState<string | null>(null);

    const filteredMembers = TEAM_MEMBERS.filter(m => {
        const q = searchQuery.toLowerCase();
        return m.name.toLowerCase().includes(q) ||
            m.role.toLowerCase().includes(q) ||
            m.department.toLowerCase().includes(q);
    });

    const handleMemberClick = (memberName: string) => {
        if (selectedMember === memberName) {
            setSelectedMember(null);
        } else {
            setSelectedMember(memberName);
        }
    };

    return (
        <div className="flex flex-col h-full bg-muted/10 relative">
            {/* Header */}
            <div className="p-6 pb-4 border-b border-border/50 bg-card/80 backdrop-blur-md z-10 sticky top-0 shadow-sm">
                <div className="flex justify-between items-start mb-4">
                    <div>
                        <h2 className="text-2xl font-bold tracking-tight text-foreground">Team Directory</h2>
                        <p className="text-sm text-muted-foreground mt-1">
                            {TEAM_MEMBERS.length} members • Click a card to view their tasks
                        </p>
                    </div>
                    <Badge variant="secondary" className="text-xs font-medium px-3 py-1 rounded-full">
                        {filteredMembers.length} shown
                    </Badge>
                </div>

                {/* Search */}
                <div className="relative max-w-sm">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search by name, role, or department..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="pl-9 h-9 rounded-lg text-sm bg-background border-border/50"
                        aria-label="Search team members"
                    />
                    {searchQuery && (
                        <button
                            onClick={() => setSearchQuery("")}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                            aria-label="Clear search"
                        >
                            <X size={14} />
                        </button>
                    )}
                </div>
            </div>

            {/* Members grid */}
            <div className="flex-1 overflow-y-auto px-6 py-5 h-full scroll-smooth custom-scrollbar">
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 max-w-7xl mx-auto">
                    {filteredMembers.map(member => {
                        const isSelected = selectedMember === member.name;
                        return (
                            <Card
                                key={member.id}
                                className={`border hover:shadow-lg transition-all rounded-xl group overflow-hidden bg-card cursor-pointer hover:-translate-y-0.5 duration-200 ${isSelected
                                    ? "border-primary/40 shadow-md ring-2 ring-primary/20"
                                    : "border-border/30 hover:border-primary/20 shadow-sm"
                                    }`}
                                onClick={() => handleMemberClick(member.name)}
                                role="button"
                                tabIndex={0}
                                aria-label={`View ${member.name}'s profile`}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter" || e.key === " ") handleMemberClick(member.name);
                                }}
                            >
                                <CardContent className="p-5">
                                    <div className="flex items-center gap-4 mb-4">
                                        <Avatar className={`h-14 w-14 border-2 ${isSelected ? "border-primary/30" : "border-background"} shadow-sm group-hover:scale-105 transition-transform`}>
                                            <AvatarFallback className={`${member.color} text-white font-bold text-lg shadow-inner`}>
                                                {member.initials}
                                            </AvatarFallback>
                                        </Avatar>
                                        <div className="flex-1 min-w-0">
                                            <h3 className="font-bold text-base text-foreground group-hover:text-primary transition-colors truncate">
                                                {member.name}
                                            </h3>
                                            <p className="text-sm font-medium text-muted-foreground group-hover:text-foreground transition-colors uppercase tracking-tight">{member.role}</p>
                                            <div className="flex items-center gap-1.5 mt-1">
                                                <Briefcase size={11} className="text-muted-foreground group-hover:text-primary/70 dark:group-hover:text-white/70 transition-colors" />
                                                <span className="text-xs text-muted-foreground group-hover:text-foreground/80 dark:group-hover:text-slate-100 transition-colors">{member.department}</span>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="space-y-2 pt-3 border-t border-border/40">
                                        <div className="flex items-center gap-2.5 text-xs text-muted-foreground hover:text-foreground transition-colors group/link">
                                            <div className="w-7 h-7 rounded-full bg-muted flex items-center justify-center group-hover/link:bg-primary/10 transition-colors flex-shrink-0">
                                                <Mail className="h-3.5 w-3.5 group-hover/link:text-primary transition-colors" />
                                            </div>
                                            <span className="truncate">{member.name.toLowerCase().replace(" ", ".")}@smartbridge.com</span>
                                        </div>
                                        <div className="flex items-center gap-2.5 text-xs text-muted-foreground hover:text-foreground transition-colors group/link">
                                            <div className="w-7 h-7 rounded-full bg-muted flex items-center justify-center group-hover/link:bg-primary/10 transition-colors flex-shrink-0">
                                                <Phone className="h-3.5 w-3.5 group-hover/link:text-primary transition-colors" />
                                            </div>
                                            <span>+91 98765 4321{member.id}</span>
                                        </div>
                                    </div>

                                    {/* "View Tasks" action */}
                                    {isSelected && onViewMemberTasks && (
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                onViewMemberTasks(member.name);
                                            }}
                                            className="mt-4 w-full flex items-center justify-center gap-2 py-2.5 bg-primary/5 hover:bg-primary/10 text-primary text-xs font-semibold rounded-lg transition-colors border border-primary/10"
                                        >
                                            <ExternalLink size={13} />
                                            View {member.name.split(" ")[0]}'s Tasks
                                        </button>
                                    )}
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>

                {filteredMembers.length === 0 && (
                    <div className="text-center p-16 text-muted-foreground mt-4">
                        <Search className="mx-auto h-10 w-10 text-muted-foreground/30 mb-3" />
                        <h3 className="text-base font-semibold text-foreground">No members found</h3>
                        <p className="text-sm mt-1">Try searching with a different term.</p>
                    </div>
                )}
            </div>
        </div>
    );
}
