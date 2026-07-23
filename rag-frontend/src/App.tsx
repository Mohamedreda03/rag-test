import { useEffect } from 'react';

import { Sidebar } from './components/layout/Sidebar';
import { ChatArea } from './components/chat/ChatArea';
import { ChatInput } from './components/chat/ChatInput';
import { useChat } from './hooks/useChat';

function App() {
  const { 
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
  } = useChat();

  // Force dark mode for better aesthetics as requested
  useEffect(() => {
    document.documentElement.classList.add('dark');
  }, []);

  return (
    <div className="flex h-screen w-full bg-white dark:bg-[#0a0a0a] text-gray-900 dark:text-gray-100 overflow-hidden font-sans">
      <Sidebar 
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={selectConversation}
        onNewChat={createNewChat}
        onDeleteConversation={deleteConversation}
        documents={documents}
        onDeleteDocument={deleteDocument}
        onIngestSuccess={loadDocuments}
      />
      <main className="flex-1 flex flex-col relative h-full">
        {/* Topbar mobile toggle goes here if needed later */}
        
        <ChatArea 
          messages={messages} 
          onSuggestionClick={(text) => sendMessage(text)} 
        />
        
        <ChatInput 
          onSend={sendMessage} 
          isLoading={isLoading} 
        />
      </main>
    </div>
  );
}

export default App;
