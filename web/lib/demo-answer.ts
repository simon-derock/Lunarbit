import type { CommerceDataProfile } from "@/lib/types";

export interface DemoAnswer {
  status: "verified" | "abstained";
  directAnswer: string | null;
  calculation: string | null;
  confidence: string;
  graphPath: readonly string[];
  evidence: readonly string[];
  limitations: readonly string[];
}

export function reviewedDemoAnswer(profile: CommerceDataProfile, question: string): DemoAnswer {
  const index = profile.questions.indexOf(question);
  if (index < 0) {
    return {
      status: "abstained",
      directAnswer: null,
      calculation: null,
      confidence: "Public projection gate",
      graphPath: [],
      evidence: [],
      limitations: (
        ["This public surface answers only reviewed synthetic questions.", "Private retrieval remains behind an authenticated server boundary."]
      ),
    };
  }

  const reviewed = profile.answers[index];
  const finding = profile.findings[reviewed.findingIndex];
  return {
    status: "verified",
    directAnswer: reviewed.directAnswer,
    calculation: reviewed.calculation,
    confidence: `${reviewed.confidenceScope} · confidence ${finding.confidence}`,
    graphPath: profile.nodes.slice(0, 6).map((node) => node.id),
    evidence: profile.nodes.filter((node) => node.kind === "evidence").map((node) => node.label),
    limitations: [profile.disclosure, "This demonstration does not expose or query private source text."],
  };
}
