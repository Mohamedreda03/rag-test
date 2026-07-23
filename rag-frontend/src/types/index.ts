export interface IngestAccepted {
  job_id: string;
  filenames: string[];
  status: string;
}

export interface IngestStatus {
  job_id: string;
  status: 'processing' | 'done' | 'failed';
  detail?: string;
  chunks_indexed: number;
}

export interface Source {
  ref: number;
  source: string;
  text: string;
  score: number;
}

export interface QueryResponse {
  answer: string;
  question_type: string;
  sub_questions: string[];
  sources: Source[];
  verified: boolean;
  trace_id?: string;
  conversation_id?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  status?: 'understanding' | 'searching' | 'ranking' | 'generating' | 'done' | 'error';
  statusMessage?: string;
  sources?: Source[];
  traceId?: string;
  isStreaming?: boolean;
}

export interface DocumentResponse {
  id: string;
  filename: string;
  status: 'processing' | 'done' | 'failed';
  chunks_indexed: number;
  error_detail?: string;
  created_at: string;
}

export interface ConversationResponse {
  id: string;
  title: string;
  created_at: string;
}

