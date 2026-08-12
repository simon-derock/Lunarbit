"use client";

import { useState } from "react";

import { Icon } from "@/components/Icons";
import { useProfiles } from "@/components/ProfileProvider";
import {
  DATA_PROFILE_IDS,
  DATA_PROFILES,
  VISUAL_PROFILE_IDS,
  VISUAL_PROFILES,
} from "@/lib/profiles";

export function ProfileControls() {
  const { dataProfile, visualProfile, setDataProfile, setVisualProfile } = useProfiles();
  const [open, setOpen] = useState<"data" | "visual" | null>(null);

  return (
    <div className="profile-controls" aria-label="Workspace profiles">
      <div className="profile-control-wrap">
        <span className="profile-control-label">DATA PROFILE</span>
        <button
          aria-expanded={open === "data"}
          aria-haspopup="listbox"
          className="profile-trigger"
          onClick={() => setOpen(open === "data" ? null : "data")}
          type="button"
        >
          <span className="profile-orbit" aria-hidden="true"><i /><i /><i /></span>
          <span><b>{dataProfile.handle}</b><small>{dataProfile.title}</small></span>
          <Icon name="chevron" />
        </button>
        {open === "data" && (
          <div className="profile-menu data-profile-menu" role="listbox" aria-label="Commerce data profile">
            <div className="menu-kicker">SYNTHETIC COMMERCE MIRRORS</div>
            {DATA_PROFILE_IDS.map((id) => {
              const profile = DATA_PROFILES[id];
              const selected = id === dataProfile.id;
              return (
                <button
                  aria-selected={selected}
                  className="data-profile-option"
                  key={id}
                  onClick={() => { setDataProfile(id); setOpen(null); }}
                  role="option"
                  type="button"
                >
                  <span className="option-index">0{DATA_PROFILE_IDS.indexOf(id) + 1}</span>
                  <span><b>{profile.title}</b><small>{profile.archetype}</small></span>
                  {selected && <Icon name="check" />}
                </button>
              );
            })}
            <p className="menu-disclosure">Profiles are isolated synthetic datasets. Switching replaces the entire graph and analytical state.</p>
          </div>
        )}
      </div>

      <div className="profile-divider" />

      <div className="profile-control-wrap visual-control-wrap">
        <span className="profile-control-label">VISUAL PROFILE</span>
        <button
          aria-expanded={open === "visual"}
          aria-haspopup="listbox"
          className="profile-trigger visual-trigger"
          onClick={() => setOpen(open === "visual" ? null : "visual")}
          type="button"
        >
          <span className="palette-mini" aria-hidden="true">
            {visualProfile.palette.slice(0, 4).map((color) => <i key={color} style={{ background: color }} />)}
          </span>
          <span><b>{visualProfile.shortName}</b><small>{visualProfile.rendering}</small></span>
          <Icon name="chevron" />
        </button>
        {open === "visual" && (
          <div className="profile-menu visual-profile-menu" role="listbox" aria-label="Visualization profile">
            <div className="menu-kicker">RENDERING SYSTEM</div>
            {VISUAL_PROFILE_IDS.map((id, index) => {
              const profile = VISUAL_PROFILES[id];
              const selected = id === visualProfile.id;
              return (
                <button
                  aria-selected={selected}
                  className="visual-profile-option"
                  key={id}
                  onClick={() => { setVisualProfile(id); setOpen(null); }}
                  role="option"
                  type="button"
                >
                  <span className="option-index">0{index + 1}</span>
                  <span className="palette-strip" aria-hidden="true">
                    {profile.palette.map((color) => <i key={color} style={{ background: color }} />)}
                  </span>
                  <span><b>{profile.name}</b><small>{profile.description}</small></span>
                  {selected && <Icon name="check" />}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
