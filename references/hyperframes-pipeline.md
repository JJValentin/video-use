# Video Use + HyperFrames Pipeline

Use this lane when the edit needs a real creative system: creator-forward motion graphics, layered captions, screenshots/logos/proof flashes, product UI motion, handwritten notes, transparent overlays, or a fully composed social video.

Do not use this lane for a simple talking-head trim with burned captions. Plain `video-use` is enough for that.

## Source Docs

- Prompting: `https://hyperframes.mintlify.app/guides/prompting`
- Pipeline: `https://hyperframes.mintlify.app/guides/pipeline`
- Video editor cheatsheet: `https://hyperframes.mintlify.app/guides/video-editor-cheatsheet`

## Ownership

`video-use` owns:
- source inventory, ffprobe, transcription, packed transcript
- audio-first story selection
- EDL and base cut timing
- cut correctness: word boundaries, padding, audio fades, transcript cache
- final audio polish: speech cleanup + ducked music/SFX + loudnorm (Gate C, `clean_audio.py` then `audio_bed.py`)
- final session memory in `<videos_dir>/edit/project.md`

HyperFrames owns:
- visual identity and style system
- beat-by-beat storyboard
- composed overlays, captions, proof flashes, logos, screenshots, UI motion
- deterministic HTML/GSAP timeline rendering
- visual QA: lint, validate, inspect, snapshots, rendered review MP4

The bridge artifact is the selected cut:
- `edit/edl.json`
- `edit/base-cut.mp4`
- `edit/takes_packed.md`
- `edit/hyperframes/SCRIPT.md`
- `edit/hyperframes/STORYBOARD.md`

## Directory Layout

Keep everything inside the footage folder. Never write project outputs into the `video-use/` repo.

```text
<videos_dir>/
├── raw source files
└── edit/
    ├── project.md
    ├── takes_packed.md
    ├── edl.json
    ├── base-cut.mp4
    ├── transcripts/
    ├── verify/
    ├── final.mp4
    └── hyperframes/
        ├── DESIGN.md
        ├── SCRIPT.md
        ├── STORYBOARD.md
        ├── QA.md
        ├── assets/
        │   ├── base-cut.mp4
        │   ├── source stills/screenshots/logos
        │   └── fonts/
        ├── compositions/
        ├── snapshots/
        ├── renders/
        └── index.html
```

## Process

This pipeline maps onto the 3-gate process in `SKILL.md`:

- **Gate A — Story & Cut:** steps 1–3 (Inventory, Strategy Gate, Base Cut). The base cut must be the strongest audio/story version on its own; its approval (Checkpoint A2) gates everything below.
- **Gate B — Picture Lock:** steps 4–9 (the HyperFrames build and validation). The review render is Checkpoint B.
- **Gate C — Audio & Polish:** step 10 below (audio polish), run on the composed HyperFrames render before delivery.

Self-eval (see `SKILL.md`) runs inside every checkpoint.

### 1. Inventory And Transcript

Run the normal `video-use` front half:

```bash
python <video-use>/helpers/transcribe_batch.py <videos_dir>
python <video-use>/helpers/pack_transcripts.py --edit-dir <videos_dir>/edit
```

Use local transcription when footage is private or only exists locally:

```bash
TRANSCRIBE_PROVIDER=local-whisper
```

Use Castmagic only when the source has public URLs and diarization matters:

```bash
TRANSCRIBE_PROVIDER=castmagic
```

### 2. Strategy Gate

Before cutting, propose the edit in plain English and wait for confirmation.

The strategy must state:
- target platform, aspect ratio, and length
- story order and must-keep beats
- what gets cut and why
- where HyperFrames is needed
- visual system: typography, captions, overlays, proof assets, transitions
- whether the final deliverable is a full HyperFrames comp or a base cut with HyperFrames overlay slots

### 3. Base Cut

Create `edit/edl.json`, then render a clean base cut without final decorative captions:

```bash
python <video-use>/helpers/render.py <videos_dir>/edit/edl.json \
  -o <videos_dir>/edit/base-cut.mp4 --no-subtitles --no-loudnorm
```

The base cut should be the strongest audio/story version by itself. HyperFrames should enhance meaning, not rescue weak storyboarding. Use `--no-loudnorm` here — final loudness is set in Gate C (step 10) after the HyperFrames render, because the composed render is the audio that actually ships.

### 4. HyperFrames Project

Create the HyperFrames project inside `edit/hyperframes/`:

```bash
cd <videos_dir>/edit
npx --yes hyperframes init hyperframes --example blank --non-interactive
```

Copy or symlink:

```bash
mkdir -p hyperframes/assets
ln -sfn ../base-cut.mp4 hyperframes/assets/base-cut.mp4
```

If you need a full source clip, screenshots, logos, or proof images, place them in `hyperframes/assets/` with semantic filenames.

### 5. Design Artifact

Create `edit/hyperframes/DESIGN.md` before writing HTML.

Required sections:
- Overview
- Colors
- Typography
- Components / Graphic Language
- Imagery / Proof Assets
- Do / Don't

