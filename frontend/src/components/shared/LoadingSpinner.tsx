interface LoadingSpinnerProps {
  label?: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function LoadingSpinner({
  label = 'Loading insights…',
  size = 'md',
  className = '',
}: LoadingSpinnerProps) {
  const sizeMap = {
    sm: 'w-4 h-4 border-2',
    md: 'w-8 h-8 border-[3px]',
    lg: 'w-12 h-12 border-4',
  };

  return (
    <div className={`flex flex-col items-center justify-center gap-3 p-6 text-center ${className}`}>
      <div
        className={`${sizeMap[size]} rounded-full border-slate-200 border-t-paytm border-r-paytmNavy animate-spin`}
        role="status"
        aria-label="loading"
      />
      {label && <span className="text-xs font-medium text-slate-600">{label}</span>}
    </div>
  );
}

export function SkeletonBox({ className = '' }: { className?: string }) {
  return (
    <div
      className={`animate-pulse bg-slate-100 border border-slate-200/80 rounded-card ${className}`}
    />
  );
}

export default LoadingSpinner;
