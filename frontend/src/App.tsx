import { useState, lazy, Suspense, useEffect } from "react";
import { Navbar } from "@/components/Navbar";
import { NavigationSidebar, type TabId } from "@/components/NavigationSidebar";
import { ThemeProvider } from "@/components/ThemeProvider";
import { LoginPage } from "@/components/LoginPage";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { getUser, logout, setUser as persistAuthUser, type AuthUser } from "@/lib/auth";
import api from "@/lib/api";
import { Toaster } from "sonner";

// Lazy load panels for performance
const AIChatPanel = lazy(() => import("@/components/AIChatPanel").then(m => ({ default: m.AIChatPanel })));
const TaskManagerPanel = lazy(() => import("@/components/TaskManagerPanel").then(m => ({ default: m.TaskManagerPanel })));
const TeamDirectoryPanel = lazy(() => import("@/components/TeamDirectoryPanel").then(m => ({ default: m.TeamDirectoryPanel })));
const TeamChatPanel = lazy(() => import("@/components/TeamChatPanel").then(m => ({ default: m.TeamChatPanel })));
const DashboardPanel = lazy(() => import("@/components/DashboardPanel").then(m => ({ default: m.DashboardPanel })));
const KnowledgeBasePanel = lazy(() => import("@/components/KnowledgeBasePanel").then(m => ({ default: m.KnowledgeBasePanel })));
const DocumentAnalysisPanel = lazy(() => import("@/components/DocumentAnalysisPanel").then(m => ({ default: m.DocumentAnalysisPanel })));
const SqlAgentPanel = lazy(() => import("@/components/SqlAgentPanel").then(m => ({ default: m.SqlAgentPanel })));
const GitHubAgentPanel = lazy(() => import("@/components/GitHubAgentPanel").then(m => ({ default: m.GitHubAgentPanel })));
const GoogleDriveAgentPanel = lazy(() => import("@/components/GoogleDriveAgentPanel").then(m => ({ default: m.GoogleDriveAgentPanel })));
const SettingsPanel = lazy(() => import("@/components/SettingsPanel").then(m => ({ default: m.SettingsPanel })));
const ChatHistoryPanel = lazy(() => import("@/components/ChatHistoryPanel").then(m => ({ default: m.ChatHistoryPanel })));

