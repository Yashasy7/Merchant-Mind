import { IconAlertTriangle, IconRefresh } from './Icons';

interface ErrorMessageProps {
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export default function ErrorMessage({
  message = 'Unable to load data from backend API.',
  onRetry,
  className = '',
}: ErrorMessageProps) {
  return (
    <div
      className={`p-4 bg-red-50 border border-red-200 rounded-card flex flex-col sm:flex-row items-center justify-between gap-3 text-left shadow-subtle ${className}`}
    >
      <div className="flex items-center gap-3">
        <IconAlertTriangle className="text-red-600 flex-shrink-0" size={20} />
        <div>
          <p className="text-xs font-semibold text-red-800">API Connection Notice</p>
          <p className="text-xs text-red-700/90">{message}</p>
        </div>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-white border border-red-200 text-red-700 hover:bg-red-100/50 transition-colors duration-150 flex-shrink-0 shadow-sm"
        >
          <IconRefresh size={14} />
          Retry
        </button>
      )}
    </div>
  );
}
