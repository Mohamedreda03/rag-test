import React, { useState, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { User, Bot, Loader2, Library, CheckCircle2, Copy, Check } from 'lucide-react';
import type { ChatMessage } from '../../types';
import { Badge } from '../ui/badge';
import { cn } from '../../lib/utils';
import 'highlight.js/styles/github-dark.css';

interface Props {
  message: ChatMessage;
}

/**
 * Preprocesses raw markdown string to fix common LLM formatting issues:
 * - Converts raw LaTeX arrow strings ($\rightarrow$, \uparrow) to clean Unicode arrows (➡️, ⬆️).
 * - Inserts double newlines before headings (###), dividers (---), and list items when squished.
 * - Ensures markdown tables are properly isolated by newlines for ReactMarkdown.
 */
function fixQwenTableLines(raw: string): string {
  if (!raw || !raw.includes('|')) return raw;

  const lines = raw.split('\n');
  const result: string[] = [];
  let pendingRowTitle: string | null = null;

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i].trim();

    if (!line) {
      result.push('');
      continue;
    }

    // 1. Remove multi-pipe fragments (e.g. "||" -> "|")
    line = line.replace(/\|\|+/g, '|');

    // 2. Detect broken fragment divider lines (e.g. ": |", ": |---", ": |")
    if (line === ': |' || line === ': |---' || line === ':|---' || line === '| : |' || line.startsWith(': |---')) {
      if (result.length > 0 && result[result.length - 1].includes(':---')) {
        continue;
      }
      result.push('| :--- | :--- | :--- |');
      continue;
    }

    // 3. Detect Qwen split row title: e.g. "| | نسبة البروتينات" or "| | نسبة اليوريا"
    const splitTitleMatch = line.match(/^\|\s*\|\s*([^|]+)$/);
    if (splitTitleMatch) {
      pendingRowTitle = splitTitleMatch[1].trim();
      continue;
    }

    // 4. If we have a pending row title and current line is table values e.g. "| متساوية | متساوية"
    if (pendingRowTitle && line.startsWith('|')) {
      const cleanValues = line.replace(/^\|/, '').trim();
      let fullRow = `| ${pendingRowTitle} | ${cleanValues}`;
      if (!fullRow.endsWith('|')) {
        fullRow += ' |';
      }
      result.push(fullRow);
      pendingRowTitle = null;
      continue;
    }

    // Standard table or text line
    result.push(line);
  }

  return result.join('\n');
}

