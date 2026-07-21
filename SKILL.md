---
name: video-use
description: Edit any video by conversation. Transcribe, cut, color grade, generate overlay animations, burn subtitles — especially creator talking-head/yap videos, plus montages, tutorials, travel, interviews, BTS, and sponsored posts. Finds the thesis, proposes the cut, protects the voice, creates hook variants when useful, executes, verifies, iterates, and persists. Production-correctness rules are hard; everything else is artistic freedom.
---

# Video Use

## Principle

1. **LLM reasons from raw transcript + on-demand visuals.** The only derived artifact that earns its keep is a packed phrase-level transcript (`takes_packed.md`). Everything else — filler tagging, retake detection, shot classification, emphasis scoring — you derive at decision time.
2. **Audio is primary, visuals follow.** Cut candidates come from speech boundaries and silence gaps. Drill into visuals only at decision points.
3. **Ask → confirm → execute → iterate → persist.** Never touch the cut until the user has confirmed the strategy in plain English.
4. **Generalize.** Do not assume what kind of video this is. Look at the material, ask the user, then edit.
5. **Artistic freedom is the default.** Every specific value, preset, font, color, duration, pitch structure, and technique in this document is a *worked example* from one proven video — not a mandate. Read them to understand what's possible and why each worked. Then make your own taste calls based on what the material actually is and what the user actually wants. **The only things you MUST do are in the Hard Rules section below.** Everything else is yours.
6. **Invent freely.** If the material calls for a technique not described here — split-screen, picture-in-picture, lower-third identity cards, reaction cuts, speed ramps, freeze frames, crossfades, match cuts, L-cuts, J-cuts, speed ramps over breath, whatever — build it. The helpers are ffmpeg and PIL. They can do anything the format supports. Do not wait for permission.
7. **Verify your own output before showing it to the user.** If you wouldn't ship it, don't present it.

## Hard Rules (production correctness — non-negotiable)

These are the things where deviation produces silent failures or broken output. They are not taste, they are correctness. Memorize them.

1. **Subtitles are applied LAST in the filter chain**, after every overlay. Otherwise overlays hide captions. Silent failure.
2. **Per-segment extract → lossless `-c copy` concat**, not single-pass filtergraph. Otherwise you double-encode every segment when overlays are added.
3. **30ms audio fades at every segment boundary** (`afade=t=in:st=0:d=0.03,afade=t=out:st={dur-0.03}:d=0.03`). Otherwise audible pops at every cut.
4. **Overlays use `setpts=PTS-STARTPTS+T/TB`** to shift the overlay's frame 0 to its window start. Otherwise you see the middle of the animation during the overlay window.
5. **Master SRT uses output-timeline offsets**: `output_time = word.start - segment_start + segment_offset`. Otherwise captions misalign after segment concat.
6. **Never cut inside a word.** Snap every cut edge to a word boundary from the Scribe transcript.
7. **Pad every cut edge.** Working window: 30–200ms. Scribe timestamps drift 50–100ms — padding absorbs the drift. Tighter for fast-paced, looser for cinematic.
8. **Word-level verbatim ASR only.** Never SRT/phrase mode (loses sub-second gap data). Never normalized fillers (loses editorial signal).
9. **Cache transcripts per source.** Never re-transcribe unless the source file itself changed.
10. **Parallel sub-agents for multiple animations.** Never sequential. Spawn N at once via the `Agent` tool; total wall time ≈ slowest one.
11. **Strategy confirmation before execution.** Never touch the cut until the user has approved the plain-English plan.
12. **All session outputs in `<videos_dir>/edit/`.** Never write inside the `video-use/` project directory.
13. **Audio cleanup, music, and SFX run as audio-only passes on the concatenated/composited track — never per-segment.** Video is `-c:v copy` through every audio step. The only per-segment audio operation is the 30ms boundary fade (Rule 3). Loudnorm is ALWAYS the last audio action — run it after music is mixed, because added music changes integrated loudness.

Everything else in this document is a worked example. Deviate whenever the material calls for it.

## Directory layout

The skill lives in `video-use/`. User footage lives wherever they put it. All session outputs go into `<videos_dir>/edit/`.

