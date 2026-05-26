"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { apiFetch, DocumentRecord, fileTypeFromName, mimeForFileType } from "../../../../lib/api";

interface UploadUrlResponse {
  document_id: string;
  upload_url: string;
  r2_object_key: string;
  expires_in_seconds: number;
}

// 渲染资料库、上传和解析状态。
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
      setError(err instanceof Error ? err.message : "无法加载文件");
    }
  }

  useEffect(() => {
    void loadDocuments();
  }, [projectId]);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setStatus("准备上传...");
    try {
      if (!selectedFile) {
        throw new Error("请选择 PDF/DOCX/PPTX 文件");
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
      setStatus(`Signed URL ready: ${uploadUrl.expires_in_seconds}s`);
      const extractedText = manualText.trim() || (await selectedFile.text());
      await apiFetch(`/documents/${uploadUrl.document_id}/complete`, {
        method: "POST",
        body: JSON.stringify({ extracted_text: extractedText }),
      });
      setStatus("解析与索引完成");
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传失败");
    }
  }

  return (
    <main className="app-shell">
      <section className="workspace-header glass-panel">
        <div>
          <p className="eyebrow">Library</p>
          <h1>上传、解析与索引</h1>
          <p>本地开发通过 extracted_text 模拟 worker 从 R2 解析后的文本；上线后替换为真实 R2 + parser。</p>
        </div>
        <div className="row-actions">
          <Link href={`/app/projects/${projectId}`}>Ask</Link>
          <Link href={`/app/projects/${projectId}/quiz`}>Quiz</Link>
        </div>
      </section>

      <section className="content-grid two-columns">
        <form className="glass-panel stack" onSubmit={upload}>
          <h2>上传资料</h2>
          <input type="file" accept=".pdf,.docx,.pptx" onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)} />
          <label htmlFor="manual-text">本地解析文本 fallback</label>
          <textarea id="manual-text" rows={8} value={manualText} onChange={(event) => setManualText(event.target.value)} />
          <button className="primary-button" type="submit">上传并解析</button>
          {status && <p className="success-banner">{status}</p>}
          {error && <p className="error-banner">{error}</p>}
        </form>

        <div className="glass-panel stack">
          <h2>文件状态</h2>
          {documents.length === 0 && <p>暂无文件。</p>}
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
