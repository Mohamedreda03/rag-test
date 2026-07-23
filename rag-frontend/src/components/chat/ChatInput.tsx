import React, { useState, type KeyboardEvent, useRef, useEffect } from 'react';

import { SendHorizonal } from 'lucide-react';
import { Button } from '../ui/button';
import { Textarea } from '../ui/textarea';

interface Props {
  onSend: (message: string) => void;
  isLoading: boolean;
}

export const ChatInput: React.FC<Props> = ({ onSend, isLoading }) => {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    if (!input.trim() || isLoading) return;
    onSend(input);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'; // reset height
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Auto resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  return (
    <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-white via-white dark:from-[#0a0a0a] dark:via-[#0a0a0a] to-transparent pt-10 pb-6 px-4 md:px-8">
      <div className="max-w-4xl mx-auto relative group">
        <Textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          dir="rtl"
          placeholder="اسأل سؤالاً عن مستنداتك..."
          className="min-h-[60px] w-full resize-none rounded-2xl border-gray-300 dark:border-gray-800 bg-white dark:bg-[#111111] pr-5 pl-14 py-4 shadow-sm focus-visible:ring-emerald-500 focus-visible:border-emerald-500 text-base font-sans text-right"
          rows={1}
        />

        <div className="absolute bottom-3 left-3">
          <Button 
            size="icon" 
            onClick={handleSend} 
            disabled={!input.trim() || isLoading}
            className="rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white h-10 w-10 disabled:opacity-50"
          >
            <SendHorizonal size={20} className={isLoading ? "animate-pulse" : ""} />
          </Button>
        </div>
      </div>
      <div className="text-center mt-2 text-xs text-muted-foreground">
        يستخدم النظام RAG Pipeline متقدم. الإجابات تعتمد بشكل كامل على المستندات المرفوعة.
      </div>
    </div>
  );
};
