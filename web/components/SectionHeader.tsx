import type { ReactNode } from "react";

export function SectionHeader({
  eyebrow,
  title,
  description,
  aside,
}: Readonly<{
  eyebrow: string;
  title: string;
  description: string;
  aside?: ReactNode;
}>) {
  return (
    <header className="section-header">
      <div>
        <span className="eyebrow"><i /> {eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {aside && <div className="section-aside">{aside}</div>}
    </header>
  );
}