```
<videos_dir>/
├── <source files, untouched>
└── edit/
    ├── project.md               ← memory; appended every session
    ├── takes_packed.md          ← phrase-level transcripts, the LLM's primary reading view
    ├── edl.json                 ← cut decisions
    ├── transcripts/<name>.json  ← cached raw Scribe JSON
    ├── animations/slot_<id>/    ← per-animation source + render + reasoning
    ├── clips_graded/            ← per-segment extracts with grade + fades
    ├── hyperframes/             ← optional HyperFrames visual pass
    ├── master.srt               ← output-timeline subtitles
    ├── downloads/               ← yt-dlp outputs
    ├── verify/                  ← debug frames / timeline PNGs
    ├── preview.mp4
    └── final.mp4
```

## Setup

First-time install lives in `install.md` (clone, deps, ffmpeg, skill registration, API key). Don't re-run it every session; on cold start just verify:

- `TRANSCRIBE_PROVIDER` resolves. This install defaults to `castmagic`.
- For `TRANSCRIBE_PROVIDER=castmagic`, `CASTMAGIC_API_KEY` resolves from environment or OpenClaw env files. Castmagic needs a public media URL, so local files must have either a `<video>.url` sidecar or an `edit/source_urls.json` mapping before transcription.
- For `TRANSCRIBE_PROVIDER=local-whisper`, transcription runs locally through `faster-whisper`. It creates word-level timestamps and uses `Speaker 1` for all words because local Whisper does not diarize.
- For `TRANSCRIBE_PROVIDER=elevenlabs`, `ELEVENLABS_API_KEY` resolves — either in the environment or in `.env` at the video-use repo root. If missing, ask the user to paste one and write it to `.env` (never to the user's `<videos_dir>`).
- `ffmpeg` + `ffprobe` on PATH.
- Python deps installed (`uv sync` or `pip install -e .` inside the repo).
- Node.js + npm available if the session needs HyperFrames or Remotion slots. HyperFrames currently requires Node.js 22+.
- `yt-dlp`, HyperFrames, Remotion, Manim installed only on first use.
- First-use animation setup happens inside the slot directory, never at the video-use repo root. HyperFrames can be invoked with `npx --yes hyperframes ...`; Remotion can be scaffolded with `npx create-video@latest` or installed as a project-local dependency before using its `remotion render` command.
- This skill vendors `skills/manim-video/`. Read its SKILL.md when building a Manim slot.

Helpers (`helpers/transcribe.py`, `helpers/render.py`, etc.) live alongside this SKILL.md. Resolve their paths relative to the directory containing this file — the skill is typically symlinked at `~/.claude/skills/video-use/` or `~/.codex/skills/video-use/`.

## Helpers

- **`transcribe.py <video>`** — single-file transcript call using `TRANSCRIBE_PROVIDER`. `--num-speakers N` optional for ElevenLabs. Cached.
- **`transcribe_batch.py <videos_dir>`** — 4-worker parallel transcription using `TRANSCRIBE_PROVIDER`. Use for multi-take.
- **`pack_transcripts.py --edit-dir <dir>`** — `transcripts/*.json` → `takes_packed.md` (phrase-level, break on silence ≥ 0.5s).
- **`timeline_view.py <video> <start> <end>`** — filmstrip + waveform PNG. On-demand visual drill-down. **Not a scan tool** — use it at decision points, not constantly.
- **`render.py <edl.json> -o <out>`** — per-segment extract → concat → overlays (PTS-shifted) → subtitles LAST. `--preview` for 720p fast. `--build-subtitles` to generate master.srt inline. Also auto tone-maps HDR (HLG/PQ) sources to Rec.709 SDR, preserves portrait orientation, and applies two-pass loudnorm (-14 LUFS / -1 dBTP / LRA 11) by default (disable with `--no-loudnorm`).
- **`grade.py <in> -o <out>`** — ffmpeg filter chain grade. Presets + `--filter '<raw>'` for custom.
- **`clean_audio.py <video> -o <out>`** — audio-only spectral cleanup: high-pass (default 80 Hz), denoise (`afftdn`), optional `--deess`. Defaults to `--no-loudnorm` (loudness deferred to the music step). Video `-c:v copy`. Gate C step 1.
- **`audio_bed.py <video> -o <out>`** — ducked music bed (`--music`, sidechain `--duck`) + SFX (`--sfx "file@time:gain"`, repeatable), then loudnorm LAST (-14 LUFS / -1 dBTP / LRA 11). Video `-c:v copy`. Gate C step 2.
- **`scaffold_hyperframes_pipeline.py --edit-dir <dir>`** — creates `edit/hyperframes/` with DESIGN/SCRIPT/STORYBOARD/QA templates and project folders for the HyperFrames visual pass.

For animations, create `<edit>/animations/slot_<id>/` with `Bash` and spawn a sub-agent via the `Agent` tool.

## HyperFrames Visual Pass

When the user asks for creator-forward motion graphics, layered captions, handwritten notes, logos, screenshots, proof flashes, product UI motion, or a more artistic video-editing pass, read `references/hyperframes-pipeline.md` before planning.

The short version:

- `video-use` owns source inventory, transcript, story selection, EDL, and a clean base cut.
- HyperFrames owns the visual system, storyboard, composed overlays/captions, validation, and review/final render.
- The bridge artifacts are `edit/edl.json`, `edit/base-cut.mp4`, `edit/takes_packed.md`, `edit/hyperframes/DESIGN.md`, `edit/hyperframes/SCRIPT.md`, and `edit/hyperframes/STORYBOARD.md`.
- Do not freestyle a full HyperFrames edit without `DESIGN.md` and `STORYBOARD.md`; those files are the creative contract.
- For user-visible HyperFrames work, run `lint`, `validate`, `inspect`, snapshots or contact sheet, and a review render before delivery.

## Creator Talking-Head / Yap Videos

For raw yaps, founder takes, personal-brand clips, walk-and-talks, car talks, podcast clips, BTS reels, or any video where the person is the product, read `references/creator-talking-head-workflow.md` before proposing the strategy.

Default operating stance for these videos:

- The editor finds the story; do not make the user supply a full brief.
- Center the cut around one thesis.
- Protect the speaker's voice and human rhythm.
- Generate hook options before committing to a final opening when useful.
- Keep graphics, captions, memes, proof flashes, and music in service of the message.
- Leave organized run notes so the content system compounds over time.

## The process

The pipeline runs in three gates. Each gate ends with automated technical QA (the Hard Rules — pops, flashes, caption/overlay alignment) FOLLOWED BY a review with the user. Nothing in a later gate begins until the current gate's checkpoint is approved. QA happens at every gate, not once at the end — so breakage cannot accumulate.

### Gate A — Story & Cut

Lock the words and the rhythm before any visual or audio polish.

1. **Inventory.** `ffprobe` every source. `transcribe_batch.py` on the directory. `pack_transcripts.py` → `takes_packed.md`. Sample one or two `timeline_view`s for a visual first impression.
2. **Transcript pre-scan.** One pass over `takes_packed.md` as a SHARED read: surface verbal slips, mis-speaks, phrasings to avoid, thesis candidates, hook candidates, proof moments, emotional moments, framework/list moments, proactive clip opportunities. The user reacts; this becomes the editor brief. (Plain list — do not pre-compute stored tags; see Anti-patterns.)
3. **Converse + filler/long-pause pass.** Describe what you see in plain English and ask questions shaped by the material (content type, target length/aspect, aesthetic/brand, pacing feel, must-preserve/must-cut moments, animation/grade/subtitle prefs). In the same pass, mark obvious fillers and dead pauses LIVE on the transcript — never as pre-computed stored tags (Hard Rule 8 + Anti-patterns) — and propose removals.
4. **Propose strategy + rough cut.** State the single thesis, story shape, take choices, hook options, and cut-rhythm rules in 4–8 sentences, and WAIT for confirmation (Hard Rule 11). Then produce `edl.json` via the editor sub-agent brief, built around the strongest ideas, drilling into `timeline_view` at ambiguous moments. Render a no-frills base cut (`render.py --preview --no-subtitles --no-loudnorm`, no overlays).

   **→ CHECKPOINT A1 (rough cut).** Run boundary self-eval on the rendered base cut, then watch it with the user. "Does the story land?" Iterate until the story is right.

5. **Tighten pacing.** A SEPARATE cycle, not folded into the rough cut. Trim handoff air, protect breath, cut dead silence, repair choppy thought-jumps. Re-render the base cut.

   **→ CHECKPOINT A2 (tighten) — BLOCKS GATE B.** Review the tightened cut with the user. No visual or audio work begins until this checkpoint is approved.

### Gate B — Picture Lock

6. **Captions.** Choose chunking / case / placement for the content. Build via `render.py --build-subtitles` (or a hand-authored SRT). Hard Rule 1 (subtitles LAST) and Hard Rule 5 (output-timeline offsets) are enforced by `render.py`.
7. **B-roll / screenshots / overlays.** HyperFrames (read `references/hyperframes-pipeline.md` first) or PIL / Remotion / Manim slots, built in parallel sub-agents (Hard Rule 10). Compose via `render.py` — overlays PTS-shifted (Rule 4), subtitles last (Rule 1). For talking-head/yap edits the base cut must already work without graphics (Gate A) before anything here.

   **→ CHECKPOINT B (picture lock).** Render with visuals (`--no-loudnorm` — Gate C owns final audio). Self-eval every overlay boundary: captions not hidden, overlays PTS-aligned, no flashes. Review with the user. "Does it look right?" This is picture lock.

### Gate C — Audio & Polish

The audio chain runs as audio-only passes on the picture-locked file. Video stays `-c:v copy` throughout (Hard Rule 13).

8. **Clean audio.** `clean_audio.py <picture_lock.mp4> -o <cleaned.mp4>` — high-pass rumble, denoise, optional de-ess. Run with `--no-loudnorm` (loudness is deferred to the music step).
9. **SFX / light music.** `audio_bed.py <cleaned.mp4> -o <mixed.mp4> [--music <file> --duck] [--sfx "file@time:gain" ...]` — ducked music bed under speech, SFX placed on the output timeline, then loudnorm LAST (-14 LUFS / -1 dBTP / LRA 11). If there is no music or SFX, skip `audio_bed.py` and let `render.py`'s built-in loudnorm finish instead (do not pass `--no-loudnorm` on the final render).
10. **Clarity & energy review.** A CREATIVE review, not just technical: is it tight, alive, on-message? Run the technical self-eval too.

   **→ CHECKPOINT C (final).** Review with the user. Final render on approval. Append `project.md` (see the Memory section).

### Self-eval (runs inside every checkpoint, before showing the user)

Run `timeline_view` on the RENDERED output (not the sources) at every cut boundary (±1.5s) and check each frame for: visual discontinuity / flash / jump; waveform spike (audio pop past the 30ms fade); subtitle hidden behind an overlay (Rule 1); overlay misaligned or showing wrong frames (Rule 4); for talking-head/yap, choppy thought-jumps or missing breath. Also sample first 2s, last 2s, and 2–3 mid-points for grade consistency and caption readability. `ffprobe` the output to confirm duration matches the EDL. If anything fails: fix → re-render → re-eval. Cap at 3 self-eval passes per checkpoint — if issues remain after 3, flag them to the user rather than looping forever. Only present a checkpoint once its self-eval passes.

## Cut craft (techniques)

- **Audio-first.** Candidate cuts from word boundaries and silence gaps.
- **Preserve peaks.** Laughs, punchlines, emphasis beats. Extend past punchlines to include reactions — the laugh IS the beat.
- **Speaker handoffs** benefit from air between utterances. Common values: 400–600ms. Less for fast-paced, more for cinematic. Taste call.
- **Audio events as signals.** `(laughs)`, `(sighs)`, `(applause)` mark beats. Extend past them.
- **Silence gaps are cut candidates.** Silences ≥400ms are usually the cleanest. 150–400ms phrase boundaries are usable with a visual check. <150ms is unsafe (mid-phrase).
- **Example cut padding** (the launch video shipped with this): 50ms before the first kept word, 80ms after the last. Tighter for montage energy, looser for documentary. Stay in the 30–200ms working window (Hard Rule 7).
- **Never reason audio and video independently.** Every cut must work on both tracks.

## The packed transcript (primary reading view)

`pack_transcripts.py` reads all `transcripts/*.json` and produces one markdown file where each take is a list of phrase-level lines, each prefixed with its `[start-end]` time range. Phrases break on any silence ≥ 0.5s OR speaker change. This is the artifact the editor sub-agent reads to pick cuts — it gives word-boundary precision from text alone at 1/10 the tokens of raw JSON.

Example line:
```
## C0103  (duration: 43.0s, 8 phrases)
  [002.52-005.36] S0 Ninety percent of what a web agent does is completely wasted.
  [006.08-006.74] S0 We fixed this.
```

## Editor sub-agent brief (for multi-take selection)

When the task is "pick the best take of each beat across many clips," spawn a dedicated sub-agent with a brief shaped like this. The structure is load-bearing; the pitch-shape example is not.

```
You are editing a <type> video. Pick the best take of each beat and 
assemble them chronologically by beat, not by source clip order.

INPUTS:
  - takes_packed.md (time-annotated phrase-level transcripts of all takes)
  - Product/narrative context: <2 sentences from the user>
  - Speaker(s): <name, role, delivery style note>
  - Expected structure: <pick an archetype or invent one>
  - Verbal slips to avoid: <list from the pre-scan pass>
  - Target runtime: <seconds>

Common structural archetypes (pick, adapt, or invent):
  - Tech launch / demo:   HOOK → PROBLEM → SOLUTION → BENEFIT → EXAMPLE → CTA
  - Tutorial:             INTRO → SETUP → STEPS → GOTCHAS → RECAP
  - Interview:            (QUESTION → ANSWER → FOLLOWUP) repeat
  - Travel / event:       ARRIVAL → HIGHLIGHTS → QUIET MOMENTS → DEPARTURE
  - Documentary:          THESIS → EVIDENCE → COUNTERPOINT → CONCLUSION
  - Music / performance:  INTRO → VERSE → CHORUS → BRIDGE → OUTRO
  - Or invent your own.

RULES:
  - Start/end times must fall on word boundaries from the transcript.
  - Pad cut boundaries (working window 30–200ms).
  - Prefer silences ≥ 400ms as cut targets.
  - Unavoidable slips are kept if no better take exists. Note them in "reason".
  - If over budget, revise: drop a beat or trim tails. Report total and self-correct.

OUTPUT (JSON array, no prose):
  [{"source": "C0103", "start": 2.42, "end": 6.85, "beat": "HOOK",
    "quote": "...", "reason": "..."}, ...]

Return the final EDL and a one-line total runtime check.
```

## Color grade (when requested)

Your job is to **reason about the image**, not apply a preset. Look at a frame (via `timeline_view`), decide what's wrong, adjust one thing, look again.

Mental model is ASC CDL. Per channel: `out = (in * slope + offset) ** power`, then global saturation. `slope` → highlights, `offset` → shadows, `power` → midtones.

**Example filter chains** (`grade.py` has `--list-presets`; use them as starting points or mix your own):

- **`warm_cinematic`** — retro/technical, subtle teal/orange split, desaturated. Shipped in a real launch video. Safe for talking heads.
- **`neutral_punch`** — minimal corrective: contrast bump + gentle S-curve. No hue shifts.
- **`none`** — straight copy. Default when the user hasn't asked.

For anything else — portraiture, nature, product, music video, documentary — invent your own chain. `grade.py --filter '<raw ffmpeg>'` accepts any filter string.

Hard rules: apply **per-segment during extraction** (not post-concat, which re-encodes twice). Never go aggressive without testing skin tones.

## Subtitles (when requested)

Subtitles have three dimensions worth reasoning about: **chunking** (how much text per cue), **case** (Natural/Title/UPPER), and **placement** (margin from bottom). The right combo depends on content.

**Chunking — one phrase at a time.** Captions exist to convey meaning, so show **one clean phrase per cue**, usually **3–5 words at a time**. Each line should read well on its own as the viewer scans it. `render.py`'s `build_master_srt` prefers punctuation and clause boundaries when they land inside that 3–5 word window; otherwise it splits at the word/character cap while avoiding dangling connectors at the end of a line. Avoid 1–2 word fragments unless the source phrase is genuinely that short, e.g. "Why?". Default to **natural case**, not all-caps walls.

**Default style** — `render.py` ships this as `SUB_FORCE_STYLE`: TikTok Sans Bold, white text, **no caption background**, and **no black outline on the letters**. `MarginV=80` for vertical-social safe-zone; drop to `~34` for landscape/desktop deliverables. TikTok Sans is the default caption font for all video-use renders unless the user explicitly asks for a different font.

```
FontName=TikTok Sans,FontSize=18,Bold=1,
PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H00000000,
BorderStyle=1,Outline=0,Shadow=0,
Alignment=2,MarginV=80
```

Adapt freely when the user asks for a specific style, but the default is phrase-level TikTok Sans with no box and no outline. Hard rules: subtitles LAST (Rule 1), output-timeline offsets (Rule 5).

## Animations (when requested)

Animations match the content and the brand. **Get the palette, font, and visual language from the conversation** — never assume a default. If the user hasn't told you, propose a palette in the strategy phase and wait for confirmation before building anything.

**Tool options:**

Pick the engine per animation slot. Do not default to Remotion just because the animation is web-adjacent.

- **HyperFrames** — Browser-native HTML/CSS/GSAP video compositions: product UI motion, website-to-video or mockup-to-video captures, kinetic typography, landing-page/storyboard promos, data-driven UI states, transparent WebM overlays, and clips that need deterministic frame capture plus HyperFrames lint/validate/render checks. Best when the animation should be authored and verified like a web composition instead of a React component tree.
- **Remotion** — React/CSS compositions with component state, reusable React primitives, or an existing Remotion brand system. Best when the user specifically asks for React/Remotion or when React composition is the simpler authoring model.
- **Manim** — formal diagrams, state machines, equation derivations, graph morphs. Read `skills/manim-video/SKILL.md` and its references for depth.
- **PIL + PNG sequence + ffmpeg** — simple overlay cards: counters, typewriter text, single bar reveals, progressive draws. Fast to iterate, any aesthetic you want. The launch video used this.

For HyperFrames slots, scaffold the slot inside `edit/animations/slot_<id>/` with `npx --yes hyperframes init . --example blank --non-interactive --skip-skills`, build the HTML composition there, run the HyperFrames checks that fit the slot (`lint`, `validate`, and a draft render when practical), then produce the final overlay video with `npx --yes hyperframes render . -o render.mp4` or `--format webm -o render.webm` when alpha is required. Point the EDL overlay `file` at the actual rendered path.

For Remotion slots, keep the Remotion project isolated inside the same slot directory, scaffold with `npx create-video@latest` or install Remotion locally there, render the composition to `render.mp4` with the project-local `remotion render` command, and verify duration and dimensions with `ffprobe`.

None is mandatory. Invent hybrids if useful (e.g., PIL background with a HyperFrames or Remotion layer on top).

**Duration rules of thumb, context-dependent:**

- **Sync-to-narration explanations.** A viewer needs to parse the content at 1×. Rough floor 3s, typical 5–7s for simple cards, 8–14s for complex diagrams. The launch video shipped at 5–7s per simple card.
- **Beat-synced accents** (music video, fast montage). 0.5–2s is fine — they're visual accents, not information. The "readable at 1×" rule becomes *"recognizable at 1×"*, not *"fully parseable."*
- **Hold the final frame ≥ 1s** before the cut (universal).
- **Over voiceover:** total duration ≥ `narration_length + 1s` (universal).
- **Never parallel-reveal independent elements** — the eye can't track two new things at once. One thing, pause, next thing.

**Animation payoff timing (rule for sync-to-narration):** get the payoff word's timestamp. Start the overlay `reveal_duration` seconds earlier so the landing frame coincides with the spoken payoff word. Without this sync the animation feels disconnected.

**Easing** (universal — never `linear`, it looks robotic):

```python
def ease_out_cubic(t):    return 1 - (1 - t) ** 3
def ease_in_out_cubic(t):
    if t < 0.5: return 4 * t ** 3
    return 1 - (-2 * t + 2) ** 3 / 2
```

`ease_out_cubic` for single reveals (slow landing). `ease_in_out_cubic` for continuous draws.

**Typing text anchor trick:** center on the FULL string's width, not the partial-string width — otherwise text slides left during reveal.

**Example palette** (the launch video — one aesthetic among infinite):
- Background `(10, 10, 10)` near-black
- Accent `#FF5A00` / `(255, 90, 0)` orange
- Labels `(110, 110, 110)` dim gray
- Font: Menlo Bold at `/System/Library/Fonts/Menlo.ttc` (index 1)
- ≤ 2 accent colors, ~40% empty space, minimal chrome
- Result: terminal / retro tech feel

This is one style. If the brand is warm and serif, use that. If it's colorful and playful, use that. If the user handed you a style guide, follow it. If they didn't, propose one and confirm.

**Parallel sub-agent brief** — each animation is one sub-agent spawned via the `Agent` tool. Each prompt is self-contained (sub-agents have no parent context). Include:

1. One-sentence goal: *"Build ONE animation: [spec]. Nothing else."*
2. Absolute output path (`<edit>/animations/slot_<id>/render.mp4`)
3. Exact technical spec: resolution, fps, codec, pix_fmt, CRF, duration
4. Style palette as concrete values (RGB tuples, hex, or reference to a design system)
5. Font path with index
6. Frame-by-frame timeline (what happens when, with easing)
7. Anti-list ("no chrome, no extras, no titles unless specified")
8. Code pattern reference (copy helpers inline, don't import across slots)
9. Deliverable checklist (script, render, verify duration via ffprobe, report)
10. **"Do not ask questions. If anything is ambiguous, pick the most obvious interpretation and proceed."**

One sub-agent = one file (unique filenames, parallel agents don't overwrite each other).

## Output spec

Match the source unless the user asked for something specific. Common targets: `1920×1080@24` cinematic, `1920×1080@30` screen content, `1080×1920@30` vertical social, `3840×2160@24` 4K cinema, `1080×1080@30` square. `render.py` defaults the scale to 1080p from any source; pass `--filter` or edit the extract command for other targets. Worth asking the user which delivery format matters.

## EDL format

```json
{
  "version": 1,
  "sources": {"C0103": "/abs/path/C0103.MP4", "C0108": "/abs/path/C0108.MP4"},
  "ranges": [
    {"source": "C0103", "start": 2.42, "end": 6.85,
     "beat": "HOOK", "quote": "...", "reason": "Cleanest delivery, stops before slip at 38.46."},
    {"source": "C0108", "start": 14.30, "end": 28.90,
     "beat": "SOLUTION", "quote": "...", "reason": "Only take without the false start."}
  ],
  "grade": "warm_cinematic",
  "overlays": [
    {"file": "edit/animations/slot_1/render.mp4", "start_in_output": 0.0, "duration": 5.0}
  ],
  "subtitles": "edit/master.srt",
  "total_duration_s": 87.4
}
```

`grade` is a preset name or raw ffmpeg filter. `overlays` are rendered animation clips. `subtitles` is optional and applied LAST.

## Memory — `project.md`

Append one section per session at `<edit>/project.md`:

```markdown
## Session N — YYYY-MM-DD

**Strategy:** one paragraph describing the approach
**Decisions:** take choices, cuts, grades, animations + why
**Reasoning log:** one-line rationale for non-obvious decisions
**Outstanding:** deferred items
```

On startup, read `project.md` if it exists and summarize the last session in one sentence before asking whether to continue.

## Anti-patterns

Things that consistently fail regardless of style:

- **Hierarchical pre-computed codec formats** with USABILITY / tone tags / shot layers. Over-engineering. Derive from the transcript at decision time.
- **Hand-tuned moment-scoring functions.** The LLM picks better than any heuristic you'll write.
- **Whisper SRT / phrase-level output.** Loses sub-second gap data. Always word-level verbatim.
- **Running Whisper locally on CPU.** Slow and it normalizes fillers. Use hosted Scribe.
- **Burning subtitles into base before compositing overlays.** Overlays hide them. (Hard Rule 1.)
- **Single-pass filtergraph when you have overlays.** Double re-encodes. Use per-segment extract → concat.
- **Linear animation easing.** Looks robotic. Always cubic.
- **Hard audio cuts at segment boundaries.** Audible pops. (Hard Rule 3.)
- **Typing text centered on the partial string.** Text slides left as it grows.
- **Sequential sub-agents for multiple animations.** Always parallel.
- **Editing before confirming the strategy.** Never.
- **Re-transcribing cached sources.** Immutable outputs of immutable inputs.
- **Assuming what kind of video it is.** Look first, ask second, edit last.
- **Re-encoding video during the audio pass.** Audio cleanup, music, and SFX are audio-only — keep `-c:v copy`. (Hard Rule 13.)
- **Loudnorm before adding music.** Music changes integrated loudness; loudnorm runs LAST. (Hard Rule 13.)
