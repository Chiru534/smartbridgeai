import { useEffect, useState, useCallback, useMemo } from "react";
import { format, parseISO } from "date-fns";
import api from "@/lib/api";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select as UISelect, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { TEAM_MEMBERS, getMemberColor, getMemberInitials } from "@/lib/team";
import type { AuthUser } from "@/lib/auth";
import { PlusCircle, Clock, CheckCircle2, CircleDashed, Calendar, Search, X, MessageSquare, Pencil, Trash2, Paperclip, ExternalLink } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";

export type Task = {
    id: number;
    title: string;
    description: string | null;
    assignee: string;
    due_date: string | null;
    status: string;
    created_at: string;
    updated_at: string;
    comments?: any[];
    attachment_filename?: string | null;
    attachment_url?: string | null;
};

// Skeleton loader for tasks
function TaskSkeleton() {
    return (
        <div className="grid gap-4 max-w-5xl">
            {[1, 2, 3, 4].map(i => (
                <div key={i} className="bg-card border border-border/30 rounded-2xl p-5 flex items-center gap-4 animate-skeleton">
                    <div className="w-10 h-10 rounded-xl bg-muted" />
                    <div className="flex-1 space-y-2">
                        <div className="h-4 w-48 bg-muted rounded-md" />
                        <div className="h-3 w-32 bg-muted/60 rounded-md" />
                    </div>
                    <div className="h-7 w-20 bg-muted rounded-full" />
                </div>
            ))}
        </div>
    );
}

