import type { IngestAccepted, IngestStatus, DocumentResponse, ConversationResponse } from '../types';

const API_BASE = 'http://127.0.0.1:8000';

export const api = {
  async checkHealth(): Promise<boolean> {
    try {
      const res = await fetch(`${API_BASE}/health`);
      return res.ok;
    } catch {
      return false;
    }
  },

  async uploadFiles(files: File[]): Promise<IngestAccepted> {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    
    const res = await fetch(`${API_BASE}/ingest`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error('Upload failed');
    return res.json();
  },

  async getIngestStatus(jobId: string): Promise<IngestStatus> {
    const res = await fetch(`${API_BASE}/ingest/status/${jobId}`);
    if (!res.ok) throw new Error('Failed to get status');
    return res.json();
  },

  async getDocuments(): Promise<DocumentResponse[]> {
    const res = await fetch(`${API_BASE}/documents`);
    if (!res.ok) throw new Error('Failed to fetch documents');
    return res.json();
  },

  async deleteDocument(id: string): Promise<void> {
    const res = await fetch(`${API_BASE}/documents/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('Failed to delete document');
  },

  async getConversations(): Promise<ConversationResponse[]> {
    const res = await fetch(`${API_BASE}/conversations`);
    if (!res.ok) throw new Error('Failed to fetch conversations');
    return res.json();
  },

  async createConversation(title: string): Promise<ConversationResponse> {
    const res = await fetch(`${API_BASE}/conversations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    });
    if (!res.ok) throw new Error('Failed to create conversation');
    return res.json();
  },

  async deleteConversation(id: string): Promise<void> {
    const res = await fetch(`${API_BASE}/conversations/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('Failed to delete conversation');
  },

  async getConversationMessages(id: string): Promise<any[]> {
    const res = await fetch(`${API_BASE}/conversations/${id}/messages`);
    if (!res.ok) throw new Error('Failed to fetch messages');
    return res.json();
  },

  async getTraces(): Promise<any[]> {
    const res = await fetch(`${API_BASE}/traces`);
    if (!res.ok) return [];
    return res.json();
  },

  async getTrace(id: string): Promise<any> {
    const res = await fetch(`${API_BASE}/traces/${id}`);
    if (!res.ok) throw new Error('Trace not found');
    return res.json();
  }
};

export const API_URLS = {
  stream: `${API_BASE}/query/stream`,
  dashboard: `${API_BASE}/dashboard`,
  docs: `${API_BASE}/docs`,
};
