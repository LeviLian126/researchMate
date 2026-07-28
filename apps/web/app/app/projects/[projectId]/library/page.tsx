// Implements the project source library against the authenticated document API contract.
"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { ProjectNav } from "../../../../components/project-nav";
import { StateNotice } from "../../../../components/state-notice";
import { apiFetch, DocumentRecord, fileTypeFromName, mimeForFileType } from "../../../../lib/api";

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

  /** Stores only supported file selections so invalid input never reaches the upload contract. */
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

  return (
    <main className="app-shell workspace-shell">
      <ProjectNav projectId={projectId} current="library" />
      <header className="product-header">
        <div><p className="eyebrow">Project source collection</p><h1>Library</h1><p>Upload, inspect, and recover the evidence available to this workspace.</p></div>
        <label className="search-control"><span className="sr-only">Search materials</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search materials…" /></label>
      </header>

      <section className="library-layout" aria-label="Source library">
        <form className="upload-panel" onSubmit={upload}>
          <div
            className="upload-dropzone"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => { event.preventDefault(); selectFile(event.dataTransfer.files[0] ?? null); }}
          >
            <span className="upload-dropzone__icon" aria-hidden="true">⇧</span>
            <h2>Upload materials</h2>
            <p>Drop a PDF, DOCX, or PPTX here, or choose a file from your device.</p>
            <input ref={fileInput} className="sr-only" id="source-file" type="file" accept=".pdf,.docx,.pptx" onChange={(event) => selectFile(event.target.files?.[0] ?? null)} />
            <label className="secondary-button" htmlFor="source-file">Choose file</label>
            {selectedFile && <strong className="selected-file">{selectedFile.name}</strong>}
          </div>
          <details className="local-fallback">
            <summary>Local parsed-text fallback</summary>
            <label htmlFor="manual-text">Text used only by the local in-memory upload path</label>
            <textarea id="manual-text" rows={5} value={manualText} onChange={(event) => setManualText(event.target.value)} />
          </details>
          <button className="primary-button" type="submit" disabled={!selectedFile || uploading}>{uploading ? "Uploading…" : "Upload and index"}</button>
          <div aria-live="polite">
            {status && <StateNotice state={{ title: "Ingestion status", detail: status, kind: "success" }} />}
            {error && <StateNotice state={{ title: "Library needs attention", detail: error, kind: "error" }} action={<button type="button" onClick={() => void loadDocuments()}>Retry</button>} />}
          </div>
        </form>

        <section className="document-panel" aria-labelledby="source-status-heading">
          <div className="section-heading"><div><p className="eyebrow">Indexed evidence</p><h2 id="source-status-heading">Materials</h2></div><span>{filteredDocuments.length} source{filteredDocuments.length === 1 ? "" : "s"}</span></div>
          {loading && <div className="empty-state" role="status">Loading source status…</div>}
          {!loading && filteredDocuments.length === 0 && <div className="empty-state">{query ? "No materials match this search." : "No sources yet. Upload one to make research and quizzes meaningful."}</div>}
          <div className="document-list">
            {filteredDocuments.map((document) => (
              <article className={`document-row document-row--${document.status}`} key={document.id}>
                <span className="document-row__type" aria-hidden="true">{document.file_type.toUpperCase()}</span>
                <div><strong>{document.filename}</strong><small>{formatBytes(document.size_bytes)} · {document.error_message || "Stored in this project"}</small></div>
                <div className="document-row__actions">
                  <span className={`status-badge status-badge--${document.status}`}>{document.status}</span>
                  {deleteConfirmationId === document.id ? (
                    <span className="document-delete-confirm">
                      <button type="button" onClick={() => void deleteDocument(document.id)}>Confirm remove</button>
                      <button type="button" onClick={() => setDeleteConfirmationId(null)}>Cancel</button>
                    </span>
                  ) : (
                    <button type="button" onClick={() => setDeleteConfirmationId(document.id)}>Remove</button>
                  )}
                </div>
              </article>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}

/** Formats a byte count for compact source-list metadata. */
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
