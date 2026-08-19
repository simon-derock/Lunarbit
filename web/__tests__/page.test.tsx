import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import Page from "@/app/page";
import { ProfileProvider } from "@/components/ProfileProvider";

function renderOverview() {
  return render(
    <ProfileProvider>
      <Page />
    </ProfileProvider>,
  );
}

describe("Lunarbit public experience", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.history.replaceState({}, "", "/");
  });

  it("leads with the evidence-verifiable commerce thesis and measured graph", () => {
    renderOverview();

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /personal commerce, reconstructed as evidence/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("454")).toBeInTheDocument();
    expect(screen.getByText("Orders reconstructed")).toBeInTheDocument();
    expect(screen.getByText(/synthetic mirror calibrated/i)).toBeInTheDocument();
  });

  it("offers advanced questions and an inspectable graph path", () => {
    renderOverview();

    expect(screen.getAllByRole("button", { name: /what|when|which|show/i })).toHaveLength(4);
    expect(screen.getByRole("heading", { name: /evidence constellation/i })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /urban omnivore evidence graph/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /evidence: evidence 01/i })).toBeInTheDocument();
  });

  it("publishes benchmark and privacy boundaries instead of hiding them", () => {
    renderOverview();

    expect(screen.getByText(/canonical oracle verified/i)).toBeInTheDocument();
    expect(screen.getByText(/no private source text/i)).toBeInTheDocument();
  });
});
