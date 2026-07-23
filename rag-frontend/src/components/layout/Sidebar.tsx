import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { 
  FileUp, 
  UploadCloud, 
  CheckCircle2, 
  Loader2, 
  AlertCircle, 
  MessageSquare, 
  Plus, 
  Trash2, 
  Database,
  History,
  FileCheck2
} from 'lucide-react';
import { api } from '../../lib/api';
import type { IngestStatus, ConversationResponse, DocumentResponse } from '../../types';

interface SidebarProps {
  conversations: ConversationResponse[];
  activeConversationId: string | null;
  onSelectConversation: (id: string | null) => void;
  onNewChat: (title?: string) => void;
  onDeleteConversation: (id: string) => void;
  documents: DocumentResponse[];
  onDeleteDocument: (id: string) => void;
  onIngestSuccess: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewChat,
  onDeleteConversation,
  documents,
  onDeleteDocument,
  onIngestSuccess
}) => {
  const [jobs, setJobs] = useState<Record<string, IngestStatus>>({});


  const pollJobStatus = async (jobId: string) => {
    const interval = setInterval(async () => {
      try {
        const status = await api.getIngestStatus(jobId);
        setJobs(prev => ({ ...prev, [jobId]: status }));
        if (status.status !== 'processing') {
          clearInterval(interval);
          onIngestSuccess(); // Refresh documents list in parent
        }
      } catch (err) {
        clearInterval(interval);
      }
    }, 2000);
  };

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;
    try {
      const res = await api.uploadFiles(acceptedFiles);
      setJobs(prev => ({ 
        ...prev, 
        [res.job_id]: { job_id: res.job_id, status: 'processing', chunks_indexed: 0 } 
      }));
      pollJobStatus(res.job_id);
    } catch (err) {
      console.error(err);
      alert("فشل رفع الملفات");
    }
  }, [onIngestSuccess]);


  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
      'text/markdown': ['.md'],
      'text/html': ['.html'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png']
    }
  });

  return (
    <aside className="w-80 bg-gray-50 dark:bg-[#0f0f0f] border-l border-gray-200 dark:border-gray-800/80 flex flex-col h-screen overflow-hidden text-gray-900 dark:text-gray-100 font-sans">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-800/80 flex items-center justify-between">
        <h2 className="text-md font-bold flex items-center gap-2">
          <div className="w-8 h-8 bg-emerald-600 rounded-lg flex items-center justify-center text-white">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
          </div>
          RAG Chat System
        </h2>
      </div>

      {/* New Chat Button */}
      <div className="p-3">
        <button 
          onClick={() => onNewChat('محادثة جديدة')}
          className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-700 active:scale-[0.98] text-white font-medium rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-emerald-600/10 transition-all duration-200"
        >
          <Plus size={18} />
          <span>محادثة جديدة</span>
        </button>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto px-3 pb-4 space-y-5 scrollbar-thin">
        
        {/* Conversations History */}
        <div className="space-y-1">
          <h3 className="text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wider px-2 mb-1 flex items-center gap-1.5">
            <History size={11} />
            <span>سجل المحادثات</span>
          </h3>
          
          <div className="space-y-0.5 max-h-48 overflow-y-auto pr-1">
            {conversations.length === 0 ? (
              <p className="text-xs text-gray-400 dark:text-gray-600 px-2 py-3 text-center">لا توجد محادثات سابقة</p>
            ) : (
              conversations.map((conv) => {
                const isActive = activeConversationId === conv.id;
                return (
                  <div 
                    key={conv.id}
                    className={`group w-full flex items-center justify-between rounded-lg p-2 text-sm text-right cursor-pointer transition-colors ${
                      isActive 
                        ? 'bg-gray-200 dark:bg-gray-800 text-gray-900 dark:text-white font-medium' 
                        : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-900'
                    }`}
                    onClick={() => onSelectConversation(conv.id)}
                  >
                    <div className="flex items-center gap-2 truncate flex-1 min-w-0">
                      <MessageSquare size={14} className={isActive ? 'text-emerald-500' : 'text-gray-400'} />
                      <span className="truncate">{conv.title}</span>
                    </div>
                    <button 
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteConversation(conv.id);
                      }}
                      className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-500 rounded transition-opacity"
                      title="مسح المحادثة"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Upload Zone */}
        <div className="space-y-2">
          <h3 className="text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wider px-2 flex items-center gap-1.5">
            <FileUp size={11} />
            <span>رفع المستندات (PostgreSQL)</span>
          </h3>
          
          <div 
            {...getRootProps()} 
            className={`border border-dashed rounded-xl p-4 text-center cursor-pointer transition-all ${
              isDragActive 
                ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-950/10' 
                : 'border-gray-200 dark:border-gray-800/80 hover:bg-gray-100 dark:hover:bg-gray-900/60'
            }`}
          >
            <input {...getInputProps()} />
            <UploadCloud className="w-7 h-7 mx-auto mb-1 text-gray-400" />
            <p className="text-xs font-semibold">اسحب الملفات هنا أو اضغط للرفع</p>
            <p className="text-[10px] text-gray-400 mt-0.5">PDF, DOCX, TXT, MD, HTML</p>
          </div>
        </div>

        {/* Active Upload Jobs */}
        {Object.keys(jobs).length > 0 && (
          <div className="space-y-1.5">
            <h3 className="text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wider px-2">جاري المعالجة</h3>
            <div className="space-y-1">
              {Object.values(jobs).map((job) => (
                <div key={job.job_id} className="bg-white dark:bg-[#151515] border border-gray-100 dark:border-gray-800/60 p-2.5 rounded-lg flex items-center gap-2">
                  {job.status === 'processing' ? (
                    <Loader2 className="w-4 h-4 text-blue-500 animate-spin flex-shrink-0" />
                  ) : job.status === 'done' ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] font-semibold truncate" dir="ltr">Job: {job.job_id.slice(0, 8)}</p>
                    {job.status === 'processing' ? (
                      <p className="text-[10px] text-gray-400">جاري فهرسة النصوص...</p>
                    ) : job.status === 'done' ? (
                      <p className="text-[10px] text-emerald-500">اكتملت ({job.chunks_indexed} جزء)</p>
                    ) : (
                      <p className="text-[10px] text-red-500 truncate">{job.detail || 'فشل الفهرسة'}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Ingested Documents List */}
        <div className="space-y-1.5">
          <h3 className="text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wider px-2 flex items-center gap-1.5">
            <Database size={11} />
            <span>المستندات المفهرسة</span>
          </h3>
          
          <div className="space-y-1 max-h-52 overflow-y-auto pr-1">
            {documents.length === 0 ? (
              <p className="text-xs text-gray-400 dark:text-gray-600 px-2 py-3 text-center">لا توجد مستندات مرفوعة</p>
            ) : (
              documents.map((doc) => (
                <div 
                  key={doc.id}
                  className="group bg-white dark:bg-[#151515] hover:bg-gray-100 dark:hover:bg-[#1a1a1a] border border-gray-100 dark:border-gray-800/60 p-2 rounded-lg flex items-center justify-between gap-2 transition-colors"
                >
                  <div className="flex items-center gap-2 truncate flex-1 min-w-0">
                    <FileCheck2 size={14} className="text-emerald-500 flex-shrink-0" />
                    <div className="truncate flex-1 min-w-0">
                      <p className="text-xs font-semibold truncate">{doc.filename}</p>
                      <p className="text-[9px] text-gray-400">
                        {doc.status === 'done' ? `تمت الفهرسة (${doc.chunks_indexed} جزء)` : doc.status === 'failed' ? 'فشل الفهرسة' : 'جاري الفهرسة...'}
                      </p>
                    </div>
                  </div>
                  
                  <button 
                    onClick={() => onDeleteDocument(doc.id)}
                    className="p-1 hover:text-red-500 text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-800 rounded transition-colors"
                    title="حذف المستند والـ Vectors"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

      </div>

      {/* Footer Links */}
      <div className="p-3 border-t border-gray-200 dark:border-gray-800/80 flex justify-between items-center bg-gray-100/50 dark:bg-black/20">
        <a 
          href="/traces-dashboard" 
          target="_blank" 
          rel="noreferrer" 
          className="text-xs font-bold px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-all flex items-center gap-1.5"
        >
          <span>⚡</span>
          <span>لوحة تتبع الـ Tokens والـ Pipeline ↗</span>
        </a>
        <div className="flex items-center gap-1.5">
          <span className="text-[9px] text-emerald-500 font-semibold">نشط</span>
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
        </div>
      </div>
    </aside>
  );
};

