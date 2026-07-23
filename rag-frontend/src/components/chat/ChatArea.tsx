import React, { useRef, useEffect } from 'react';
import type { ChatMessage } from '../../types';
import { MessageBubble } from './MessageBubble';
import { Bot } from 'lucide-react';

interface Props {
  messages: ChatMessage[];
  onSuggestionClick: (text: string) => void;
}

export const ChatArea: React.FC<Props> = ({ messages, onSuggestionClick }) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center animate-in fade-in duration-700">
        <div className="w-16 h-16 bg-emerald-100 dark:bg-emerald-900/30 rounded-full flex items-center justify-center mb-6">
          <Bot size={32} className="text-emerald-600 dark:text-emerald-400" />
        </div>
        <h1 className="text-2xl font-bold mb-2">مرحباً بك في RAG Chat</h1>
        <p className="text-muted-foreground max-w-md mb-8">
          قم برفع مستنداتك من القائمة الجانبية، ثم اسأل أي سؤال وسأجيبك بدقة مع توفير المصادر التي استندت إليها.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-2xl">
          {[
            "لخص لي أهم النقاط في المستند؟",
            "قارن بين المفاهيم الرئيسية المذكورة",
            "ما هي الاستنتاجات والتوصيات النهائية؟",
            "اشرح لي بالتفصيل الفكرة الأساسية"
          ].map((text, i) => (
            <button 
              key={i}
              onClick={() => onSuggestionClick(text)}
              className="p-4 border border-gray-200 dark:border-gray-800 rounded-xl text-sm text-right hover:bg-gray-50 dark:hover:bg-gray-900 transition-colors"
            >
              {text}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto pb-32">
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      <div ref={bottomRef} className="h-4" />
    </div>
  );
};
