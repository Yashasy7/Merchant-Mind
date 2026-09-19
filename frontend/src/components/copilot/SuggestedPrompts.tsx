import { IconSparkles } from '../shared/Icons';

interface SuggestedPromptsProps {
  onSelectPrompt: (prompt: string) => void;
  disabled?: boolean;
}

const defaultPrompts = [
  'My sales are falling. Help me increase weekend revenue.',
  'How much profit did I make this month?',
  'Who are my at-risk customers and what should I do?',
  'Explain the 16% sales decline in evening hours',
];

export default function SuggestedPrompts({
  onSelectPrompt,
  disabled = false,
}: SuggestedPromptsProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-500">
        <IconSparkles size={13} className="text-paytm" />
        <span>Suggested Merchant Inquiries</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {defaultPrompts.map((prompt, idx) => (
          <button
            key={idx}
            onClick={() => onSelectPrompt(prompt)}
            disabled={disabled}
            className="text-xs text-left px-3.5 py-1.5 rounded-full bg-slate-100 hover:bg-sky-50 text-slate-700 hover:text-paytmNavy border border-slate-200/80 hover:border-sky-200 transition-all duration-150 disabled:opacity-50 disabled:pointer-events-none"
          >
            "{prompt}"
          </button>
        ))}
      </div>
    </div>
  );
}
