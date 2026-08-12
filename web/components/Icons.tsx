import type { SVGProps } from "react";

export type IconName =
  | "overview"
  | "graph"
  | "economics"
  | "transactions"
  | "evidence"
  | "benchmark"
  | "spark"
  | "arrow"
  | "check"
  | "chevron"
  | "command";

const paths: Record<IconName, React.ReactNode> = {
  overview: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
  graph: <><circle cx="5" cy="6" r="2.4" /><circle cx="19" cy="5" r="2.4" /><circle cx="13" cy="19" r="2.4" /><path d="m7.3 6 9.3-.8M6.5 8l5.2 8.8M18 7l-4 9.7" /></>,
  economics: <><path d="M4 19V9m5 10V5m5 14v-7m5 7V3" /><path d="M2 21h20" /></>,
  transactions: <><path d="M4 6h16M4 12h16M4 18h16" /><circle cx="7" cy="6" r="1.5" fill="currentColor" /><circle cx="15" cy="12" r="1.5" fill="currentColor" /><circle cx="10" cy="18" r="1.5" fill="currentColor" /></>,
  evidence: <><path d="M6 3h9l4 4v14H6z" /><path d="M14 3v5h5M9 12h7M9 16h5" /></>,
  benchmark: <><path d="M4 20V10h4v10m4 0V4h4v16m4 0V7h-4" /><path d="M2 20h20" /></>,
  spark: <><path d="m12 2 1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8z" /><path d="m19 16 .7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7z" /></>,
  arrow: <><path d="M5 12h14M14 7l5 5-5 5" /></>,
  check: <path d="m5 12 4 4L19 6" />,
  chevron: <path d="m9 18 6-6-6-6" />,
  command: <><path d="M8 9H5.5a3 3 0 1 1 3-3v12a3 3 0 1 1-3-3H18a3 3 0 1 1-3 3V6a3 3 0 1 1 3 3z" /></>,
};

export function Icon({ name, ...props }: SVGProps<SVGSVGElement> & { name: IconName }) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      height="20"
      viewBox="0 0 24 24"
      width="20"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.5"
      {...props}
    >
      {paths[name]}
    </svg>
  );
}
