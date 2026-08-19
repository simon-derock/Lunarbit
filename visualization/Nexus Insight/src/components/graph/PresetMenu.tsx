import { Check, ChevronDown } from "lucide-react";
import type { ReactNode } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

interface Option {
  id: string;
  name: string;
  hint?: string;
  swatches?: string[];
}

interface Props {
  eyebrow: string;
  value: string;
  options: Option[];
  onChange: (id: string) => void;
  align?: "start" | "end";
  footer?: ReactNode;
  width?: string;
}

export function PresetMenu({
  eyebrow,
  value,
  options,
  onChange,
  align = "start",
  footer,
  width = "w-[19rem]",
}: Props) {
  const active = options.find((o) => o.id === value) ?? options[0]!;

  return (
    <Popover>
      <PopoverTrigger
        className={cn(
          "group panel flex min-w-[10.5rem] items-center gap-3 px-3 py-2 text-left transition-colors",
          "hover:border-primary/40 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
        )}
      >
        <span className="flex-1">
          <span className="label-mono block">{eyebrow}</span>
          <span className="block truncate text-[0.8125rem] font-medium tracking-tight">
            {active.name}
          </span>
        </span>
        {active.swatches && (
          <span className="flex -space-x-1">
            {active.swatches.slice(0, 4).map((c, i) => (
              <span
                key={i}
                className="size-2.5 rounded-full border border-border"
                style={{ background: c }}
              />
            ))}
          </span>
        )}
        <ChevronDown className="size-3.5 text-muted-foreground transition-transform group-data-[state=open]:rotate-180" />
      </PopoverTrigger>
      <PopoverContent
        align={align}
        sideOffset={8}
        className={cn("panel glow-ring z-50 p-1.5", width)}
      >
        <div className="label-mono px-2 pb-1.5 pt-1">{eyebrow}</div>
        <div className="max-h-[19rem] space-y-0.5 overflow-y-auto no-scrollbar">
          {options.map((o) => {
            const selected = o.id === value;
            return (
              <button
                key={o.id}
                onClick={() => onChange(o.id)}
                className={cn(
                  "flex w-full items-start gap-2.5 rounded-sm px-2 py-2 text-left transition-colors",
                  selected ? "bg-primary/10" : "hover:bg-primary/5",
                )}
              >
                <span className="flex-1">
                  <span className="flex items-center gap-2 text-[0.8125rem] font-medium tracking-tight">
                    {o.name}
                    {selected && <Check className="size-3 text-primary" />}
                  </span>
                  {o.hint && (
                    <span className="mt-0.5 block font-mono text-[0.65rem] leading-relaxed text-muted-foreground">
                      {o.hint}
                    </span>
                  )}
                </span>
                {o.swatches && (
                  <span className="mt-1 flex -space-x-1">
                    {o.swatches.slice(0, 5).map((c, i) => (
                      <span
                        key={i}
                        className="size-2.5 rounded-full border border-border"
                        style={{ background: c }}
                      />
                    ))}
                  </span>
                )}
              </button>
            );
          })}
        </div>
        {footer && <div className="mt-1 border-t border-border px-2 pb-1 pt-2">{footer}</div>}
      </PopoverContent>
    </Popover>
  );
}
