import clsx from "clsx";

interface BadgeProps {
  children: React.ReactNode;
  variant?: "default" | "long" | "short" | "entry" | "exit" | "accent";
  className?: string;
}

const variants = {
  default: "bg-bg-elevated text-text-muted border-border",
  long: "bg-positive/10 text-positive border-positive/20",
  short: "bg-negative/10 text-negative border-negative/20",
  entry: "bg-positive/10 text-positive border-positive/20",
  exit: "bg-text-muted/10 text-text-muted border-border",
  accent: "bg-accent/10 text-accent border-accent/20",
};

export function Badge({ children, variant = "default", className }: BadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
        variants[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
