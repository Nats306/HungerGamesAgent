export interface Source {
  index: number;
  document_id: string;
  title: string;
  source_url?: string | null;
  page?: number | null;
  section?: string | null;
  similarity: number;
  snippet: string;
}

export type AnswerStatus = "answered" | "rejected" | "greeting" | "clarification" | "error";

export interface ChatResponse {
  conversation_id: string;
  answer: string;
  status: AnswerStatus;
  sources: Source[];
}

export interface Message {
  id: number | string;
  role: "user" | "assistant";
  content: string;
  status?: AnswerStatus | null;
  sources: Source[];
  created_at?: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface DocumentItem {
  id: string;
  filename: string;
  title: string;
  source_url?: string | null;
  content_type: string;
  status: "processing" | "ready" | "failed";
  error?: string | null;
  chunk_count: number;
  uploaded_by_name: string;
  created_at: string;
  can_delete: boolean;
}
