import { useEffect, useState } from "react";

export type ViewportProfile = "phone" | "tablet" | "desktop";

export interface ViewportState {
  profile: ViewportProfile;
  width: number;
  height: number;
  orientation: "portrait" | "landscape";
  coarsePointer: boolean;
  reducedMotion: boolean;
}

function readViewport(): ViewportState {
  if (typeof window === "undefined") {
    return {
      profile: "desktop",
      width: 1280,
      height: 800,
      orientation: "landscape",
      coarsePointer: false,
      reducedMotion: false,
    };
  }

  const visual = window.visualViewport;
  const width = Math.round(visual?.width ?? window.innerWidth);
  const height = Math.round(visual?.height ?? window.innerHeight);
  const coarsePointer = window.matchMedia("(pointer: coarse)").matches;
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const shortestSide = Math.min(width, height);
  const profile: ViewportProfile =
    shortestSide < 600 ? "phone" : shortestSide < 900 || coarsePointer ? "tablet" : "desktop";

  return {
    profile,
    width,
    height,
    orientation: width >= height ? "landscape" : "portrait",
    coarsePointer,
    reducedMotion,
  };
}

export function useViewportState(): ViewportState {
  const [state, setState] = useState(readViewport);

  useEffect(() => {
    const visual = window.visualViewport;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const pointer = window.matchMedia("(pointer: coarse)");
    const update = () => setState(readViewport());

    window.addEventListener("resize", update, { passive: true });
    window.addEventListener("orientationchange", update, { passive: true });
    visual?.addEventListener("resize", update, { passive: true });
    visual?.addEventListener("scroll", update, { passive: true });
    motion.addEventListener("change", update);
    pointer.addEventListener("change", update);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("orientationchange", update);
      visual?.removeEventListener("resize", update);
      visual?.removeEventListener("scroll", update);
      motion.removeEventListener("change", update);
      pointer.removeEventListener("change", update);
    };
  }, []);

  return state;
}
