-- Expand document ingestion to structured Office files and bounded plain-text formats.

alter table documents
  drop constraint if exists documents_file_type_check;

alter table documents
  add constraint documents_file_type_check check (
    file_type in (
      'pdf', 'docx', 'pptx', 'xlsx',
      'txt', 'md', 'csv', 'tsv', 'json', 'jsonl', 'xml', 'html', 'yaml', 'toml',
      'rst', 'log', 'tex', 'bib', 'py', 'ipynb', 'js', 'jsx', 'ts', 'tsx', 'css',
      'scss', 'sql', 'sh', 'ps1', 'java', 'c', 'cpp', 'h', 'hpp', 'cs', 'go', 'rs',
      'php', 'rb', 'swift', 'kt', 'kts'
    )
  ) not valid;

alter table documents
  validate constraint documents_file_type_check;
