import { TEAM_MEMBERS } from "@/lib/team";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

export function TeamSidebar() {
    return (
        <div className="w-full h-full bg-card flex flex-col">
            <div className="p-6 border-b border-border/50 bg-muted/20">
                <h2 className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Team Directory</h2>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-2">
                {TEAM_MEMBERS.map(member => (
                    <div key={member.id} className="flex items-center gap-4 group px-3 py-2 rounded-xl hover:bg-muted/50 transition-colors cursor-pointer">
                        <Avatar className="h-11 w-11 border border-border shadow-sm group-hover:scale-105 transition-transform">
                            <AvatarFallback className={`${member.color} text-slate-900 font-semibold shadow-inner`}>
                                {member.initials}
                            </AvatarFallback>
                        </Avatar>
                        <div className="flex flex-col">
                            <span className="text-sm font-semibold text-foreground group-hover:text-primary transition-colors uppercase tracking-tight">{member.name}</span>
                            <span className="text-xs text-muted-foreground font-medium group-hover:text-foreground transition-colors">{member.role}</span>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
