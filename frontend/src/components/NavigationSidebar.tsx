import {
    LayoutDashboard,
    MessageSquare,
    CheckSquare,
    BookOpen,
    FileSearch,
    Database,
    Github,
    FolderKanban,
    Slack,
    Settings
} from "lucide-react";


export type TabId =
    | "dashboard"
    | "chat"
    | "knowledge"
    | "documentanalysis"
    | "sqlagent"
    | "githubagent"
    | "driveagent"
    | "slackagent"
    | "history"

    | "tasks"
    | "settings";

interface NavigationSidebarProps {
    activeTab: TabId;
    setActiveTab: (tab: TabId) => void;
    className?: string;
    onNavigate?: () => void;
}

export function NavigationSidebar({ activeTab, setActiveTab, className = "", onNavigate }: NavigationSidebarProps) {
    const navItems = [
        { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
        { id: "chat", label: "Standard Chat", icon: MessageSquare },
        { id: "knowledge", label: "Knowledge Base RAG", icon: BookOpen },
        { id: "documentanalysis", label: "Document Analysis", icon: FileSearch },
        { id: "sqlagent", label: "SQL Agent", icon: Database },
        { id: "githubagent", label: "GitHub Agent", icon: Github },
        { id: "driveagent", label: "Google Drive Agent", icon: FolderKanban },
        { id: "slackagent", label: "Slack Agent", icon: Slack },
    ];


    const futureItems = [
        { id: "history", label: "History", icon: BookOpen },
        { id: "tasks", label: "Task Manager", icon: CheckSquare },
        { id: "settings", label: "Settings", icon: Settings },
    ];

    const renderNavItems = (items: typeof navItems) => (
        items.map(item => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
                <button
                    key={item.id}
                    onClick={() => {
                        setActiveTab(item.id as TabId);
                        if (onNavigate) onNavigate();
                    }}
                    className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg transition-all duration-200 text-left font-medium text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 ${isActive
                        ? "bg-primary text-primary-foreground shadow-sm"
                        : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                        }`}
                    aria-label={`Navigate to ${item.label}`}
                    aria-current={isActive ? "page" : undefined}
                >
                    <Icon className={`h-[18px] w-[18px] flex-shrink-0 ${isActive ? "text-primary-foreground" : "text-muted-foreground"}`} />
                    <span className="truncate">{item.label}</span>
                </button>
            );
        })
    );

    return (
        <nav className={`w-full h-full flex flex-col bg-card border-r border-border/40 ${className}`} aria-label="Main navigation">
            <div className="flex-1 overflow-y-auto p-3.5 space-y-6 mt-3 md:mt-0 custom-scrollbar">
                <div>
                    <h3 className="px-3.5 text-[10px] font-semibold text-muted-foreground/70 uppercase tracking-[0.15em] mb-2.5">
                        Main Menu
                    </h3>
                    <div className="space-y-1" role="list">
                        {renderNavItems(navItems)}
                    </div>
                </div>

                <div>
                    <h3 className="px-3.5 text-[10px] font-semibold text-muted-foreground/70 uppercase tracking-[0.15em] mb-2.5">
                        Workspace
                    </h3>
                    <div className="space-y-1" role="list">
                        {renderNavItems(futureItems)}
                    </div>
                </div>
            </div>

            <div className="p-3.5 border-t border-border/30 mt-auto">
                <div className="bg-muted/20 rounded-lg p-3 border border-border/30 text-center">
                    <p className="text-[10px] text-muted-foreground/80 font-medium">Smartbridge Platform v2.1</p>
                    <p className="text-[9px] text-muted-foreground/50 mt-0.5">Internal Use Only</p>
                </div>
            </div>
        </nav>
    );
}
