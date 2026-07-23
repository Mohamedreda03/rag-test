import { useState, useCallback, useEffect } from 'react';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import type { ChatMessage, ConversationResponse, DocumentResponse } from '../types';
import { api, API_URLS } from '../lib/api';

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [conversations, setConversations] = useState<ConversationResponse[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);

  // Load conversations and documents on mount
  const loadConversations = useCallback(async (selectFirst = false) => {
    try {
      const data = await api.getConversations();
      setConversations(data);
      if (selectFirst && data.length > 0) {
        selectConversation(data[0].id);
      }
    } catch (err) {
      console.error(err);
    }
  }, []);

  const loadDocuments = useCallback(async () => {
    try {
      const data = await api.getDocuments();
      setDocuments(data);
    } catch (err) {
      console.error(err);
    }
  }, []);

  useEffect(() => {
    loadConversations(true);
    loadDocuments();
  }, [loadConversations, loadDocuments]);

  const selectConversation = useCallback(async (id: string | null) => {
    setActiveConversationId(id);
    if (!id) {
      setMessages([]);
      return;
    }
    setIsLoading(true);
    try {
      const msgs = await api.getConversationMessages(id);
      const formatted = msgs.map(m => ({
        id: m.id,
        role: m.role as 'user' | 'assistant',
        content: m.content,
        sources: m.sources || [],
        traceId: m.trace_id,
        status: m.status || 'done'
      }));
      setMessages(formatted);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const createNewChat = useCallback(async (title: string = 'محادثة جديدة') => {
    try {
      const conv = await api.createConversation(title);
      setConversations(prev => [conv, ...prev]);
      setActiveConversationId(conv.id);
      setMessages([]);
      return conv.id;
    } catch (err) {
      console.error(err);
    }
  }, []);

  const deleteConversation = useCallback(async (id: string) => {
    try {
      await api.deleteConversation(id);
      setConversations(prev => prev.filter(c => c.id !== id));
      if (activeConversationId === id) {
        setMessages([]);
        setActiveConversationId(null);
      }
    } catch (err) {
      console.error(err);
    }
  }, [activeConversationId]);

  const deleteDocument = useCallback(async (id: string) => {
    try {
      await api.deleteDocument(id);
      setDocuments(prev => prev.filter(d => d.id !== id));
    } catch (err) {
      console.error(err);
      alert("فشل حذف المستند");
    }
  }, []);

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoading) return;

    let currentConvId = activeConversationId;
    
    // If no active conversation, create one first
    if (!currentConvId) {
      try {
        const title = content.length > 30 ? content.slice(0, 30) + '...' : content;
        const conv = await api.createConversation(title);
        setConversations(prev => [conv, ...prev]);
        setActiveConversationId(conv.id);
        currentConvId = conv.id;
      } catch (err) {
        console.error("Failed to auto-create conversation:", err);
        return;
      }
    }

    const userMsgId = Date.now().toString();
    const assistantMsgId = (Date.now() + 1).toString();

    setMessages(prev => [
      ...prev,
      { id: userMsgId, role: 'user', content },
      { id: assistantMsgId, role: 'assistant', content: '', isStreaming: true, statusMessage: 'جاري الاتصال...' }
    ]);
    
    setIsLoading(true);

    try {
      await fetchEventSource(API_URLS.stream, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: content, conversation_id: currentConvId }),
        openWhenHidden: true,
        onmessage(ev) {
          const { event, data } = ev;
          
          if (event === 'status') {
            const parsed = JSON.parse(data);
            setMessages(prev => prev.map(msg => 
              msg.id === assistantMsgId 
                ? { ...msg, status: parsed.stage, statusMessage: parsed.message }
                : msg
            ));
          } 
          else if (event === 'meta') {
            const parsed = JSON.parse(data);
            setMessages(prev => prev.map(msg => 
              msg.id === assistantMsgId 
                ? { ...msg, sources: parsed.sources, traceId: parsed.trace_id }
                : msg
            ));
          }
          else if (event === 'token') {
            let token = data;
            try { token = JSON.parse(data); } catch {}

            setMessages(prev => prev.map(msg => 
              msg.id === assistantMsgId 
                ? { ...msg, content: msg.content + token, statusMessage: undefined }
                : msg
            ));
          }
          else if (event === 'done') {
            setMessages(prev => prev.map(msg => 
              msg.id === assistantMsgId 
                ? { ...msg, isStreaming: false, statusMessage: undefined, status: 'done' }
                : msg
            ));
          }
        },
        onerror(err) {
          console.error('SSE Error:', err);
          setMessages(prev => prev.map(msg => 
            msg.id === assistantMsgId 
              ? { ...msg, isStreaming: false, status: 'error', statusMessage: 'حدث خطأ أثناء الاتصال' }
              : msg
          ));
          // Return nothing to prevent fetchEventSource from retrying duplicate POST requests
          return;
        }
      });
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, [activeConversationId, isLoading]);


  return {
    messages,
    sendMessage,
    isLoading,
    conversations,
    activeConversationId,
    selectConversation,
    createNewChat,
    deleteConversation,
    documents,
    loadDocuments,
    deleteDocument
  };
}
