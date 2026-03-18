import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { LogOut, User, ChevronDown, Menu, Shield, Zap } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "@/components/ui/sheet";
import { NavigationSidebar, type TabId } from "./NavigationSidebar";
import { type AuthUser } from "@/lib/auth";

interface NavbarProps {
    activeTab: TabId;
    setActiveTab: (tab: TabId) => void;
    user: AuthUser;
    onLogout: () => void;
}

export function Navbar({ activeTab, setActiveTab, user, onLogout }: NavbarProps) {
    const initials = user.displayName.slice(0, 2).toUpperCase();
    const roleLabel = user.role === "admin" ? "Workspace Owner" : "Team Member";

    return (
        <header
            className="flex items-center justify-between px-4 md:px-5 py-3 bg-[#001f3f] text-white shadow-lg backdrop-blur-sm z-20 sticky top-0 dark:bg-slate-900/95 border-b border-white/5"
            role="banner"
        >
            <div className="flex items-center gap-3">
                <Sheet>
                    <SheetTrigger asChild>
                        <button
                            className="md:hidden p-2 hover:bg-white/10 rounded-lg transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
                            aria-label="Open navigation menu"
                        >
                            <Menu className="h-5 w-5 text-white" />
                        </button>
                    </SheetTrigger>
                    <SheetContent side="left" className="w-[260px] p-0 border-r-0 bg-transparent block" aria-describedby="navigation-menu">
                        <SheetTitle className="sr-only">Navigation Menu</SheetTitle>
                        <NavigationSidebar activeTab={activeTab} setActiveTab={setActiveTab} className="rounded-r-xl shadow-xl" />
                    </SheetContent>
                </Sheet>

                <div className="flex items-center gap-2.5">
                    <div className="bg-white/10 backdrop-blur-sm p-1.5 rounded-lg flex items-center justify-center border border-white/10">
                        <Zap className="w-5 h-5 text-blue-300" />
                    </div>
                    <div className="hidden sm:block">
                        <h1 className="text-sm font-bold tracking-tight leading-none">SMARTBRIDGE</h1>
                        <p className="text-[10px] text-white/50 font-medium tracking-wider">AI AGENT PLATFORM</p>
                    </div>
                </div>
            </div>

            <div className="flex items-center gap-2 md:gap-3">
                <ThemeToggle />

                <div className="w-px h-6 bg-white/10 hidden md:block" />

                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <button
                            className="flex items-center gap-2.5 hover:bg-white/10 p-1.5 pr-3 rounded-xl transition-all outline-none focus-visible:ring-2 focus-visible:ring-white/50"
                            aria-label="User menu"
                        >
                            <Avatar className="h-8 w-8 border-2 border-white/15 shadow-sm">
                                <AvatarFallback className="bg-blue-500/80 text-white text-xs font-semibold">{initials}</AvatarFallback>
                            </Avatar>
                            <div className="hidden md:flex flex-col items-start leading-tight">
                                <span className="font-medium text-sm leading-none">{user.displayName}</span>
                                <span className="text-[10px] text-white/50 flex items-center gap-1 mt-0.5">
                                    {user.role === "admin" && <Shield size={9} />}
                                    {roleLabel}
                                </span>
                            </div>
                            <ChevronDown className="h-3.5 w-3.5 text-white/50 hidden md:block" />
                        </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-52 mt-1 border-border/50 shadow-xl rounded-xl overflow-hidden p-1">
                        <DropdownMenuItem className="cursor-pointer py-2.5 rounded-lg">
                            <User className="mr-2 h-4 w-4 text-muted-foreground" />
                            <span className="font-medium text-sm">Profile Settings</span>
                        </DropdownMenuItem>
                        <div className="h-px bg-border/50 my-1" />
                        <DropdownMenuItem
                            className="cursor-pointer py-2.5 text-destructive focus:bg-destructive/10 focus:text-destructive rounded-lg"
                            onClick={onLogout}
                        >
                            <LogOut className="mr-2 h-4 w-4" />
                            <span className="font-medium text-sm">Logout</span>
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>
        </header>
    );
}
