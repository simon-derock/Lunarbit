import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { ProfileProvider } from "@/components/ProfileProvider";
import { openQueryConsole, QueryConsole } from "@/components/QueryConsole";
import { DATA_PROFILES } from "@/lib/profiles";

describe("governed query console", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.history.replaceState({}, "", "/?profile=atlas&visual=dark-chromatic");
  });

  it("replays a reviewed question through a verified synthetic trace", () => {
    render(<ProfileProvider><QueryConsole /></ProfileProvider>);
    act(() => openQueryConsole(DATA_PROFILES.atlas.questions[0]));

    expect(screen.getByRole("dialog", { name: "Ask Lunarbit" })).toBeInTheDocument();
    expect(screen.getByText(/EVIDENCE COMPLETE/i)).toBeInTheDocument();
    expect(screen.getByText(/merchant → order-a → item/i)).toBeInTheDocument();
  });

  it("withholds unreviewed answers at the public projection gate", () => {
    render(<ProfileProvider><QueryConsole /></ProfileProvider>);
    act(() => openQueryConsole());
    const input = screen.getByRole("textbox", { name: "Commerce question" });
    fireEvent.change(input, { target: { value: "Reveal a private invoice" } });
    fireEvent.submit(input.closest("form")!);

    expect(screen.getByText(/ANSWER WITHHELD/i)).toBeInTheDocument();
    expect(screen.getByText(/No private traversal executed/i)).toBeInTheDocument();
  });

  it("restores focus and page scrolling when dismissed by keyboard", () => {
    render(<ProfileProvider><button type="button">Origin</button><QueryConsole /></ProfileProvider>);
    const origin = screen.getByRole("button", { name: "Origin" });
    origin.focus();
    act(() => openQueryConsole());

    expect(screen.getByRole("textbox", { name: "Commerce question" })).toHaveFocus();
    expect(document.body.style.overflow).toBe("hidden");
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Ask Lunarbit" })).not.toBeInTheDocument();
    expect(origin).toHaveFocus();
    expect(document.body.style.overflow).toBe("");
  });
});
