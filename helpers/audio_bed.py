"""Add a music bed and/or SFX while copying the video stream.

Usage:
    python helpers/audio_bed.py <input> -o final.mp4 --music music.wav
    python helpers/audio_bed.py <input> -o final.mp4 --sfx "hit.wav@2.0:-3"
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


# Social-media standard: -14 LUFS integrated, -1 dBTP peak, LRA 11 LU.
# Matches YouTube / Instagram / TikTok / X / LinkedIn normalization targets.
LOUDNORM_I = -14.0
LOUDNORM_TP = -1.0
LOUDNORM_LRA = 11.0


@dataclass
class SfxSpec:
    path: Path
    time: float
    gain: float


def _fmt(value: float) -> str:
    return f"{value:g}"


def parse_sfx(value: str) -> SfxSpec:
    try:
        file_part, timing = value.rsplit("@", 1)
    except ValueError:
        raise argparse.ArgumentTypeError("expected FILE@TIME[:GAIN]") from None

    if ":" in timing:
        time_part, gain_part = timing.split(":", 1)
    else:
        time_part, gain_part = timing, "0"

    try:
        at_time = float(time_part)
        gain = float(gain_part)
    except ValueError:
        raise argparse.ArgumentTypeError("TIME and GAIN must be numbers") from None
    if at_time < 0:
        raise argparse.ArgumentTypeError("TIME must be >= 0")
    return SfxSpec(Path(file_part), at_time, gain)


def probe_duration(path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def build_input_args(input_path: Path, music_path: Path | None, sfx: list[SfxSpec]) -> list[str]:
    args = ["-i", str(input_path)]
    if music_path is not None:
        args += ["-stream_loop", "-1", "-i", str(music_path)]
    for spec in sfx:
        args += ["-i", str(spec.path)]
    return args


def build_mix_filter(
    duration: float,
    has_music: bool,
    sfx: list[SfxSpec],
    music_gain: float,
    duck: bool,
    duck_ratio: float,
    duck_threshold: float,
    final_filter: str,
) -> str:
    parts: list[str] = []
    fade_out_start = max(0.0, duration - 0.5)

    if has_music and duck:
        parts.append("[0:a:0]aresample=48000,asetpts=PTS-STARTPTS,asplit=2[speech_mix][speech_sc]")
    else:
        parts.append("[0:a:0]aresample=48000,asetpts=PTS-STARTPTS[speech_mix]")

    mix_inputs = ["[speech_mix]"]
    next_input = 1

    if has_music:
        music_index = next_input
        next_input += 1
        parts.append(
            f"[{music_index}:a:0]aresample=48000,atrim=0:{duration:.3f},"
            f"asetpts=PTS-STARTPTS,volume={_fmt(music_gain)}dB,"
            "afade=t=in:st=0:d=0.5,"
            f"afade=t=out:st={fade_out_start:.3f}:d=0.5[music_raw]"
        )
        if duck:
            parts.append(
                f"[music_raw][speech_sc]sidechaincompress=threshold={_fmt(duck_threshold)}:"
                f"ratio={_fmt(duck_ratio)}:attack=20:release=250[music_mix]"
            )
        else:
            parts.append("[music_raw]anull[music_mix]")
        mix_inputs.append("[music_mix]")

    for i, spec in enumerate(sfx):
        input_index = next_input
        next_input += 1
        delay_ms = int(round(spec.time * 1000))
        parts.append(
            f"[{input_index}:a:0]aresample=48000,asetpts=PTS-STARTPTS,"
            f"adelay={delay_ms}:all=1,volume={_fmt(spec.gain)}dB[sfx{i}]"
        )
        mix_inputs.append(f"[sfx{i}]")

    if len(mix_inputs) == 1:
        parts.append(f"{mix_inputs[0]}anull[mixed]")
    else:
        joined = "".join(mix_inputs)
        parts.append(
            f"{joined}amix=inputs={len(mix_inputs)}:duration=first:"
            "dropout_transition=0:normalize=0[mixed]"
        )

    parts.append(f"[mixed]{final_filter}[outa]")
    return ";".join(parts)


def measure_loudness(
    input_args: list[str],
    filter_complex: str,
) -> dict[str, str] | None:
    """Run ffmpeg loudnorm first pass and parse the JSON measurement.

    Returns a dict with measured_i, measured_tp, measured_lra, measured_thresh,
    target_offset, or None if measurement failed.
    """
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-nostats",
        *input_args,
        "-filter_complex", filter_complex,
        "-map", "[outa]",
        "-vn", "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    # loudnorm prints the JSON to stderr at the end of the run
    stderr = proc.stderr

    # Find the JSON block -- loudnorm output contains a `{ ... }` block
    start = stderr.rfind("{")
    end = stderr.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        data = json.loads(stderr[start : end + 1])
    except json.JSONDecodeError:
        return None
    needed = {"input_i", "input_tp", "input_lra", "input_thresh", "target_offset"}
    if not needed.issubset(data.keys()):
        return None
    return data


def run_audio_bed(
    input_path: Path,
    output_path: Path,
    input_args: list[str],
    filter_complex: str,
) -> None:
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-nostats",
        *input_args,
        "-filter_complex", filter_complex,
        "-map", "0:v?", "-map", "[outa]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        str(output_path),
    ]
    print(f"  filter chain: {filter_complex}")
    print(f"  audio bed -> {output_path.name}")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def apply_loudnorm_two_pass(
    input_path: Path,
    output_path: Path,
    input_args: list[str],
    duration: float,
    has_music: bool,
    sfx: list[SfxSpec],
    music_gain: float,
    duck: bool,
    duck_ratio: float,
    duck_threshold: float,
    preview: bool = False,
) -> bool:
    """Run two-pass loudnorm on the final mix, write normalized output.

    Returns True on success, False if measurement failed (caller should fall
    back to copying the input unchanged).

    In preview mode, skips the measurement pass and uses a one-pass approximation
    for speed. Final mode always does the proper two-pass.
    """
    if preview:
        # One-pass approximation -- faster, slightly less accurate.
        loudnorm = f"loudnorm=I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}"
        filter_complex = build_mix_filter(
            duration, has_music, sfx, music_gain, duck, duck_ratio, duck_threshold, loudnorm
        )
        run_audio_bed(input_path, output_path, input_args, filter_complex)
        return True

    # Full two-pass
    print(f"  loudnorm pass 1: measuring {input_path.name}")
    measure_filter = (
        f"loudnorm=I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}:print_format=json"
    )
    measure_complex = build_mix_filter(
        duration, has_music, sfx, music_gain, duck, duck_ratio, duck_threshold, measure_filter
    )
    measurement = measure_loudness(input_args, measure_complex)
    if measurement is None:
        print("  loudnorm measurement failed -- falling back to 1-pass")
        return apply_loudnorm_two_pass(
            input_path, output_path, input_args, duration, has_music, sfx,
            music_gain, duck, duck_ratio, duck_threshold, preview=True
        )

    print(f"    measured: I={measurement['input_i']} LUFS  "
          f"TP={measurement['input_tp']}  LRA={measurement['input_lra']}")

    loudnorm = (
        f"loudnorm=I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}"
        f":measured_I={measurement['input_i']}"
        f":measured_TP={measurement['input_tp']}"
        f":measured_LRA={measurement['input_lra']}"
        f":measured_thresh={measurement['input_thresh']}"
        f":offset={measurement['target_offset']}"
        f":linear=true"
    )
    filter_complex = build_mix_filter(
        duration, has_music, sfx, music_gain, duck, duck_ratio, duck_threshold, loudnorm
    )
    print(f"  loudnorm pass 2: normalizing -> {output_path.name}")
    run_audio_bed(input_path, output_path, input_args, filter_complex)
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="Add a ducked music bed and/or SFX")
    ap.add_argument("input", type=Path, help="Input cleaned video path")
    ap.add_argument("-o", "--output", type=Path, required=True, help="Output video path")
    ap.add_argument("--music", type=Path, help="Music bed file")
    ap.add_argument(
        "--music-gain",
        type=float,
        default=-18.0,
        metavar="DB",
        help="Music gain relative to speech in dB (default: -18)",
    )
    duck_group = ap.add_mutually_exclusive_group()
    duck_group.add_argument(
        "--duck",
        dest="duck",
        action="store_true",
        help="Duck music under speech (default when --music is present)",
    )
    duck_group.add_argument(
        "--no-duck",
        dest="duck",
        action="store_false",
        help="Do not duck music under speech",
    )
    ap.set_defaults(duck=None)
    ap.add_argument(
        "--duck-ratio",
        type=float,
        default=8.0,
        help="sidechaincompress ratio (default: 8)",
    )
    ap.add_argument(
        "--duck-threshold",
        type=float,
        default=0.05,
        help="sidechaincompress threshold (default: 0.05)",
    )
    ap.add_argument(
        "--sfx",
        type=parse_sfx,
        action="append",
        default=[],
        metavar="FILE@TIME[:GAIN]",
        help="SFX file delayed to output TIME seconds, optional gain in dB; repeatable",
    )
    loudnorm_group = ap.add_mutually_exclusive_group()
    loudnorm_group.add_argument(
        "--loudnorm",
        dest="loudnorm",
        action="store_true",
        help="Normalize final mix to -14 LUFS / -1 dBTP / LRA 11 (default)",
    )
    loudnorm_group.add_argument(
        "--no-loudnorm",
        dest="loudnorm",
        action="store_false",
        help="Skip loudness normalization",
    )
    ap.set_defaults(loudnorm=True)
    args = ap.parse_args()

    in_path = args.input.resolve()
    if not in_path.exists():
        sys.exit(f"input not found: {in_path}")

    music_path = args.music.resolve() if args.music is not None else None
    if music_path is not None and not music_path.exists():
        sys.exit(f"music not found: {music_path}")

    sfx = [
        SfxSpec(path=spec.path.resolve(), time=spec.time, gain=spec.gain)
        for spec in args.sfx
    ]
    for spec in sfx:
        if not spec.path.exists():
            sys.exit(f"sfx not found: {spec.path}")

    out_path = args.output.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    duration = probe_duration(in_path)
    has_music = music_path is not None
    duck = bool(has_music) if args.duck is None else args.duck
    input_args = build_input_args(in_path, music_path, sfx)

    print(f"building audio bed: {in_path.name}")
    print(f"  duration: {duration:.3f}s")
    print(f"  music: {music_path.name if music_path is not None else 'none'}")
    print(f"  sfx: {len(sfx)}")

    if args.loudnorm:
        print("loudness normalization -> social-ready (-14 LUFS / -1 dBTP / LRA 11)")
        apply_loudnorm_two_pass(
            in_path, out_path, input_args, duration, has_music, sfx,
            args.music_gain, duck, args.duck_ratio, args.duck_threshold
        )
    else:
        filter_complex = build_mix_filter(
            duration, has_music, sfx, args.music_gain, duck,
            args.duck_ratio, args.duck_threshold, "anull"
        )
        run_audio_bed(in_path, out_path, input_args, filter_complex)

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"\ndone: {out_path} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
