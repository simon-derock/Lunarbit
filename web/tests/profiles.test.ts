import { describe, expect, it } from "vitest";

import {
  DATA_PROFILES,
  DEFAULT_SELECTION,
  selectionFromSearch,
  selectionSearch,
  validateProfileIsolation,
  VISUAL_PROFILES,
} from "@/lib/profiles";

describe("profile architecture", () => {
  it("keeps every commerce graph closed inside its data profile", () => {
    for (const profile of Object.values(DATA_PROFILES)) {
      expect(() => validateProfileIsolation(profile)).not.toThrow();
      expect(profile.answers).toHaveLength(profile.questions.length);
      expect(profile.nodes.every((node) => node.profileId === profile.id)).toBe(true);
      expect(profile.edges.every((edge) => edge.profileId === profile.id)).toBe(true);
    }
  });

  it("defines presentation profiles without commerce data", () => {
    expect(Object.keys(VISUAL_PROFILES)).toHaveLength(5);
    for (const profile of Object.values(VISUAL_PROFILES)) {
      expect(profile.palette).toHaveLength(5);
      expect(profile.tokens["--void"]).toMatch(/^#/);
      expect("nodes" in profile).toBe(false);
      expect("orders" in profile).toBe(false);
    }
  });

  it("round-trips independent data and visualization choices through the URL", () => {
    const selection = selectionFromSearch("?profile=nova&visual=economic-terrain");
    expect(selection).toEqual({
      dataProfileId: "nova",
      visualProfileId: "economic-terrain",
    });
    expect(selectionFromSearch(selectionSearch(selection))).toEqual(selection);
  });

  it("rejects unknown URL profiles at the public boundary", () => {
    expect(selectionFromSearch("?profile=private-owner&visual=unknown")).toEqual(
      DEFAULT_SELECTION,
    );
  });
});
