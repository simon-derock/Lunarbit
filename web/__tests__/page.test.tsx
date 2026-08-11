import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Page from "@/app/page";

describe("Lunarbit public experience", () => {
  it("leads with the evidence-verifiable commerce thesis and measured graph", () => {
    render(<Page />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /six years of food commerce, reconstructed as evidence/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("48,784")).toBeInTheDocument();
    expect(screen.getByText("Graph nodes")).toBeInTheDocument();
    expect(screen.getByText(/synthetic longitudinal mirror/i)).toBeInTheDocument();
  });

  it("offers advanced questions and an inspectable graph path", () => {
    render(<Page />);

    expect(screen.getAllByRole("button", { name: /ask:/i }).length).toBeGreaterThanOrEqual(10);
    expect(screen.getByRole("heading", { name: /knowledge graph explorer/i })).toBeInTheDocument();
    expect(screen.getByText("EVIDENCED_BY")).toBeInTheDocument();
    expect(screen.getByText(/answer → calculation → graph path → evidence/i)).toBeInTheDocument();
  });

  it("publishes benchmark and privacy boundaries instead of hiding them", () => {
    render(<Page />);

    expect(screen.getByRole("heading", { name: /benchmark laboratory/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /privacy is an architecture/i })).toBeInTheDocument();
    expect(screen.getByText(/no private source text/i)).toBeInTheDocument();
  });
});
