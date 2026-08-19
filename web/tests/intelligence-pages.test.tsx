import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import BenchmarksPage from "@/app/benchmarks/page";
import EconomicsPage from "@/app/economics/page";
import EvidencePage from "@/app/evidence/page";
import GraphPage from "@/app/graph/page";
import TransactionsPage from "@/app/transactions/page";
import { ProfileProvider } from "@/components/ProfileProvider";

const views = [
  [GraphPage, "Navigate the truth topology."],
  [EconomicsPage, "Commerce becomes an economic terrain."],
  [TransactionsPage, "Every order, reconciled—not flattened."],
  [EvidencePage, "Replay every claim back to proof."],
  [BenchmarksPage, "Benchmarks with the caveats left in."],
] as const;

describe("intelligence workspace routes", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.history.replaceState({}, "", "/?profile=nova&visual=spectral-bloom");
  });

  it.each(views)("renders %s inside the selected dual-profile workspace", (Page, heading) => {
    const { container } = render(<ProfileProvider><Page /></ProfileProvider>);

    expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
    expect(container.querySelector('[data-visual-profile="spectral-bloom"]')).toBeInTheDocument();
  });
});
