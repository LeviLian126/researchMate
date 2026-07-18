"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { ProjectNav } from "../../../../components/project-nav";
import { StateNotice } from "../../../../components/state-notice";
import { apiFetch, DocumentRecord, fileTypeFromName, mimeForFileType } from "../../../../lib/api";

interface UploadUrlResponse {
  document_id: string;
  upload_url: string;
  r2_object_key: string;
  expires_in_seconds: number;
}

export default function LibraryPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [manualText, setManualText] = useState("RAG uses retrieval before generation. Citations must point to source chunks.");
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  async function loadDocuments() {
    try {
      setDocuments(await apiFetch<DocumentRecord[]>(`/projects/${projectId}/documents`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Documents could not be loaded.");
    }
  }

  useEffect(() => {
    void loadDocuments();
  }, [projectId]);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setStatus("Requesting a bounded upload URL…");
    try {
      if (!selectedFile) {
        throw new Error("Select a PDF, DOCX, or PPTX file.");
      }
      const fileType = fileTypeFromName(selectedFile.name);
      const mimeType = mimeForFileType(fileType);
      const uploadPayload = {
        project_id: projectId,
        filename: selectedFile.name,
        file_type: fileType,
        mime_type: mimeType,
        size_bytes: selectedFile.size || manualText.length || 1,
      };
      const uploadUrl = await apiFetch<UploadUrlResponse>("/documents/upload-url", {
        method: "POST",
        body: JSON.stringify(uploadPayload),
      });
      setStatus(`Upload URL ready for ${uploadUrl.expires_in_seconds} seconds.`);
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
      setStatus("Upload verified. Parsing and indexing are queued.");
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload could not be completed.");
    }
  }

  return (
    <main className="app-shell">
      <ProjectNav projectId={projectId} current="library" />
      <section className="workspace-header glass-panel">
        <div>
          <p className="eyebrow">Source library</p>
          <h1>Upload, parse, and index</h1>
          <p>Production uploads directly to a short-lived R2 URL. Local memory mode uses an explicit text fallback because it has no object-storage endpoint.</p>
        </div>
        <Link className="secondary-button" href={`/app/projects/${projectId}`}>Review evidence</Link>
      </section>

      <section className="content-grid two-columns">
        <form className="glass-panel stack" onSubmit={upload}>
          <h2>Add a source</h2>
          <input type="file" accept=".pdf,.docx,.pptx" onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)} />
          <label htmlFor="manual-text">Local-only parsed text fallback</label>
          <textarea id="manual-text" rows={8} value={manualText} onChange={(event) => setManualText(event.target.value)} />
          <button className="primary-button" type="submit">Upload and queue ingestion</button>
          {status && <StateNotice state={{ title: "Ingestion status", detail: status, kind: "success" }} />}
          {error && <StateNotice state={{ title: "Upload needs attention", detail: error, kind: "error" }} />}
        </form>

        <div className="glass-panel stack">
          <h2>Source status</h2>
          {documents.length === 0 && <p className="empty-state">No sources yet. Upload one to make retrieval and evidence review meaningful.</p>}
          {documents.map((document) => (
            <article className="resource-card" key={document.id}>
              <div>
                <strong>{document.filename}</strong>
                <span>{document.status}</span>
              </div>
              <small>{document.error_message || `${document.size_bytes} bytes`}</small>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
