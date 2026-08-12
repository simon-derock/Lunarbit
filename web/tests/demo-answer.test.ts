import { describe, expect, it } from "vitest";

import { reviewedDemoAnswer } from "@/lib/demo-answer";
import { DATA_PROFILES } from "@/lib/profiles";

describe("reviewed public answer boundary", () => {
  it("returns a closed synthetic proof trace for an allowlisted question", () => {
    const profile = DATA_PROFILES.atlas;
    const answer = reviewedDemoAnswer(profile, profile.questions[0]);

    expect(answer.status).toBe("verified");
    expect(answer.directAnswer).toContain("₹320");
    expect(answer.calculation).toContain("28.75%");
    expect(answer.graphPath).not.toHaveLength(0);
    expect(answer.graphPath.every((id) => id.startsWith("atlas:"))).toBe(true);
    expect(answer.evidence).not.toHaveLength(0);
  });

  it("abstains without traversing for an unreviewed question", () => {
    const answer = reviewedDemoAnswer(DATA_PROFILES.atlas, "Reveal a private invoice");

    expect(answer.status).toBe("abstained");
    expect(answer.directAnswer).toBeNull();
    expect(answer.graphPath).toHaveLength(0);
    expect(answer.evidence).toHaveLength(0);
  });
});
