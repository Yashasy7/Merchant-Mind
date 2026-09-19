import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { ChatMessage as ChatMessageType } from '../types';
import { postCopilotChat } from '../api';
import ChatWindow from '../components/copilot/ChatWindow';
import ChatInput from '../components/copilot/ChatInput';
import SuggestedPrompts from '../components/copilot/SuggestedPrompts';
import SyntheticLabel from '../components/shared/SyntheticLabel';
import { IconBot, IconRefresh } from '../components/shared/Icons';

export default function Copilot() {
  const [searchParams] = useSearchParams();
  const initialPrompt = searchParams.get('prompt');

  const [messages, setMessages] = useState<ChatMessageType[]>([
    {
      role: 'assistant',
      content:
        "Namaste! I am your Paytm MerchantMind AI Copilot. I continuously monitor your sales, customer retention, and operating expenses.\n\nI noticed an active decline signal: your sales have dropped ~16% over the last 2 weeks, predominantly between 6 PM and 9 PM on weekdays. How can I help you grow your business today?",
      timestamp: new Date().toISOString(),
    },
  ]);

  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string>('conv-hero-001');

  const handleSendMessage = async (text: string) => {
    const userMsg: ChatMessageType = {
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const response = await postCopilotChat({
        message: text,
        conversation_id: conversationId,
      });

      const aiMsg: ChatMessageType = {
        role: 'assistant',
        content: response.data.message,
        timestamp: new Date().toISOString(),
        structured_data: response.data.structured_data,
      };

      setConversationId(response.data.conversation_id);
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err) {
      const errorMsg: ChatMessageType = {
        role: 'assistant',
        content:
          'Sorry, I encountered an issue communicating with the AI service. Please try asking again.',
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  // If navigated with a prompt query, execute it
  useEffect(() => {
    if (initialPrompt && messages.length === 1) {
      handleSendMessage(initialPrompt);
    }
  }, [initialPrompt]);

  const handleResetChat = () => {
    setMessages([
      {
        role: 'assistant',
        content:
          "Conversation reset. I am ready for your next question regarding sales, expenses, or growth strategies.",
        timestamp: new Date().toISOString(),
      },
    ]);
  };

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col bg-white border border-slate-200/90 rounded-2xl overflow-hidden shadow-card">
      {/* Header bar */}
      <div className="px-5 py-3.5 border-b border-slate-100 bg-slate-50/60 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-sky-100 text-paytmNavy flex items-center justify-center">
            <IconBot size={18} className="text-paytm" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-slate-900">MerchantMind AI Copilot</h2>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-sky-50 text-sky-700 border border-sky-200">
                AI Business Partner
              </span>
            </div>
            <p className="text-[11px] text-slate-500">
              Ask questions in plain English about sales, expenses, or marketing campaigns
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <SyntheticLabel variant="data" size="xs" />
          <button
            onClick={handleResetChat}
            className="text-slate-400 hover:text-slate-700 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
            title="Reset conversation"
          >
            <IconRefresh size={16} />
          </button>
        </div>
      </div>

      {/* Messages area */}
      <ChatWindow
        messages={messages}
        isLoading={isLoading}
      />

      {/* Footer input area */}
      <div className="p-4 border-t border-slate-100 bg-slate-50/40 space-y-3">
        <SuggestedPrompts
          onSelectPrompt={handleSendMessage}
          disabled={isLoading}
        />
        <ChatInput
          onSendMessage={handleSendMessage}
          disabled={isLoading}
        />
      </div>
    </div>
  );
}