For Joshua creator videos, default direction unless he overrides it:
- human, creator-forward, premium but not overproduced
- handwritten/layered notes can appear behind or in front of the subject
- proof assets are fast receipts, not decorative logo spam
- captions are high-contrast, mobile readable, away from face and key visuals
- graphics support the message and never overpower the person

### 6. Script Artifact

Create `edit/hyperframes/SCRIPT.md` from the chosen EDL and transcript.

For talking-head footage, `SCRIPT.md` is not a rewrite. It is:
- exact selected spoken lines
- output timeline timing
- beat labels
- intended on-screen text or emphasis

### 7. Storyboard Artifact

Create `edit/hyperframes/STORYBOARD.md`.

Each beat needs:
- timing on the output timeline
- spoken line or transcript excerpt
- mood and camera feel
- assets by exact path
- foreground/background layer plan
- caption behavior
- motion techniques
- transition into/out of the beat
- QA risk for that beat

For creator talking-head videos, storyboard around meaning:
- thesis / hook
- proof
- tension
- emotional turn
- framework
- close

Avoid storyboard beats that only restate captions. Every graphic should add context, structure, emphasis, or proof.

### 8. Build Rules

Before editing HTML, read the local HyperFrames skills that match the job:
- `hyperframes`
- `hyperframes-cli`
- `hyperframes-media` if TTS, transcription, or background removal is needed
- `gsap`, `css-animations`, `lottie`, or `three` only if those techniques are used

HyperFrames correctness:
- timed layers use `class="clip"` with `data-start`, `data-duration`, and `data-track-index`
- video elements are muted; audio is separate when needed
- register paused GSAP timelines on `window.__timelines`
- no `Math.random()` without seeded determinism
- no async fetch during timeline setup
- layout first, animation second
- use `npx hyperframes inspect` for overflow and text fit

### 9. Validation

Run from `edit/hyperframes/`:

```bash
npx --yes hyperframes lint
npx --yes hyperframes validate
npx --yes hyperframes inspect --samples 15
npx --yes hyperframes snapshot --at <comma-separated beat times>
npx --yes hyperframes render --quality standard --output renders/review.mp4
```

For final:

```bash
npx --yes hyperframes render --quality high --fps 30 --output renders/final.mp4
```

Also run:

```bash
ffprobe -hide_banner renders/final.mp4
ffmpeg -i renders/final.mp4 -vf blackdetect=d=0.1:pic_th=0.98 -an -f null -
```

Create `QA.md` with:
- commands run
- duration, resolution, fps
- lint/validate/inspect result
- snapshot/contact-sheet review notes
- residual risks

### 10. Audio Polish (Gate C)

The HyperFrames render is the audio that ships. Polish it as audio-only passes — video stays `-c:v copy` (Hard Rule 13), and loudnorm always runs last:

```bash
python <video-use>/helpers/clean_audio.py renders/final.mp4 \
  -o renders/final.clean.mp4 --no-loudnorm
python <video-use>/helpers/audio_bed.py renders/final.clean.mp4 \
  -o renders/final.mixed.mp4 \
  [--music <track> --duck] [--sfx "<file>@<time>:<gain>" ...]
```

If there is no music or SFX, skip `audio_bed.py` and run `clean_audio.py` with `--loudnorm` instead so loudness is still normalized. The audio-polished render (`renders/final.mixed.mp4`, or the `clean_audio.py` output when there is no music) is what becomes the delivery file in the next step.

### 11. Delivery

Copy the Gate C audio-polished render (from step 10) to:

```text
<videos_dir>/edit/final.mp4
```

If the user wants a Telegram upload, upload the MP4 from `edit/final.mp4` or the named export copy, not a transient render work file.

Append to `edit/project.md`:
- source files
- transcript path
- EDL path
- HyperFrames project path
- final render path
- what changed creatively
- known limitations

## Prompt Shape

Use this shape when asking an agent or sub-agent to build the HyperFrames pass:

```text
Use /hyperframes and /hyperframes-cli.

Goal: Build the HyperFrames visual pass for a video-use base cut.

Inputs:
- Base cut: <absolute path>/edit/base-cut.mp4
- Packed transcript: <absolute path>/edit/takes_packed.md
- EDL: <absolute path>/edit/edl.json
- Design: <absolute path>/edit/hyperframes/DESIGN.md
- Script: <absolute path>/edit/hyperframes/SCRIPT.md
- Storyboard: <absolute path>/edit/hyperframes/STORYBOARD.md
- Assets: <absolute path>/edit/hyperframes/assets/

Rules:
- Keep the spoken meaning unchanged.
- Build graphics that add meaning, proof, structure, or emotion.
- Do not cover faces or important visuals.
- Use mobile-readable captions.
- Run lint, validate, inspect, snapshots, and render.
- Write QA.md.

Output:
- <absolute path>/edit/hyperframes/renders/review.mp4
- <absolute path>/edit/final.mp4 when approved
```

## Decision Rule

If the edit is mostly cut timing and captions, stay in `video-use`.

If the edit needs layered visual language, proof assets, kinetic typography, scene composition, or a creator-forward art direction, use this lane.
