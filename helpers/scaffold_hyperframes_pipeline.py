"""Scaffold the video-use -> HyperFrames artifact lane.

Creates <edit_dir>/hyperframes/ with DESIGN.md, SCRIPT.md, STORYBOARD.md,
QA.md, assets/, compositions/, renders/, and snapshots/. It does not run
HyperFrames or transcribe media.

Usage:
    python helpers/scaffold_hyperframes_pipeline.py --edit-dir <videos_dir>/edit
    python helpers/scaffold_hyperframes_pipeline.py --edit-dir <videos_dir>/edit --base-cut base-cut.mp4
"""

from __future__ import annotations

import argparse
from pathlib import Path


def write_once(path: Path, text: str) -> None:
    if not path.exists():
        path.write_text(text)


def rel(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def main() -> None:
    ap = argparse.ArgumentParser(description="Scaffold a HyperFrames pass inside a video-use edit directory")
    ap.add_argument("--edit-dir", type=Path, required=True, help="Existing video-use edit directory")
    ap.add_argument(
        "--base-cut",
        type=Path,
        default=None,
        help="Base cut path. Defaults to <edit-dir>/base-cut.mp4",
    )
    args = ap.parse_args()

    edit_dir = args.edit_dir.resolve()
    edit_dir.mkdir(parents=True, exist_ok=True)
    hf_dir = edit_dir / "hyperframes"
    for child in ["assets", "assets/fonts", "compositions", "renders", "snapshots"]:
        (hf_dir / child).mkdir(parents=True, exist_ok=True)

    base_cut = (args.base_cut or (edit_dir / "base-cut.mp4")).resolve()
    transcript = edit_dir / "takes_packed.md"
    edl = edit_dir / "edl.json"
    project = edit_dir / "project.md"

    if base_cut.exists():
        asset_base = hf_dir / "assets" / "base-cut.mp4"
        if not asset_base.exists():
            asset_base.symlink_to(base_cut)

    write_once(
        project,
        """# Project

## Source Inventory

- Source:
- Transcript:
- Base cut:

## Thesis Scan

- Central thesis:
- Strongest verbal hook:
- Strongest text-on-screen hook:
- Proof / authority moments:
- Emotional human moments:
- Framework/list moments:
- Likely fluff or dead zones:
- Proactive clip opportunities:

## Approved Strategy

- Story shape:
- Target length:
- Hook version(s):
- Cut rhythm rules:
- Visual system:

## Feedback / Decisions

- 

## Exports

- 
""",
    )

    write_once(
        hf_dir / "DESIGN.md",
        f"""# Design

## Overview

Define the visual identity for this edit. Use real source material, brand assets, or explicit user direction.

## Colors

- Primary surface:
- Primary text:
- Accent:
- Secondary accent:
- Warning / emphasis:

## Typography

- Caption font:
- Handwritten / note font:
- Utility font:

## Components / Graphic Language

- Captions:
- Notes:
- Proof flashes:
- Logos / screenshots:
- Transitions:

## Imagery / Proof Assets

- Base cut: `{rel(base_cut, hf_dir)}`
- Packed transcript: `{rel(transcript, hf_dir)}`
- EDL: `{rel(edl, hf_dir)}`

## Do

- Keep graphics meaning-led.
- Keep captions mobile-readable.
- Keep face and important visuals clear.

## Don't

- Do not overpower the speaker.
- Do not add decorative logos without proof value.
- Do not change spoken meaning.
""",
    )

    write_once(
        hf_dir / "SCRIPT.md",
        f"""# Script

Source transcript: `{rel(transcript, hf_dir)}`
Source EDL: `{rel(edl, hf_dir)}`

Use this file for the exact selected spoken lines, output-timeline timings, beat labels, and intended on-screen emphasis. Do not rewrite the speaker unless the user explicitly asks for a scripted voiceover.

## Beats

| Time | Beat | Spoken Line | On-Screen Emphasis |
| --- | --- | --- | --- |
| 0.00-0.00 | Hook | TBD | TBD |
""",
    )

    write_once(
        hf_dir / "STORYBOARD.md",
        """# Storyboard

## Global Direction

- Format:
- Platform:
- Runtime:
- Visual thesis:
- Caption style:
- Motion style:
- Guardrails:

## Asset Audit

| Asset | Path | Purpose |
| --- | --- | --- |
| Base cut | `assets/base-cut.mp4` | Primary video |

## Beats

### Beat 1: Hook

- Timing:
- Spoken line:
- Mood / camera:
- Layering:
- Assets:
- Captions:
- Motion techniques:
- Transition in:
- Transition out:
- QA risk:
""",
    )

    write_once(
        hf_dir / "QA.md",
        """# QA

## Commands

- [ ] `npx --yes hyperframes lint`
- [ ] `npx --yes hyperframes validate`
- [ ] `npx --yes hyperframes inspect --samples 15`
- [ ] `npx --yes hyperframes snapshot --at ...`
- [ ] `npx --yes hyperframes render --quality standard --output renders/review.mp4`
- [ ] `ffprobe -hide_banner renders/review.mp4`
- [ ] `ffmpeg -i renders/review.mp4 -vf blackdetect=d=0.1:pic_th=0.98 -an -f null -`

## Visual Review

- Duration:
- Resolution:
- FPS:
- Captions:
- Face/important visual clearance:
- Text overflow:
- Residual risks:
""",
    )

    print(hf_dir)


if __name__ == "__main__":
    main()
