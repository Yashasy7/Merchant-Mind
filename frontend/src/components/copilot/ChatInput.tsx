import React, { useState } from 'react';
import { IconSend, IconSparkles } from '../shared/Icons';

interface ChatInputProps {
  onSendMessage: (content: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSendMessage, disabled = false }: ChatInputProps) {
  const [input, setInput] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || disabled) return;
    onSendMessage(input.trim());
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="relative flex items-center gap-2 bg-white border border-slate-200 rounded-2xl p-2 shadow-card focus-within:border-paytm focus-within:ring-2 focus-within:ring-sky-100 transition-all"
    >
      <div className="pl-2 text-slate-400">
        <IconSparkles size={18} className="text-paytm" />
      </div>
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask anything about your store sales, profits, or growth campaigns…"
        disabled={disabled}
        className="flex-1 bg-transparent border-none text-xs sm:text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none px-2 py-2 font-sans"
      />
      <button
        type="submit"
        disabled={!input.trim() || disabled}
        className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-paytmNavy hover:bg-[#001c4d] text-white disabled:opacity-40 disabled:cursor-not-allowed transition-all flex-shrink-0 shadow-sm active:scale-95"
        title="Send inquiry"
      >
        <IconSend size={16} />
      </button>
    </form>
  );
}
