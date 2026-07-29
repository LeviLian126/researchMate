"use client";

import Link from "next/link";
import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  apiFetch,
  ConversationSummary,
  describeApiError,
  ProjectRecord,
} from "../lib/api";
import { BrandLogo } from "./brand-logo";

const PROJECT_PATTERN = /\/app\/projects\/([^/]+)/;

interface DeletionJob {
  status: "pending" | "running" | "succeeded" | "failed" | "cancelled";
  error_message?: string | null;
}

/** Owns project, conversation, and source navigation for the authenticated workspace. */
export function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeProjectId = pathname.match(PROJECT_PATTERN)?.[1] ?? null;
  const activeConversationId = searchParams.get("conversation");
  const [collapsed, setCollapsed] = useState(false);
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
    setCollapsed(saved === null ? window.innerWidth <= 820 : saved === "true");
    void loadNavigation();
    const refresh = () => void loadNavigation();
    window.addEventListener("researchmate:sidebar-refresh", refresh);
    return () => {
      requestGeneration.current += 1;
      window.removeEventListener("researchmate:sidebar-refresh", refresh);
    };
  }, [loadNavigation]);

  function toggleSidebar() {
    setCollapsed((current) => {
      window.localStorage.setItem("researchmate_sidebar_collapsed", String(!current));
      return !current;
    });
  }

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
      await loadNavigation();
      router.push(`/app/projects/${project.id}/chat?new=1`);
    } catch (requestError) {
      setError(describeApiError(requestError).detail);
    }
  }

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

  async function deleteProject(projectId: string) {
    try {
      const accepted = await apiFetch<{ job_id: string }>(`/projects/${projectId}`, {
        method: "DELETE",
      });
      setDeletingProject(null);
      setError(`Project removal job ${accepted.job_id} is pending.`);
      for (let attempt = 0; attempt < 20; attempt += 1) {
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
        await new Promise((resolve) => window.setTimeout(resolve, 1_500));
      }
      setError(`Project removal is still processing. Track job ${accepted.job_id}.`);
    } catch (requestError) {
      setError(describeApiError(requestError).detail);
    }
  }

  function startRename(conversation: ConversationSummary) {
    setEditingConversation(conversation);
    setEditingTitle(conversation.title);
    setConfirmConversationDelete(false);
  }

  return (
    <aside
      className={`app-sidebar ${collapsed ? "app-sidebar--collapsed" : ""}`}
      aria-label="Workspace navigation"
    >
      <div className="app-sidebar__top">
        <Link className="app-sidebar__brand" href="/app" aria-label="ResearchMate">
          <BrandLogo withName={!collapsed} />
        </Link>
        <button
          className="app-sidebar__collapse"
          type="button"
          onClick={toggleSidebar}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? "›" : "‹"}
        </button>
      </div>

      <nav className="app-sidebar__primary">
        <Link href="/app?new=1" aria-current={!activeProjectId && !activeConversationId ? "page" : undefined}>
          <span aria-hidden="true">＋</span><b>New chat</b>
        </Link>
        <button
          type="button"
          onClick={() => {
            if (collapsed) toggleSidebar();
            setCreatingProject((current) => !current);
          }}
        >
          <span aria-hidden="true">□</span><b>New project</b>
        </button>
      </nav>

      {creatingProject && !collapsed && (
        <form className="app-sidebar__create" onSubmit={createProject}>
          <input
            aria-label="Project name"
            autoFocus
            maxLength={120}
            value={projectName}
            onChange={(event) => setProjectName(event.target.value)}
            placeholder="Project name"
          />
          <div><button type="submit">Create</button><button type="button" onClick={() => setCreatingProject(false)}>Cancel</button></div>
        </form>
      )}

      <div className="app-sidebar__scroll">
        {!!projects.length && (
          <section>
            <div className="app-sidebar__section-title">Projects</div>
            {projects.map((project) => (
              <div className="app-sidebar__project-row" key={project.id}>
                <Link
                  className="app-sidebar__item"
                  aria-current={project.id === activeProjectId ? "page" : undefined}
                  href={`/app/projects/${project.id}/chat`}
                >
                  <span aria-hidden="true">□</span><b>{project.name}</b>
                </Link>
                {!collapsed && (
                  <details className="sidebar-menu">
                    <summary aria-label={`Manage ${project.name}`}>•••</summary>
                    <Link href={`/app/projects/${project.id}/library`}>Sources</Link>
                    <button type="button" onClick={() => setDeletingProject(project)}>Delete project</button>
                  </details>
                )}
                {!collapsed && project.id === activeProjectId && activeProjectConversations.map((conversation) => (
                  <ConversationLink
                    key={conversation.id}
                    conversation={conversation}
                    href={`/app/projects/${project.id}/chat?conversation=${conversation.id}`}
                    active={conversation.id === activeConversationId}
                    onManage={startRename}
                  />
                ))}
              </div>
            ))}
          </section>
        )}

        {!!personalConversations.length && (
          <section>
            <div className="app-sidebar__section-title">Recents</div>
            {personalConversations.map((conversation) => (
              <ConversationLink
                key={conversation.id}
                conversation={conversation}
                href={`/app?conversation=${conversation.id}`}
                active={!activeProjectId && conversation.id === activeConversationId}
                onManage={startRename}
              />
            ))}
          </section>
        )}
      </div>

      <div className="app-sidebar__footer">
        <a href="https://github.com/LeviLian126/researchMate">
          <span aria-hidden="true">↗</span><b>GitHub</b>
        </a>
        {error && !collapsed && <small role="status">{error}</small>}
      </div>

      {editingConversation && (
        <div className="sidebar-dialog" role="dialog" aria-modal="true" aria-label="Manage conversation">
          <form onSubmit={renameConversation}>
            <strong>Manage chat</strong>
            <input
              aria-label="Conversation title"
              value={editingTitle}
              onChange={(event) => setEditingTitle(event.target.value)}
              maxLength={120}
            />
            <div>
              <button type="submit">Rename</button>
              {!confirmConversationDelete ? (
                <button type="button" onClick={() => setConfirmConversationDelete(true)}>Delete</button>
              ) : (
                <button type="button" onClick={() => void deleteConversation(editingConversation)}>
                  Confirm delete
                </button>
              )}
              <button type="button" onClick={() => setEditingConversation(null)}>Cancel</button>
            </div>
          </form>
        </div>
      )}
      {deletingProject && (
        <div className="sidebar-dialog" role="dialog" aria-modal="true" aria-label="Delete project">
          <form onSubmit={(event) => {
            event.preventDefault();
            void deleteProject(deletingProject.id);
          }}>
            <strong>Delete {deletingProject.name}?</strong>
            <p>This schedules removal of its chats, sources, and indexed data.</p>
            <div>
              <button type="submit">Delete project</button>
              <button type="button" onClick={() => setDeletingProject(null)}>Cancel</button>
            </div>
          </form>
        </div>
      )}
    </aside>
  );
}
function ConversationLink({
  conversation,
  href,
  active,
  onManage,
}: {
  conversation: ConversationSummary;
  href: string;
  active: boolean;
  onManage: (conversation: ConversationSummary) => void;
}) {
  return (
    <div className="app-sidebar__conversation-row">
      <Link aria-current={active ? "page" : undefined} href={href}>{conversation.title}</Link>
      <button
        type="button"
        aria-label={`Manage ${conversation.title}`}
        onClick={() => onManage(conversation)}
      >
        •••
      </button>
    </div>
  );
}
