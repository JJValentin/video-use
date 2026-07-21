"""Transcribe a video with the configured transcript provider.

Default provider: ElevenLabs Scribe.
Alternative providers:
  - Castmagic via TRANSCRIBE_PROVIDER=castmagic
  - Local Whisper via TRANSCRIBE_PROVIDER=local-whisper

Cached: if the output file already exists, the upload is skipped.

Usage:
    python helpers/transcribe.py <video_path>
    python helpers/transcribe.py <video_path> --edit-dir /custom/edit
    python helpers/transcribe.py <video_path> --language en
    python helpers/transcribe.py <video_path> --num-speakers 2
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests


SCRIBE_URL = "https://api.elevenlabs.io/v1/speech-to-text"
CASTMAGIC_URL = "https://app.castmagic.io/v1/transcripts"
ENV_FILES = [
    Path(__file__).resolve().parent.parent / ".env",
    Path(".env"),
    Path.home() / ".openclaw" / ".env",
    Path.home() / ".openclaw" / "gateway.systemd.env",
]


def _read_env_files() -> dict[str, str]:
    values: dict[str, str] = {}
    for candidate in ENV_FILES:
        if candidate.exists():
            for line in candidate.read_text(errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                values.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return values


def env_value(name: str) -> str:
    return os.environ.get(name, "") or _read_env_files().get(name, "")


def load_transcribe_config() -> dict[str, str]:
    provider = (env_value("TRANSCRIBE_PROVIDER") or "elevenlabs").lower()
    if provider in {"scribe", "elevenlabs_scribe"}:
        provider = "elevenlabs"
    if provider in {"local", "whisper", "faster-whisper", "local_whisper"}:
        provider = "local-whisper"

    key = ""
    if provider == "castmagic":
        key = env_value("CASTMAGIC_API_KEY")
        if not key:
            sys.exit("CASTMAGIC_API_KEY not found in .env or environment")
    elif provider == "elevenlabs":
        key = env_value("ELEVENLABS_API_KEY")
        if not key:
            sys.exit("ELEVENLABS_API_KEY not found in .env or environment")
    elif provider != "local-whisper":
        raise RuntimeError(f"unknown TRANSCRIBE_PROVIDER: {provider}")

    return {"provider": provider, "api_key": key}


def load_api_key() -> str:
    """Backward-compatible import for older helper callers."""
    return load_transcribe_config()["api_key"]


def load_provider() -> str:
    return load_transcribe_config()["provider"]


def require_local_video(video_path: Path) -> None:
    if not video_path.exists():
        sys.exit(f"video not found: {video_path}")


def looks_like_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def video_public_url(video: Path) -> str:
    """Resolve the public URL Castmagic needs for a source.

    Castmagic does not accept direct local file uploads. To keep video-use's
    transcript shape stable without inventing an upload step, support explicit
    sidecars:
      - <video>.url
      - edit/source_urls.json mapping filename/stem/path to URL
    """
    if looks_like_url(str(video)):
        return str(video)

    sidecar = video.with_suffix(video.suffix + ".url")
    if sidecar.exists():
        url = sidecar.read_text().strip()
        if looks_like_url(url):
            return url

    edit_urls = video.parent / "edit" / "source_urls.json"
    if edit_urls.exists():
        data = json.loads(edit_urls.read_text())
        for key in [video.name, video.stem, str(video)]:
            url = data.get(key)
            if isinstance(url, str) and looks_like_url(url):
                return url

    raise RuntimeError(
        "Castmagic requires a public media URL. Add a sidecar file named "
        f"{sidecar.name} containing the URL, or add edit/source_urls.json."
    )


def _seconds(value: object) -> float:
    if value is None:
        return 0.0
    try:
        n = float(value)
    except (TypeError, ValueError):
        return 0.0
    return n / 1000.0 if n > 1000 else n


def _word_text(word: dict) -> str:
    return str(
        word.get("text")
        or word.get("word")
        or word.get("punctuated_word")
        or ""
    ).strip()


def normalize_castmagic(payload: dict) -> dict:
    normalized: list[dict] = []
    previous_end: float | None = None

    for utterance in payload.get("utterances") or []:
        speaker = utterance.get("speaker") or utterance.get("speaker_id") or "1"
        speaker_id = f"Speaker {speaker}"
        raw_words = utterance.get("words") or []

        if not raw_words:
            parts = [p for p in str(utterance.get("text") or "").split() if p]
            start = _seconds(utterance.get("start"))
            end = _seconds(utterance.get("end"))
            duration = max(end - start, 0.01)
            step = duration / max(len(parts), 1)
            raw_words = [
                {"text": part, "start": start + i * step, "end": start + (i + 1) * step}
                for i, part in enumerate(parts)
            ]

        for raw in raw_words:
            text = _word_text(raw)
            if not text:
                continue
            start = _seconds(raw.get("start"))
            end = _seconds(raw.get("end"))
            if end < start:
                end = start
            if previous_end is not None and start > previous_end:
                normalized.append({
                    "type": "spacing",
                    "text": " ",
                    "start": previous_end,
                    "end": start,
                })
            normalized.append({
                "type": "word",
                "text": text,
                "start": start,
                "end": end,
                "speaker_id": speaker_id,
            })
            previous_end = end

    return {
        "provider": "castmagic",
        "source_id": payload.get("id"),
        "status": payload.get("status"),
        "words": normalized,
        "castmagic_raw": payload,
    }


def call_castmagic(
    video: Path,
    api_key: str,
    language: str | None = None,
    num_speakers: int | None = None,
) -> dict:
    del num_speakers  # Castmagic auto-diarizes; no supported fixed-speaker option.
    url = video_public_url(video)
    body: dict[str, object] = {"url": url}
    if language:
        body["language_code"] = language
    resp = requests.post(
        CASTMAGIC_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=body,
        timeout=60,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Castmagic submit returned {resp.status_code}: {resp.text[:500]}")

    submitted = resp.json()
    transcript_id = submitted.get("id")
    if not transcript_id:
        raise RuntimeError(f"Castmagic submit did not return an id: {submitted}")

    for attempt in range(90):
        time.sleep(15)
        poll = requests.get(
            f"{CASTMAGIC_URL}/{transcript_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60,
        )
        if poll.status_code >= 400:
            raise RuntimeError(f"Castmagic poll returned {poll.status_code}: {poll.text[:500]}")
        payload = poll.json()
        status = payload.get("status")
        if status == "completed":
            return normalize_castmagic(payload)
        if status in {"error", "failed"}:
            raise RuntimeError(f"Castmagic transcription failed: {json.dumps(payload)[:500]}")
        print(f"  Castmagic status [{attempt + 1}/90]: {status}", flush=True)

    raise RuntimeError(f"Castmagic transcription timed out. Resume with id: {transcript_id}")


def call_local_whisper(
    audio_path: Path,
    language: str | None = None,
    num_speakers: int | None = None,
) -> dict:
    del num_speakers  # Local Whisper does not diarize; use a single speaker label.
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper is not installed; run `uv sync` in video-use") from exc

    model_name = env_value("LOCAL_WHISPER_MODEL") or "small"
    compute_type = env_value("LOCAL_WHISPER_COMPUTE_TYPE") or "int8"
    model = WhisperModel(model_name, device="cpu", compute_type=compute_type)
    segments, info = model.transcribe(
        str(audio_path),
        language=language,
        word_timestamps=True,
        vad_filter=True,
    )

    words: list[dict] = []
    previous_end: float | None = None
    full_text: list[str] = []
    for segment in segments:
        full_text.append(segment.text.strip())
        for word in segment.words or []:
            text = (word.word or "").strip()
            if not text:
                continue
            start = float(word.start or 0.0)
            end = float(word.end or start)
            if previous_end is not None and start > previous_end:
                words.append({
                    "type": "spacing",
                    "text": " ",
                    "start": previous_end,
                    "end": start,
                })
            words.append({
                "type": "word",
                "text": text,
                "start": start,
                "end": end,
                "speaker_id": "Speaker 1",
            })
            previous_end = end

    return {
        "provider": "local-whisper",
        "model": model_name,
        "language": getattr(info, "language", language),
        "language_probability": getattr(info, "language_probability", None),
        "text": " ".join(part for part in full_text if part),
        "words": words,
    }


def load_api_key_old() -> str:
    v = env_value("ELEVENLABS_API_KEY")
    if not v:
        sys.exit("ELEVENLABS_API_KEY not found in .env or environment")
    return v


def extract_audio(video_path: Path, dest: Path) -> None:
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        str(dest),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def call_scribe(
    audio_path: Path,
    api_key: str,
    language: str | None = None,
    num_speakers: int | None = None,
) -> dict:
    data: dict[str, str] = {
        "model_id": "scribe_v1",
        "diarize": "true",
        "tag_audio_events": "true",
        "timestamps_granularity": "word",
    }
    if language:
        data["language_code"] = language
    if num_speakers:
        data["num_speakers"] = str(num_speakers)

    with open(audio_path, "rb") as f:
        resp = requests.post(
            SCRIBE_URL,
            headers={"xi-api-key": api_key},
            files={"file": (audio_path.name, f, "audio/wav")},
            data=data,
            timeout=1800,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"Scribe returned {resp.status_code}: {resp.text[:500]}")

    return resp.json()


def transcribe_one(
    video: Path,
    edit_dir: Path,
    api_key: str | None = None,
    language: str | None = None,
    num_speakers: int | None = None,
    verbose: bool = True,
    provider: str | None = None,
) -> Path:
    """Transcribe a single video. Returns path to transcript JSON.

    Cached: returns existing path immediately if the transcript already exists.
    """
    transcripts_dir = edit_dir / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    out_path = transcripts_dir / f"{video.stem}.json"

    if out_path.exists():
        if verbose:
            print(f"cached: {out_path.name}")
        return out_path

    config = load_transcribe_config()
    provider = provider or config["provider"]
    api_key = api_key or config["api_key"]

    t0 = time.time()
    if provider == "castmagic":
        if verbose:
            print(f"  submitting {video.name} to Castmagic", flush=True)
        payload = call_castmagic(video, api_key, language, num_speakers)
    elif provider == "local-whisper":
        if verbose:
            print(f"  extracting audio from {video.name}", flush=True)
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / f"{video.stem}.wav"
            extract_audio(video, audio)
            if verbose:
                print(f"  transcribing {video.stem}.wav locally with Whisper", flush=True)
            payload = call_local_whisper(audio, language, num_speakers)
    elif provider == "elevenlabs":
        if verbose:
            print(f"  extracting audio from {video.name}", flush=True)
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / f"{video.stem}.wav"
            extract_audio(video, audio)
            size_mb = audio.stat().st_size / (1024 * 1024)
            if verbose:
                print(f"  uploading {video.stem}.wav ({size_mb:.1f} MB)", flush=True)
            payload = call_scribe(audio, api_key, language, num_speakers)
    else:
        raise RuntimeError(f"unknown TRANSCRIBE_PROVIDER: {provider}")

    out_path.write_text(json.dumps(payload, indent=2))
    dt = time.time() - t0

    if verbose:
        kb = out_path.stat().st_size / 1024
        print(f"  saved: {out_path.name} ({kb:.1f} KB) in {dt:.1f}s")
        if isinstance(payload, dict) and "words" in payload:
            print(f"    words: {len(payload['words'])}")

    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Transcribe a video with ElevenLabs Scribe")
    ap.add_argument("video", type=Path, help="Path to video file")
    ap.add_argument(
        "--edit-dir",
        type=Path,
        default=None,
        help="Edit output directory (default: <video_parent>/edit)",
    )
    ap.add_argument(
        "--language",
        type=str,
        default=None,
        help="Optional ISO language code (e.g., 'en'). Omit to auto-detect.",
    )
    ap.add_argument(
        "--num-speakers",
        type=int,
        default=None,
        help="Optional number of speakers when known. Improves diarization accuracy.",
    )
    args = ap.parse_args()

    video = args.video.resolve()
    require_local_video(video)

    edit_dir = (args.edit_dir or (video.parent / "edit")).resolve()
    config = load_transcribe_config()

    transcribe_one(
        video=video,
        edit_dir=edit_dir,
        api_key=config["api_key"],
        provider=config["provider"],
        language=args.language,
        num_speakers=args.num_speakers,
    )


if __name__ == "__main__":
    main()
