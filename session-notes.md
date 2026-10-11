# Session working files (consolidated)

Notes on the throwaway analysis scripts and measurement dumps produced during this
investigation (kept locally; the scripts ship in `session_scripts/`, the data dumps and the
emulator venv are not part of this repository).

## Layout

| path | what |
|---|---|
| `scripts/` | 112 throwaway analysis/probe scripts from the codec tasks (GainLaw `gl_*.py`, APath `measure*.py`/`probe1.py`/`run_port.py`/`snaps*`, UpperBands `e2e_*.py`/`apply_patch.py`/`gen_from_spec.py`, drift chase `apply_ring.py`/`e2e_ring.py`, plus the generated port copies `codec210_patched*.py`, `codec210_specpatch.py`, `codec210_ring.py`) |
| `data/` | 15 measurement dumps, oracles and lexicon extracts (a stray `/tmp/ubfetest` matched the file-name sweep but turned out to be another session's shader temp dir and was put back in `/tmp`) (`gl_meas.json`, `gl_dbg.json`, `snaps_apath.json`, `snaps2.json`, `real_apath.json`, `oracle_pcm_0_38.json`, `oracle_pcm_0_299.json`, reference PCM `ref*.raw`, plus the SQLite lexicon extracts `SpanishEs.dbl.db`, `SpanishAm.dbl.db`, `German.dbl5.db`) |

The *durable* versions of everything important are elsewhere in the tree and are the ones to use:

* codec: `tools/codec210.py` (exact decoder), `tools/codec210_oracle.py` (emulator oracle),
  `tools/verify_codec.py` (acceptance harness), `tools/oracle_*.py` (stage probes),
  `tools/codec210_tables.json` (extracted tables), `jorge_re/ref_pcm_f0_{119,299}.raw`
* formats: `tools/bin_dump.py`, `tools/sde_parse.py`, `tools/render_bin.py`, `tools/render_unit.py`
* specs: `specs/{GainLaw,APath,UpperBands,DriftFrames,Codec210,ELQBin,SDE,EngineBinding,SpanishLanguage}.md`
* decompilations: root `decomp_*.txt` (old build) and `jorge_re/decomp_*.txt` (jorge build)
* Ghidra projects used for those dumps: `ghidra_projects/` (also the earlier `ghidra_proj*` dirs)

## Toolchain (formerly in /tmp)

* `tools/venv/` — Python venv with `unicorn` + `pefile` (see `tools/requirements-oracle.txt`),
  used by every `tools/oracle_*.py` and `tools/codec210_oracle.py` script:
  `tools/venv/bin/python tools/codec210_oracle.py 0 300 0x6d ref.raw`
* Recreate if needed: `python3 -m venv tools/venv && tools/venv/bin/pip install unicorn pefile`
* Ghidra headless dumps were produced with
  `/opt/ghidra/support/analyzeHeadless <projdir> proj -import <dll> -scriptPath ghidra_scripts -postScript DumpAll.java <out>`
  (script in `ghidra_scripts/`; `ghidra_projects/` holds the run projects).

Nothing outside this directory is needed to reproduce or continue the work.
