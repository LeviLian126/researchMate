// Owns authenticated project and conversation navigation plus its management dialogs.
"use client";

import Link from "next/link";
import {
  FormEvent,
  PointerEvent as ReactPointerEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  ChevronLeft,
  ChevronRight,
  Folder,
  FolderPlus,
  GitBranch,
  Menu,
  MessageSquare,
  MoreHorizontal,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";
import {
  apiFetch,
  ConversationSummary,
  describeApiError,
  ProjectRecord,
} from "../lib/api";
import { BrandLogo } from "./brand-logo";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

const PROJECT_PATTERN = /\/app\/projects\/([^/]+)/;
const SIDEBAR_MIN_WIDTH = 220;
const SIDEBAR_MAX_WIDTH = 520;
const SIDEBAR_DEFAULT_WIDTH = 300;
const SIDEBAR_WIDTH_STORAGE_KEY = "researchmate_sidebar_width";
// Viewport width below which the sidebar collapses by default on first load.
const MOBILE_BREAKPOINT_PX = 820;
// Hard cap on deletion-job polling attempts before surfacing "still processing".
const POLLING_CAP = 20;
// Interval between deletion-job status polls, in milliseconds.
const POLL_INTERVAL_MS = 1500;

interface DeletionJob {
  status: "pending" | "running" | "succeeded" | "failed" | "cancelled";
  error_message?: string | null;
}

/** Renders a shared nav action row used by the primary navigation. */
function navItemClass(active: boolean, compact: boolean) {
  return cn(
    "flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm transition-all duration-300 ease-out",
    compact && "justify-center px-0",
    active
      ? "bg-accent font-medium text-accent-foreground"
      : "text-foreground hover:bg-accent/50 hover:text-foreground",
  );
}

/** Owns project, conversation, and source navigation for the authenticated workspace. */
export function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeProjectId = pathname.match(PROJECT_PATTERN)?.[1] ?? null;
  const activeConversationId = searchParams.get("conversation");
  const [collapsed, setCollapsed] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(SIDEBAR_DEFAULT_WIDTH);
  const [isResizing, setIsResizing] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [personalProjectId, setPersonalProjectId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [creatingProject, setCreatingProject] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [editingConversation, setEditingConversation] = useState<ConversationSummary | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [deletingProject, setDeletingProject] = useState<ProjectRecord | null>(null);
  const [confirmConversationDelete, setConfirmConversationDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestGeneration = useRef(0);

  const personalConversations = useMemo(
    () => conversations.filter((item) => item.project_id === personalProjectId),
    [conversations, personalProjectId],
  );
  const activeProjectConversations = useMemo(
    () => conversations.filter((item) => item.project_id === activeProjectId),
    [activeProjectId, conversations],
  );

  /** Reloads projects and conversations while rejecting stale overlapping responses. */
  const loadNavigation = useCallback(async () => {
    const generation = ++requestGeneration.current;
    try {
      const [ownedProjects, allConversations, personalProject] = await Promise.all([
        apiFetch<ProjectRecord[]>("/projects"),
        apiFetch<{ items: ConversationSummary[] }>("/conversations"),
        apiFetch<ProjectRecord>("/chat/bootstrap", { method: "POST" }),
      ]);
      if (generation !== requestGeneration.current) return;
      setProjects(ownedProjects);
      setConversations(allConversations.items);
      setPersonalProjectId(personalProject.id);
      setError(null);
    } catch (requestError) {
      if (generation === requestGeneration.current) {
        setError(describeApiError(requestError).detail);
      }
    }
  }, []);

  useEffect(() => {
    const saved = window.localStorage.getItem("researchmate_sidebar_collapsed");
    const savedWidth = window.localStorage.getItem(SIDEBAR_WIDTH_STORAGE_KEY);
    setCollapsed(saved === null ? window.innerWidth <= MOBILE_BREAKPOINT_PX : saved === "true");
    if (savedWidth !== null && Number.isFinite(Number(savedWidth))) {
      setSidebarWidth(
        Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, Number(savedWidth))),
      );
    }
    void loadNavigation();
    const refresh = () => void loadNavigation();
    window.addEventListener("researchmate:sidebar-refresh", refresh);
    return () => {
      requestGeneration.current += 1;
      window.removeEventListener("researchmate:sidebar-refresh", refresh);
    };
  }, [loadNavigation]);

  /** Toggles the sidebar and broadcasts its responsive layout state. */
  function toggleSidebar() {
    setCollapsed((current) => {
      window.localStorage.setItem("researchmate_sidebar_collapsed", String(!current));
      return !current;
    });
  }

  /** Stores a bounded desktop width so the workspace always retains usable room. */
  function setDesktopSidebarWidth(nextWidth: number) {
    const boundedWidth = Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, nextWidth));
    setSidebarWidth(boundedWidth);
    window.localStorage.setItem(SIDEBAR_WIDTH_STORAGE_KEY, String(boundedWidth));
  }

  /** Starts pointer resizing from the sidebar's trailing edge. */
  function startSidebarResize(event: ReactPointerEvent<HTMLDivElement>) {
    if (collapsed) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    setIsResizing(true);
  }

  /** Creates a workspace project and navigates to its chat. */
  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectName.trim()) return;
    try {
      const project = await apiFetch<ProjectRecord>("/projects", {
        method: "POST",
        body: JSON.stringify({ name: projectName.trim() }),
      });
      setProjectName("");
      setCreatingProject(false);
      setMobileOpen(false);
      await loadNavigation();
      router.push(`/app/projects/${project.id}/chat?new=1`);
    } catch (requestError) {
      setError(describeApiError(requestError).detail);
    }
  }

  /** Persists a conversation title and updates the navigation snapshot. */
  async function renameConversation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingConversation || !editingTitle.trim()) return;
    try {
      await apiFetch(`/conversations/${editingConversation.id}`, {
        method: "PATCH",
        body: JSON.stringify({ title: editingTitle.trim() }),
      });
      setEditingConversation(null);
      await loadNavigation();
    } catch (requestError) {
      setError(describeApiError(requestError).detail);
    }
  }

  /** Deletes a conversation after the explicit confirmation state is satisfied. */
  async function deleteConversation(conversation: ConversationSummary) {
    try {
      await apiFetch(`/conversations/${conversation.id}`, { method: "DELETE" });
      setEditingConversation(null);
      setConfirmConversationDelete(false);
      await loadNavigation();
      if (conversation.id === activeConversationId) {
        router.push(
          conversation.project_id === personalProjectId
            ? "/app?new=1"
            : `/app/projects/${conversation.project_id}/chat?new=1`,
        );
      }
    } catch (requestError) {
      setError(describeApiError(requestError).detail);
    }
  }

  /** Requests project deletion and follows the asynchronous deletion job to completion. */
  async function deleteProject(projectId: string) {
    try {
      const accepted = await apiFetch<{ job_id: string }>(`/projects/${projectId}`, {
        method: "DELETE",
      });
      setDeletingProject(null);
      setError(`Project removal job ${accepted.job_id} is pending.`);
      for (let attempt = 0; attempt < POLLING_CAP; attempt += 1) {
        const job = await apiFetch<DeletionJob>(`/jobs/${accepted.job_id}`);
        if (job.status === "succeeded") {
          setProjects((current) => current.filter((project) => project.id !== projectId));
          setError(null);
          if (projectId === activeProjectId) router.push("/app");
          return;
        }
        if (job.status === "failed" || job.status === "cancelled") {
          setError(job.error_message || `Project removal ${job.status}.`);
          await loadNavigation();
          return;
        }
        setError(`Project removal is ${job.status}.`);
        await new Promise((resolve) => window.setTimeout(resolve, POLL_INTERVAL_MS));
      }
      setError(`Project removal is still processing. Track job ${accepted.job_id}.`);
    } catch (requestError) {
      setError(describeApiError(requestError).detail);
    }
  }

  /** Opens rename mode with the current canonical conversation title. */
  function startRename(conversation: ConversationSummary) {
    setEditingConversation(conversation);
    setEditingTitle(conversation.title);
    setConfirmConversationDelete(false);
  }

  /** Renders the shared sidebar body for both desktop and mobile surfaces. */
  const renderSidebarBody = (compact: boolean, showToggle: boolean) => (
    <>
      <div
        className={cn(
          "flex items-center gap-2 px-3 py-4",
          compact ? "flex-col gap-3" : "justify-between",
        )}
      >
        <Link
          href="/app"
          aria-label="ResearchMate"
          onClick={() => setMobileOpen(false)}
          className="transition-opacity hover:opacity-80"
        >
          <BrandLogo withName={!compact} />
        </Link>
        {showToggle && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0 text-muted-foreground hover:text-foreground"
            onClick={toggleSidebar}
            aria-label={compact ? "Expand sidebar" : "Collapse sidebar"}
          >
            {compact ? (
              <ChevronRight strokeWidth={1.5} />
            ) : (
              <ChevronLeft strokeWidth={1.5} />
            )}
          </Button>
        )}
      </div>

      <nav className={cn("flex flex-col gap-1 px-3", compact && "items-center")}>
        <Link
          href="/app?new=1"
          onClick={() => setMobileOpen(false)}
          aria-current={!activeProjectId && !activeConversationId ? "page" : undefined}
          className={navItemClass(!activeProjectId && !activeConversationId, compact)}
        >
          <Plus strokeWidth={1.5} className="size-4 shrink-0" />
          {!compact && <span>New chat</span>}
        </Link>
        <button
          type="button"
          onClick={() => {
            if (compact) toggleSidebar();
            setCreatingProject((current) => !current);
          }}
          className={navItemClass(false, compact)}
        >
          <FolderPlus strokeWidth={1.5} className="size-4 shrink-0" />
          {!compact && <span>New project</span>}
        </button>
      </nav>

      {creatingProject && !compact && (
        <form
          onSubmit={createProject}
          className="mx-3 mb-1 flex flex-col gap-2 rounded-xl border border-white/30 bg-white/60 p-3 shadow-sm"
        >
          <Input
            aria-label="Project name"
            autoFocus
            maxLength={120}
            value={projectName}
            onChange={(event) => setProjectName(event.target.value)}
            placeholder="Project name"
            className="rounded-lg"
          />
          <div className="flex gap-2">
            <Button type="submit" size="sm" className="rounded-lg">
              Create
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="rounded-lg"
              onClick={() => setCreatingProject(false)}
            >
              Cancel
            </Button>
          </div>
        </form>
      )}

      <ScrollArea className="min-h-0 flex-1">
        <div className="flex min-w-0 flex-col gap-3 px-3 pb-3">
          {!!projects.length && (
            <section className="flex min-w-0 flex-col gap-0.5">
              {!compact && (
                <div className="px-2 py-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Projects
                </div>
              )}
              {projects.map((project) => (
                <div key={project.id} className="flex min-w-0 flex-col">
                  <div className="group/project flex w-full min-w-0 items-center gap-1 overflow-hidden">
                    <Link
                      href={`/app/projects/${project.id}/chat`}
                      onClick={() => setMobileOpen(false)}
                      aria-current={project.id === activeProjectId ? "page" : undefined}
                      className={cn(
                        navItemClass(project.id === activeProjectId, compact),
                        !compact && "min-w-0 flex-1 basis-0 overflow-hidden",
                      )}
                    >
                      <Folder strokeWidth={1.5} className="size-4 shrink-0" />
                      {!compact && <span className="truncate">{project.name}</span>}
                    </Link>
                    {!compact && (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="relative z-10 h-7 w-7 shrink-0 text-muted-foreground hover:text-foreground"
                            aria-label={`Manage ${project.name}`}
                          >
                            <MoreHorizontal strokeWidth={1.5} />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent
                          align="end"
                          className="rounded-xl border-white/30 bg-white/80 backdrop-blur-xl"
                        >
                          <DropdownMenuItem asChild>
                            <Link
                              href={`/app/projects/${project.id}/library`}
                              onClick={() => setMobileOpen(false)}
                            >
                              Sources
                            </Link>
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            className="text-destructive focus:text-destructive"
                            onClick={() => setDeletingProject(project)}
                          >
                            <Trash2 strokeWidth={1.5} className="mr-2 size-4" />
                            Delete project
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </div>
                  {!compact &&
                    project.id === activeProjectId &&
                    activeProjectConversations.map((conversation) => (
                      <ConversationLink
                        key={conversation.id}
                        conversation={conversation}
                        href={`/app/projects/${project.id}/chat?conversation=${conversation.id}`}
                        active={conversation.id === activeConversationId}
                        onManage={startRename}
                        onNavigate={() => setMobileOpen(false)}
                      />
                    ))}
                </div>
              ))}
            </section>
          )}

          {!compact && !!personalConversations.length && (
            <section className="flex min-w-0 flex-col gap-0.5">
              <div className="px-2 py-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Recents
              </div>
              {personalConversations.map((conversation) => (
                <ConversationLink
                  key={conversation.id}
                  conversation={conversation}
                  href={`/app?conversation=${conversation.id}`}
                  active={!activeProjectId && conversation.id === activeConversationId}
                  onManage={startRename}
                  onNavigate={() => setMobileOpen(false)}
                />
              ))}
            </section>
          )}
        </div>
      </ScrollArea>

      <div className="mt-auto border-t border-white/30 px-3 py-3">
        <a
          href="https://github.com/LeviLian126/researchMate"
          className={cn(
            "flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm text-muted-foreground transition-all duration-300 ease-out hover:bg-accent/50 hover:text-foreground",
            compact && "justify-center px-0",
          )}
        >
          <GitBranch strokeWidth={1.5} className="size-4 shrink-0" />
          {!compact && <span>GitHub</span>}
        </a>
        {error && !compact && (
          <p role="status" className="mt-2 px-2 text-xs text-destructive">
            {error}
          </p>
        )}
      </div>
    </>
  );

  return (
    <>
      {/* Mobile navigation overlay */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetTrigger asChild>
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="fixed left-4 top-4 z-40 rounded-lg border-border/60 bg-card shadow-md md:hidden"
            aria-label="Open workspace navigation"
          >
            <Menu strokeWidth={1.5} />
          </Button>
        </SheetTrigger>
        <SheetContent
          side="left"
          className="flex w-[280px] flex-col gap-0 border-white/30 bg-white/80 p-0 backdrop-blur-xl"
        >
          <SheetHeader className="px-5 pt-5">
            <SheetTitle className="sr-only">Workspace navigation</SheetTitle>
          </SheetHeader>
          {renderSidebarBody(false, false)}
        </SheetContent>
      </Sheet>

      {/* Desktop sidebar */}
      <aside
        className={cn(
          "relative hidden h-full shrink-0 flex-col overflow-hidden border-r border-border/60 bg-card md:flex",
          isResizing ? "transition-none" : "transition-[width] duration-300 ease-out",
        )}
        style={{ width: collapsed ? 72 : sidebarWidth }}
        aria-label="Workspace navigation"
      >
        {renderSidebarBody(collapsed, true)}
        {!collapsed && (
          <div
            role="separator"
            tabIndex={0}
            aria-label="Resize sidebar"
            aria-orientation="vertical"
            aria-valuemin={SIDEBAR_MIN_WIDTH}
            aria-valuemax={SIDEBAR_MAX_WIDTH}
            aria-valuenow={sidebarWidth}
            className="absolute inset-y-0 right-0 z-20 w-2 cursor-col-resize touch-none bg-transparent outline-none hover:bg-primary/15 focus-visible:bg-primary/20"
            onPointerDown={startSidebarResize}
            onPointerMove={(event) => {
              if (isResizing) setDesktopSidebarWidth(event.clientX);
            }}
            onPointerUp={(event) => {
              if (!isResizing) return;
              event.currentTarget.releasePointerCapture(event.pointerId);
              setIsResizing(false);
            }}
            onPointerCancel={() => setIsResizing(false)}
            onKeyDown={(event) => {
              const delta = event.shiftKey ? 32 : 16;
              if (event.key === "ArrowLeft") {
                event.preventDefault();
                setDesktopSidebarWidth(sidebarWidth - delta);
              }
              if (event.key === "ArrowRight") {
                event.preventDefault();
                setDesktopSidebarWidth(sidebarWidth + delta);
              }
            }}
          />
        )}
      </aside>

      {/* Conversation management dialog */}
      <Dialog
        open={!!editingConversation}
        onOpenChange={(open) => {
          if (!open) {
            setEditingConversation(null);
            setConfirmConversationDelete(false);
          }
        }}
      >
        <DialogContent className="rounded-2xl border-white/30 bg-white/80 shadow-xl shadow-primary/5 backdrop-blur-xl">
          <DialogHeader>
            <DialogTitle>Manage chat</DialogTitle>
          </DialogHeader>
          <form onSubmit={renameConversation} className="flex flex-col gap-4">
            <Input
              aria-label="Conversation title"
              value={editingTitle}
              onChange={(event) => setEditingTitle(event.target.value)}
              maxLength={120}
              className="rounded-lg"
            />
            <div className="flex flex-row justify-end gap-2">
              <Button type="submit" className="rounded-lg" disabled={!editingTitle.trim()}>
                <Pencil strokeWidth={1.5} />
                Rename
              </Button>
              {!confirmConversationDelete ? (
                <Button
                  type="button"
                  variant="destructive"
                  className="rounded-lg"
                  onClick={() => setConfirmConversationDelete(true)}
                >
                  <Trash2 strokeWidth={1.5} />
                  Delete
                </Button>
              ) : (
                <Button
                  type="button"
                  variant="destructive"
                  className="rounded-lg"
                  onClick={() => {
                    if (editingConversation) void deleteConversation(editingConversation);
                  }}
                >
                  <Trash2 strokeWidth={1.5} />
                  Confirm delete
                </Button>
              )}
              <Button
                type="button"
                variant="ghost"
                className="rounded-lg"
                onClick={() => setEditingConversation(null)}
              >
                Cancel
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Project deletion dialog */}
      <Dialog
        open={!!deletingProject}
        onOpenChange={(open) => {
          if (!open) setDeletingProject(null);
        }}
      >
        <DialogContent className="rounded-2xl border-white/30 bg-white/80 shadow-xl shadow-primary/5 backdrop-blur-xl">
          <DialogHeader>
            <DialogTitle>Delete {deletingProject?.name}?</DialogTitle>
            <DialogDescription>
              This schedules removal of its chats, sources, and indexed data.
            </DialogDescription>
          </DialogHeader>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (deletingProject) void deleteProject(deletingProject.id);
            }}
            className="flex flex-col gap-4"
          >
            <div className="flex flex-row justify-end gap-2">
              <Button type="submit" variant="destructive" className="rounded-lg">
                <Trash2 strokeWidth={1.5} />
                Delete project
              </Button>
              <Button
                type="button"
                variant="ghost"
                className="rounded-lg"
                onClick={() => setDeletingProject(null)}
              >
                Cancel
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

/** Renders a selectable conversation and its rename/delete actions. */
function ConversationLink({
  conversation,
  href,
  active,
  onManage,
  onNavigate,
}: {
  conversation: ConversationSummary;
  href: string;
  active: boolean;
  onManage: (conversation: ConversationSummary) => void;
  onNavigate?: () => void;
}) {
  return (
    <div className="group/convo flex w-full min-w-0 items-center gap-1 overflow-hidden pl-7">
      <Link
        aria-current={active ? "page" : undefined}
        href={href}
        onClick={onNavigate}
        className={cn(
          "flex min-w-0 flex-1 basis-0 items-center gap-2 overflow-hidden rounded-lg px-2 py-1.5 text-sm transition-all duration-300 ease-out",
          active
            ? "bg-accent font-medium text-accent-foreground"
            : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
        )}
      >
        <MessageSquare strokeWidth={1.5} className="size-4 shrink-0" />
        <span className="truncate">{conversation.title}</span>
      </Link>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="relative z-10 h-7 w-7 shrink-0 text-muted-foreground hover:text-foreground"
        aria-label={`Manage ${conversation.title}`}
        onClick={() => onManage(conversation)}
      >
        <MoreHorizontal strokeWidth={1.5} />
      </Button>
    </div>
  );
}
