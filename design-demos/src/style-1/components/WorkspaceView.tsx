import {
 Beaker,
 BookOpen,
 FileText,
  FileUp,
  HelpCircle,
  Menu,
  MessageSquare,
  Search,
  Upload,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { mockLibraryDocuments, mockProjects, mockQuizQuestions } from "@/lib/mock-data";
import { Sidebar } from "./Sidebar";
import { BrandLogo } from "./BrandLogo";

interface WorkspaceViewProps {
  activeProjectId: string;
  onSelectConversation?: (id: string) => void;
  onNewChat?: () => void;
  onNewProject?: () => void;
  onSelectProject?: (id: string) => void;
}

const typeStyles: Record<string, string> = {
  PDF: "bg-red-50 text-red-600 border-red-200/60",
  DOCX: "bg-blue-50 text-blue-600 border-blue-200/60",
  PPTX: "bg-orange-50 text-orange-600 border-orange-200/60",
};

export function WorkspaceView({
  activeProjectId,
  onSelectConversation,
  onNewChat,
  onNewProject,
  onSelectProject,
}: WorkspaceViewProps) {
  const project =
    mockProjects.find((p) => p.id === activeProjectId) ?? mockProjects[0];
  const sidebarProps = {
    activeProjectId,
    onSelectConversation,
    onNewChat,
    onNewProject,
    onSelectProject,
  };

  return (
    <Sheet>
      <div className="grid h-[100dvh] bg-gradient-to-br from-accent via-background to-background md:grid-cols-[260px_1fr]">
        {/* Desktop sidebar */}
        <aside className="hidden h-full md:block">
          <Sidebar {...sidebarProps} />
        </aside>

        {/* Main column */}
        <main className="flex h-full min-h-0 flex-col overflow-hidden">
          {/* Mobile top bar */}
          <div className="flex items-center gap-2 border-b border-border/40 bg-white/50 px-4 py-2.5 backdrop-blur-sm md:hidden">
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="h-9 w-9">
                <Menu className="h-5 w-5" strokeWidth={1.5} />
              </Button>
            </SheetTrigger>
            <BrandLogo />
          </div>

          <Tabs
            defaultValue="sources"
            className="flex min-h-0 flex-1 flex-col overflow-hidden"
          >
            {/* Project header — non-scrolling */}
            <header className="border-b border-border/40 bg-white/40 px-5 py-3 backdrop-blur-sm sm:px-6">
              <h1 className="truncate text-lg font-semibold tracking-tight text-foreground">
                {project.name}
              </h1>
              <TabsList className="mt-2.5 h-auto gap-1 bg-transparent p-0">
                <TabsTrigger
                  value="chat"
                  className="gap-1.5 rounded-lg px-3 py-1.5 text-sm data-[state=active]:bg-white/70 data-[state=active]:shadow-sm"
                >
                  <MessageSquare className="h-3.5 w-3.5" strokeWidth={1.5} />
                  Chat
                </TabsTrigger>
                <TabsTrigger
                  value="sources"
                  className="gap-1.5 rounded-lg px-3 py-1.5 text-sm data-[state=active]:bg-white/70 data-[state=active]:shadow-sm"
                >
                  <BookOpen className="h-3.5 w-3.5" strokeWidth={1.5} />
                  Sources
                </TabsTrigger>
                <TabsTrigger
                  value="labs"
                  className="gap-1.5 rounded-lg px-3 py-1.5 text-sm data-[state=active]:bg-white/70 data-[state=active]:shadow-sm"
                >
                  <Beaker className="h-3.5 w-3.5" strokeWidth={1.5} />
                  Labs
                </TabsTrigger>
                <TabsTrigger
                  value="quiz"
                  className="gap-1.5 rounded-lg px-3 py-1.5 text-sm data-[state=active]:bg-white/70 data-[state=active]:shadow-sm"
                >
                  <HelpCircle className="h-3.5 w-3.5" strokeWidth={1.5} />
                  Quiz
                </TabsTrigger>
              </TabsList>
            </header>

            {/* Scrollable tab content */}
            <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto">
              <TabsContent value="chat" className="mt-0">
                <PlaceholderTab
                  icon={MessageSquare}
                  title="No conversations yet"
                  desc="Start a new chat to explore this project's sources."
                />
              </TabsContent>
              <TabsContent value="sources" className="mt-0">
                <SourcesPanel />
              </TabsContent>
              <TabsContent value="labs" className="mt-0">
                <PlaceholderTab
                  icon={Beaker}
                  title="Labs coming soon"
                  desc="Run experiments and generate insights from your sources."
                />
              </TabsContent>
              <TabsContent value="quiz" className="mt-0">
                <QuizPanel />
              </TabsContent>
            </div>
          </Tabs>
        </main>
      </div>

      {/* Mobile sidebar */}
      <SheetContent side="left" className="w-[280px] p-0">
        <Sidebar {...sidebarProps} className="border-r-0" />
      </SheetContent>
    </Sheet>
  );
}

function SourcesPanel() {
  return (
    <div className="mx-auto max-w-4xl p-5 sm:p-6">
      {/* Search + Upload */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Search
            className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
            strokeWidth={1.5}
          />
          <Input
            placeholder="Search sources…"
            className="rounded-lg border-border/60 bg-white/50 pl-9 backdrop-blur-sm"
          />
        </div>
        <Button className="gap-2 rounded-lg">
          <Upload className="h-4 w-4" strokeWidth={1.5} />
          <span className="hidden sm:inline">Upload</span>
        </Button>
      </div>

      {/* Upload dropzone */}
      <div className="mt-4 flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-border bg-secondary/30 px-6 py-10 text-center transition-all duration-300 hover:border-primary/40 hover:bg-accent/30">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent text-primary">
          <FileUp className="h-5 w-5" strokeWidth={1.5} />
        </div>
        <p className="mt-3 text-sm font-medium text-foreground">
          Drop files here or click to upload
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          PDF, DOCX, PPTX up to 50 MB
        </p>
      </div>

      {/* Document list */}
      <div className="mt-6">
        <h2 className="mb-3 text-sm font-medium text-foreground">
          {mockLibraryDocuments.length} sources
        </h2>
        <div className="space-y-2">
          {mockLibraryDocuments.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center gap-3 rounded-xl border border-border/50 bg-white/50 px-4 py-3 backdrop-blur-sm transition-all duration-300 hover:border-primary/20 hover:bg-white/70 hover:shadow-md hover:shadow-primary/5"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-secondary">
                <FileText className="h-5 w-5 text-muted-foreground" strokeWidth={1.5} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-foreground">
                  {doc.filename}
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {doc.size} · {doc.uploaded}
                </p>
              </div>
              <Badge
                variant="outline"
                className={cn(
                  "shrink-0 font-mono text-[10px]",
                  typeStyles[doc.type] ?? "",
                )}
              >
                {doc.type}
              </Badge>
              <Badge
                variant={doc.status === "ready" ? "success" : "warning"}
                className="shrink-0 capitalize"
              >
                {doc.status}
              </Badge>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function QuizPanel() {
  return (
    <div className="mx-auto max-w-3xl p-5 sm:p-6">
      <div className="mb-5">
        <h2 className="text-lg font-semibold tracking-tight text-foreground">
          Test your understanding
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {mockQuizQuestions.length} questions generated from your sources.
        </p>
      </div>
      <div className="space-y-4">
        {mockQuizQuestions.map((q, i) => (
          <div
            key={q.id}
            className="rounded-2xl border border-border/50 bg-white/50 p-5 backdrop-blur-sm"
          >
            <p className="text-sm font-medium text-foreground">
              <span className="text-muted-foreground">{i + 1}.</span>{" "}
              {q.question}
            </p>
            <div className="mt-3 space-y-2">
              {q.options.map((opt, j) => (
                <button
                  key={j}
                  className="flex w-full items-center gap-2.5 rounded-lg border border-border/50 bg-white/40 px-3 py-2 text-left text-sm text-foreground transition-all hover:border-primary/30 hover:bg-accent/30"
                >
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-border text-xs font-medium text-muted-foreground">
                    {String.fromCharCode(65 + j)}
                  </span>
                  {opt}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PlaceholderTab({
  icon: Icon,
  title,
  desc,
}: {
  icon: LucideIcon;
  title: string;
  desc: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-20 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent text-primary">
        <Icon className="h-6 w-6" strokeWidth={1.5} />
      </div>
      <h3 className="mt-4 text-base font-semibold text-foreground">{title}</h3>
      <p className="mt-1.5 max-w-sm text-sm text-muted-foreground">{desc}</p>
    </div>
  );
}
