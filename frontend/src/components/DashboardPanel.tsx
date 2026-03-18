import { useEffect, useState, useCallback, useMemo } from "react";
import { format, parseISO } from "date-fns";
import api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PlusCircle, Clock, CheckCircle2, CircleDashed, Calendar, ListTodo, ArrowRight } from "lucide-react";
import { motion } from "framer-motion";
import type { Task } from "./TaskManagerPanel";
import { getMemberColor, getMemberInitials } from "@/lib/team";

export function DashboardPanel({ onNavigateToTasks }: { onNavigateToTasks: () => void }) {
    const [tasks, setTasks] = useState<Task[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    const fetchTasks = useCallback(async () => {
        try {
            const response = await api.get("/api/tasks");
            setTasks(response.data);
        } catch (err) {
            console.error("Failed to fetch dashboard tasks", err);
        } finally {
            setIsLoading(false);
        }
    }, []);

    // Smart polling: only when tab is visible
    useEffect(() => {
        fetchTasks();

        let interval: ReturnType<typeof setInterval>;
        const startPolling = () => {
            interval = setInterval(() => {
                if (!document.hidden) fetchTasks();
            }, 10000);
        };
        const stopPolling = () => clearInterval(interval);

        const handleVisibilityChange = () => {
            if (document.hidden) stopPolling();
            else {
                fetchTasks();
                startPolling();
            }
        };

        startPolling();
        document.addEventListener("visibilitychange", handleVisibilityChange);

        return () => {
            stopPolling();
            document.removeEventListener("visibilitychange", handleVisibilityChange);
        };
    }, [fetchTasks]);

    const metrics = useMemo(() => ({
        total: tasks.length,
        pending: tasks.filter(t => t.status === "Pending").length,
        inProgress: tasks.filter(t => t.status === "In Progress").length,
        completed: tasks.filter(t => t.status === "Completed").length,
    }), [tasks]);

    const recentTasks = useMemo(() => {
        // Assume API returns tasks sorted by created_at desc, take top 5
        return tasks.slice(0, 5);
    }, [tasks]);

    const getStatusBadge = (status: string) => {
        const styles: Record<string, string> = {
            Pending: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
            "In Progress": "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
            Completed: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
        };
        return (
            <Badge className={`${styles[status] ?? "bg-muted text-muted-foreground"} hover:opacity-80 px-2 py-0.5 rounded-full text-[10px] font-medium transition-opacity`}>
                {status}
            </Badge>
        );
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case "Pending": return <CircleDashed className="text-amber-500 w-4 h-4" />;
            case "In Progress": return <Clock className="text-blue-500 w-4 h-4" />;
            case "Completed": return <CheckCircle2 className="text-emerald-500 w-4 h-4" />;
            default: return null;
        }
    };

    return (
        <div className="flex flex-col h-full bg-muted/10 relative overflow-y-auto custom-scrollbar p-6">
            <div className="flex justify-between items-center mb-8">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight text-foreground">Dashboard Overview</h2>
                    <p className="text-sm text-muted-foreground mt-1">Get a bird's-eye view of your workspace.</p>
                </div>
                <Button onClick={onNavigateToTasks} className="bg-primary hover:bg-primary/90 text-primary-foreground shadow-md rounded-xl h-10 px-5 text-sm font-medium transition-all active:scale-95">
                    <PlusCircle className="mr-2 h-4 w-4" /> New Task
                </Button>
            </div>

            {/* Metrics cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                {[
                    { label: "Total Tasks", value: metrics.total, icon: <ListTodo className="h-5 w-5 text-foreground/60" />, accent: "" },
                    { label: "Pending", value: metrics.pending, icon: <CircleDashed className="h-5 w-5 text-amber-500" />, accent: "border-l-amber-500" },
                    { label: "In Progress", value: metrics.inProgress, icon: <Clock className="h-5 w-5 text-blue-500" />, accent: "border-l-blue-500" },
                    { label: "Completed", value: metrics.completed, icon: <CheckCircle2 className="h-5 w-5 text-emerald-500" />, accent: "border-l-emerald-500" },
                ].map((m, i) => (
                    <motion.div key={m.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
                        <Card className={`shadow-sm border-border/40 bg-card rounded-xl hover:shadow-md transition-all border-l-4 ${m.accent || "border-l-primary/30"}`}>
                            <CardContent className="p-5 flex items-center justify-between">
                                <div>
                                    <p className="text-[12px] font-semibold text-muted-foreground uppercase tracking-wider">{m.label}</p>
                                    <p className="text-3xl font-bold text-foreground mt-1">{isLoading ? "-" : m.value}</p>
                                </div>
                                <div className="opacity-80 bg-muted/50 p-3 rounded-xl">{m.icon}</div>
                            </CardContent>
                        </Card>
                    </motion.div>
                ))}
            </div>

            {/* Main Content Area */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Recent Tasks List */}
                <Card className="lg:col-span-2 shadow-sm border-border/40 bg-card rounded-2xl flex flex-col">
                    <CardHeader className="pb-4 border-b border-border/40 flex flex-row items-center justify-between">
                        <div>
                            <CardTitle className="text-lg">Recent Tasks</CardTitle>
                            <CardDescription>The 5 most recently created tasks.</CardDescription>
                        </div>
                        <Button variant="ghost" size="sm" onClick={onNavigateToTasks} className="text-xs text-muted-foreground hover:text-foreground group">
                            View All <ArrowRight className="ml-1 w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
                        </Button>
                    </CardHeader>
                    <CardContent className="p-0 flex-1 flex flex-col">
                        {isLoading ? (
                            <div className="p-6 text-center text-muted-foreground text-sm">Loading tasks...</div>
                        ) : recentTasks.length === 0 ? (
                            <div className="p-12 text-center text-muted-foreground border-border/50 bg-muted/5 flex-1 flex flex-col items-center justify-center">
                                <CircleDashed className="mx-auto h-8 w-8 text-muted-foreground/30 mb-3" />
                                <h3 className="text-sm font-semibold text-foreground">No tasks to show</h3>
                                <p className="text-xs mt-1">Get started by creating your first task.</p>
                            </div>
                        ) : (
                            <div className="divide-y divide-border/40 flex-1">
                                {recentTasks.map(task => (
                                    <div key={task.id} className="p-4 hover:bg-muted/30 transition-colors flex items-center gap-4 group">
                                        <div className="bg-muted p-2 rounded-lg flex-shrink-0">
                                            {getStatusIcon(task.status)}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <h4 className="text-sm font-semibold text-foreground truncate group-hover:text-primary transition-colors">{task.title}</h4>
                                            <div className="flex items-center gap-3 mt-1.5 text-[11px] text-muted-foreground">
                                                <span className="flex items-center gap-1 font-medium">
                                                    <div className={`w-3.5 h-3.5 rounded-full ${getMemberColor(task.assignee)} flex items-center justify-center text-[7px] font-bold text-white`}>
                                                        {getMemberInitials(task.assignee).charAt(0)}
                                                    </div>
                                                    {task.assignee}
                                                </span>
                                                {task.due_date && (
                                                    <span className="flex items-center gap-1 font-medium">
                                                        <Calendar className="w-3 h-3 opacity-70" />
                                                        {format(parseISO(task.due_date), "MMM d")}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                        <div className="flex-shrink-0">
                                            {getStatusBadge(task.status)}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Info Panel / Call to Action */}
                <Card className="shadow-sm border-border/40 bg-card rounded-2xl">
                    <CardHeader className="pb-3 border-b border-border/40">
                        <CardTitle className="text-lg">Productivity Hub</CardTitle>
                    </CardHeader>
                    <CardContent className="p-5">
                        <div className="space-y-4">
                            <div className="bg-primary/5 border border-primary/20 rounded-xl p-4">
                                <h4 className="text-sm font-semibold text-primary mb-1">Stay on Track</h4>
                                <p className="text-xs text-muted-foreground leading-relaxed">
                                    Use the AI Chat assistant to naturally create tasks simply by asking.
                                    Or manually add tasks right here to keep your team aligned.
                                </p>
                            </div>
                            <div className="bg-muted/30 rounded-xl p-4 border border-border/40">
                                <h4 className="text-sm font-semibold text-foreground mb-1">Live Updates</h4>
                                <p className="text-xs text-muted-foreground leading-relaxed">
                                    Your dashboard updates in real-time. Team members will see your changes instantly.
                                </p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
