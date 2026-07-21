"""Clean a speech track while copying the video stream.

Usage:
    python helpers/clean_audio.py <input> -o clean.mp4
    python helpers/clean_audio.py <input> -o clean.mp4 --deess
    python helpers/clean_audio.py <input> -o clean.mp4 --loudnorm
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


# Social-media standard: -14 LUFS integrated, -1 dBTP peak, LRA 11 LU.
# Matches YouTube / Instagram / TikTok / X / LinkedIn normalization targets.
LOUDNORM_I = -14.0
LOUDNORM_TP = -1.0
LOUDNORM_LRA = 11.0


def _fmt(value: float) -> str:
    return f"{value:g}"


def append_filter(filter_chain: str, next_filter: str) -> str:
    if not filter_chain:
        return next_filter
    return f"{filter_chain},{next_filter}"


def measure_loudness(input_path: Path, pre_filter: str = "") -> dict[str, str] | None:
    """Run ffmpeg loudnorm first pass and parse the JSON measurement.

    Returns a dict with measured_i, measured_tp, measured_lra, measured_thresh,
    target_offset, or None if measurement failed.
    """
    loudnorm = (
        f"loudnorm=I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}:print_format=json"
    )
    filter_str = append_filter(pre_filter, loudnorm)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-nostats",
        "-i", str(input_path),
        "-af", filter_str,
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


def apply_audio_filter(input_path: Path, output_path: Path, filter_str: str) -> None:
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-nostats",
        "-i", str(input_path),
        "-map", "0:v?", "-map", "0:a:0",
        "-c:v", "copy",
        "-af", filter_str,
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        str(output_path),
    ]
    print(f"  filter chain: {filter_str}")
    print(f"  clean audio -> {output_path.name}")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def apply_loudnorm_two_pass(
    input_path: Path,
    output_path: Path,
    pre_filter: str = "",
    preview: bool = False,
) -> bool:
    """Run two-pass loudnorm on input_path, write normalized copy to output_path.

    Returns True on success, False if measurement failed (caller should fall
    back to copying the input unchanged).

    In preview mode, skips the measurement pass and uses a one-pass approximation
    for speed. Final mode always does the proper two-pass.
    """
    if preview:
        # One-pass approximation -- faster, slightly less accurate.
        loudnorm = f"loudnorm=I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}"
        filter_str = append_filter(pre_filter, loudnorm)
        apply_audio_filter(input_path, output_path, filter_str)
        return True

    # Full two-pass
    print(f"  loudnorm pass 1: measuring {input_path.name}")
    measurement = measure_loudness(input_path, pre_filter)
    if measurement is None:
        print("  loudnorm measurement failed -- falling back to 1-pass")
        return apply_loudnorm_two_pass(input_path, output_path, pre_filter, preview=True)

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
    filter_str = append_filter(pre_filter, loudnorm)
    print(f"  loudnorm pass 2: normalizing -> {output_path.name}")
    apply_audio_filter(input_path, output_path, filter_str)
    return True


def build_filter_chain(args: argparse.Namespace) -> str:
    filters: list[str] = []
    if args.highpass > 0:
        filters.append(f"highpass=f={_fmt(args.highpass)}")
    if not args.no_denoise:
        filters.append(f"afftdn=nf={_fmt(args.denoise)}")
    if args.deess:
        filters.append("deesser=i=0.4:m=0.5:f=0.5")
    return ",".join(filters) or "anull"


def main() -> None:
    ap = argparse.ArgumentParser(description="Clean speech audio while copying video")
    ap.add_argument("input", type=Path, help="Input video or audio path")
    ap.add_argument("-o", "--output", type=Path, required=True, help="Output path")
    ap.add_argument(
        "--highpass",
        type=float,
        default=80.0,
        metavar="HZ",
        help="High-pass cutoff in Hz; pass 0 to disable (default: 80)",
    )
    ap.add_argument(
        "--denoise",
        type=float,
        default=-25.0,
        metavar="NF",
        help="afftdn noise floor in dB (default: -25)",
    )
    ap.add_argument(
        "--no-denoise",
        action="store_true",
        help="Disable afftdn denoise",
    )
    ap.add_argument(
        "--deess",
        action="store_true",
        help="Apply ffmpeg deesser with sane speech defaults",
    )
    loudnorm_group = ap.add_mutually_exclusive_group()
    loudnorm_group.add_argument(
        "--loudnorm",
        dest="loudnorm",
        action="store_true",
        help="Normalize cleaned audio to -14 LUFS / -1 dBTP / LRA 11",
    )
    loudnorm_group.add_argument(
        "--no-loudnorm",
        dest="loudnorm",
        action="store_false",
        help="Skip loudness normalization (default)",
    )
    ap.set_defaults(loudnorm=False)
    args = ap.parse_args()

    in_path = args.input.resolve()
    if not in_path.exists():
        sys.exit(f"input not found: {in_path}")
    out_path = args.output.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cleanup_chain = build_filter_chain(args)
    print(f"cleaning audio: {in_path.name}")
    if args.loudnorm:
        print("loudness normalization -> social-ready (-14 LUFS / -1 dBTP / LRA 11)")
        apply_loudnorm_two_pass(in_path, out_path, cleanup_chain)
    else:
        apply_audio_filter(in_path, out_path, cleanup_chain)

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"\ndone: {out_path} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
