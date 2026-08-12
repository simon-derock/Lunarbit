import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { ProfileControls } from "@/components/ProfileControls";
import { ProfileProvider, useProfiles } from "@/components/ProfileProvider";

function ActiveProfiles() {
  const { dataProfile, visualProfile } = useProfiles();
  return <output>{`${dataProfile.id}:${visualProfile.id}`}</output>;
}

describe("dual profile controls", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.history.replaceState({}, "", "/");
  });

  it("switches data and rendering profiles independently", () => {
    render(
      <ProfileProvider>
        <ProfileControls />
        <ActiveProfiles />
      </ProfileProvider>,
    );

    expect(screen.getByText("atlas:dark-chromatic")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Atlas/i }));
    fireEvent.click(screen.getByRole("option", { name: /Deal Optimizer/i }));
    expect(screen.getByText("nova:dark-chromatic")).toBeInTheDocument();
    expect(window.location.search).toContain("profile=nova");

    fireEvent.click(screen.getByRole("button", { name: /Chromatic/i }));
    fireEvent.click(screen.getByRole("option", { name: /Economic Terrain/i }));
    expect(screen.getByText("nova:economic-terrain")).toBeInTheDocument();
    expect(window.location.search).toContain("visual=economic-terrain");
  });
});
