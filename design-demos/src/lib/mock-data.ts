export interface ProjectRecord {
  id: string;
  name: string;
}

export interface ConversationSummary {
  id: string;
  title: string;
  project_id: string;
}

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
}

export interface Citation {
  id: string;
  source_type: "web_page" | "document";
  url?: string;
  page_no?: number;
  quote: string;
}

export interface DocumentRecord {
  id: string;
  filename: string;
  status: "ready" | "processing" | "failed";
  error_message?: string | null;
}

export const mockProjects: ProjectRecord[] = [
  { id: "p1", name: "Transformer attention mechanisms" },
  { id: "p2", name: "Climate adaptation policy review" },
  { id: "p3", name: "CRISPR gene therapy ethics" },
];

export const mockPersonalProjectId = "personal";

export const mockConversations: ConversationSummary[] = [
  { id: "c1", title: "Multi-head attention vs single-head", project_id: "p1" },
  { id: "c2", title: "Linear attention complexity analysis", project_id: "p1" },
  { id: "c3", title: "Coastal resilience frameworks", project_id: "p2" },
  { id: "c4", title: "Somatic vs germline editing boundaries", project_id: "p3" },
  { id: "c5", title: "Summarize the IPCC AR6 synthesis", project_id: "personal" },
  { id: "c6", title: "What assumptions should I verify?", project_id: "personal" },
  { id: "c7", title: "Research plan for RLHF survey", project_id: "personal" },
];

export const mockMessages: ConversationMessage[] = [
  {
    id: "m1",
    role: "user",
    content: "Summarize the key differences between multi-head and single-head attention mechanisms in transformers.",
  },
  {
    id: "m2",
    role: "assistant",
    content: "Multi-head attention runs several attention functions in parallel, each over a different linear projection of the input. This lets the model jointly attend to information from different representation subspaces at different positions. Single-head attention uses one set of projection weights, so it can only model one type of relationship at a time.\n\nThe main trade-offs are:\n- Capacity: multi-head captures diverse relational patterns (syntactic, semantic, positional) simultaneously.\n- Cost: both have O(n^2 * d) time complexity for sequence length n and model dimension d, but multi-head adds a constant factor for the extra projections.\n- Empirical results: Vaswani et al. found that removing heads degrades translation quality, and single-head models need wider dimensions to match multi-head performance.",
    citations: [
      {
        id: "cit1",
        source_type: "web_page",
        url: "https://arxiv.org/abs/1706.03762",
        quote: "Multi-head attention allows the model to jointly attend to information from different representation subspaces at different positions.",
      },
      {
        id: "cit2",
        source_type: "document",
        page_no: 12,
        quote: "With a single attention head, we observed the model averaging the embedding dimensions, diminishing the effective resolution.",
      },
    ],
  },
  {
    id: "m3",
    role: "user",
    content: "What assumptions should I verify before claiming linear attention is more efficient?",
  },
  {
    id: "m4",
    role: "assistant",
    content: "Before claiming linear attention is more efficient, verify these assumptions:\n\n1. Sequence length is the bottleneck. Linear attention reduces O(n^2) to O(n) in sequence length, but if your sequences are short (< 512 tokens), the constant overhead of kernel feature maps may negate the savings.\n2. The kernel approximation preserves task quality. Linear attention replaces the softmax with a kernel feature map. Check whether retrieval or generation quality drops on your specific benchmark.\n3. Memory, not compute, is your constraint. The main win of linear attention is memory reduction, not wall-clock speedup. If you are compute-bound, the benefit is smaller.\n4. Your model is autoregressive. For bidirectional models, chunked linear attention can leverage full parallelism, changing the efficiency calculus.",
    citations: [
      {
        id: "cit3",
        source_type: "web_page",
        url: "https://arxiv.org/abs/2006.16236",
        quote: "We show that linear attention achieves comparable performance to standard softmax attention while reducing the memory complexity from O(n^2) to O(n).",
      },
    ],
  },
];

export const mockDocuments: DocumentRecord[] = [
  { id: "d1", filename: "attention-is-all-you-need.pdf", status: "ready" },
  { id: "d2", filename: "linear-attention-survey.docx", status: "ready" },
  { id: "d3", filename: "transformer-benchmark-results.pdf", status: "processing" },
];

export const mockQuizQuestions = [
  {
    id: "q1",
    question: "What is the time complexity of standard multi-head attention with respect to sequence length?",
    options: ["O(n)", "O(n log n)", "O(n^2)", "O(n^3)"],
    answer: 2,
    explanation: "Standard attention computes a full n x n attention matrix, giving O(n^2) complexity in sequence length.",
  },
  {
    id: "q2",
    question: "Which technique allows linear attention to reduce memory complexity?",
    options: [
      "Quantization of attention weights",
      "Kernel feature maps that avoid explicit attention matrix",
      "Low-rank approximation of the value matrix",
      "Pruning inactive attention heads",
    ],
    answer: 1,
    explanation: "Linear attention replaces the softmax with a kernel feature map, allowing the attention matrix to be decomposed and computed without materializing the full n x n matrix.",
  },
  {
    id: "q3",
    question: "What is a key trade-off when switching from multi-head to single-head attention?",
    options: [
      "Single-head is always faster",
      "Single-head captures fewer relational patterns simultaneously",
      "Multi-head requires less memory",
      "There is no practical difference",
    ],
    answer: 1,
    explanation: "Multi-head attention captures diverse relational patterns at different positions. Reducing to a single head limits the model to one type of relationship at a time.",
  },
];

export const mockLibraryDocuments = [
  { id: "lib1", filename: "attention-is-all-you-need.pdf", type: "PDF", size: "2.1 MB", uploaded: "2 days ago", status: "ready" as const },
  { id: "lib2", filename: "linear-attention-survey.docx", type: "DOCX", size: "847 KB", uploaded: "1 day ago", status: "ready" as const },
  { id: "lib3", filename: "transformer-benchmark-results.pdf", type: "PDF", size: "1.4 MB", uploaded: "3 hours ago", status: "processing" as const },
  { id: "lib4", filename: "rlhf-training-notes.pptx", type: "PPTX", size: "3.2 MB", uploaded: "5 days ago", status: "ready" as const },
];

export const emptyPrompts = [
  "Summarize the material and identify its strongest claim.",
  "What assumptions should I verify?",
  "Turn these ideas into a clear research plan.",
];