export function TaskManagerPanel({ user, filterAssignee }: { user: AuthUser; filterAssignee?: string }) {
    const [tasks, setTasks] = useState<Task[]>([]);
    const [filter, setFilter] = useState("All");
    const [searchQuery, setSearchQuery] = useState("");
    const [isLoadingTasks, setIsLoadingTasks] = useState(true);

    // New task dialog
    const [isNewTaskOpen, setIsNewTaskOpen] = useState(false);
    const [newTaskTitle, setNewTaskTitle] = useState("");
    const [newTaskDesc, setNewTaskDesc] = useState("");
    const [newTaskAssignee, setNewTaskAssignee] = useState("");
    const [newTaskDue, setNewTaskDue] = useState("");
    const [newTaskAttachment, setNewTaskAttachment] = useState<File | null>(null);

    // Edit task dialog
    const [editTask, setEditTask] = useState<Task | null>(null);
    const [editTitle, setEditTitle] = useState("");
    const [editDesc, setEditDesc] = useState("");
    const [editAssignee, setEditAssignee] = useState("");
    const [editDue, setEditDue] = useState("");
    const [editStatus, setEditStatus] = useState("");
    const [editComment, setEditComment] = useState("");
    const [editTaskAttachment, setEditTaskAttachment] = useState<File | null>(null);
    const [isSaving, setIsSaving] = useState(false);

    const fetchTasks = useCallback(async (showLoading = false) => {
        if (showLoading) setIsLoadingTasks(true);
        try {
            const endpoint = filterAssignee ? `/api/tasks?assignee=${encodeURIComponent(filterAssignee)}` : "/api/tasks";
            const response = await api.get(endpoint);
            setTasks(response.data);
        } catch (err: any) {
            console.error(err);
            toast.error(err.response?.data?.detail || "Failed to load tasks.");
        } finally {
            if (showLoading) setIsLoadingTasks(false);
        }
    }, [filterAssignee]);

    const handleCreateTask = async () => {
        if (!newTaskTitle || !newTaskAssignee) return;
        setIsSaving(true);
        try {
            let attachmentUrl = null;
            let attachmentFilename = null;

            if (newTaskAttachment) {
                const formData = new FormData();
                formData.append("file", newTaskAttachment);
                const uploadRes = await api.post("/api/upload_attachment", formData, {
                    headers: { "Content-Type": "multipart/form-data" }
                });
                attachmentUrl = uploadRes.data.url;
                attachmentFilename = uploadRes.data.filename;
            }

            const taskData = {
                title: newTaskTitle.trim(),
                description: newTaskDesc.trim() || null,
                assignee: newTaskAssignee,
                due_date: newTaskDue ? new Date(newTaskDue).toISOString() : null,
                status: "Pending",
                attachment_filename: attachmentFilename,
                attachment_url: attachmentUrl
            };

            const response = await api.post('/api/tasks', taskData);
            setTasks(prev => [response.data, ...prev]);

            setIsNewTaskOpen(false);
            setNewTaskTitle("");
            setNewTaskDesc("");
            setNewTaskAssignee("");
            setNewTaskDue("");
            setNewTaskAttachment(null);
            toast.success("Task created", { description: `"${newTaskTitle}" assigned to ${newTaskAssignee}` });
        } catch {
            toast.error("Failed to create task");
        } finally {
            setIsSaving(false);
        }
    };

    const handleUpdateTask = async () => {
        if (!editTask) return;
        setIsSaving(true);
        try {
            let updatedTask = editTask;
            let attachmentUrl = editTask.attachment_url;
            let attachmentFilename = editTask.attachment_filename;

            if (editTaskAttachment) {
                const formData = new FormData();
                formData.append("file", editTaskAttachment);
                const uploadRes = await api.post("/api/upload_attachment", formData, {
                    headers: { "Content-Type": "multipart/form-data" }
                });
                attachmentUrl = uploadRes.data.url;
                attachmentFilename = uploadRes.data.filename;
            }

            const taskData: any = {
                title: editTitle.trim(),
                description: editDesc.trim(),
                assignee: editAssignee,
                due_date: editDue ? new Date(editDue).toISOString() : null,
                status: editStatus,
                attachment_filename: attachmentFilename,
                attachment_url: attachmentUrl
            };

            const response = await api.put(`/api/tasks/${editTask.id}`, taskData);
            updatedTask = response.data;

            if (editComment.trim()) {
                const commentRes = await api.post(`/api/tasks/${editTask.id}/comments`, {
                    author_name: user?.displayName || "Unknown User",
                    comment: editComment.trim()
                });

                updatedTask.comments = [commentRes.data, ...(updatedTask.comments || [])];
                toast.success("Comment added");
            }

            setTasks(prev => prev.map(t => t.id === editTask.id ? updatedTask : t));
            setEditTask(null);
            setEditComment(""); // clear comment input
            toast.success("Task updated");
        } catch {
            toast.error("Failed to update task");
        } finally {
            setIsSaving(false);
        }
    };

    const handleDeleteTask = async (taskId: number, e?: React.MouseEvent) => {
        if (e) {
            e.stopPropagation();
            e.preventDefault();
        }
        if (!window.confirm("Are you sure you want to delete this task? This action cannot be undone.")) return;

        try {
            await api.delete(`/api/tasks/${taskId}`);
            setTasks(prev => prev.filter(t => t.id !== taskId));
            if (editTask?.id === taskId) {
                setEditTask(null);
            }
            toast.success("Task deleted successfully");
        } catch {
            toast.error("Failed to delete task");
        }
    };

    const openEditModal = (task: Task) => {
        setEditTask(task);
        setEditTitle(task.title);
        setEditDesc(task.description ?? "");
        setEditAssignee(task.assignee);
        setEditStatus(task.status);
        setEditDue(task.due_date ? task.due_date.split("T")[0] : "");
        setEditComment("");
        setEditTaskAttachment(null);
    };

    // Real-Time Updates (SSE)
    useEffect(() => {
        fetchTasks(true); // Initial fetch

        const token = user.token || localStorage.getItem("token");
        if (!token) return;

        const eventSource = new EventSource(`http://localhost:8000/api/events?token=${token}`);

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === "task_created") {
                    setTasks(prev => {
                        if (prev.find(t => t.id === data.payload.id)) return prev;
                        return [data.payload, ...prev];
                    });
                } else if (data.type === "task_updated") {
                    setTasks(prev => prev.map(t => t.id === data.payload.id ? data.payload : t));
                    setEditTask(prev => prev?.id === data.payload.id ? data.payload : prev);
                } else if (data.type === "task_deleted") {
                    setTasks(prev => prev.filter(t => t.id !== data.payload.task_id));
                    setEditTask(prev => prev?.id === data.payload.task_id ? null : prev);
                }
            } catch (err) {
                console.error("SSE parse error", err);
            }
        };

        eventSource.onerror = (err) => {
            console.error("SSE connection error", err);
        };

        // Re-fetch everything if tab becomes visible (fallback)
        const handleVisibilityChange = () => {
            if (!document.hidden) fetchTasks();
        };
        document.addEventListener("visibilitychange", handleVisibilityChange);

        return () => {
            eventSource.close();
            document.removeEventListener("visibilitychange", handleVisibilityChange);
        };
    }, [fetchTasks, user.token]);

    // Expose fetchTasks for cross-component triggers
    useEffect(() => {
        (window as any).refreshTasks = fetchTasks;
    }, [fetchTasks]);

    // Filter + search
    const filteredTasks = useMemo(() => {
        let result = tasks;
        if (filter !== "All") result = result.filter(t => t.status === filter);
        if (searchQuery.trim()) {
            const q = searchQuery.toLowerCase();
            result = result.filter(t =>
                t.title.toLowerCase().includes(q) ||
                t.assignee.toLowerCase().includes(q) ||
                (t.description && t.description.toLowerCase().includes(q))
            );
        }
        return result;
    }, [tasks, filter, searchQuery]);

    const getStatusBadge = (status: string) => {
        const styles: Record<string, string> = {
            Pending: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
            "In Progress": "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
            Completed: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
        };
        return (
            <Badge className={`${styles[status] ?? "bg-muted text-muted-foreground"} hover:opacity-80 font-medium px-3 py-1 rounded-full shadow-sm text-xs transition-opacity`}>
                {status}
            </Badge>
        );
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case "Pending": return <CircleDashed className="text-amber-500 w-4.5 h-4.5 flex-shrink-0" />;
            case "In Progress": return <Clock className="text-blue-500 w-4.5 h-4.5 flex-shrink-0" />;
            case "Completed": return <CheckCircle2 className="text-emerald-500 w-4.5 h-4.5 flex-shrink-0" />;
            default: return null;
        }
    };

    const metrics = {
        total: tasks.length,
        pending: tasks.filter(t => t.status === "Pending").length,
        inProgress: tasks.filter(t => t.status === "In Progress").length,
        completed: tasks.filter(t => t.status === "Completed").length,
    };

    return (
        <div className="flex flex-col h-full bg-muted/10 relative">
            {/* Header area */}
            <div className="p-6 pb-4 border-b border-border/50 bg-card/80 backdrop-blur-md z-10 sticky top-0 shadow-sm">
                <div className="flex justify-between items-center mb-6">
                    <div>
                        <h2 className="text-2xl font-bold tracking-tight text-foreground">
                            Task Manager
                            {filterAssignee && (
                                <span className="text-base font-normal text-muted-foreground ml-2">
                                    — {filterAssignee}'s tasks
                                </span>
                            )}
                        </h2>
                        <p className="text-sm text-muted-foreground mt-1">
                            {metrics.total} total • {metrics.pending} pending • {metrics.inProgress} in progress
                        </p>
                    </div>
                    <Dialog open={isNewTaskOpen} onOpenChange={setIsNewTaskOpen}>
                        <DialogTrigger asChild>
                            <Button className="bg-primary hover:bg-primary/90 text-primary-foreground shadow-md hover:shadow-lg transition-all active:scale-95 rounded-xl h-10 px-5 font-medium text-sm">
                                <PlusCircle className="mr-2 h-4 w-4" /> New Task
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="sm:max-w-[480px] rounded-2xl border-border/50 shadow-2xl p-6">
                            <DialogHeader className="mb-2">
                                <DialogTitle className="text-xl font-bold">Create New Task</DialogTitle>
                            </DialogHeader>
                            <div className="grid gap-5 py-2">
                                <div className="space-y-1.5">
                                    <Label htmlFor="title" className="text-sm font-semibold">Title</Label>
                                    <Input id="title" placeholder="e.g. Update dashboard UI" value={newTaskTitle} onChange={(e) => setNewTaskTitle(e.target.value)} className="h-10 rounded-xl" />
                                </div>
                                <div className="space-y-1.5">
                                    <Label htmlFor="desc" className="text-sm font-semibold">Description <span className="text-muted-foreground font-normal">(optional)</span></Label>
                                    <Textarea id="desc" placeholder="Add details..." value={newTaskDesc} onChange={(e) => setNewTaskDesc(e.target.value)} className="min-h-[80px] rounded-xl resize-none" />
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-1.5">
                                        <Label className="text-sm font-semibold">Assignee</Label>
                                        <UISelect value={newTaskAssignee} onValueChange={setNewTaskAssignee}>
                                            <SelectTrigger className="h-10 rounded-xl">
                                                <SelectValue placeholder="Select member" />
                                            </SelectTrigger>
                                            <SelectContent className="rounded-xl shadow-xl">
                                                {TEAM_MEMBERS.map(m => (
                                                    <SelectItem key={m.id} value={m.name} className="cursor-pointer">
                                                        <span className="flex items-center gap-2">
                                                            <span className={`w-2 h-2 rounded-full ${m.color}`} />
                                                            {m.name}
                                                        </span>
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </UISelect>
                                    </div>
                                    <div className="space-y-1.5">
                                        <Label className="text-sm font-semibold">Due Date</Label>
                                        <Input type="date" value={newTaskDue} onChange={(e) => setNewTaskDue(e.target.value)} className="h-10 rounded-xl" />
                                    </div>
                                </div>
                                <div className="space-y-1.5 border-t border-border/40 pt-4">
                                    <Label className="text-sm font-semibold flex items-center gap-1.5">
                                        <Paperclip size={14} className="text-muted-foreground" />
                                        Attachment <span className="text-muted-foreground font-normal">(optional)</span>
                                    </Label>
                                    <Input type="file" onChange={(e) => setNewTaskAttachment(e.target.files?.[0] || null)} className="h-10 rounded-xl text-xs file:text-primary file:font-semibold" />
                                </div>
                            </div>
                            <DialogFooter className="mt-4">
                                <Button variant="ghost" onClick={() => setIsNewTaskOpen(false)} className="rounded-xl">Cancel</Button>
                                <Button onClick={handleCreateTask} disabled={!newTaskTitle || !newTaskAssignee || isSaving} className="bg-primary hover:bg-primary/90 text-primary-foreground h-10 px-6 rounded-xl font-medium shadow-sm active:scale-95 transition-transform">
                                    {isSaving ? "Creating..." : "Create Task"}
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </div>

                {/* Metrics cards */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
                    {[
                        { label: "Total", value: metrics.total, icon: null, accent: "" },
                        { label: "Pending", value: metrics.pending, icon: <CircleDashed className="h-4 w-4 text-amber-500" />, accent: "border-l-amber-500" },
                        { label: "In Progress", value: metrics.inProgress, icon: <Clock className="h-4 w-4 text-blue-500" />, accent: "border-l-blue-500" },
                        { label: "Completed", value: metrics.completed, icon: <CheckCircle2 className="h-4 w-4 text-emerald-500" />, accent: "border-l-emerald-500" },
                    ].map(m => (
                        <Card key={m.label} className={`shadow-sm border-border/40 bg-card rounded-xl hover:shadow-md transition-all border-l-4 ${m.accent || "border-l-primary/30"}`}>
                            <CardContent className="p-4 flex items-center justify-between">
                                <div>
                                    <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">{m.label}</p>
                                    <p className="text-2xl font-bold text-foreground mt-0.5">{m.value}</p>
                                </div>
                                {m.icon && <div className="opacity-60">{m.icon}</div>}
                            </CardContent>
                        </Card>
                    ))}
                </div>

                {/* Search + Filter tabs */}
                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
                    <div className="relative flex-1 max-w-sm">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <Input
                            placeholder="Search tasks..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="pl-9 h-9 rounded-lg text-sm bg-background border-border/50"
                            aria-label="Search tasks"
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
                    <Tabs defaultValue="All" onValueChange={setFilter} className="flex-shrink-0">
                        <TabsList className="bg-muted/50 p-1 rounded-lg h-9">
                            {["All", "Pending", "In Progress", "Completed"].map(tab => (
                                <TabsTrigger
                                    key={tab}
                                    value={tab}
                                    className="rounded-md px-3 text-xs data-[state=active]:bg-background data-[state=active]:shadow-sm data-[state=active]:text-primary font-medium transition-all"
                                >
                                    {tab}
                                </TabsTrigger>
                            ))}
                        </TabsList>
                    </Tabs>
                </div>
            </div>

            {/* Task list */}
            <div className="flex-1 overflow-y-auto px-6 py-5 bg-muted/10 h-full scroll-smooth custom-scrollbar">
                {isLoadingTasks ? (
                    <TaskSkeleton />
                ) : (
                    <div className="grid gap-3 max-w-5xl">
                        <AnimatePresence>
                            {filteredTasks.length === 0 ? (
                                <motion.div
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, scale: 0.95 }}
                                    className="text-center p-16 text-muted-foreground border-2 border-dashed border-border/50 rounded-2xl bg-muted/10 mt-2"
                                >
                                    <CircleDashed className="mx-auto h-10 w-10 text-muted-foreground/30 mb-3" />
                                    <h3 className="text-base font-semibold text-foreground">No tasks found</h3>
                                    <p className="text-sm mt-1">
                                        {searchQuery ? "Try a different search term." : "Get started by creating a new task."}
                                    </p>
                                </motion.div>
                            ) : (
                                filteredTasks.map(task => (
                                    <motion.div
                                        key={task.id}
                                        initial={{ opacity: 0, y: 8 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        exit={{ opacity: 0, scale: 0.95 }}
                                        transition={{ duration: 0.15 }}
                                        layout
                                    >
                                        <div
                                            onClick={() => openEditModal(task)}
                                            className="bg-card border border-border/30 hover:border-primary/30 rounded-xl shadow-sm hover:shadow-md transition-all cursor-pointer group p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:-translate-y-0.5 duration-200"
                                            role="button"
                                            tabIndex={0}
                                            aria-label={`Edit task: ${task.title}`}
                                            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") openEditModal(task); }}
                                        >
                                            <div className="flex gap-3 items-start flex-1 min-w-0">
                                                <div className="mt-0.5 bg-muted/60 p-2 rounded-lg group-hover:bg-primary/5 transition-colors flex-shrink-0">
                                                    {getStatusIcon(task.status)}
                                                </div>
                                                <div className="min-w-0 flex-1">
                                                    <h3 className="font-semibold text-sm text-foreground group-hover:text-primary transition-colors truncate">
                                                        {task.title}
                                                    </h3>
                                                    {task.description && (
                                                        <p className="text-xs text-muted-foreground mt-0.5 truncate">{task.description}</p>
                                                    )}
                                                    {task.attachment_url && (
                                                        <div className="flex items-center gap-1 mt-1 text-xs text-primary bg-primary/5 border border-primary/20 px-2 py-0.5 rounded-md w-max">
                                                            <Paperclip className="w-3 h-3" />
                                                            <span className="truncate max-w-[150px]">{task.attachment_filename}</span>
                                                        </div>
                                                    )}
                                                    <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                                                        <span className="flex items-center gap-1.5 font-medium">
                                                            <div className={`w-4 h-4 rounded-full ${getMemberColor(task.assignee)} flex items-center justify-center text-[8px] font-bold text-white`}>
                                                                {getMemberInitials(task.assignee).charAt(0)}
                                                            </div>
                                                            {task.assignee}
                                                        </span>
                                                        {task.due_date && (
                                                            <span className="flex items-center gap-1 bg-muted/50 px-2 py-0.5 rounded-md">
                                                                <Calendar className="w-3 h-3" />
                                                                {format(parseISO(task.due_date), "MMM d, yyyy")}
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-1 flex-shrink-0">
                                                {getStatusBadge(task.status)}
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-8 w-8 ml-1 text-muted-foreground/0 group-hover:text-destructive/70 hover:!text-destructive hover:!bg-destructive/10 transition-colors"
                                                    onClick={(e) => handleDeleteTask(task.id, e)}
                                                    title="Delete task"
                                                >
                                                    <Trash2 size={14} />
                                                </Button>
                                                <Pencil size={14} className="text-muted-foreground/0 group-hover:text-muted-foreground/60 transition-colors ml-1" />
                                            </div>
                                        </div>
                                    </motion.div>
                                ))
                            )}
                        </AnimatePresence>
                    </div>
                )}
            </div>

            {/* Edit Task Modal */}
            <Dialog open={!!editTask} onOpenChange={(open) => { if (!open) setEditTask(null); }}>
                <DialogContent className="sm:max-w-[520px] rounded-2xl border-border/50 shadow-2xl p-6">
                    <DialogHeader className="mb-2">
                        <DialogTitle className="text-xl font-bold flex items-center gap-2">
                            <Pencil size={18} className="text-primary" />
                            Edit Task
                        </DialogTitle>
                    </DialogHeader>
                    {editTask && (
                        <div className="grid gap-4 py-2">
                            <div className="space-y-1.5">
                                <Label className="text-sm font-semibold">Title</Label>
                                <Input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} className="h-10 rounded-xl" />
                            </div>
                            <div className="space-y-1.5">
                                <Label className="text-sm font-semibold">Description</Label>
                                <Textarea value={editDesc} onChange={(e) => setEditDesc(e.target.value)} placeholder="Add task details..." className="min-h-[80px] rounded-xl resize-none" />
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1.5">
                                    <Label className="text-sm font-semibold">Assignee</Label>
                                    <UISelect value={editAssignee} onValueChange={setEditAssignee}>
                                        <SelectTrigger className="h-10 rounded-xl">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent className="rounded-xl shadow-xl">
                                            {TEAM_MEMBERS.map(m => (
                                                <SelectItem key={m.id} value={m.name}>
                                                    <span className="flex items-center gap-2">
                                                        <span className={`w-2 h-2 rounded-full ${m.color}`} />
                                                        {m.name}
                                                    </span>
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </UISelect>
                                </div>
                                <div className="space-y-1.5">
                                    <Label className="text-sm font-semibold">Status</Label>
                                    <UISelect value={editStatus} onValueChange={setEditStatus}>
                                        <SelectTrigger className="h-10 rounded-xl">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent className="rounded-xl shadow-xl">
                                            {["Pending", "In Progress", "Completed"].map(s => (
                                                <SelectItem key={s} value={s}>{s}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </UISelect>
                                </div>
                            </div>
                            <div className="space-y-1.5">
                                <Label className="text-sm font-semibold">Due Date</Label>
                                <Input type="date" value={editDue} onChange={(e) => setEditDue(e.target.value)} className="h-10 rounded-xl" />
                            </div>
                            <div className="space-y-1.5 border-t border-border/40 pt-4">
                                <Label className="text-sm font-semibold flex items-center gap-1.5">
                                    <Paperclip size={14} className="text-muted-foreground" />
                                    Attachment
                                </Label>
                                {editTask.attachment_url && !editTaskAttachment ? (
                                    <div className="flex items-center justify-between border border-border/40 rounded-lg p-2 bg-muted/20">
                                        <div className="flex items-center gap-2 overflow-hidden">
                                            <Paperclip className="w-4 h-4 text-primary shrink-0" />
                                            <span className="text-xs truncate">{editTask.attachment_filename}</span>
                                        </div>
                                        <div className="flex gap-1 shrink-0">
                                            <a href={`http://localhost:8000${editTask.attachment_url}`} target="_blank" rel="noreferrer" className="text-xs text-primary hover:underline px-2 flex items-center gap-1">
                                                <ExternalLink className="w-3 h-3" /> View
                                            </a>
                                            <Button variant="ghost" size="sm" className="h-6 px-2 text-xs text-destructive hover:bg-destructive/10" onClick={() => setEditTask({ ...editTask, attachment_url: null, attachment_filename: null })}>Remove</Button>
                                        </div>
                                    </div>
                                ) : (
                                    <Input type="file" onChange={(e) => setEditTaskAttachment(e.target.files?.[0] || null)} className="h-10 rounded-xl text-xs file:text-primary file:font-semibold" />
                                )}
                            </div>
                            <div className="border-t border-border/40 pt-4 space-y-1.5">
                                <Label className="text-sm font-semibold flex items-center gap-1.5">
                                    <MessageSquare size={14} className="text-muted-foreground" />
                                    Add Comment
                                </Label>
                                <div className="flex gap-2">
                                    <Input
                                        value={editComment}
                                        onChange={(e) => setEditComment(e.target.value)}
                                        placeholder="Leave a note..."
                                        className="h-10 rounded-xl flex-1"
                                    />
                                    <Button
                                        variant="secondary"
                                        size="sm"
                                        className="h-10 px-4 rounded-xl text-xs"
                                        disabled={!editComment.trim() || isSaving}
                                        onClick={async () => {
                                            if (!editTask || !editComment.trim()) return;
                                            try {
                                                const commentRes = await api.post(`/api/tasks/${editTask.id}/comments`, {
                                                    author_name: user?.displayName || "Admin",
                                                    comment: editComment.trim()
                                                });
                                                setEditTask({
                                                    ...editTask,
                                                    comments: [commentRes.data, ...(editTask.comments || [])]
                                                });
                                                setEditComment("");
                                                toast.success("Comment added");
                                            } catch {
                                                toast.error("Failed to add comment");
                                            }
                                        }}
                                    >
                                        Add
                                    </Button>
                                </div>
                                <div className="space-y-4 max-h-40 overflow-y-auto custom-scrollbar pr-2 mt-4 border-t border-border/30 pt-4">
                                    {editTask.comments && editTask.comments.length > 0 ? (
                                        editTask.comments.map((comment: any) => (
                                            <div key={comment.id} className="bg-muted/30 p-3 rounded-lg border border-border/40 text-sm animate-in fade-in slide-in-from-bottom-2">
                                                <div className="flex justify-between items-center mb-1 text-xs">
                                                    <span className="font-semibold text-foreground/80">{comment.author_name}</span>
                                                    <span className="text-muted-foreground/60">{format(parseISO(comment.timestamp), 'MMM d, h:mm a')}</span>
                                                </div>
                                                <p className="text-muted-foreground break-words">{comment.comment}</p>
                                            </div>
                                        ))
                                    ) : (
                                        <div className="text-center py-4 bg-muted/20 border border-border/20 border-dashed rounded-lg text-xs text-muted-foreground">
                                            No comments yet.
                                        </div>
                                    )}
                                </div>
                            </div>
                            <div className="text-[11px] text-muted-foreground pt-1">
                                Created {format(parseISO(editTask.created_at), "MMM d, yyyy 'at' h:mm a")}
                                {editTask.updated_at !== editTask.created_at && (
                                    <> • Updated {format(parseISO(editTask.updated_at), "MMM d, yyyy 'at' h:mm a")}</>
                                )}
                            </div>
                        </div>
                    )}
                    <DialogFooter className="mt-2 flex-col sm:flex-row sm:justify-between items-center gap-2">
                        {editTask && (
                            <Button
                                variant="ghost"
                                className="text-destructive hover:text-destructive hover:bg-destructive/10 rounded-xl sm:mr-auto w-full sm:w-auto"
                                onClick={(e) => handleDeleteTask(editTask.id, e)}
                            >
                                <Trash2 size={16} className="mr-2" /> Delete Task
                            </Button>
                        )}
                        <div className="flex gap-2 w-full sm:w-auto justify-end">
                            <Button variant="ghost" onClick={() => setEditTask(null)} className="rounded-xl">Cancel</Button>
                            <Button
                                onClick={handleUpdateTask}
                                disabled={isSaving || !editTitle}
                                className="bg-primary hover:bg-primary/90 text-primary-foreground h-10 px-6 rounded-xl font-medium shadow-sm active:scale-95 transition-transform"
                            >
                                {isSaving ? (
                                    <div className="w-4 h-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                                ) : (
                                    "Save Changes"
                                )}
                            </Button>
                        </div>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
