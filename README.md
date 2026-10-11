# Loquendo TTS 7 / LTTS Director 7 — reverse engineering

Reverse-engineering notes **and working code** for the Loquendo TTS 7 voice engine and its
"TTS Director 7" front-end: the vocal-database and unit-inventory formats, the engine ↔ voice
binding, and a **binary-free decoder for the `LTTS7Codec210` speech codec** that reproduces the
shipped voice to within the DLL's own floating-point rounding.

## Highlights

* **`.bin` vocal database container** — two plain key bytes (`key = file[0]^file[1]`), XOR-obfuscated
  `LOQUENDOTTS7` header, TLV fields (Name/Label/Comment/Freq/Coding/BitRate/Rank/Version), a 28-byte
  big-endian sub-header (`BitRate, Rank, samples/frame, Freq, bytes/frame, nframes, cookie`) and
  110-byte coded frames (640 samples = 20 ms @ 32 kHz, 44 kbit/s) each XORed with the sub-header's
  last byte.
* **`.sde` unit inventory** — bit-7-masked text, two generations (base-93 `L<n>`/`R<n>` records and the
  legacy decimal `D=` records), a 10 µs position time base, non-frame-aligned atom times.
* **Engine ↔ voice binding** — descriptor family (`.vcf/.vde/.gde/.lde/.lcf/.ycf`), database discovery
  by `*.bin` glob + TLV `Label` match, variant selection, `.sde` registration, the per-unit driver and
  the decoder ABI `(handle, startSample, count, int16* out, ELQBin handle)`, pitch/duration via TD-PSOLA.
* **Codec 210 ported in pure Python** (`tools/codec210.py`) with **no fitted constants**: the 880-bit
  frame layout, LSF VQ/interp/stabilise/LSF→LPC, the 8 kHz LTP (lag-periodic ring taps), the innovation
  gains (`float32(Q[b3]·float32(exp(g8/3.5)))`, second pass ×5/11), the 16 kHz coded and 32 kHz noise
  bands, both QMF level combines and the float→int16 stage.

Measured against the real, unmodified DLL (Unicorn-emulated ground truth):

| metric | value |
|---|---|
| global correlation, 300 frames (19.2 s of speech) | **0.99965** |
| amplitude (rms) ratio | **1.001** |
| speech 10-frame windows | min 0.9991, median **1.00000**, 19 of 26 exactly 1.00000 |
| adaptive-codebook gate (S gate) | **1.0000** (4/4 sub-frames) |
| per-band buffers (16 kHz / 32 kHz) | **1.000000** each |

The remaining difference is float32 rounding in near-cancelling sums plus the int16 clamp floor — i.e. the
codec is reproduced as exactly as the DLL's own arithmetic allows. See `REPORT.md` §16.4–16.5.

## Layout

| path | contents |
|---|---|
| `REPORT.md` | the full report: application, installer, engine API, file formats, the acoustic core, the engine↔voice binding, and the codec closure with all measurements |
| `specs/` | per-layer deep dives with code addresses and evidence — `ELQBin.md` (container), `SDE.md` (inventory), `EngineBinding.md`, `Codec210.md`, `GainLaw.md`, `APath.md`, `UpperBands.md`, `DriftFrames.md`, `SpanishLanguage.md` |
| `tools/` | `codec210.py` (decoder), `codec210_oracle.py` (emulation oracle), `verify_codec.py` (acceptance harness), `codec210_extract.py` + `codec210_tables.json` (numeric tables), `bin_dump.py`, `sde_parse.py`, `render_bin.py`, `render_unit.py` |
| `probes/` | stage-local emulator probes used to close each stage (S gate, window provenance, write attribution, codebook probe) |
| `session_scripts/` | the throwaway analysis scripts from the investigation (provenance: `session-notes.md`) |
| `ghidra_scripts/` | the Ghidra headless dump script |

## Quickstart

You need **your own licensed copy** of a Loquendo TTS 7 voice package — this repository contains no
binaries or data. Voice installers are Inno Setup bundles; unpacking one yields e.g.
`…/Loquendo/LTTS7/{bin,data/voices/<Voice>}`. Point the tools at that tree:

```bash
export LTTS7_VOICE=/path/to/unpacked/pf/Loquendo/LTTS7     # or set LTTS7_BIN / LTTS7_DLL explicitly
python3 tools/bin_dump.py   "$LTTS7_VOICE/data/voices/Jorge/Jorge.32000.LTTS7Codec210.44000.10.bin"
python3 tools/sde_parse.py  "$LTTS7_VOICE/data/voices/Jorge/Jorge.sde"
python3 tools/render_unit.py "$LTTS7_VOICE/data/voices/Jorge/Jorge.32000.LTTS7Codec210.44000.10.bin" \
                            "$LTTS7_VOICE/data/voices/Jorge/Jorge.sde" 1 unit.wav
```

Ground-truth comparison (needs `unicorn` + `pefile`):

```bash
python3 -m venv tools/venv && tools/venv/bin/pip install -r tools/requirements-oracle.txt
tools/venv/bin/python tools/codec210_oracle.py 0 300 0x6d ref.raw   # reference PCM from the real DLL
python3 tools/verify_codec.py ref.raw 300                           # correlation / rms table
```

## Method

Ghidra headless decompilation plus a **Unicorn-based oracle** that runs the unmodified codec DLL to
produce ground-truth buffers and PCM. Every stage was closed with a stage-local gate (correlation
≥ 0.999 against the emulator) before moving on, and each acoustic constant is recorded with the DLL
address it was read from. Two instrumentation traps that cost real time are documented in `REPORT.md`
§16.1 (the EIP reported inside a memory-write hook is unreliable; memory-read hooks barely fire in this
Unicorn build — use a global code hook tracking the last executed address, and hook call opcodes to
snapshot arguments).

## Legal

No binaries, audio, decompiled sources or other copyrighted material from the original distribution are
included, and nothing here is needed to run the original software. The numeric constants in
`tools/codec210_tables.json` are interoperability data extracted from a legally installed copy and can be
regenerated at any time with `tools/codec210_extract.py`. "Loquendo" and "TTS Director" are trademarks of
their respective owners; this project is unaffiliated and is published for interoperability and research.
