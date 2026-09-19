/**
 * SyntheticLabel — Blueprint §13, §6 Module 06, §27
 *
 * MANDATORY: Displays synthetic demo data disclaimer.
 * Redesigned with a subtle, professional fintech badge style.
 */

interface SyntheticLabelProps {
  /** 'data' for general demo data, 'projection' for simulated/forecast values */
  variant?: 'data' | 'projection';
  /** Size of the label */
  size?: 'sm' | 'xs';
  className?: string;
}

export default function SyntheticLabel({
  variant = 'data',
  size = 'xs',
  className = '',
}: SyntheticLabelProps) {
  const text =
    variant === 'projection'
      ? 'Synthetic / Illustrative Demo Projection — Not a guaranteed forecast.'
      : 'Synthetic / Illustrative Demo Data';

  const sizeClass =
    size === 'xs'
      ? 'text-[10px] px-2 py-0.5'
      : 'text-[11px] px-2.5 py-1';

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full bg-slate-100/90 text-slate-500 border border-slate-200/80 font-normal tracking-normal select-none ${sizeClass} ${className}`}
      title="Demonstration data for hackathon prototype evaluation"
    >
      <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
      <span>{text}</span>
    </span>
  );
}
