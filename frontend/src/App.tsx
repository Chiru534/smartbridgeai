import { useState, lazy, Suspense } from "react";
import { Navbar } from "@/components/Navbar";
import { NavigationSidebar, type TabId } from "@/components/NavigationSidebar";
import { ThemeProvider } from "@/components/ThemeProvider";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { getUser, type AuthUser } from "@/lib/auth";
import { Toaster } from "sonner";

// Lazy load panels for performance
const AIChatPanel = lazy(() => import("@/components/AIChatPanel").then(m => ({ default: m.AIChatPanel })));
const TaskManagerPanel = lazy(() => import("@/components/TaskManagerPanel").then(m => ({ default: m.TaskManagerPanel })));
const DashboardPanel = lazy(() => import("@/components/DashboardPanel").then(m => ({ default: m.DashboardPanel })));
const KnowledgeBasePanel = lazy(() => import("@/components/KnowledgeBasePanel").then(m => ({ default: m.KnowledgeBasePanel })));
const DocumentAnalysisPanel = lazy(() => import("@/components/DocumentAnalysisPanel").then(m => ({ default: m.DocumentAnalysisPanel })));
const SqlAgentPanel = lazy(() => import("@/components/SqlAgentPanel").then(m => ({ default: m.SqlAgentPanel })));
const GitHubAgentPanel = lazy(() => import("@/components/GitHubAgentPanel").then(m => ({ default: m.GitHubAgentPanel })));
const GoogleDriveAgentPanel = lazy(() => import("@/components/GoogleDriveAgentPanel").then(m => ({ default: m.GoogleDriveAgentPanel })));
const SlackAgentPanel = lazy(() => import("@/components/SlackAgentPanel").then(m => ({ default: m.SlackAgentPanel })));
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
  // Auth is bypassed for testing — always logged in as mock user
  const user: AuthUser = getUser();
  const [activeTab, setActiveTab] = useState<TabId>("chat");
  const [taskFilterAssignee, setTaskFilterAssignee] = useState<string | undefined>(undefined);
  const [activeSessionId, setActiveSessionId] = useState<string | undefined>(undefined);

  const handleTaskCreated = () => {
    if (typeof (window as any).refreshTasks === "function") {
      (window as any).refreshTasks();
    }
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
      case "slackagent":
        return (
          <Suspense fallback={<PanelLoader />}>
            <SlackAgentPanel />
          </Suspense>
        );

      case "settings":
        return (
          <Suspense fallback={<PanelLoader />}>
            <SettingsPanel user={user} />
          </Suspense>
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
        <Navbar activeTab={activeTab} setActiveTab={handleTabChange} user={user} onLogout={() => {}} />

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
