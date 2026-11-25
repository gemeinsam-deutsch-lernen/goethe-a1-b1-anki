"""German speech for headwords and example sentences with Piper (https://github.com/OHF-Voice/piper1-gpl).

Audio is encoded as mono MP3 (plays everywhere, including AnkiMobile on iOS).
File names are content hashes, so synthesis is idempotent and cached in cache/audio/.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

MP3_KBPS = 32


def speakable(text: str) -> str:
    """Normalise list notation so the TTS reads natural German."""
    t = text
    t = re.sub(r"(\w)\(([a-zäöüß]+)\)(\w)", r"\1\2\3", t)  # Faschings(um)zug -> Faschingsumzug
    t = re.sub(r"\(([a-zäöüß]+)\)(\w)", r"\1\2", t)  # (he)runtergeladen -> heruntergeladen
    t = re.sub(r"(\w)\(-?\w+\)", r"\1", t)  # Ankunft(-szeit) -> Ankunft
    t = re.sub(r"\s*\((?:be|Ehe)-\)\s*", " ", t)  # mit Karte (be-) zahlen
    t = re.sub(r"(\w)/(\w)", r"\1 oder \2", t)  # Ihnen/dir -> Ihnen oder dir
    t = t.replace("…", ".").replace("z. B.", "zum Beispiel").replace("z.B.", "zum Beispiel")
    t = re.sub(r"[()]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def word_text(e: dict) -> str:
    if e["pos"] == "noun":
        return f'{e["article"]} {e["word"]}'
    if e["pos"] == "verb":
        return re.sub(r"[()]", "", e["infinitive"])
    w = re.sub(r"\s*\(.*?\)", "", e["word"]).strip()
    w = re.sub(r"(\w)-(?=$|[,/ ])", r"\1", w)  # "all-" -> "all"
    return w


def audio_name(text: str, voice: str) -> str:
    h = hashlib.sha1(f"{voice}\n{text}".encode()).hexdigest()[:16]
    return f"gwl_{h}.mp3"


def texts_for(e: dict) -> list[str]:
    return [speakable(word_text(e))] + [speakable(x) for x in e["examples"]]


def _encode_mp3(chunks) -> bytes:
    import lameenc
    import numpy as np

    pcm = []
    rate = None
    for ch in chunks:
        rate = ch.sample_rate
        pcm.append((np.clip(ch.audio_float_array, -1, 1) * 32767).astype("<i2").tobytes())
    enc = lameenc.Encoder()
    enc.set_bit_rate(MP3_KBPS)
    enc.set_in_sample_rate(rate)
    enc.set_channels(1)
    enc.set_quality(2)
    data = enc.encode(b"".join(pcm))
    data += enc.flush()
    return bytes(data)


def _voice_path(cache: Path, voice: str) -> Path:
    vdir = cache / "voices"
    model = vdir / f"{voice}.onnx"
    if not model.exists():
        vdir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [sys.executable, "-m", "piper.download_voices", "--download-dir", str(vdir), voice],
            check=True,
        )
    return model


def synthesize_all(entries_path: Path, cache: Path, voice: str, jobs: int = 1) -> None:
    from piper import PiperVoice

    entries = json.loads(entries_path.read_text(encoding="utf-8"))
    out_dir = cache / "audio"
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = {}
    for e in entries:
        for t in texts_for(e):
            name = audio_name(t, voice)
            if not (out_dir / name).exists():
                todo[name] = t
    print(f"{len(todo)} clips to synthesize with {voice}")
    if not todo:
        return
    pv = PiperVoice.load(_voice_path(cache, voice))
    for i, (name, text) in enumerate(sorted(todo.items()), 1):
        mp3 = _encode_mp3(pv.synthesize(text))
        tmp = out_dir / (name + ".part")
        tmp.write_bytes(mp3)
        tmp.rename(out_dir / name)
        if i % 250 == 0:
            print(f"  {i}/{len(todo)}")
    print("done")
