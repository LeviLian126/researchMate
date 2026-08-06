// Implements the project source library against the authenticated document API contract.
"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Search, Trash2, Upload } from "lucide-react";
import { ProjectNav } from "../../../../components/project-nav";
import { StateNotice } from "../../../../components/state-notice";
import { apiFetch, DocumentRecord, fileTypeFromName, mimeForFileType } from "../../../../lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface UploadUrlResponse {
  document_id: string;
  upload_url: string;
  r2_object_key: string;
  expires_in_seconds: number;
}

interface DeletionJob {
  id: string;
  status: "pending" | "running" | "succeeded" | "failed" | "cancelled";
  progress: number;
  error_message?: string | null;
}

/** Presents source upload, ingestion feedback, search, and document status in one operational view. */
export default function LibraryPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const fileInput = useRef<HTMLInputElement>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [manualText, setManualText] = useState("RAG uses retrieval before generation. Citations must point to source chunks.");
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deleteConfirmationId, setDeleteConfirmationId] = useState<string | null>(null);
  const mounted = useRef(true);

  const filteredDocuments = useMemo(
    () => documents.filter((document) => document.filename.toLowerCase().includes(query.trim().toLowerCase())),
    [documents, query],
  );

  /** Reloads the canonical document list and exposes recoverable failures to the user. */
  async function loadDocuments() {
    setLoading(true);
    try {
      setDocuments(await apiFetch<DocumentRecord[]>(`/projects/${projectId}/documents`));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Documents could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    mounted.current = true;
    void loadDocuments();
    return () => { mounted.current = false; };
  }, [projectId]);

  useEffect(() => {
    if (!documents.some((document) => ["uploaded", "parsing", "parsed", "indexing"].includes(document.status))) {
      return;
    }
    const timer = window.setInterval(() => void loadDocuments(), 2_000);
    return () => window.clearInterval(timer);
  }, [documents]);

  /** Stores only supported file selections so invalid input never reaches the upload contract. */
  /** Validates the selected file and prepares local preview metadata. */
  function selectFile(file: File | null) {
    if (!file) return;
    if (!/\.(pdf|docx|pptx)$/i.test(file.name)) {
      setError("Choose a PDF, DOCX, or PPTX file.");
      return;
    }
    setSelectedFile(file);
    setError(null);
    setStatus(null);
  }

  /** Completes the signed-upload flow and refreshes ingestion state after the API accepts the source. */
  /** Uploads and completes a source document while preserving recoverable form state. */
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setUploading(true);
    setStatus("Requesting a bounded upload URL…");
    try {
      if (!selectedFile) throw new Error("Select a PDF, DOCX, or PPTX file.");
      const fileType = fileTypeFromName(selectedFile.name);
      const mimeType = mimeForFileType(fileType);
      const uploadUrl = await apiFetch<UploadUrlResponse>("/documents/upload-url", {
        method: "POST",
        body: JSON.stringify({
          project_id: projectId,
          filename: selectedFile.name,
          file_type: fileType,
          mime_type: mimeType,
          size_bytes: selectedFile.size || manualText.length || 1,
        }),
      });
      const isLocalFallback = uploadUrl.upload_url.includes("/api/v1/dev/upload/");
      if (!isLocalFallback) {
        const uploadResponse = await fetch(uploadUrl.upload_url, {
          method: "PUT",
          headers: { "Content-Type": mimeType },
          body: selectedFile,
        });
        if (!uploadResponse.ok) throw new Error("Object storage rejected the upload. Request a new URL and retry.");
      }
      await apiFetch(`/documents/${uploadUrl.document_id}/complete`, {
        method: "POST",
        body: JSON.stringify({ extracted_text: isLocalFallback ? manualText.trim() || (await selectedFile.text()) : null }),
      });
      setStatus("Source accepted. Parsing and indexing are queued.");
      setSelectedFile(null);
      if (fileInput.current) fileInput.current.value = "";
      await loadDocuments();
    } catch (err) {
      setStatus(null);
      setError(err instanceof Error ? err.message : "Upload could not be completed.");
    } finally {
      setUploading(false);
    }
  }

  /** Queues canonical source deletion and refreshes the visible project collection. */
  /** Starts deletion only after the row has entered explicit confirmation state. */
  async function deleteDocument(documentId: string) {
    setError(null);
    setStatus("Scheduling source removal…");
    try {
      const accepted = await apiFetch<{ job_id: string; status: string }>(
        `/documents/${documentId}`,
        { method: "DELETE" },
      );
      setStatus(`Source removal job ${accepted.job_id} is ${accepted.status}.`);
      setDeleteConfirmationId(null);
      await loadDocuments();
      await pollDeletionJob(accepted.job_id);
    } catch (err) {
      setStatus(null);
      setError(err instanceof Error ? err.message : "Source removal could not be scheduled.");
    }
  }

  /** Polls the durable deletion job so object/vector cleanup failures stay visible. */
  /** Polls the asynchronous deletion job until it reaches a terminal state. */
  async function pollDeletionJob(jobId: string) {
    for (let attempt = 0; attempt < 20 && mounted.current; attempt += 1) {
      let job: DeletionJob;
      try {
        job = await apiFetch<DeletionJob>(`/jobs/${jobId}`);
      } catch {
        if (mounted.current) {
          setStatus(`Source removal was accepted, but job ${jobId} status is temporarily unavailable.`);
        }
        return;
      }
      if (!mounted.current) return;
      if (job.status === "succeeded") {
        setStatus("Source removal completed, including the durable cleanup job.");
        return;
      }
      if (job.status === "failed" || job.status === "cancelled") {
        setStatus(null);
        setError(job.error_message || `Source removal job ${jobId} ${job.status}. Retry the removal or contact an administrator.`);
        return;
      }
      setStatus(`Source removal is ${job.status} (${job.progress}%).`);
      await new Promise((resolve) => window.setTimeout(resolve, 1500));
    }
    if (mounted.current) {
      setStatus(`Source removal is still processing. Track job ${jobId} from the project status API.`);
    }
  }

  const typeBadgeClass = (fileType: string) => {
    switch (fileType.toLowerCase()) {
      case "pdf": return "border-red-200 bg-red-50 text-red-600";
      case "docx": return "border-blue-200 bg-blue-50 text-blue-600";
      case "pptx": return "border-orange-200 bg-orange-50 text-orange-600";
      default: return "border-border bg-secondary text-muted-foreground";
    }
  };

  const statusVariant = (documentStatus: string): "success" | "warning" | "destructive" | "secondary" => {
    if (documentStatus === "ready") return "success";
    if (["uploaded", "parsing", "parsed", "indexing"].includes(documentStatus)) return "warning";
    if (documentStatus === "failed") return "destructive";
    return "secondary";
  };

  return (
    <main className="min-h-[100dvh] bg-gradient-to-br from-accent via-background to-background">
      <ProjectNav projectId={projectId} current="library" />
      <div className="mx-auto max-w-6xl px-6 py-8">
        <header className="mb-6 flex items-center justify-between gap-4">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Sources</h1>
          <div className="relative w-full max-w-xs">
            <Search strokeWidth={1.5} className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <span className="sr-only">Search materials</span>
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search materials…"
              aria-label="Search materials"
              className="rounded-lg border-border/60 bg-white/50 pl-9 backdrop-blur-sm"
            />
          </div>
        </header>

        <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]" aria-label="Source library">
          <form className="space-y-4 rounded-2xl border border-white/30 bg-white/70 p-6 shadow-lg shadow-primary/5 backdrop-blur-xl" onSubmit={upload}>
            <div
              className="rounded-2xl border-2 border-dashed border-border bg-secondary/30 px-6 py-10 text-center transition-all hover:border-primary/40 hover:bg-accent/30"
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => { event.preventDefault(); selectFile(event.dataTransfer.files[0] ?? null); }}
            >
              <Upload strokeWidth={1.5} className="mx-auto size-8 text-primary" />
              <h2 className="mt-3 text-base font-semibold text-foreground">Upload materials</h2>
              <p className="mt-1 text-sm text-muted-foreground">Drop a PDF, DOCX, or PPTX here, or choose a file from your device.</p>
              <input ref={fileInput} className="sr-only" id="source-file" type="file" accept=".pdf,.docx,.pptx" onChange={(event) => selectFile(event.target.files?.[0] ?? null)} />
              <Button asChild variant="secondary" className="mt-4">
                <label htmlFor="source-file" className="cursor-pointer">Choose file</label>
              </Button>
              {selectedFile && <p className="mt-3 text-sm font-medium text-foreground">{selectedFile.name}</p>}
            </div>

            <details className="group">
              <summary className="cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground">Local parsed-text fallback</summary>
              <div className="mt-3 space-y-2">
                <label htmlFor="manual-text" className="text-xs text-muted-foreground">Text used only by the local in-memory upload path</label>
                <Textarea id="manual-text" rows={5} value={manualText} onChange={(event) => setManualText(event.target.value)} />
              </div>
            </details>

            <Button type="submit" disabled={!selectedFile || uploading} className="w-full">
              {uploading ? "Uploading…" : "Upload and index"}
            </Button>

            <div aria-live="polite">
              {status && <StateNotice state={{ title: "Ingestion status", detail: status, kind: "success" }} />}
              {error && <StateNotice state={{ title: "Library needs attention", detail: error, kind: "error" }} action={<Button type="button" variant="outline" size="sm" onClick={() => void loadDocuments()}>Retry</Button>} />}
            </div>
          </form>

          <section aria-labelledby="source-status-heading" className="rounded-2xl border border-white/30 bg-white/70 p-6 shadow-lg shadow-primary/5 backdrop-blur-xl">
            <div className="mb-4 flex items-center justify-between gap-4">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Indexed evidence</p>
                <h2 id="source-status-heading" className="text-lg font-semibold text-foreground">Materials</h2>
              </div>
              <Badge variant="secondary">{filteredDocuments.length} source{filteredDocuments.length === 1 ? "" : "s"}</Badge>
            </div>
            {loading && <div className="py-8 text-center text-sm text-muted-foreground" role="status">Loading source status…</div>}
            {!loading && filteredDocuments.length === 0 && <div className="py-8 text-center text-sm text-muted-foreground">{query ? "No materials match this search." : "No sources yet. Upload one to make research and quizzes meaningful."}</div>}
            <div className="space-y-2">
              {filteredDocuments.map((document) => (
                <article
                  key={document.id}
                  className="flex items-center gap-3 rounded-xl border border-border/50 bg-white/50 px-4 py-3 backdrop-blur-sm transition-all hover:-translate-y-0.5 hover:border-primary/20 hover:bg-white/70 hover:shadow-md hover:shadow-primary/5"
                >
                  <span className={cn("inline-flex shrink-0 items-center rounded-md border px-2 py-0.5 font-mono text-[10px] font-semibold", typeBadgeClass(document.file_type))}>
                    {document.file_type.toUpperCase()}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">{document.filename}</p>
                    <p className="truncate text-xs text-muted-foreground">{formatBytes(document.size_bytes)} · {document.error_message || "Stored in this project"}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Badge variant={statusVariant(document.status)}>{document.status}</Badge>
                    {deleteConfirmationId === document.id ? (
                      <span className="flex items-center gap-1">
                        <Button type="button" size="sm" variant="destructive" onClick={() => void deleteDocument(document.id)}>Confirm</Button>
                        <Button type="button" size="sm" variant="outline" onClick={() => setDeleteConfirmationId(null)}>Cancel</Button>
                      </span>
                    ) : (
                      <Button type="button" size="sm" variant="ghost" onClick={() => setDeleteConfirmationId(document.id)}>
                        <Trash2 strokeWidth={1.5} className="size-4" />
                        Remove
                      </Button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </section>
        </section>
      </div>
    </main>
  );
}

/** Formats a byte count for compact source-list metadata. */
/** Formats source size metadata for compact table display. */
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