// Fallback loading component
function PanelLoader() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-3">
      <div className="w-8 h-8 border-3 border-primary/20 border-t-primary rounded-full animate-spin" />
      <p className="text-sm text-muted-foreground font-medium">Loading...</p>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState<AuthUser | null>(getUser());
  const [activeTab, setActiveTab] = useState<TabId>("chat");
  const [taskFilterAssignee, setTaskFilterAssignee] = useState<string | undefined>(undefined);
  const [activeSessionId, setActiveSessionId] = useState<string | undefined>(undefined);

  const handleLogout = () => {
    logout();
    setActiveSessionId(undefined);
    setUser(null);
  };

  useEffect(() => {
    if (!user?.token) return;

    let isCancelled = false;
    const syncUserProfile = async () => {
      try {
        const res = await api.get("/api/user/profile");
        if (isCancelled || !res?.data) return;

        const profile = res.data;
        const nextUser: AuthUser = {
          ...user,
          displayName: profile.display_name || user.displayName,
          role: (profile.role || user.role) as AuthUser["role"],
          email: profile.email || user.email,
        };

        setUser(nextUser);
        persistAuthUser(nextUser);
      } catch {
        // Keep existing user state if profile endpoint is unavailable.
      }
    };

    syncUserProfile();
    return () => {
      isCancelled = true;
    };
  }, [user?.token]);

  // If not logged in, show login page
  if (!user) {
    return (
      <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
        <Toaster
          richColors
          position="top-right"
          toastOptions={{
            className: "!rounded-xl !shadow-lg !border-border/50",
          }}
        />
        <LoginPage onLogin={(u) => setUser(u)} />
      </ThemeProvider>
    );
  }

  const handleTaskCreated = () => {
    if (typeof (window as any).refreshTasks === "function") {
      (window as any).refreshTasks();
    }
  };

  // Navigate to tasks filtered by a team member
  const handleViewMemberTasks = (memberName: string) => {
    setTaskFilterAssignee(memberName);
    setActiveTab("tasks");
  };

  const handleLoadSession = (sessionId: string) => {
    setActiveSessionId(sessionId);
    setActiveTab("chat");
  };

  const renderMainContent = () => {
    switch (activeTab) {
      case "chat":
        return (
          <Suspense fallback={<PanelLoader />}>
            <AIChatPanel
              onTaskCreated={handleTaskCreated}
              sessionId={activeSessionId}
              onNewChat={() => setActiveSessionId(undefined)}
            />
          </Suspense>
        );
      case "tasks":
        return (
          <Suspense fallback={<PanelLoader />}>
            <TaskManagerPanel user={user} filterAssignee={taskFilterAssignee} />
          </Suspense>
        );
      case "history":
        return (
          <Suspense fallback={<PanelLoader />}>
            <ChatHistoryPanel onLoadSession={handleLoadSession} />
          </Suspense>
        );
      case "team":
        return (
          <Suspense fallback={<PanelLoader />}>
            <TeamDirectoryPanel onViewMemberTasks={handleViewMemberTasks} />
          </Suspense>
        );
      case "teamchat":
        return (
          <Suspense fallback={<PanelLoader />}>
            <TeamChatPanel />
          </Suspense>
        );
      case "dashboard":
        return (
          <Suspense fallback={<PanelLoader />}>
            <DashboardPanel onNavigateToTasks={() => handleTabChange("tasks")} />
          </Suspense>
        );
      case "knowledge":
        return (
            <Suspense fallback={<PanelLoader />}>
              <KnowledgeBasePanel />
            </Suspense>
          );
      case "documentanalysis":
        return (
          <Suspense fallback={<PanelLoader />}>
            <DocumentAnalysisPanel />
          </Suspense>
        );
      case "sqlagent":
        return (
          <Suspense fallback={<PanelLoader />}>
            <SqlAgentPanel />
          </Suspense>
        );
      case "githubagent":
        return (
          <Suspense fallback={<PanelLoader />}>
            <GitHubAgentPanel />
          </Suspense>
        );
      case "driveagent":
        return (
          <Suspense fallback={<PanelLoader />}>
            <GoogleDriveAgentPanel />
          </Suspense>
        );
      case "settings":
        return (
          <Suspense fallback={<PanelLoader />}>
            <SettingsPanel user={user} />
          </Suspense>
        );
      case "notifications":
        return (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground bg-muted/5">
            <div className="text-center p-12 max-w-md bg-card border border-border/40 shadow-sm rounded-2xl">
              <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
                <span className="text-primary text-lg font-bold">🚧</span>
              </div>
              <h2 className="text-xl font-bold mb-2 text-foreground capitalize">{activeTab}</h2>
              <p className="text-sm text-muted-foreground">This module is currently under development. Check back soon for updates.</p>
            </div>
          </div>
        );
      default:
        return (
          <Suspense fallback={<PanelLoader />}>
            <AIChatPanel
              onTaskCreated={handleTaskCreated}
              sessionId={activeSessionId}
              onNewChat={() => setActiveSessionId(undefined)}
            />
          </Suspense>
        );
    }
  };

  // Clear task filter when navigating away from tasks
  const handleTabChange = (tab: TabId) => {
    if (tab !== "tasks") {
      setTaskFilterAssignee(undefined);
    }
    setActiveTab(tab);
  };

  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      <Toaster
        richColors
        position="top-right"
        toastOptions={{
          className: "!rounded-xl !shadow-lg !border-border/50",
        }}
      />
      <div className="flex flex-col h-screen w-full bg-background text-foreground overflow-hidden font-sans">
        <Navbar activeTab={activeTab} setActiveTab={handleTabChange} user={user} onLogout={handleLogout} />
        <ErrorBoundary>
          <div className="flex flex-1 overflow-hidden">
            <div className="hidden md:block w-[260px] flex-shrink-0 z-0 bg-card">
              <NavigationSidebar activeTab={activeTab} setActiveTab={handleTabChange} />
            </div>
            <main className="flex flex-1 flex-col overflow-hidden relative bg-muted/5">
              {renderMainContent()}
            </main>
          </div>
        </ErrorBoundary>
      </div>
    </ThemeProvider>
  );
}
