// Owns global project, conversation, source, quiz, and developer navigation.
"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { apiFetch, ConversationSummary, describeApiError, ProjectRecord } from "../lib/api";
import { getSupabaseSession, isLocalDevelopment } from "../lib/supabase";

const PROJECT_PATTERN = /\/app\/projects\/([^/]+)/;

/** Renders the collapsible ChatGPT-style application rail backed by owned API data. */
export function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeProjectId = pathname.match(PROJECT_PATTERN)?.[1] ?? null;
  const activeConversationId = searchParams.get("conversation");
  const [collapsed, setCollapsed] = useState(false);
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [creating, setCreating] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [developer, setDeveloper] = useState(isLocalDevelopment());
  const [managedConversationId, setManagedConversationId] = useState<string | null>(null);
  const [deleteConfirmationId, setDeleteConfirmationId] = useState<string | null>(null);
  const [managedProjectId, setManagedProjectId] = useState<string | null>(null);
  const [deleteProjectConfirmationId, setDeleteProjectConfirmationId] = useState<string | null>(null);
  const [deletingProjectId, setDeletingProjectId] = useState<string | null>(null);
  const [conversationTitle, setConversationTitle] = useState("");
  const navigationRequest = useRef(0);

  const activeProject = useMemo(
    () => projects.find((project) => project.id === activeProjectId) ?? null,
    [activeProjectId, projects],
  );

  const loadNavigation = useCallback(async () => {
    const requestId = ++navigationRequest.current;
    const requestedProjectId = activeProjectId;
    try {
      const ownedProjects = await apiFetch<ProjectRecord[]>("/projects");
      if (requestId !== navigationRequest.current) return;
      let ownedConversations: ConversationSummary[] = [];
      if (requestedProjectId) {
        const body = await apiFetch<{ items: ConversationSummary[] }>(
          `/projects/${requestedProjectId}/conversations`,
        );
        if (requestId !== navigationRequest.current) return;
        ownedConversations = body.items;
      }
      setProjects(ownedProjects);
      setConversations(ownedConversations);
      setError(null);
    } catch (requestError) {
      if (requestId === navigationRequest.current) {
        setError(describeApiError(requestError).detail);
      }
    }
  }, [activeProjectId]);

  useEffect(() => {
    setCollapsed(window.localStorage.getItem("researchmate_sidebar_collapsed") === "true");
    void getSupabaseSession().then((session) => {
      const role = session?.user?.role;
      setDeveloper(isLocalDevelopment() || role === "developer" || role === "admin");
    });
  }, []);

  useEffect(() => {
    void loadNavigation();
    const refresh = () => void loadNavigation();
    window.addEventListener("researchmate:sidebar-refresh", refresh);
    return () => {
      navigationRequest.current += 1;
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
    const name = projectName.trim();
    if (!name) return;
    try {
      const project = await apiFetch<ProjectRecord>("/projects", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      setProjectName("");
      setCreating(false);
      await loadNavigation();
      router.push(`/app/projects/${project.id}/chat?new=1`);
    } catch (requestError) {
      setError(describeApiError(requestError).detail);
    }
  }

  async function renameConversation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!managedConversationId || !conversationTitle.trim()) return;
    try {
      await apiFetch(`/conversations/${managedConversationId}`, {
        method: "PATCH",
        body: JSON.stringify({ title: conversationTitle.trim() }),
      });
      setManagedConversationId(null);
      setDeleteConfirmationId(null);
      await loadNavigation();
    } catch (requestError) {
      setError(describeApiError(requestError).detail);
    }
  }

  async function deleteConversation(conversationId: string) {
    try {
      await apiFetch(`/conversations/${conversationId}`, { method: "DELETE" });
      setManagedConversationId(null);
      await loadNavigation();
      if (conversationId === activeConversationId && activeProjectId) {
        router.push(`/app/projects/${activeProjectId}/chat?new=1`);
      }
    } catch (requestError) {
      setError(describeApiError(requestError).detail);
    }
  }

  async function deleteProject(projectId: string) {
    setDeletingProjectId(projectId);
    try {
      const accepted = await apiFetch<{ job_id: string }>(
        `/projects/${projectId}`,
        { method: "DELETE" },
      );
      let completed = false;
      for (let attempt = 0; attempt < 60; attempt += 1) {
        const job = await apiFetch<{ status: string; error_message?: string | null }>(
          `/jobs/${accepted.job_id}`,
        );
        if (job.status === "succeeded") {
          completed = true;
          break;
        }
        if (job.status === "failed") {
          throw new Error(
            job.error_message
              ? `Project deletion failed: ${job.error_message}`
              : "Project deletion failed. The project is available to retry.",
          );
        }
        await new Promise((resolve) => window.setTimeout(resolve, 1_000));
      }
      if (!completed) {
        throw new Error("Project deletion is still running. Refresh shortly to check its status.");
      }
      setProjects((current) => current.filter((project) => project.id !== projectId));
      setManagedProjectId(null);
      setDeleteProjectConfirmationId(null);
      if (projectId === activeProjectId) {
        setConversations([]);
        router.push("/app");
      }
      window.dispatchEvent(new Event("researchmate:sidebar-refresh"));
    } catch (requestError) {
      setError(
        requestError instanceof Error && requestError.message.startsWith("Project deletion")
          ? requestError.message
          : describeApiError(requestError).detail,
      );
      await loadNavigation();
    } finally {
      setDeletingProjectId(null);
    }
  }

  return (
    <aside className={`app-sidebar ${collapsed ? "app-sidebar--collapsed" : ""}`} aria-label="Workspace navigation">
      <div className="app-sidebar__top">
        <Link className="app-sidebar__brand" href="/app" aria-label="ResearchMate projects">
          <span aria-hidden="true">R</span><strong>ResearchMate</strong>
        </Link>
        <button className="app-sidebar__collapse" type="button" onClick={toggleSidebar} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}>{collapsed ? "›" : "‹"}</button>
      </div>

      <nav className="app-sidebar__primary">
        <Link aria-label="New chat" href={activeProjectId ? `/app/projects/${activeProjectId}/chat?new=1` : "/app"}><span aria-hidden="true">＋</span><b>New chat</b></Link>
        <button aria-label="New project" type="button" onClick={() => {
          if (collapsed) {
            setCollapsed(false);
            window.localStorage.setItem("researchmate_sidebar_collapsed", "false");
          }
          setCreating((current) => !current);
        }}><span aria-hidden="true">□</span><b>New project</b></button>
        {activeProjectId && <Link aria-label="Manage project sources" href={`/app/projects/${activeProjectId}/library`}><span aria-hidden="true">⇧</span><b>Sources</b></Link>}
        {activeProjectId && <Link aria-label="Create a new quiz" href={`/app/projects/${activeProjectId}/quiz?new=1`}><span aria-hidden="true">?</span><b>New quiz</b></Link>}
      </nav>

      {creating && !collapsed && (
        <form className="app-sidebar__create" onSubmit={createProject}>
          <label htmlFor="sidebar-project-name">Project name</label>
          <input id="sidebar-project-name" autoFocus value={projectName} onChange={(event) => setProjectName(event.target.value)} maxLength={120} />
          <div><button type="submit">Create</button><button type="button" onClick={() => setCreating(false)}>Cancel</button></div>
        </form>
      )}

      <div className="app-sidebar__scroll">
        <section>
          <div className="app-sidebar__section-title"><span>Projects</span><Link href="/app" aria-label="View all projects">•••</Link></div>
          {projects.map((project) => (
            <div className="app-sidebar__project-row" key={project.id}>
              {project.status === "active" ? (
                <Link className="app-sidebar__item" aria-current={project.id === activeProjectId ? "page" : undefined} href={`/app/projects/${project.id}/chat`}>
                  <span aria-hidden="true">□</span><b>{project.name}</b>
                </Link>
              ) : (
                <div className="app-sidebar__item" aria-disabled="true">
                  <span aria-hidden="true">!</span><b>{project.name} · deletion pending</b>
                </div>
              )}
              <button
                type="button"
                aria-label={`Manage ${project.name}`}
                onClick={() => {
                  setManagedProjectId((current) => current === project.id ? null : project.id);
                  setDeleteProjectConfirmationId(null);
                }}
              >•••</button>
              {managedProjectId === project.id && (
                <div className="app-sidebar__project-menu">
                  {deleteProjectConfirmationId === project.id ? (
                    <>
                      <p>Delete this project and all of its chats and sources?</p>
                      <button
                        className="danger-button"
                        type="button"
                        disabled={deletingProjectId === project.id}
                        onClick={() => void deleteProject(project.id)}
                      >{deletingProjectId === project.id ? "Deleting…" : "Confirm delete"}</button>
                      <button type="button" onClick={() => setDeleteProjectConfirmationId(null)}>Cancel</button>
                    </>
                  ) : (
                    <button className="danger-button" type="button" onClick={() => setDeleteProjectConfirmationId(project.id)}>
                      {project.status === "active" ? "Delete project" : "Retry deletion"}
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </section>

        {activeProject && (
          <section>
            <div className="app-sidebar__section-title"><span>Recent in {activeProject.name}</span></div>
            {conversations.length === 0 && <small>No conversations yet</small>}
            {conversations.map((conversation) => (
              <div className="app-sidebar__conversation-row" key={conversation.id}>
                <Link className="app-sidebar__conversation" aria-current={conversation.id === activeConversationId ? "page" : undefined} href={`/app/projects/${activeProject.id}/chat?conversation=${conversation.id}`}>{conversation.title}</Link>
                <button
                  type="button"
                  aria-label={`Manage ${conversation.title}`}
                  onClick={() => {
                    setManagedConversationId((current) => current === conversation.id ? null : conversation.id);
                    setDeleteConfirmationId(null);
                    setConversationTitle(conversation.title);
                  }}
                >•••</button>
                {managedConversationId === conversation.id && (
                  <form className="app-sidebar__conversation-menu" onSubmit={renameConversation}>
                    <label htmlFor={`conversation-${conversation.id}`}>Conversation title</label>
                    <input id={`conversation-${conversation.id}`} value={conversationTitle} onChange={(event) => setConversationTitle(event.target.value)} maxLength={120} />
                    <div>
                      <button type="submit">Rename</button>
                      {deleteConfirmationId === conversation.id ? (
                        <>
                          <button className="danger-button" type="button" onClick={() => void deleteConversation(conversation.id)}>Confirm delete</button>
                          <button type="button" onClick={() => setDeleteConfirmationId(null)}>Cancel</button>
                        </>
                      ) : (
                        <button className="danger-button" type="button" onClick={() => setDeleteConfirmationId(conversation.id)}>Delete</button>
                      )}
                    </div>
                  </form>
                )}
              </div>
            ))}
          </section>
        )}
      </div>

      <div className="app-sidebar__footer">
        {developer && activeProjectId && <Link aria-label="Engineering evaluation and reliability" href={`/app/projects/${activeProjectId}/labs`}><span aria-hidden="true">⌁</span><b>Engineering</b></Link>}
        <a aria-label="ResearchMate on GitHub" href="https://github.com/LeviLian126/researchMate"><span aria-hidden="true">↗</span><b>GitHub</b></a>
        {error && !collapsed && <small role="status">{error}</small>}
      </div>
    </aside>
  );
}
