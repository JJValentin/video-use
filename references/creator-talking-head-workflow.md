# Creator Talking-Head / Yap Workflow

Use this for Joshua-style personal-brand videos, raw yaps, car talks, walk-and-talks, founder takes, podcast-style clips, and any footage where the person is the product.

The goal is not to make the densest possible clip. The goal is to turn raw speech into a scroll-stopping video centered on one thesis while protecting the speaker's voice.

## Operating Standard

This workflow has three jobs:

1. **Edit the content**: find the thesis, cut the fluff, shape the story, make hook variants, build captions and graphics that strengthen the point.
2. **Operate the system**: keep files, exports, notes, hooks, QA, and feedback organized enough that another editor could continue tomorrow.
3. **Protect the brand**: effects, graphics, memes, captions, and music must enhance the speaker, not overpower them.

If the edit is louder than the person, it failed.

## Where This Sits In The Gate Process

This workflow is the taste layer on top of the 3-gate process in `SKILL.md`:

- **Gate A — Story & Cut:** format classification, Thesis Mining, Cut Rhythm Rules, Story Shapes, and the Hook Workflow. The base cut must work with no graphics, and the tightened cut (Checkpoint A2) must be approved before any visual work begins.
- **Gate B — Picture Lock:** Graphics And Captions — overlays, proof flashes, caption styling. None of it may rescue a choppy story.
- **Gate C — Audio & Polish:** clean the speech, then add music/SFX with `clean_audio.py` followed by `audio_bed.py`. Music and SFX must never sit louder than the person (see Operating Standard); loudnorm runs last.

Self-eval (see `SKILL.md`) runs inside every checkpoint — A1, A2, B, and C — not only before delivery.

## Default Format Types

Classify the source before cutting:

- **Sharp take**: one clear opinion or thesis. Bias toward authority, pace, and proof.
- **Personal / emotional**: keep more breath, reduce graphics, let human moments land.
- **Teaching / framework**: keep structure clear; graphics should organize steps, not decorate.
- **BTS / day-in-life**: find the story from moments, not just transcript. Voiceover may carry structure.
- **Sponsored / constrained**: preserve approved claims and required beats; quality bar stays high.
- **Proactive clip**: small human/funny/charming moment noticed while editing. Cut and present separately when it has standalone value.

## Thesis Mining

Before proposing an edit, produce a short thesis scan in `edit/project.md` or the strategy doc:

- central thesis in one sentence
- strongest verbal hook
- strongest text-on-screen hook
- proof moments / authority moments
- emotional human moments
- framework/list moments
- likely fluff or dead zones
- possible proactive clips

For raw talking-head footage with no brief, do not ask the user to find the story. The editor finds it and presents the strongest option.

## Cut Rhythm Rules

These are taste rules for talking-head/yap edits. They sit on top of the hard technical rules in `SKILL.md`.

1. **Base cut must work with no graphics.** HyperFrames, captions, memes, and proof flashes enhance meaning; they do not rescue a choppy story.
2. **Cut ideas, not just words.** A cut should move to a new thought, proof, turn, or payoff.
3. **Minimum cut unit is a complete spoken beat.** Avoid stitching transcript fragments that read well but sound unnatural.
4. **Preserve conversational breath.** Keep micro-pauses when they make the speaker feel human, confident, funny, or emotionally present.
5. **Use silence as structure.** Prefer natural phrase endings and silences; do not over-compress emotional or reflective lines.
6. **Prefer J-cuts/L-cuts when jumping across source time.** Let audio or visual continuity carry the viewer through big source jumps.
7. **No naked awkward jumps.** If a discontinuity is necessary, cover it with a meaning-led visual: receipt flash, push-in, handwritten note, b-roll, or intentional transition.
8. **Limit major thought jumps.** As a default, avoid more than one major thought jump every 4-6 seconds unless the style is deliberately rapid-fire.
9. **Hold after punchlines and human beats.** Reactions, smiles, eye movement, laughs, and small pauses can be the beat.
10. **Cut density follows emotional mode.** Sharp takes can be tighter. Personal/emotional clips need more air.

## Story Shapes

Pick the shape that matches the source. Do not force all clips into one formula.

- **Thesis -> proof -> implication -> close**
- **Contrarian hook -> why it matters -> example -> rule**
- **Problem -> personal observation -> framework -> invitation**
- **Moment -> meaning -> lesson**
- **Behind-the-scenes setup -> tension -> human payoff**
- **Sponsor premise -> approved proof -> natural integration -> CTA**

For Joshua's creator/business yaps, default shape:

```text
thesis -> authority/proof -> human truth -> usable framework -> grounded close
```

## Hook Workflow

For most talking-head shorts, create 2-3 hook options before finalizing:

- **Version A: Curiosity**: creates an open loop.
- **Version B: Contrarian**: challenges a common belief.
- **Version C: Personal / human**: starts from lived experience or vulnerability.

Hook variants can change:

- first spoken line
- first visual
- text-on-screen hook
- opening proof flash
- first 3 seconds of pacing
- emotional angle

Do not make full alternate renders every time by default. First produce hook candidates in the strategy or storyboard. Render variants when the user asks, when distribution testing matters, or when the hook materially changes the edit.

## Graphics And Captions

Graphics must earn their spot by doing one of four jobs:

- clarify structure
- add proof/context
- emphasize a key phrase
- create a tasteful transition across a cut

Avoid graphics that only repeat the caption. Avoid stickers, logos, memes, or b-roll that are merely decorative.

Caption defaults for Joshua talking-head clips:

- sentence-style, not all-caps walls
- high contrast and mobile-readable
- timed tightly to speech
- away from face and important visuals
- bold/color emphasis only for the key words
- lighter design for emotional/personal lines

## A/B And Distribution Notes

When a clip is meant for social testing, document:

- version label
- tested hook angle
- target platform
- expected audience reaction
- what changed from the control

Suggested labels:

- `A_curiosity`
- `B_contrarian`
- `C_personal`
- `D_proof_first`

## System Organization

Every talking-head edit should leave a trail:

```text
edit/
├── project.md              # working memory, thesis scan, decisions, feedback
├── strategy-vN.md          # proposed story and rules before execution
├── edl.json
├── base-cut.mp4
├── master.srt
├── verify/                 # cut sheets, contact sheets, black-frame checks
├── exports/                # review/final/social variants
└── hyperframes/            # if visual pass is used
```

`project.md` should record:

- source files
- selected thesis
- hook options
- approved story shape
- cut rules used
- feedback received
- exports delivered
- brand/taste lessons to reuse

## QA Checklist

At each checkpoint (A1/A2 for the cut, B for visuals, C for audio) and again before delivery:

- Watch the base cut without graphics.
- Generate a cut-boundary sheet around each jump.
- Check that every major source jump has either natural rhythm or visual cover.
- Check captions do not cover face or important visuals.
- Check graphics support the thesis.
- Confirm the speech is cleaned and any music/SFX sits under the voice (Gate C).
- Run technical QA from `SKILL.md`.
- Note residual risk plainly.

## Living Brand Database

When feedback reveals a durable preference, update the relevant local reference or project memory. Examples:

- pacing preference
- caption style
- graphic style
- words/phrases to avoid
- hook patterns that feel like Joshua
- hook patterns that feel too marketing-heavy
- examples of approved edits

For Joshua, current standing taste rules:

- human over marketing
- premium but not overproduced
- creator-forward, not corporate
- graphics support the message and never overpower him
- personal/emotional moments breathe
- the edit should feel confident, not chaotic
