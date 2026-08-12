"use client";

import {
  createContext,
  type CSSProperties,
  type ReactNode,
  useCallback,
  useContext,
  useMemo,
  useSyncExternalStore,
} from "react";

import {
  DATA_PROFILES,
  DEFAULT_SELECTION,
  selectionFromSearch,
  selectionSearch,
  VISUAL_PROFILES,
} from "@/lib/profiles";
import type {
  CommerceDataProfile,
  DataProfileId,
  ProfileSelection,
  VisualProfile,
  VisualProfileId,
} from "@/lib/types";

interface ProfileContextValue {
  selection: ProfileSelection;
  dataProfile: CommerceDataProfile;
  visualProfile: VisualProfile;
  setDataProfile: (id: DataProfileId) => void;
  setVisualProfile: (id: VisualProfileId) => void;
  query: string;
}

const ProfileContext = createContext<ProfileContextValue | null>(null);

function writeSelection(selection: ProfileSelection) {
  const url = `${window.location.pathname}${selectionSearch(selection)}${window.location.hash}`;
  window.history.replaceState({}, "", url);
  window.localStorage.setItem("lunarbit-profile-selection", JSON.stringify(selection));
  window.dispatchEvent(new Event("lunarbit:profile"));
}

const selectionKey = (selection: ProfileSelection) =>
  `${selection.dataProfileId}|${selection.visualProfileId}`;

function currentSelection(): ProfileSelection {
  if (window.location.search) return selectionFromSearch(window.location.search);
  const stored = window.localStorage.getItem("lunarbit-profile-selection");
  if (!stored) return DEFAULT_SELECTION;
  try {
    const value = JSON.parse(stored) as Partial<ProfileSelection>;
    return selectionFromSearch(
      selectionSearch({
        dataProfileId: value.dataProfileId ?? DEFAULT_SELECTION.dataProfileId,
        visualProfileId: value.visualProfileId ?? DEFAULT_SELECTION.visualProfileId,
      } as ProfileSelection),
    );
  } catch {
    return DEFAULT_SELECTION;
  }
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener("popstate", onChange);
  window.addEventListener("lunarbit:profile", onChange);
  return () => {
    window.removeEventListener("popstate", onChange);
    window.removeEventListener("lunarbit:profile", onChange);
  };
}

export function ProfileProvider({ children }: Readonly<{ children: ReactNode }>) {
  const key = useSyncExternalStore(
    subscribe,
    () => selectionKey(currentSelection()),
    () => selectionKey(DEFAULT_SELECTION),
  );
  const [dataProfileId, visualProfileId] = key.split("|") as [DataProfileId, VisualProfileId];

  const change = useCallback((next: ProfileSelection) => {
    writeSelection(next);
  }, []);

  const value = useMemo<ProfileContextValue>(() => {
    const selection = { dataProfileId, visualProfileId };
    const dataProfile = DATA_PROFILES[selection.dataProfileId];
    const visualProfile = VISUAL_PROFILES[selection.visualProfileId];
    return {
      selection,
      dataProfile,
      visualProfile,
      setDataProfile: (id) => change({ ...selection, dataProfileId: id }),
      setVisualProfile: (id) => change({ ...selection, visualProfileId: id }),
      query: selectionSearch(selection),
    };
  }, [change, dataProfileId, visualProfileId]);

  return (
    <ProfileContext.Provider value={value}>
      <div
        className="theme-root"
        data-visual-profile={value.visualProfile.id}
        data-rendering={value.visualProfile.rendering}
        style={value.visualProfile.tokens as CSSProperties}
      >
        {children}
      </div>
    </ProfileContext.Provider>
  );
}

export function useProfiles(): ProfileContextValue {
  const value = useContext(ProfileContext);
  if (!value) {
    throw new Error("useProfiles must be used inside ProfileProvider");
  }
  return value;
}