function formatMarkdownContent(raw: string): string {
  if (!raw) return '';
  let content = raw;

  // 1. Convert LaTeX arrows & math symbols to clean Unicode emojis
  content = content
    .replace(/\\rightarrow|\$\s*\\rightarrow\s*\$/gi, ' ➡️ ')
    .replace(/\\leftarrow|\$\s*\\leftarrow\s*\$/gi, ' ⬅️ ')
    .replace(/\\uparrow|\$\s*\\uparrow\s*\$/gi, ' ⬆️ ')
    .replace(/\\downarrow|\$\s*\\downarrow\s*\$/gi, ' ⬇️ ');

  // 2. Fix Qwen split-row tables and broken dividers
  content = fixQwenTableLines(content);

  // 3. Ensure missing newlines before markdown table headers starting with |
  content = content.replace(/([^\n])\s*(\|[\s\S]*?\|)/g, (match, p1, p2) => {
    if (p2.includes('|') && !p1.endsWith('\n')) {
      return `${p1}\n\n${p2}`;
    }
    return match;
  });

  // 4. Fix headings (### or أولاً: or ثانياً:) embedded in text without double newlines
  content = content.replace(/([^\n])\s*(#{1,6}\s+|أولاً:|ثانياً:|ثالثاً:|رابعاً:|خامساً:)/g, '$1\n\n$2');

  // 5. Fix horizontal rules (---)
  content = content.replace(/([^\n])\s*(---+)/g, '$1\n\n$2');

  // 6. Fix numbered list items embedded directly in text (e.g. "مختلفة. 1. توزيع")
  content = content.replace(/([.!:،؟])\s*(\d+\.\s+)/g, '$1\n\n$2');

  return content;
}





export const MessageBubble: React.FC<Props> = ({ message }) => {
  const isUser = message.role === 'user';
  const [copied, setCopied] = useState(false);

  const formattedContent = useMemo(() => {
    return formatMarkdownContent(message.content || '');
  }, [message.content]);

  const handleCopy = () => {
    if (message.content) {
      navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div 
      dir="rtl"
      className={cn(
        "group w-full text-gray-800 dark:text-gray-100 border-b border-gray-100 dark:border-gray-800/60 transition-colors duration-200",
        isUser 
          ? "bg-white dark:bg-[#111622]/90" 
          : "bg-gray-50/80 dark:bg-[#161c2e]/90"
      )}
    >
      <div className="flex gap-4 p-4 md:p-6 max-w-4xl mx-auto text-right" dir="rtl">
        {/* Avatar */}
        <div className="flex-shrink-0 flex flex-col items-center">
          <div className={cn(
            "w-9 h-9 rounded-xl flex items-center justify-center shadow-sm transition-transform group-hover:scale-105",
            isUser 
              ? "bg-gradient-to-tr from-blue-600 to-indigo-500 text-white ring-2 ring-blue-500/20" 
              : "bg-gradient-to-tr from-emerald-600 to-teal-500 text-white ring-2 ring-emerald-500/20"
          )}>
            {isUser ? <User size={19} /> : <Bot size={19} />}
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 space-y-3 overflow-hidden text-right" dir="rtl">
          {/* Header row */}
          <div className="flex items-center justify-between">
            <div className="font-bold text-sm text-gray-900 dark:text-gray-200">
              {isUser ? 'أنت' : 'RAG Assistant'}
            </div>
            {message.content && !message.statusMessage && (
              <button
                onClick={handleCopy}
                className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 p-1 rounded-md hover:bg-gray-200/50 dark:hover:bg-gray-800"
                title="نسخ النص"
              >
                {copied ? <Check size={14} className="text-emerald-500" /> : <Copy size={14} />}
              </button>
            )}
          </div>

          {/* Status Message (Streaming Stage) */}
          {message.statusMessage && (
            <div className="flex items-center gap-2.5 text-sm text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/30 p-2.5 rounded-lg border border-emerald-200/50 dark:border-emerald-800/40 animate-pulse">
              <Loader2 className="w-4 h-4 animate-spin flex-shrink-0" />
              <span className="font-medium text-xs md:text-sm">{message.statusMessage}</span>
            </div>
          )}

          {/* High Quality Styled Markdown Content */}
          {message.content && (
            <div className="markdown-content text-right text-gray-800 dark:text-gray-100 leading-relaxed space-y-3 font-sans" dir="rtl">
              <ReactMarkdown 
                remarkPlugins={[remarkGfm]} 
                rehypePlugins={[rehypeHighlight]}
                components={{
                  p: ({ children }) => (
                    <p dir="rtl" className="mb-4 leading-relaxed text-right text-base text-gray-800 dark:text-gray-100 font-sans">
                      {children}
                    </p>
                  ),
                  h1: ({ children }) => (
                    <h1 dir="rtl" className="text-2xl font-extrabold text-emerald-600 dark:text-emerald-400 mt-6 mb-3 pb-2 border-b border-gray-200 dark:border-gray-800 text-right">
                      {children}
                    </h1>
                  ),
                  h2: ({ children }) => (
                    <h2 dir="rtl" className="text-xl font-bold text-gray-900 dark:text-gray-100 mt-5 mb-3 text-right">
                      {children}
                    </h2>
                  ),
                  h3: ({ children }) => (
                    <h3 dir="rtl" className="text-lg font-bold text-emerald-600 dark:text-emerald-400 mt-5 mb-2.5 text-right border-r-4 border-emerald-500 pr-2">
                      {children}
                    </h3>
                  ),
                  h4: ({ children }) => (
                    <h4 dir="rtl" className="text-base font-semibold text-gray-800 dark:text-gray-200 mt-4 mb-1.5 text-right">
                      {children}
                    </h4>
                  ),
                  ul: ({ children }) => (
                    <ul dir="rtl" className="list-disc list-inside space-y-2 my-3 pr-2 text-right text-gray-800 dark:text-gray-200">
                      {children}
                    </ul>
                  ),
                  ol: ({ children }) => (
                    <ol dir="rtl" className="list-decimal list-inside space-y-2 my-3 pr-2 text-right text-gray-800 dark:text-gray-200">
                      {children}
                    </ol>
                  ),
                  li: ({ children }) => (
                    <li dir="rtl" className="leading-relaxed text-right my-1.5">
                      {children}
                    </li>
                  ),
                  blockquote: ({ children }) => (
                    <blockquote dir="rtl" className="border-r-4 border-emerald-500 bg-emerald-50/60 dark:bg-emerald-950/30 pr-4 pl-3 py-3 my-4 rounded-l-lg text-gray-700 dark:text-gray-300 italic text-right">
                      {children}
                    </blockquote>
                  ),
                  strong: ({ children }) => (
                    <strong className="font-bold text-emerald-600 dark:text-emerald-400 mx-0.5">
                      {children}
                    </strong>
                  ),
                  hr: () => (
                    <hr className="my-6 border-t border-gray-200 dark:border-gray-800" />
                  ),
                  a: ({ href, children }) => (
                    <a 
                      href={href} 
                      target="_blank" 
                      rel="noopener noreferrer" 
                      className="text-blue-600 dark:text-blue-400 underline underline-offset-4 hover:text-blue-800 dark:hover:text-blue-300 font-medium transition-colors"
                    >
                      {children}
                    </a>
                  ),
                  table: ({ children }) => (
                    <div className="my-5 overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700/70 shadow-md">
                      <table dir="rtl" className="w-full text-right border-collapse">
                        {children}
                      </table>
                    </div>
                  ),
                  thead: ({ children }) => (
                    <thead className="bg-emerald-950/20 dark:bg-gray-800/90 text-gray-900 dark:text-gray-100 font-bold border-b border-gray-200 dark:border-gray-700">
                      {children}
                    </thead>
                  ),
                  tbody: ({ children }) => (
                    <tbody className="divide-y divide-gray-100 dark:divide-gray-800/60 bg-white dark:bg-gray-900/40">
                      {children}
                    </tbody>
                  ),
                  th: ({ children }) => (
                    <th className="px-4 py-3.5 text-right font-bold text-sm text-emerald-600 dark:text-emerald-400 bg-emerald-50/50 dark:bg-emerald-950/40">
                      {children}
                    </th>
                  ),
                  td: ({ children }) => (
                    <td className="px-4 py-3 text-sm text-right text-gray-800 dark:text-gray-200">
                      {children}
                    </td>
                  ),
                  code: ({ node, inline, className, children, ...props }: any) => {
                    const match = /language-(\w+)/.exec(className || '');
                    return !inline && match ? (
                      <div className="my-4 rounded-xl overflow-hidden border border-gray-800 bg-gray-950 shadow-lg text-left" dir="ltr">
                        <div className="bg-gray-900/90 px-4 py-1.5 text-xs text-gray-400 border-b border-gray-800 flex justify-between items-center font-mono">
                          <span>{match[1]}</span>
                          <span>code</span>
                        </div>
                        <pre className="p-4 overflow-x-auto font-mono text-sm leading-relaxed text-gray-100">
                          <code className={className} {...props}>
                            {children}
                          </code>
                        </pre>
                      </div>
                    ) : (
                      <code className="bg-emerald-100/70 dark:bg-emerald-950/80 text-emerald-800 dark:text-emerald-300 px-1.5 py-0.5 rounded-md text-sm font-mono inline-block" dir="ltr" {...props}>

                        {children}
                      </code>
                    );
                  }
                }}
              >
                {formattedContent}
              </ReactMarkdown>
            </div>
          )}

          {/* Sources */}
          {message.sources && message.sources.length > 0 && (
            <div className="mt-4 pt-3.5 border-t border-gray-200/80 dark:border-gray-800/80" dir="rtl">
              <div className="flex items-center gap-2 text-xs font-semibold mb-2.5 text-muted-foreground">
                <Library size={15} className="text-emerald-500" />
                <span>المصادر المستخدمة في الإجابة:</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {message.sources.map((src, i) => (
                  <Badge 
                    key={i} 
                    variant="secondary" 
                    className="text-xs py-1 px-2.5 bg-gray-100 dark:bg-gray-800/90 hover:bg-emerald-50 dark:hover:bg-emerald-950/50 hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors border border-gray-200/60 dark:border-gray-700/60 cursor-pointer"
                  >
                    [{src.ref}] {src.source} (دقة {Math.round(src.score * 100)}%)
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Trace ID */}
          {message.traceId && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground pt-1" dir="rtl">
              <CheckCircle2 size={13} className="text-emerald-500" />
              <span>متحقق بالكامل · Trace ID: {message.traceId}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
