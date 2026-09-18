import { useEffect, useRef } from 'react';
import type { ChatMessage as ChatMessageType } from '../../types';
import ChatMessage from './ChatMessage';
import { LoadingSpinner } from '../shared/LoadingSpinner';

interface ChatWindowProps {
  messages: ChatMessageType[];
  isLoading: boolean;
  onSimulateRecommendation?: () => void;
}

export default function ChatWindow({
  messages,
  isLoading,
  onSimulateRecommendation,
}: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  return (
    <div className="flex-1 overflow-y-auto px-3 sm:px-5 py-4 space-y-4">
      {messages.map((msg, index) => (
        <ChatMessage
          key={index}
          message={msg}
          onSimulateRecommendation={onSimulateRecommendation}
        />
      ))}

      {isLoading && (
        <div className="flex items-center gap-3 my-4 p-4 rounded-2xl bg-white border border-slate-200 shadow-sm max-w-sm">
          <LoadingSpinner size="sm" label="" className="p-0" />
          <div className="text-xs text-slate-600 font-medium animate-pulse">
            MerchantMind AI analyzing sales data & formulation…
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
