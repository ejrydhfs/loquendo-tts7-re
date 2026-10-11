# Loquendo TTS 7 "TTS Director" — reverse-engineering package

Target: `/home/asdf/Downloads/LTTSDirector7.rar`
(md5 `9c551a2da0a71189d7168948c9d339d3`, 52,178,626 bytes)

**Verdict (final pass) — can another agent replicate the app and the synthesis engine?**

* **Application and installer: YES** — the archive ships the *complete, decompilable application*
  (Java sources recoverable with CFR), its full public API (`loqtts.h`, doxygen for the Java API),
  the voice/language descriptor formats, SDK samples and the whole 91 MB payload (1 115 files),
  extractable with the reproducible procedure in §2.
* **Voice data formats: SOLVED** (third pass, on a real voice package
  `Jorge - Spanish.exe`, Inno Setup 5.2.3, unpacked with `tools/innoextract-1.9/build/innoextract`):
  the vocal-database container (`LOQUENDOTTS7` header, two key bytes, TLV fields, 28-byte sub-header,
  110-byte frames = 640 samples = 20 ms, per-frame XOR key) in §13.1/§13.6 and `specs/ELQBin.md`;
  the unit inventory `.sde` (both generations - base-93 `L<n>`/`R<n>` and legacy decimal `D=`) in §13.5
  and `specs/SDE.md`; the 10 µs position unit in §13.4; the Spanish language layer (phoneme inventory,
  SQLite lexicon, say-as styles, phoneme table in the voice DLL) in `specs/SpanishLanguage.md`.
* **Engine ↔ voice binding: SOLVED** (§14 and `specs/EngineBinding.md`): descriptor family
  (`rcf/vcf/lcf/ycf`), database discovery by `*.bin` glob + TLV `Label` match, variant selection by
  `Freq/Coding/BitRate/Rank` vs `.vcf` keys, `.sde` registration as a shared resource, the per-unit
  driver, the decoder ABI `(handle, startSample, count, int16* out, bin)`, pitch/duration via TD-PSOLA,
  and the voice module's 8-entry dispatch table.
* **Codec 210: structurally solved, one excitation path short** (§15 and `specs/Codec210.md`):
  the 880-bit frame layout, LSF VQ, LSF->LPC, the codebooks, the polyphase band filter
  (correlation 1.000000 against the real DLL) and the final combine `out = clamp(round(2*(A-B)))` are
  exact and validated; what remains is the excitation chain (8 kHz pitch/LTP + codebooks, 16 kHz coded
  branch, 32 kHz noise branch, exact gain dequantiser), listed in order in `specs/Codec210.md` S10.3,
  with `tools/codec210_oracle.py` (Unicorn emulation of the unmodified DLL) supplying ground-truth PCM
  so every remaining stage can be validated on its own.
* **Working binary-free toolchain**: `tools/bin_dump.py`, `tools/sde_parse.py`, `tools/render_bin.py`,
  `tools/render_unit.py`, `tools/codec210.py`/`codec210_extract.py`/`codec210_oracle.py` with
  `codec210_tables.json`. Runnable end-to-end paths: §13.7 (linear voice, exact) and §15.1
  (Jorge voice, envelope-correct; waveform exactness needs the excitation stages above).
* Everything else — GUI, RMI service, prosody/lexicon/audio *control*, file formats, installer,
  licensing — is specified in §1–§9 and §12.

Single-file handoff bundle: `local://ltts7-re-bundle.md` (this report + all `specs/*.md`, ~280 KB).

Deliverables produced by this analysis (in `/home/asdf/Downloads/ltts_re/`):
`cab_folder.bin` (91,462,710 B, the uncompressed payload stream),
`payload/` (1 115 extracted files + `_manifest`/`payload_manifest.json`),
`src/` (decompiled Java), `decomp_director.txt` (Ghidra decompilation of the
Wise loader), `extract_payload.py`, `wise_unpack.py`.
Third-pass additions (voice package + engine internals):
`jorge/` (the unpacked voice package), `engine_re/` (engine + SDK data extracts),
`specs/` (`ELQBin.md`, `SDE.md`, `EngineBinding.md`, `Codec210.md`, `SpanishLanguage.md`, `CONTEXT.md`),
`jorge_re/` and the root `decomp_*.txt` Ghidra dumps (engine, Util, voice module, both codecs),
`tools/` (`bin_dump.py`, `sde_parse.py`, `render_bin.py`, `render_unit.py`, `codec210.py`,
`codec210_extract.py`, `codec210_oracle.py`, `codec210_tables.json`, `7zz`, `innoextract-1.9/`).

---

## 1. What the RAR contains

| Path in archive | Size | Type | Role |
|---|---|---|---|
| `1.-LTTS7 Engine Full Distribution/LTTS7 Engine Full Distribution.exe` | 15,553,024 | Wise self-extractor (MSI-style) | TTS **engine** + SAPI5 runtime prerequisite |
| `1.-…/spchapi.exe` | 770,784 | MS CAB self-extractor | Windows Speech API 5.1 redistributable |
| `2.-LOQUENDO TTS DIRECTOR 7/LOQUENDO TTS DIRECTOR 7.exe` | 35,443,712 | Wise self-extractor | **The app**: TTS Director 7.7.1 + JRE 6 + SDK + Spanish voice |
| `3.-LTTS7 Spanish Distribution/LTTS7 Spanish Distribution.exe` | 2,269,184 | Wise self-extractor | Spanish voice package (Ludoviko family) |
| `4.-Parche (crack) para las voses/Patch.exe` | 411,648 | Delphi GUI app | Voice **keygen/crack** (§8) |
| `idiomas de las voces/English Distribution LTTS7.rar` | 2,107,229 | RAR | English voice installer (`…English Distribution LTTS7.exe`, 3,321,344 B) + `m3troid300.url` |
| `…/French Distribution LTTS7.rar` | 778,477 | RAR | French voice (`…French Distribution LTTS7.exe`, 1,987,584 B) |
| `…/Rusian Distribution LTTS7.rar` | 968,612 | RAR | Russian voice (2,190,848 B) |
| `…/PORTUGUESE DISTRIBUTION LTTS7.rar` | 614,463 | RAR | Portuguese voice (1,823,744 B) |
| `…/Loquendo TTS 7 Galician Distribution7.7.0.zip` | 773,113 | ZIP | `Galician Distribution 7.7.0.exe` (1,957,376 B) |
| `…/Loquendo TTS 7 German Distribution 7.7.1.zip` | 1,555,253 | ZIP | `Loquendo_TTS_7-Win32_German_Distribution_7.7.1.exe` (2,408,448 B) + EULA/manual/Readme |

The voice distributions are all the same kind of Wise self-extractor; they can be
unpacked with `wise_unpack.py` (see §2.6). The `.url` files credit the repack
author (`http://youtube.com/m3troid300`); they are not part of the product.

Identified installer metadata (from the PE version resource):
`CompanyName=Loquendo`, `FileDescription=Loquendo TTS 7 SDK Distribution`,
`FileVersion/ProductVersion=7.4.0.0` (loader), product version installed `7.4.0`,
app version string `7.7.1`.

---

## 2. The installer format (Wise Installation System, "WISE30139")

### 2.1 PE layout, loader and imports

`LOQUENDO TTS DIRECTOR 7.exe` (md5 `f575b9198a334b3d74c8d624fc03ac79`) is a
32-bit PE with four sections plus resources:

| Section | RVA | VirtualSize | Raw offset | RawSize |
|---|---|---|---|---|
| `.text` | 0x1000 | 0x5F42 | 0x400 | 0x6000 |
| `.rdata` | 0x7000 | 0x1AAA | 0x6400 | 0x1C00 |
| `.data` | 0x9000 | 0x10850 | 0x8000 | 0x600 |
| `.WISE` | 0x1A000 | 0x21BF618 | 0x8600 | 0x21BF800 |
| `.rsrc` | 0x21DA000 | 0x5518 | 0x21C7E00 | 0x5600 |

Image base 0x400000. Imports (verified): `WSOCK32.dll` **by ordinal** —
`3=closesocket, 4=connect, 9=htons, 10=inet_addr, 16=recv, 19=send, 21=setsockopt,
22=shutdown, 23=socket, 52=gethostbyname, 101/111=WSAAsyncGetHostByName/
WSACancelAsyncRequest, 115=WSAStartup, 116=WSACleanup` — i.e. a built-in HTTP/FTP
downloader; plus `VERSION.dll`, `KERNEL32.dll` (incl. `_lread/_lwrite/_llseek/
_lcreat/_lclose`, registry, `GetTempPathA/GetTempFileNameA`, process/token APIs),
`USER32`, `GDI32`, `ADVAPI32`, `SHELL32` (`ShellExecuteExA`).

The loader is a stock Wise stub: it locates the `.WISE` section via the PE section
table, seeks to its `PointerToRawData`, then interprets the section (Ghidra
decompilation: `decomp_director.txt`, functions `FUN_00402f41` = find `.WISE`,
`entry` = main installer, `FUN_00403975` = XOR/PRNG file decryptor,
`FUN_0040408e` = file extractor with CRC32, `FUN_00402f17` = PRNG,
`FUN_00404197` = script/UI driver, plus `_PasswordDlg`, `_ProgressDlg`,
`_LanguageDlg` dialog procedures).

* CRC32: standard reflected polynomial `0xEDB88320`, table built by
  `FUN_004028c7`, updated by `_UpdateCRC`.
* Optional file encryption: each file's bytes are XORed with a 31-bit LCG
  keystream (`x := (x mod 0xADC8)*0xBC8F − (x div 0xADC8)*0xD47`, `+= 0x7FFFFFFF`
  when negative; dword-wise then `(seed mod 0xFF)+1` per tail byte), seeded
  `0x5BC25A` and only used when the package has a password
  (`1 < passwordLen`). **The Loquendo packages have an empty password**
  (`passwordLen = 1`), so stored data is *not* XORed.

### 2.2 `.WISE` section layout (verified for all three Wise installers)

```
0x000  76-byte header, 19×u32.  Only field [0x18] (i.e. offset 0x18) is non-zero:
       it equals the end offset of the embedded payload container
       (Director: 0x21BF204; Engine: 0xEC7004; Spanish: 0x21BE04).
0x04C  1 byte flag
0x04D  5 length bytes, then 5 NUL-terminated strings of those lengths:
         [0] staging INI name  "WIS30139AC2AB194AEA865F2154240D851F_7_4_0.TMP"
         [1] ProductCode GUID  "{30139AC2-AB19-4AEA-865F-2154240D851F}"
         [2] ProductVersion    "7.4.0"
         [3] transform name    (empty)
         [4] remove-previous   "1"
0x0B0  21 length bytes -> font/title strings, then
         87-byte font+window-title block ("MS Sans Serif" …),
         1 byte password (empty), and the message string block
         (length-prefixed installer messages, e.g. "You must have
         administrator rights…", "…is already installed…", "CRCError",
         "SpaceError", "Internet", "Reboot", "MinVerMessage",
         "/Lv c:\LTTS_7-SDK.log /I", "English,1033" …).
        Followed by installer script/messages and Wise "property"/dialog tables
        (ASCII and UTF-16, e.g. the EULA text, `[_WiseDialogFontDefault]`,
        `SOFTWARE\Loquendo\LTTS7\Engine`, regsvr32 custom actions …).
```

### 2.3 The embedded payload container (MS CAB "MSCF") — **the key find**

Inside the `.WISE` section there is a genuine **MSZIP cabinet**:

* Director: `MSCF` at section offset **0x4B014**, `cbCabinet = 0x1FEFEC2`
  (33 480 386 B), `cFolders = 1`, `cFiles = 1115`, `coffFiles = 0x1030`,
  `flags = 4` (reserve present), `cbCFHeader = 0x1000`.
* Folder 0: `coffCabStart = 0xB27B`, `cCFData = 2792`, `typeCompress = 1` (MSZIP).
* The **file index** lives at `cab + coffFiles` and ends at
  `cab + coffCabStart`.  Each record is **16 bytes followed by the NUL-terminated
  name** (note: fields *precede* the name):

  ```
  struct WiseFileRec {      // 16 bytes, little endian
      uint32 size;          //   0x00  uncompressed size
      uint32 offset;        //   0x04  offset inside the *uncompressed* folder stream
      uint16 f1;            //   0x08  flags (always 0 in these packages)
      uint16 f2;            //   0x0A  DOS date/timestamp-ish (0x38CA..0x3902)
      uint32 hash;          //   0x0C  opaque (checksum/pointer; not needed)
  };  // followed by char name[] ; NUL terminated
  ```

  Verified invariant: the records **tile the folder stream gaplessly**
  (`off[i+1] == off[i] + size[i]`, first offset 0, last end == 0x5739C36 ==
  folder length; Σ sizes = 91 462 710).  `f1/f2/hash` are not required for
  extraction.

* **CFDATA blocks** (from `cab + coffCabStart`): `uint32 csum; uint16 cbData;
  uint16 cbUncomp; byte data[cbData];` — for MSZIP each `data` starts with the
  two ASCII bytes `CK` followed by a raw DEFLATE stream that continues the
  previous block's 32 KiB history (equivalent to zlib `inflateInit2(-15)` with
  `zdict = last 32768 bytes of output`).  Concatenating the 2792 blocks yields
  the folder stream byte-for-byte (`cab_folder.bin`,
  md5 `6031c37e91c05e2fed553f125caea94f`).  It starts with
  `%PDF-1.3\n%\xe2\xe3\xcf\xd3\r\n` (Loquendo TTS 7 Installation Manual) and
  contains MZ/PE, ZIP/JAR, PNG/GIF/JPEG, TTF, HTML, text and the whole JRE.

### 2.4 Loader behaviour observed (for a faithful re-implementation of the installer)

* Administrator check, Wise staging INI (`%TEMP%\WIS30139….TMP`), progress dialog,
  splash AVI (`FindResource` + `MCIWndCreateA`), optional password dialog,
  language dialog, EULA, "remove previous version" via MSI API
  (`MsiGetProductInfoA`/`MsiConfigureProductA`), .NET/MSI/WinInit version gates,
  reboot handling (registry `…\Run`/`RunOnce` value `WiseStubReboot`,
  `ExitWindowsEx`), `msiexec` invocation with `TRANSFORMS=`, and the regsvr32
  custom actions for the SAPI engine (`\bin\LTTS7SAPI5.dll`).
* Registry written (seen in script strings): `HKLM\SOFTWARE\Loquendo\LTTS7\Engine`,
  `…\LTTS7\default.session`, `…\LTTS7\LicenseCode`, plus ARP entries.

### 2.5 Reproduction recipe

```bash
./tools/7zz e -o/tmp/ws "<installer>.exe" .WISE -y       # .WISE section
python3 extract_payload.py                               # Director (fixed offsets)
python3 wise_unpack.py "<installer>.exe" <outdir>        # generic (engine/voices)
```

`wise_unpack.py` auto-locates the sane `MSCF`, reads `cFolders/cFiles/coffFiles`,
decompresses folder 0 and splits it by the index. Confirmed output for the
Director installer: **1 115 files, 91 462 710 bytes, gapless tiling**.

### 2.6 Per-installer specifics

| Installer | `.WISE` size | MSCF offset | cFiles | Notes |
|---|---|---|---|---|
| Director 7 | 0x21BF800 | 0x4B014 | 1115 | full SDK + JRE + Spanish voice |
| Engine Full Distribution | 0xEC7600 | 0x94E823 | 9 | cabinet holds the SAPI5 prerequisite (`sapi.dll`, `sapi.cpl`, `sapisvr.exe`, `speech.chm`, `sapicpl.hlp`); the engine payload is MSI-style (embedded OLE database) |
| Spanish Distribution | 0x21C400 | 0x660F | – | Spanish voice package |
| Voice packs (EN/FR/RU/PT/GL/DE) | – | – | – | same Wise format, one voice each |

---

## 3. Extracted payload (Director installer) — inventory & install layout

`payload/` = 1 115 files, 91 462 710 bytes total; manifest with
`name/wise_name/size/off/magic` in `payload_manifest.json` (+ `_manifest.json`
when using the generic tool). File-kind census: 82 PE (`MZ`), 28 ZIP (`PK`),
39 PNG, 16 GIF, 3 JPEG, 1 PDF, 946 other (JAR/HTML/CHM/text/voice data/...).

**Naming note:** the Wise index stores `<name><decimal id>`; on-disk files keep
that id suffix (e.g. `TTSDirector.jar8`, `loqtts.h` (no id), `attstest.exe512`).
`payload_manifest.json.name` is the on-disk name and `wise_name` the index
string; the tables below drop the numeric suffix for readability.

### 3.1 Headline components

| Component | Size | Description |
|---|---|---|
| `TTSDirector.jar` | 878 997 | **The app** (`Main-Class: loquendo.tts.ttsdirector.TTSDirectorMain`, splash `TTSDirector.jpg`, 75 classes) |
| `TTSDirectorManager.jar` | 15 829 | Launcher/console (`…ttsdirectormanager.TTSDirectorManager`, 6 classes) |
| `TTSEngineServer.jar` | 61 506 | RMI TTS engine server (`…engineserver.TTSServerManager`, 15 classes, incl. RMI `_Skel`) |
| `TTSEngineServerClient.jar` | 39 860 | Server-side stubs/skeletons + shared classes |
| `TTSEngineClient.jar` | 30 669 | RMI client + streaming player (`…engineclient.TTSEngineClientRMI`, 7 classes) |
| `TTSLexiconManager.jar` | 377 326 | Lexicon editor GUI (181 classes) |
| `TTSDirectorlookandfeel.jar`, `TTSLexiconManagerlookandfeel.jar`, `lookandfeel.jar` | 138 756 / 666 778 / … | Loquendo Swing L&F (`loquendo.lookandfeel.LoquendoLookAndFeel`) |
| `LTTS7JavaTTSUtil.jar` (164 100), `LTTS7JavaUtil.jar` (65 214) | | JDOM-based utilities, lexicon XML, DB/diff helpers |
| `rt.jar` (42 718 562), `jvm.dll` (2 334 720), `java.exe/javaw.exe`, `awt.dll`, `fontmanager.dll`, `msvcr71.dll` (348 160), … | | bundled **JRE 6** (Sun 1.6.0_07, `java -version` strings `10.0-b22`) |
| `LTTS7Ludoviko.dll` (57 344), `LTTS7Esperanto.dll` (73 728) | | per-voice native libraries |
| `Ludoviko.vde` 455, `Ludoviko.vcf` 331, `Ludoviko.sde` 186 290, `Ludoviko.16000.linear.256000.10.bin` 5 069 459 | | Spanish voice descriptors + vocal database |
| `Esperanto.lde` 258, `Esperanto.lcf` 181 | | Esperanto language descriptors |
| `LoqTTS7.lib` 69 054, `loqtts.h` 13 340, `loqtypes.h` 9 243 | | **engine C API** (import lib + headers) |
| `HelloTTS.c/.dsp/.java/.vbp/.vcproj`, `ReadSlice.c/.dsp/.vcproj`, `SAPI4.*`, `SAPI5.*`, `LangGuess.c`, `TTSWebServer.asp` | | SDK samples (C, Java, VB, ASP, SAPI4/SAPI5) |
| `TTSApp.exe` 806 912, `attstest.exe` 204 824, `destfile.exe` 36 376 | | SAPI5 test applications |
| `VoiceExperience.exe` 2 076 672, `TTSFileGenerator.exe` 77 824 | | voice demo player, batch audio generator |
| `Loquendo_TTS_7_{Installation,Users,Programmers,Java_Programmers}_…` (`pdf`, 3× `chm`) | | documentation |
| doxygen HTML tree (`*.html`, `loquendo.css`, `ftv2*.png`, `tabs.css`…) | | **Java engine API reference** (`loquendo.tts.engine.*`) |
| `client.policy` (582), `administrator.policy` (649), `security.policy` (807), `rmid.policy` (257), `US_export_policy.jar`, `local_policy.jar` | | Java security policies (see §8) |
| `TTSDirector.bat` (81), `TTSDirectorManager.bat` (70), `TTSDirectorClient.bat` (100) | | launchers (contents below) |

Launchers (verbatim):

```bat
rem TTSDirector.bat
@echo off
start ..\jre\bin\javaw.exe -jar TTSDirectorManager.jar standalone
exit

rem TTSDirectorManager.bat
@echo off
start ..\jre\bin\javaw.exe -jar TTSDirectorManager.jar
exit

rem TTSDirectorClient.bat
@echo off
start ..\jre\bin\javaw.exe -Djava.security.policy=client.policy -jar TTSDirector.jar
exit
```

**Install layout** (inferred from launcher paths, engine strings and the Wise
script; the Wise script encodes per-file destinations):
`<INSTALLDIR>\bin\` (native engine + `LTTS7SAPI5.dll` registered with
`regsvr32 /s`), `<INSTALLDIR>\…\<app>\` (the `.bat` files next to
`TTSDirector.jar`, with `..\jre\` as sibling), `voices\<Voice>\` (voice data,
cf. `VoicePath = "voices/Ludoviko"` in `Ludoviko.vcf`), documentation folders.
Registry: `HKLM\SOFTWARE\Loquendo\LTTS7\{Engine,default.session,LicenseCode}`.

---

## 4. Application architecture (fully recovered, decompiled sources in `src/`)

The product is a **3-tier client/server TTS system** (Java RMI), 7.7.1:

```
TTSDirector.bat  -> Manager (TTSDirectorManager.jar standalone)
                      |  creates RMI registry on port 1099
                      |  binds rmi://localhost:1099/TTSEngineServer  (TTSEngineServerUnicastImpl)
                      |  binds rmi://localhost:1099/TTSEngineServerAdministrator
                      |  spawns: javaw -Djava.security.policy=client.policy -jar TTSDirector.jar -standalone
                      v
TTSDirector.jar (Swing GUI) --RMI--> TTSEngineServer  --JNI--> loquendo.tts.engine.* --> loqtts.dll
```

* RMI constants: registry port **1099** (configurable in the manager GUI),
  service names **`TTSEngineServer`** and **`TTSEngineServerAdministrator`**
  (`TTSServerManager.SERVER_NAME`, `ADMIN_NAME`), codebase
  `java.rmi.server.codebase = file:/<dir>/TTSEngineServerClient.jar`,
  policy `administrator.policy`.
* `TTSServerManager` also supports RMI **activation** (`ActivationGroup`,
  `ActivationDesc`) and a graphic mode.
* Client (`TTSEngineClientRMI`, 3898 lines) registers itself
  (`server.registerClient()` → `clientCode`), pushes a `TTSParams` record, calls
  `server.read(text, params, aSync, clientCode)`, and streams the synthesised PCM
  back with `server.getOutBuffer(clientCode)` from a `Writer` thread
  (`saveAudio()` writes it to a `.wav`/`.asf` file, a `Player` thread feeds
  `javax.sound`). `getTextInfo()` returns per-word/phoneme timing and
  `getPhoneticTranscription()` the phoneme string.
* Engine server (`TTSEngineServerImpl`/`TTSEngineServerUnicastImpl`,
  1 237/1 216 lines) wraps one native reader per client
  (`TTSReaderWrapper`, 568 lines) and implements the whole API below; the native
  layer is the `loquendo.tts.engine` JNI package from `Loqjapi.jar`
  (shipped by the *Engine* distribution, not the Director archive).

### 4.1 RMI service interface `TTSEngineServer` (recovered signature list)

Server/client lifecycle: `initServer()`, `initServer(boolean)`, `shutDown()`,
`ping()`, `registerClient() -> String`, `unregisterClient(String)`,
`deleteSession()`.
Resources: `GetAvailableTTSResources(boolean)`, `FillVoicesAndComments()`,
`GetVoicesAndComments() -> String[]`, `GetVoiceAndComments(String)`,
`GetVoice(int)`, `GetVoiceIndex/GetLanguageIndex/GetFrequencyIndex`,
`checkVoicePresence/checkLanguagePresence`, `isBuiltinVoice`,
`GetVoiceMotherTongue`, `getVoiceParams(String,String) -> int[]`,
`deleteVoice(String)`, `GetGilded(String,String)`, `GetLanguages`, `GetStyles`,
`getVoiceFlavours(String,String)`.
Enumerations/ranges: `GetFrequencies`, `GetCodings`, `GetVolumeRange`,
`GetVolumePercentageRange`, `GetPitchRange`, `GetPitchPercentageRange`,
`GetSpeedRange`, `GetSpeedPercentageRange`, `GetTimbreRange`,
`GetTimbrePercentageRange`, `GetBalanceRange`, `GetGainRange`, `GetDelayRange`,
`GetDefault{Gain,Delay,Balance}`.
Speech: `read(String,TTSParams,boolean,String)`,
`readForUnitSelection(String,TTSParams,String)`, `stop(String)`,
`getReadingsMode()`, `getPhoneticTranscription(String,TTSParams,String)`,
`getOutBuffer(String) -> byte[]`, `getTextInfo(String) -> ArrayList<ArrayList>`,
`GetSpeechAtomTree(String,String) -> TreeModel`,
`saveVoiceConfiguration(String,String,TTSParams)`, `setDefaultAttributes(String)`.
Equaliser: `getGraphicEQBand(int[],String) -> float[]`,
`setGraphicEQBand(int[],float[],String)`, `resetGraphicEQ(String)`,
`setGraphicEQPreset(String,String)`, `getGraphicEQPreset(String) -> String[]`,
`addParametricEQ`, plus `detectLanguage`/language-guess helpers (see below).

`TTSParams` (serialisable; defaults): `voice="Mario"`, `language="Italian"`,
`frequency="32000"`, `coding="linear"`, `textFormat="autodetect"`,
`textEncoding="utf8"`, `voiceFlavour=null`, `channels=2`, `volume=50`,
`pitch=50`, `speed=50`, `timbre=50`, `gain=0`, `delay=0`, `balance=0`, plus
percentage variants (`*Percent`).

### 4.2 The `read()` pipeline (server side) — behavioural spec

1. `wrapper.setParam("TextCoding", params.textEncoding)`.
2. Format detection: if `textFormat == "autodetect"` → try `validateXML(text,false)`;
   success ⇒ SSML. `"ssml"` ⇒ SSML.
3. Language/voice: take the first space-separated token of `params.language` /
   `params.voice`; `"mother"` resolves via `GetVoiceMotherTongue(voice)`.
   A *voice flavour* makes the server synthesise a derived VCF:
   `TTSVoice(voice)`, `setParam ForcedSampleRate/ForcedCoding/ForcedBitrate`,
   `setParam <VOICEFLAVOURID>=yes`, `saveCF(voice+"-"+flavour+"-"+rate+"-"+coding+"-"+bitrate)`.
4. Audio: `setLanguage(lang)` then `audioDestination.setAudio(frequency, coding, channels)`.
5. If SSML: `setParam("TextFormat","ssml")`, `reader.read(text, aSync, false)`.
6. Else (plain text): `setParam("TextFormat","plain")` and the server **wraps the
   text in LTD control tags**:

   ```
   \{voice=<V>\{language=<L>\{volume=<vol>\{pitch=<p>\{speed=<s>\{timbre=<t>\
   {balance=<b>\{reverb=<gain>,<delay>\{pause=0 . \n <text>[ .]
   ```
   and calls `reader.read(that, aSync, false)`. (Single-character text gets a
   trailing " ." to make the engine speak it.)

This is the canonical "speak this text with these prosody settings" behaviour a
re-implementation must reproduce.

---

## 5. Engine API to be reproduced

### 5.1 Java API — `loquendo.tts.engine` (documented in the payload's doxygen)

* `TTSSession` — `TTSSession()`, `delete()`, `query()`, `queryAttribute()`,
  `getParam()`, `testPersona()`.
* `TTSReader` — `TTSReader(TTSSession)`, `delete()`, `read(text, async, fromFile)`,
  `pause()`, `resume()`, `done()`, `setAudio(dest, device, rate, coding, channels)`,
  `audioFreeSpace()`, `loadPersona(name, language, style)`,
  `setVoice/setLanguage/setStyle` (via voice objects), prosody
  `set/get Pitch|Speed|Volume|Timbre|Balance|Gain|Delay` (+ absolute and
  percentage variants, `setPitchRange`, `setSpeedRange`, `setDefaultAttribute`,
  `setReverb`), text `setParam/getParam` (`TextEncoding`, `TextFormat`,
  `TextCoding`, `VoiceFlavour`, …), lexicon hooks, events
  `addTTSListener/removeTTSListener/removeAllListeners`, speech atoms
  (unit selection), `phoneticTranscription()`, `checkPhoneticTranscription()`,
  `saveCF(name)`, graphic EQ `set/getGraphicEQBand`, `setGraphicEQPreset`,
  `resetGraphicEQ`.
* `TTSVoice` — `TTSVoice(session,name)`, `activate()`, `delete()`,
  `setParam/getParam` (`ForcedSampleRate`, `ForcedCoding`, `ForcedBitrate`, …),
  `saveCF(name)`, speech-atom inventory access
  (`locateSpeechAtomInventory`, `getSpeechAtomChild/Sibling`).
* `TTSLanguage` — `activate()`, `setParam/getParam`, `saveCF`.
* `TTSLexicon` — `addEntry`, `removeEntry`, `findEntry`, `activate`, `importfile`,
  `exportfile`.
* `TTSConfiguration` — `getVersionInfo`, `saveParam`, `loadParam`, `delete`.
* `TTSEvent` — `getReason()`, `getStringData()`; `TTSListener` callback interface;
  `TTSAudioDestination` — `setAudio(rate, coding, channels)` (per-client PCM sink);
  `TTSException` — `failure()`.

### 5.2 C API — `loqtts.h` / `loqtypes.h` (complete surface, 100+ entry points)

Reader/session: `ttsNewSession`, `ttsDeleteSession`, `ttsNewReader`,
`ttsDeleteReader`, `ttsClone`, `ttsClaimLicense`, `ttsUnclaimLicense`,
`ttsGetVersionInfo`, `ttsGetErrorMessage`.
Speech output: `ttsRead`, `ttsReadSlice`, `ttsReadNextSlice`, `ttsPause`,
`ttsResume`, `ttsSkip`, `ttsWaitForEndOfSpeech`, `ttsStop`, `ttsReset`,
`ttsAudioFreeSpace`, `ttsInject`, `ttsSetAudio`, `ttsGetPCM`.
Voices/personas/languages/styles: `ttsNewVoice`, `ttsDeleteVoice`, `ttsSetVoice`,
`ttsLoadPersona`, `ttsLoadPersonaFromFile`, `ttsTestPersona`, `ttsNewLanguage`,
`ttsSetLanguage`, `ttsDeleteLanguage`, `ttsNewStyle`, `ttsSetStyle`,
`ttsDeleteStyle`, `ttsLanguageGuess`, `ttsSetTextEncoding/Format` (+getters).
Prosody/audio processing: `ttsSet/Get Pitch|Speed|Volume|Timbre|Reverb|Balance`
(int + absolute), `ttsSet/GetAbsolutePitch/Speed/Volume`, `ttsAddParametricEQ`,
`ttsSetGraphicEQPreset/Band`, `ttsGetGraphicEQBand`, `ttsResetGraphicEQ`,
`ttsResetParametricEQ`, `ttsSaveCF`.
Lexicons: `ttsOpenLexicon`, `ttsActivateLexicon`, `ttsCloseLexicon`,
`ttsFindLexiconEntry`, `ttsAddLexiconEntry`, `ttsRemoveLexiconEntry`,
`ttsImportLexicon`, `ttsExportLexicon`, `ttsEnumLexicon{Entry}First/Next`,
`ttsGetLexiconFilename`.
Events/callbacks: `ttsSetCallback`, `ttsEnableEvent`, `ttsSetURLCallback`.
Queries/atoms/XML: `ttsQuery`, `ttsQueryAttribute`, `ttsEnumFirst/Next/Close`,
`ttsLocateSpeechAtomInventory`, `ttsGetSpeechAtom`, `ttsValidateXML`,
`ttsSSMLConvert`, `ttsPhoneticTranscription`, `ttsCheckPhoneticTranscription`,
`ttsGetPhonemeInfo`, `ttsGetTag`.
Configuration: `ttsSetParam`, `ttsGetParam`, `ttsSaveConfigurationParam`,
`ttsLoadConfigurationParam`, `ttsDeleteConfiguration`,
`ttsEnumConfigurationParameterFirst/Next`.

Types (`loqtypes.h`): `ttsHandleType`, `ttsResultType` (`tts_OK`, error codes),
`ttsBoolType`, `ttsCodings` (`tts_LINEAR`, …), channel consts, page/mix-language
enums, `ttsReasonType` for events. Error strings via `ttsGetErrorMessage`.
Minimal usage (payload `HelloTTS.c`): `ttsNewReader(&h,NULL)` →
`ttsLoadPersona(h,"Ludoviko",NULL,NULL)` →
`ttsSetAudio(h,"LTTS7AudioBoard",NULL,32000,tts_LINEAR,tts_STEREO,0)` →
`ttsRead(h,"\\demosentence",FALSE,FALSE,NULL)` → `ttsDeleteSession(NULL)`.
Java equivalent in `HelloTTS.java` (same sequence with `new TTSSession()`,
`new TTSReader`, `setAudio`, `loadPersona`, `setParam("TextEncoding","utf-8")`,
`read`).

### 5.3 LTD control-tag language (used by the Director and by `read()`)

Backslash tags (single `\` opens a tag, `\` closes the previous one; `\{name=value`
sets a parameter, remaining text is spoken):
`\voice=`, `\language=`, `\style=`, `\persona=`, `\volume`, `\pitch`,
`\speed`, `\SpeedFast=`, `\PitchDelta=`, `\PitchContour=`, `\pause=`,
`\emphasis`, `\prominence`, `\ipa=`, `\pause=`, `\spell`, `\say-as`-family
(see the Say-As menu), `\book=`, `\bookmark=`, `\item=`, `\plugin=`,
`\ExcludeUnit=`, `\u`, `\U`, and SSML is accepted verbatim when
`TextFormat=ssml` (`validateXML` autodetects `<speak>`/`<…>` documents).
Payload sample: `ttsRead(h,"\\demosentence",…)` = built-in demo sentence macro.

### 5.4 Audio destinations / formats

* Destinations: `LTTS7AudioBoard` (DirectSound/WaveOut playback),
  `LTTS7AudioFile` (write WAV/raw), buffer destination (used with the RMI
  `clientCode` so the server hands PCM chunks to the client), `LTTS7AudioExt`
  (streaming). Coding strings from `GetCodings()`: `linear`, `alaw`, `ulaw`,
  `adpcm`, … Sample rates from `GetFrequencies()` (8/11.025/16/22.05/32/44.1/48 kHz),
  1–2 channels.

### 5.5 Voice / language descriptor file formats (plain text, verified)

`<Voice>.vde` — voice descriptor (`; LTTSComponentVersion=7.1.0`):
`BaseDescription`, `Library` (`LTTS7Ludoviko, Ludoviko`), `BaseSpeed`, `BasePitch`,
`Algorithm` (`Sequens`), `Gender`, `Age`, `MotherTongue`, `MotherTongueAliases`,
`DemoSentence`, … (455 B for Ludoviko).

`<Voice>.vcf` — voice configurator (created/edited by "Voice Creator"/flavours):
`Description`, `BaseVoice`, `VoicePath` (`voices/Ludoviko`), `VocalDBName[0]`,
optional `Pitch/Speed/Volume/Timber`, `Built-in`.

`<Lang>.lde` — language descriptor: `BaseDescription`, `Library`
(`LTTS7Esperanto, Esperanto`), `Language` (`Esperanto,eo`), `WinLangid` (1536),
`DefaultVariant`.

`<Lang>.lcf` — language configurator (companion of `.lde`).

Voice payload: `<Voice>.<rate>.linear.<bitrate>.<n>.bin` = vocal database
(Ludoviko: 5 069 459 B, the `Ludoviko.16000.linear.256000.10.bin` file),
`<Voice>.sde` = Sequens segment/DB index (186 290 B), plus the per-voice
`LTTS7<Voice>.dll` (57 344 B for Ludoviko). These are the binary acoustic assets;
their internal structure is not documented and is engine-specific.

---

## 6. GUI functionality — what the Director app does

Constants are in `TTSDirectorConst` (decompiled, `src/TTSDirector/…`):
`TTSDirectorVersion="7.7.1"`, `TOOL_NAME="Loquendo TTS Director"`,
default frame 1024×768, `MAXUNDO=100`, OS enum (Windows/Linux/SunOS/other),
fonts, DRCRange `{1,1,5}`.

### 6.1 Main window

* Top strip: **voice combo** (250×19), **language combo** (180×19),
  **reading-mode combo** + label, **Play** and **Stop** buttons, and a
  font/size combo for the editor; mouse auto-play support
  (`MenuMouseAutoPlayGapX`, timed play of the current paragraph).
* Central `JTabbedPane`: one document per tab ("Untitled", "*" when dirty),
  each tab = rich text editor + per-document prosody controls
  (`TTSEditorPane`, `TTSTabbedPane`, `TTSSlidersControl`).
* Documents: plain text, **LTD** (Loquendo TTS Director format) or **SSML**,
  chosen under *View ▸ Highlight as* (Plain Text / LTD / SSML) with
  syntax highlighting (`TTSColorChooser` to customise colours) and
  *View ▸ Validate*.
* Editor: undo/redo (100), cut/copy/paste/select-all, word wrap,
  document size filter, print (`TTSPrintingThread`), font config
  (`TTSDirectorFont`), search/replace, bookmarks list.

### 6.2 Menus and commands (verbatim command names from `TTSDirectorConst`)

* **File**: New, Open…, Load…, Save, Save As…, Save All, Close, Close All,
  **Save Audio As…**, Print selected tab…, Exit.
* **Edit**: Cut, Copy, Paste, Select All, Undo, Redo.
* **View**: WordWrap, Highlight as ▸ Plain Text / LTD / SSML,
  Customize Highlight Colors…, Validate.
* **Effects**: Mixer… (mixer wizard), Play/Manage/Pause/Resume/Stop audio files,
  Set Global Path, Recording (start/stop), Loop, Repeat Counter,
  Fade In/Fade Out (ms), Volume (%), Ignore Absolute Path, Switch to Play Mode,
  Save Effects list as….
* **Configuration**: Voice flavours (Default/…), ControlTags, Audio, Mixer,
  Audio Files, **Reverb**, **Balance**, **Dynamic Range Control** ("Set DRC
  curve", "Reset DRC"), Bookmarks, Language (Set Foreign Language…, Reset Native
  Language, Language Guesser Configuration, Greeklish on/off, French stress
  on/off), AutoGuesser Capability (voice/language change per
  paragraph/sentence/phrase/word — 12 modes), Pronunciation, Phonetic Input
  (Transcription Plus Word, Insert IPA Phonemes, Insert SAMPA Phonemes),
  Say As (cardinal/ordinal masc/fem, telephone number, code number, time, date,
  currency, reset all permanent modifiers), User Lexicon (Load/Unload/Activate),
  Prosody (Duration Control → Force/End Force Duration; Emphasis → Increase/
  Decrease/Reset; Expressivity → Play An Extraphonetic Sound; Punctuation Pauses
  → Insert A Pause, short/medium/long pause lengths; Prominence → Stress/
  Unstress A Word; Speaking Rate → percentage/increase/decrease/reset, Use Fast
  Algorithm; Pitch → percentage/increase/decrease/reset, Monotonous, Pitch Delta,
  Pitch Contour, End Pitch Contour; Volume → percentage/increase/decrease/reset;
  Timbre → change/reset; Reverb → change/reset; Balance → change/left/right/reset),
  Reading Settings (Reading Style set/reset, Unit Selection, Tuning…),
  Spelling (Spell Next Word, Spelling level Normal/Every word/None, Read Aloud
  Control Tags, Spell punctuation), Prosodic Pauses (breath pause at phrase
  boundaries, word-by-word, pauses at empty lines/multiple spaces/titles),
  Voice (Voice Change…, Persona Change…).
* **Tools**: Loquendo LexEditor (`LexEditor.exe`), Loquendo TTS Voice Creator
  (`voices manager`), Loquendo TTS Lexicons Converter, Loquendo TTS Lexicon
  Manager (`TTSLexiconManager.jar`).
* **Help**: about box, HTML help (`TTSDirectorHelp`), CHM manuals.

Dialogs/wizards delivered: `TTSMixerWizard` (1237 lines, audio-file mixing with
fade/volume/loop/record and tag insertion), `TTSGraphicEqualizer` /
`TTSGraphicEqualizer1030Bande` (10- and 30-band EQ incl. presets),
`TTSDRCWizard` (dynamic range control curve — DRCRange `{1,1,5}`),
`TTSUnitSelector` (voice unit/persona selection), `TTSLangChooser`,
`TTSVoicesManager` (create/delete voice variants), `TTSChooserDialog`,
`OpenConvertDialog` + `ConvertDialog` (562 lines: batch conversion),
`TTSDirectorAboutBox`, `TTSAccessoryFileChooser`, `TimedMessage`.

### 6.3 File formats

* `.txt` — plain text; `.ssml` — SSML; `.ltd` — Director document: an editor text
  that *begins with an LTD header line of control tags*, parsed by
  `TTSFileHeader.extractHeaderParam()` which scans for `voice=`, `language=`,
  `volume=`, `speed=`, `pitch=`, `timbre=`, `reverb=` (two comma-separated values
  → `gain`,`delay`), `balance=`, values terminated by `\` or space
  (e.g. `\voice=Ludoviko\language=Spanish\volume=50…`).
* Export: **WAV** (`WAV file (*.wav)`) and **ASF**
  (`Microsoft Advanced Systems Format (*.asf)`) through
  `TTSEngineClientRMI.saveAudio(file, type, text)`; selectable channels, coding
  and sample rate; conversion dialog also emits `.txt`/`.ssml`/`.ltd` targets.
* Printing produces the current tab.

### 6.4 Other executables

* `TTSDirectorManager` — GUI console (port field default 1099, uri `rmi://`,
  "start server"/"stop server" buttons, standalone switch) and CLI
  (`standalone` argument starts registry + server + Director).
* `TTSLexiconManager.jar` — full lexicon editor (`.lex`/XML via
  `LTTS7JavaTTSUtil` JDOM classes: `Lex`, `Entry`, `Lex0`, diff/patch, DB).
* `VoiceExperience.exe` — voice demo player (vocabulary demo sentences).
* `TTSFileGenerator.exe` — batch generator (text → audio files).
* `TTSApp.exe`, `attstest.exe`, `destfile.exe` — SAPI5 validation utilities
  (voice attributes / destination-file / generic TTS app).
* `TTSWebServer.asp` — ActiveX/ASP sample server (per README).

---

## 7. Licensing model

* Engine licences are **per-voice**, keyed to the machine: the crack
  (`Patch.exe`, Borland Delphi, 8 sections) reads the MAC from
  `HKLM\SOFTWARE\Microsoft\SystemID`, computes a key and writes
  `HKLM\SOFTWARE\Loquendo\LTTS7\LicenseCode` (strings: `Enter valid MAC!`,
  `Can't delete HKLM\`, `Can't delete HKCU\`, `TTSVersion`, `Channels`,
  `keygen`, `0123456789ABCDEF`). Error strings `Error #1..#7` mark the flow.
* Java side: `client.policy` grants read/write/delete on `<<ALL FILES>>`,
  sockets ≥1024, clipboard/show-window; `administrator.policy` additionally
  `loadLibrary.*`, `exitVM`, writes to `${user.home}/.Loquendo/*`;
  `rmid.policy`/`security.policy` are the JRE defaults.
* A re-implementation that keeps the original engine must keep the
  `LicenseCode` contract (or reuse the same MAC-key scheme) for the voices to
  load; a re-implementation with a substitute engine can drop it.

---

## 8. How to re-implement (concrete plan for another agent)

**Phase 0 — reproduce the payload.** Run `wise_unpack.py` (or
`extract_payload.py`) to obtain `payload/`; verify: 1 115 files,
91 462 710 bytes, `TTSDirector.jar` md5 `0ee06cf651fea786b6cd816e96a05097`,
`TTSEngineServer.jar1` md5 `aa6863d02162cbc1f68b9cb322d442a5`,
`loqtts.h` md5 `6ac716ab4cdd7416fc1b9842f5aadea3`,
`Ludoviko.vde` md5 `7ef62dafd49eba4741b437f33badb8cc`, `cab_folder.bin` md5
`6031c37e91c05e2fed553f125caea94f`.

**Phase 1 — app skeleton (no synthesis).** Rebuild the Java client/server:
* `TTSEngineServer` RMI interface exactly as in §4.1, bound as
  `rmi://<host>:1099/TTSEngineServer` (+ `…Administrator`), `clientCode`
  registration, `TTSParams` transfer object, PCM streaming via `getOutBuffer`.
* `TTSEngineServerImpl.read()` semantics of §4.2 (SSML autodetect via XML
  validation, LTD wrapper string, audio destination setup, voice flavours as
  derived VCFs).
* Director Swing GUI: top strip + tabs + menus of §6 using the same command
  strings, `.ltd` header parsing, `.txt`/`.ssml`/`.ltd` documents, WAV/ASF
  export, undo/redo, highlight modes, bookmarks, EQ/DRC/mixer wizards
  (the decompiled `src/TTSDirector/**` is a direct reference implementation).

**Phase 2 — engine binding.** Two options:
1. *Reuse*: load `loqtts.dll` + voice DLLs + voice databases from the Engine
   distribution and bind them through the documented API (§5.1/§5.2) via JNI
   (recreate `Loqjapi.jar`’s `loquendo.tts.engine.*` classes) — the semantics of
   every call are documented in the payload’s doxygen/headers and exercised by
   the samples.
2. *Substitute*: implement the same C/Java API on top of any modern TTS backend
   (eSpeak-NG, Piper, Azure/Google TTS, …). Keep the API, parameter ranges
   (`get*Range`), tag syntax (§5.3), voice/language descriptor files (§5.5) and
   event model; map `setVoice/loadPersona` to installed backend voices,
   `setAudio` to WAV/stream sinks, `getPhoneticTranscription` to the backend’s
   phonemiser, EQ/DRC/reverb to DSP.

**Phase 3 — packaging.** Recreate the Wise installer or (better) a modern
installer reproducing: file set from `payload/`, install layout of §3
(`bin\` with `regsvr32` of `LTTS7SAPI5.dll`), registry keys
(`SOFTWARE\Loquendo\LTTS7\{Engine,default.session,LicenseCode}`), Start-menu
shortcuts and ARP entry, plus the SAPI5 registration for `TTSApp.exe`-style
usage. §2 fully documents the original format if byte-identical installers are
required.

**Acceptance criteria for equivalence**
1. `TTSDirector` GUI exposes the same commands/dialogs and speaks the text of a
   document with the same prosody controls; `.ltd` documents round-trip.
2. `read()` of a given text with given `TTSParams` yields a playable PCM stream
   with the same rate/coding/channels and the same tag semantics.
3. RMI contract: a stock client can `registerClient`, `GetVoicesAndComments`,
   `read`, `stop`, `getOutBuffer`, `saveVoiceConfiguration`,
   `getPhoneticTranscription`, `GetSpeechAtomTree`, EQ calls.
4. Voice/language descriptors (`.vde`/`.vcf`/`.lde`/`.lcf`) are parsed with the
   documented keys, and a new voice can be registered by dropping a folder under
   `voices\`.
5. SAPI5 engine registered (`regsvr32 \bin\LTTS7SAPI5.dll`) enumerates the
   voices as SAPI tokens (`SpEnumTokens(SPCAT_VOICES,"Name=…")`) and speaks.

---

## 9. Evidence, reproducibility and limits

* Extraction re-verified end-to-end: `.WISE` → `MSCF` (cbCabinet 33 480 386,
  1115 files, 1 folder) → 2792 MSZIP blocks, 0 failures → 91 462 710 bytes,
  gapless file index → 1115 files. Both tools (`extract_payload.py` and the
  generic `wise_unpack.py`) were re-run independently and produce **identical
  name/size sets** for the Director installer.
* Generality check: `wise_unpack.py` also unpacks the voice installers — e.g. the
  German distribution yields 15 files / 2 247 763 B (`German.lde4`, `German.lcf`,
  `German.lex`, `German.rex8`, `German.ycf`, `German.dbl5`,
  `German_Automotive.lex6`, `German_Cities.lex`, `LTTS7German.dll1`,
  `Loquendo_TTS_7_Installation_Manual.pdf4`, `Logo.ico`, …). The *Engine*
  distribution uses the MSI-style variant, so its cabinet only carries the SAPI5
  prerequisite (9 files; `sapi.dll`, `sapi.cpl`, `sapisvr.exe`, `speech.chm`,
  `sapicpl.hlp`).
* Ghidra headless decompilation of the loader (`decomp_director.txt`, 4489 lines)
  used to derive the container/decryption/CRC behaviour; CFR 0.152 was used for
  the Java jars (`src/`).
* Not recoverable from this archive: the acoustic engine internals
  (`loqtts.dll` isn't even present — it comes from the MSI-style *Engine*
  distribution whose payload is stored as an OLE/MSI database, not as the
  MSZIP cabinet used by the SDK/voice packages), the voice databases
  (`.bin`/`.sde` binary formats), and the exact Wise script destination strings
  (the script is stored in a Wise-proprietary encoded section; only its ASCII
  fragments — EULA, registry keys, regsvr32 lines — are readable).
* Marked as [inferred]: the `f2` field semantics (DOS date), the last u32 of the
  file record, the exact install tree (derived from launcher paths, `VoicePath`,
  and `INSTALLDIR\bin\…` strings in the script).

---

### Appendix A — key file contents (verbatim, for quick reference)

`Ludoviko.vde` (455 B):
```
; LTTSComponentVersion=7.1.0
; Voice descriptor file for Loquendo TTS
"BaseDescription"	=	"Esperanto robotic male voice"
"Library"		=	"LTTS7Ludoviko, Ludoviko"
"BaseSpeed"		=	"128"
"BasePitch"		=	"95"
"Algorithm"		=	"Sequens"
"Gender"		=	"Male"
"Age"			=	"40"
"MotherTongue"		=	"Esperanto"
"MotherTongueAliases"	=	"Esperanto,eo"
"DemoSentence"		=	"Mia nomo estas Ludoviko, mi estas lo robota vocxo d…"
```

`Ludoviko.vcf` (331 B):
```
; Voice Configurator File for Loquendo TTS
"Description"       = "Esperanto robotic male voice"
"BaseVoice"         = "Ludoviko"
"VoicePath"         = "voices/Ludoviko"
"VocalDBName[0]"    = "Ludoviko"
;"Pitch"            = ""
;"Speed"            = ""
;"Volume"           = ""
;"Timber"           = ""
"Built-in"          = "Yes"
```

`Esperanto.lde` (258 B):
```
; LTTSComponentVersion=7.3.0
; Language descriptor file for Loquendo TTS
"BaseDescription"	=	"Esperanto generic descriptor file"
"Library"		=	"LTTS7Esperanto, Esperanto"
"Language"		=	"Esperanto,eo"
"WinLangid"		=	"1536"
"DefaultVariant"  	= 	"yes"
```

### Appendix B — extracted artefact checksums

| Artifact | md5 |
|---|---|
| `LTTSDirector7.rar` | `9c551a2da0a71189d7168948c9d339d3` |
| `LOQUENDO TTS DIRECTOR 7.exe` | `f575b9198a334b3d74c8d624fc03ac79` |
| `cab_folder.bin` (uncompressed payload) | `6031c37e91c05e2fed553f125caea94f` |

---

# 10. Acoustic synthesis core — reverse-engineered specification

Everything below is derived from the extracted engine modules (all decompiled into
`decomp_loqtts.txt`, `decomp_db.txt`, `decomp_ludoviko.txt`, `decomp_codecmsx.txt`,
`decomp_codec210.txt`, `decomp_util.txt`) plus byte-level analysis of the voice
data (`.vde`, `.sde`, `.bin`, `.dbl`, `.rex`, `.lex`, `.lde`, `.lcf`, `.vcf`, `.ycf`).

## 10.1 Module map (from the Engine distribution, cab `cab05_9d8423`)

| Module | Role |
|---|---|
| `LoqTTS7.dll` (888,832 B) | engine core: C++ classes `CttsSession/Reader/Voice/Language/Style/Lexicon/Enum/Error` (232 exported methods), prosody, SSML, streaming, unit selection |
| `LTTS7DB.dll` (331,776 B) | DB layer `DBOpen/DBGetTable/DBGetNext/DBExecuteQuery/DBCreateTable/DBGetVersion/…` |
| `LTTS7Util.dll` (266,240 B) | 546 `ELQ*` exports: `ELQBinaryHeader*` (self-describing binary file headers), `ELQBin*` (buffered/smart-buffer file I/O), `ELQDB*` (lexicon DB access), `ELQXML*` (XML/SSML parser), `ELQAtm*` (text automata), `ELQNum*` (118 number/date/telephone normalisers), `ELQToken/ELQList/ELQBuffer/ELQMemory/ELQPlugin/ELQShared/ELQLog/ELQFile/ELQUrl/ELQRequest/ELQRxc/ELQText/ELQG` |
| `LTTS7CodecMsx.dll` (122,880 B) | voice-DB **decoder** (LPC/CELP, "Msx") |
| `LTTS7Codec210.dll` (204,800 B) | voice-DB **decoder** (LPC/CELP, "210") |
| `LTTS7Morphyzer.dll` (106,496 B) | morphological analysis |
| `LTTS7GPR.dll` (57,344 B) | grapheme-to-phoneme rules (reads its own rule files via `ELQfopen/ELQfread`) |
| `LTTS7LanguageGuesser.dll` (1,433,600 B) | language identification |
| `LTTS7XML.dll` | XML/SSML helper |
| `LTTS7jni.dll` (122,880 B) | 87 JNI exports `Java_loquendo_tts_engine_*` → `tts*` C API |
| `LTTS7SAPI4/5.dll`, `LTTS7.ocx` | SAPI4/SAPI5 engines (`CTTSEngine : ISpTTSEngine, ISpObjectWithToken`, ATL) and ActiveX control |
| `LTTS7AudioBoard/File/Asf/SAPI4.dll` | audio destinations (board, WAV/raw file, ASF, SAPI4) |
| `LTTS7<Voice>.dll` | **voice plugin**: `LTTS7Ludoviko.dll` 57 344 B, `LTTS7Spanish.dll` 196 608 B, `LTTS7German.dll` 1 566 208 B |
| `LTTS7<Language>.dll` | language module (e.g. `LTTS7Esperanto.dll` 73 728 B, `LTTS7German.dll`) |
| `Loqjapi.jar` (14,408 B) | Java↔JNI bindings (`loquendo.tts.engine.*`) |
| `TTSDiag.exe` | diagnostic tool |

## 10.2 Text → speech pipeline and the plugin procedure contract

`LoqTTS7.dll` loads modules with `ELQPlugin*` and resolves named procedures with
`ELQPluginGetProc(plugin, "<name>", &fn)`; failures are logged as
`Error loading <name> procedure from %s`:

```
resolved from the LANGUAGE module:
  FonNewLanguage, FonAllofonoLingua, FonAllofonoAnalisi, FonMetafonema, FonTrasParola,
  FonTrasConfini, FonIngloba, FonSetStile, Fonetica_, Fonetiche_, Fonema, CatVoiceVersion
resolved from the VOICE module (synthesis side):
  FonNewVoice, FonCommonIniChan, FonIniGlob, FonAllofonoVoce, FonAnalisi2Sintesi,
  FonGetSamples, FonOut, and the "Vid" variants FonVidAllofonoVoce, FonVidAnalisi2Sintesi,
  FonVidIngloba, FonVidAllofonoAnalisi, FonVidMetaFonema
resolved from the per-voice "SDE" module (unit database):
  GetVersion, CatVoiceVersion, CatSdeData   (log: "Error loading dbunita from %s",
                                             "%s voice version (%s) is not compatible …",
                                             "Missing version information in sde dynamic library")
```

So a re-implementation must provide, per language and per voice, a module exporting
these procedures (name-significant C linkage), where:

* `FonAnalisi2Sintesi` performs **unit selection + concatenation** ("Algorithm = Sequens"
  in the `.vde`), using the SDE unit inventory and the codec-decoded samples;
* `FonAllofono*` builds allophones from the phoneme string, `FonMetafonema` maps
  metaphonemes, `FonIngloba`/`FonTrasParola`/`FonTrasConfini` handle
  word/phrase/boundary level processing, `FonSetStile` selects style, `FonGetSamples`
  yields PCM/float samples, `FonOut` writes the output stream;
* `CatSdeData` loads the **dbunita** (unit DB) — implemented by the voice's SDE module.

`LTTS7Ludoviko.dll` shows the concrete plugin dispatch shape: it exports a single
symbol `Ludoviko` and a 4-entry name→function table:

| name | address |
|---|---|
| `GetVersion` | 0x10001150 |
| `ELQGetPhonemes` | 0x10001060 |
| `ELQVoiceChannelOpen` | 0x10001070 |
| `ELQVoiceChannelClose` | 0x10001100 |

(`ELQ<Voice>ChannelType` / `Fon<Voice>ChannelType` allocation objects appear in
`ELQmalloc`/`ELQLogWrite` diagnostics.)

## 10.3 Linguistic data formats (all verified byte-level)

* **`<Language>.dbl` — pronunciation lexicon = SQLite 3 database.**
  `CREATE TABLE 'lessico'(grafemica, fonetica, grammaticale, specgramm, gennum, tempomodo,
  abbreviazione, gradoaccentuale)` + `CREATE INDEX idx_lessico on lessico (grafemica)`.
  Row counts: Spanish-Es 5 469, Spanish-Am 5 464, German 4 712.
  Example row: `('ABM', 'a: b e: `E m', 'ACC', '', '', '', 'ABM', '')`
  (graphemes → SAMPA-like phoneme string, POS, gender/number, tense/mood, abbreviation flag,
  accent degree). Node encoding is not UTF-8 everywhere — read with `text_factory=bytes`.
  Exported: `engine_re/SpanishEs.csv`, `SpanishAm.csv`, `German.csv`.
* **`<Language>.rex` — text normalisation rules, plain text** (regex → replacement with LTD
  tags), e.g. German: `"(^|[^0-9\.,;:])([1-9][0-9]*)(\.)[ \t]+" = "\1 \{number=ordinalM \2 "`,
  plus Spanish contraction rules (`"([cdhlmnrstvzjCDHLMN…])([aeiou…])" = "\1 \2"`).
  UTF-8 BOM + CRLF, comments start with `;`.
* **`<Language>.lde` — language descriptor (text)**:
  `BaseDescription`, `Library` (`LTTS7German, German`), `Language` (`German,de,de-DE`),
  `WinLangid` (1031/1536), `LexicalDB` (`German.dbl`), `RegExp` (`German.rex`),
  `DefaultVariant`, `Le…`; `LTTSComponentVersion=7.3.1`.
* **`<Language>.lcf` — language configurator (text)**: `Description`, `BaseLanguage`,
  `LanguagePath` (`languages/German`), `SpecialLexicon[0]`, `Built-in`.
* **`<Voice>.vde` — voice descriptor (text)**: `BaseDescription`, `Library`
  (`LTTS7Ludoviko, Ludoviko`), `BaseSpeed` (128), `BasePitch` (95),
  **`Algorithm` = `Sequens`**, `Gender`, `Age`, `MotherTongue`, `MotherTongueAliases`,
  `DemoSentence`; `LTTSComponentVersion=7.1.0`.
* **`<Voice>.vcf` — voice configurator (text)**: `Description`, `BaseVoice`,
  `VoicePath` (`voices/Ludoviko`), `VocalDBName[0]`, optional `Pitch/Speed/Volume/Timber`,
  `Built-in`. The engine *writes* derived flavour files (`<voice>-<VOICEFLAVOURID>-<rate>-<coding>-<bitrate>.vcf`)
  containing `ForcedSampleRate`, `ForcedCoding`, `ForcedBitrate`.
* **`<Style>.ycf` — style configurator (text)**: `SampaSecondAccent`, `lexicon[0..n]`.
* **`<Voice>.lex` / `SI<Language>.lex` / `SMS<Language>.lex` — binary special lexicons**
  (word lists with companion data; e.g. `German_Automotive.lex`, `German_Cities.lex`,
  `SIGerman.lex` = abbreviation/expansion, `SMSGerman.lex` = SMS abbreviations).
* **`<Voice>.sde` — unit/segment index, ASCII with bit 7 set on every byte**
  (decode by `b & 0x7F`). Structure (verified, `engine_re/Ludoviko.sde.txt`, 10 062 lines):

  ```
  14,1
  VERSION=7
  N=3482,6953,6578              ; units, records, D-records
  U=<phoneme> [<flags>]         ; one unit definition (3482 of them, 3416 distinct,
                                ;   e.g. "U=Dg: #", "U=`E #", "U=a~ #")
  D=0,S,<start>,<end>,0         ; S-record  = left*/static part of the unit
  D=0,D,<start>,<end>,0         ; D-record  = the unit body (6577 D/S pairs total)
  ```
  Positions are in **decoded sample units** (max end 15 829 000 ≈ 989 s @16 kHz);
  `S` records of ~9 675 samples vs `D` records of ~15 319 samples are the per-unit
  static (context) and dynamic parts used by the concatenator.
* **`<Voice>.<rate>.<coding>.<bitrate>.<version>.bin` — codec bitstream** (§10.4);
  Ludoviko: `Ludoviko.16000.linear.256000.10.bin` = 5 069 459 B. The name describes the
  **decoded** format (16 000 Hz, linear PCM, 256 kbit/s, DB version 10), not the storage codec.

## 10.4 Voice-database codec (`LTTS7CodecMsx` / `LTTS7Codec210`)

### 10.4.1 Plugin ABI (identical in both codecs)

`LTTS7CodecMsx(name)` / `LTTS7Codec210(name)` dispatch a 7-entry name table
(Msx table @VA 0x10015230, 210 table @VA 0x1002D000):

| name | Msx | 210 |
|---|---|---|
| `GetVersion` | 0x100010e0 | 0x10001030 |
| `ELQOpenDecoder` | 0x10001c30 | 0x10001410 |
| `ELQCloseDecoder` | 0x10001b20 | 0x10001550 |
| `ELQGetDecodedFileSize` | 0x10001100 | 0x10001050 |
| `ELQGetDecoderDescription` | 0x10001000 | 0x10001000 |
| `ELQDecoderFileChanged` | 0x10001010 | 0x10001010 |
| `ELQDecode` | 0x10001b90 | 0x10001360 |

`ELQDecoderFileChanged(handle, dbId, filename)` binds the codec to a voice file
(`*(state+0x4C) = dbId`). All file access is `ELQBinGetSmartBuffer/ELQBinGetBuffer`
(LTTS7Util) — i.e. cached/mapped random access, never plain stdio.

### 10.4.2 DB header — 124 bytes (`0x7C`), **big-endian** 32-bit fields

The codec reads `0x7C` bytes at the DB offset through `ELQBinGetSmartBuffer(...,0x7C,...)`;
fields are decoded by `FUN_10001110` = `(p[0]<<24)|(p[1]<<16)|(p[2]<<8)|p[3]`
(header parser: `FUN_10001160`).

| off | meaning | notes |
|---|---|---|
| +0x0C | sample rate (Hz) | recognized values: 8000, 11000, 11025 (0x2B11), 16000, 22000, 22050 (0x5622), 32000, 44000, 44100 (0xAC44); mapped to a rate class 0/1/2 stored at state+0x11D0 |
| +0x10 | **bytes per frame** | stored as short at state+0x11D2; observed table of legal values 27, 29, 33, 35, 39, 43, 48, 52, 56, 60, 66, 70, 82, 86, 102, 106 → ≈10.8–42.4 kbit/s at 20 ms |
| +0x14 | header/extra size | added to the frame-stream base offset |
| +0x18 | byte flag | stored at state+0x11E8 |
| +0x1C | layout version | `<2` ⇒ legacy: fixed LPC/quantizer widths; `>=2` ⇒ extended: extra fields at +0x54…+0x74 are read |
| +0x20…+0x50 | per-parameter **bit counts** (up to 13 streams: LPC, pitch, gains, codebooks, …) | copied to decoder-state +4…+0x80 |
| +0x2C,+0x30,+0x34,+0x38,+0x3C,+0x40,+0x44,+0x48,+0x4C | **bits per code** of the matching streams | word counts derived by `log2(bits/width)` (`FUN_10001130` = floor log2) |
| +0x54…+0x74 | extended per-stream sizes (version ≥2 only) | |
| +0x7A | (byte) **XOR obfuscation key** | read into decoder state +0x47A |

Frame stream layout: frame *i* occupies
`dbOffset + state[0x78] + i * bytesPerFrame`, `bytesPerFrame = header(+0x10)`,
`state[0x78] = header(+0x20)`. Frame length in samples = `state[0x11D4]`
(used with `samplePos / frameLength` for random access).

### 10.4.3 Frame decode and synthesis

`FUN_10001830` (per-frame decode, driven by `ELQDecode` → `FUN_100018E0` loop):

1. **De-obfuscate**: `for i in 0..bytesPerFrame-1: payload[i] ^= key`, `key = state[0x47A]`.
2. **Unpack** parameters: `FUN_10002070` (reset) then
   `FUN_10002090(state, payload, bytesPerFrame)` — bit reader that fills the
   per-parameter arrays according to the header bit counts/widths.
3. **Synthesise**: `FUN_10001F90(decoderObject, state, out, arg)` calls the decoder
   object's method at vtable `+0x1C`, producing a **float** frame buffer
   (`float afStack_a3c[654]`), then converts to int16 with saturation:
   `if x > +K → 0x7FFF; if x < −K → 0x8000; else short(round(x + C))`
   (constants `_DAT_10015300/08/10`), i.e. **float internal precision, 16-bit linear PCM out**
   — matching the "linear" in the file name.
4. The decoder object (created by `FUN_10001E70/FUN_100021A0`, methods at vtable
   `+0x14/+0x18/+0x1C/+0x20`) is the actual LPC/CELP synth: it complains
   `"No pitch prediction, what's wrong"` and `"?No fixed codebook"` when the DB lacks
   the pitch (adaptive codebook) or fixed-codebook streams, and validates the filter
   orders: `"La dimensione del filtro lpc (%d) non …"`, `"La dimensione del filtro lpc wide (%d) non …"`
   → the codec is a **CELP/RELP vocoder** with an LPC synthesis filter (a short "lpc" and a
   "wide"/long-term or wideband filter), **pitch prediction** (adaptive codebook) and a
   **fixed codebook**, per-frame gains, and per-parameter bit allocation driven by the header.

### 10.4.4 Random access (this is what unit selection needs)

`FUN_100018E0(state, outPtr, outLenPtr, handle)`:
`frame = *pos / state[0x11D4]`; if `frame == state[0x11E0]+1` seek forward, if
`frame != state[0x11E4]` decode all frames up to it, then `memcpy` the requested
samples from the 2-frame cache at `state[0x11D8]` (current) / `state[0x11DC]`
(previous) and advance. Silence is emitted (`_memset(buf,0,frameLen*2)`) when a frame
is absent. ⇒ the voice DB is a **frame-indexed, randomly addressable CELP stream**,
which is how `FonAnalisi2Sintesi` concatenates arbitrary units from the `.sde` ranges.

### 10.4.5 Empirical geometry of the available voice (Ludoviko)

* file 5 069 459 B; `.sde` max end 15 829 000 decoded samples (≈989 s @16 kHz);
* divisibility search over `(headerSize, bytesPerFrame)` with frame lengths 160/240/320/480
  gives the consistent solutions
  `header = 59, bytesPerFrame = 102, 49 700 frames × 320 samples = 15 904 000` (+0.47 % vs SDE)
  and `header = 5, bytesPerFrame = 103, 49 218 frames × 320 = 15 749 760`;
* ⇒ **20 ms frames (320 samples @16 kHz), ≈102 bytes/frame (≈40.8 kbit/s)** for the
  Ludoviko DB version 10. (Header offsets inside the file are consistent with the codec's
  `dbOffset + state[0x78]` formula; `state[0x78]` is taken from the DB header itself.)

## 10.5 Reusable extracts produced for the re-implementation

| file | content |
|---|---|
| `engine_re/codecmsx_rdata.bin` / `codecmsx_data.bin` | Msx read-only data (VA 0x10015000) and data (VA 0x10019000) — quantizer/codebook tables (`DAT_10019510`, `DAT_1001B080`, `DAT_1001A73C`, `DAT_1001AC28`, `DAT_100192AC/A8`, `DAT_1001B040/68/3C/64`, …) |
| `engine_re/codec210_rdata.bin` / `codec210_data.bin` | same for the "210" codec (VA 0x10021000 / VA 0x1002D000 — the dispatch table lives at the start of `.data`) |
| `engine_re/Ludoviko.sde.txt` | decoded unit index (10 062 lines: `VERSION=7`, `N=3482,6953,6578`, 3482 `U=`, 6577 `D=`) |
| `engine_re/SpanishEs.csv`, `SpanishAm.csv`, `German.csv` | full pronunciation lexicons (SQLite → CSV) |
| `engine_re/vox.bin` | the Ludoviko codec bitstream (5 069 459 B) |
| `decomp_codecmsx.txt` / `decomp_codec210.txt` | decompiled codec DLLs (header parser `FUN_10001160`, unpack `FUN_10002070/90`, frame decode `FUN_10001830/E0`, float→int16 `FUN_10001F90`, DSP `FUN_100030C0…FUN_10005AB0`) |
| `decomp_loqtts.txt` | engine core: plugin resolution (~lines 32037, 79317), `Ctts*` classes, SSML, prosody |
| `decomp_util.txt` | `ELQBinaryHeader*`, `ELQBin*`, `ELQDB*`, `ELQXML*`, `ELQAtm*` implementations |
| `decomp_ludoviko.txt` | voice plugin dispatch (`GetVersion`, `ELQGetPhonemes`, `ELQVoiceChannelOpen/Close`) |

## 10.6 What still has to be derived (and exactly how)

The remaining unknowns are *localised*, not open-ended:

1. **Per-CELP-parameter bit widths and packing order** — read
   `FUN_10002090`/`FUN_10002070` in `decomp_codecmsx.txt` (bit reader) together with the
   header fields at +0x20…+0x50 and the widths at +0x2C…+0x4C; each stream is a
   contiguous bit-slice of the 102-byte frame.
2. **Quantizer/codebook tables** — already extracted verbatim in
   `codecmsx_data.bin` (VA 0x10019000 base; the arrays referenced as `DAT_10019510`,
   `DAT_1001B080`, `DAT_1001A73C`, `DAT_1001AC28`, … are at `VA − 0x10019000` in that file).
3. **LPC order / sub-frame partitioning per bitrate** — the switch on the bytes-per-frame
   value in `FUN_10001160` sets the orders (10 or 8) and 5-sample sub-frames for the
   high-rate modes; the "lpc"/"lpc wide" filter sizes come from the same fields.
4. **Float→int16 constants** — `_DAT_10015300`, `_DAT_10015308`, `_DAT_10015310`
   (in `codecmsx_rdata.bin`) hold the scale/clip constants.
5. **Which codec a voice uses** — resolve `dbunita`'s codec through the SDE plugin
   (`CatSdeData`) or by trying both decoders: the header's sample-rate/bytes-per-frame
   values must match the legal tables listed in §10.4.2.

**Acceptance test for a re-implementation of the acoustic core**: implement the codec
plugin (7 entry points) + header parser + bit unpack + CELP synth, then decode the
`.sde` ranges of a voice and compare: (a) decoded sample counts must equal
`end-start` of each `D`/`S` record; (b) a concatenation of e.g. `\demosentence` for
Ludoviko must produce the same number of PCM samples as the original engine and be
intelligible; (c) `ELQGetDecodedFileSize` must return the `.sde` maximum end.

## 10.7 Voice-data observations and the one remaining mapping question

Checks performed after §10.6 was written:

* `Ludoviko.16000.linear.256000.10.bin` (5 069 459 B): the last 64 bytes are
  `f4 ff f3 ff f6 ff f7 ff … 00 00`, i.e. **int16 little-endian near-silence**, and the
  byte histogram peaks symmetrically at `00/FF/01/FE/…` — consistent with 16-bit
  **linear PCM** (as the file name states: 16 000 Hz, linear, 256 kbit/s). No ELQ binary
  header keys (`Coding`, `BitRate`, `Endian`, `DataDescriptor`, …) and no big/little-endian
  sample-rate constant (8000/11025/16000/22050/32000/44100) exists anywhere in the file,
  and no single-byte-XOR variant of the first 0x100 bytes yields the codec header either.
* `Ludoviko.sde` is **100 % the 0x80-biased text index** (186 290 B, 10 062 lines, last
  byte is the final newline) — no binary tail, no codec header inside it.
* `.sde` range limit is 15 829 000; the `.bin` holds 2 534 729 int16 samples ⇒ a factor
  6.245. Correlating unit boundaries with PCM energy at plausible scales (÷4, ÷8, ÷16,
  ÷32) shows **no** alignment (median RMS at boundaries ≈ random RMS ≈ 18 7xx for all
  divisors), so the positions are neither sample indices, bit offsets nor byte offsets
  into this PCM file at any of those scales.
* The language/voice installers in this RAR ship **language data only** — the English
  pack yields exactly: `English{Gb,Us}.dbl` (SQLite lexicons), `English{Gb,Us}.gpr`
  (**1 230 841 / 1 009 561 B** — the GPR rule data used by `LTTS7GPR.dll`),
  `English{Gb,Us}.rex` (regex normalisers), `English{Gb,Us}.lde/.lcf` (descriptors),
  `LTTS7English.dll` (282 624 B) — i.e. **no `.sde`/`.bin`**. The Spanish pack
  (`Spanish{Am,Ar,Cl,Es,Mx}.{dbl,lde,lcf}`, `Spanish.rex`, `LTTS7Spanish.dll`) is the same.
  The only acoustic pair in the whole RAR is therefore the SDK's
  `Ludoviko.sde` + `Ludoviko.16000.linear.256000.10.bin`.

Consequences for the re-implementation:

1. The **unit index** (`.sde`: `U=`/`D=`/`S=` records) and the **sample database** are the
   two halves of a voice; their binding is done at runtime by the voice/SDE plugin
   (`CatSdeData` → "dbunita", `FonGetSamples` → samples). The index positions use a
   granularity that is *not* the stored byte/sample domain of the shipped `.bin`
   (either a finer position unit — e.g. the codec's internal sub-frame/pitch-mark domain —
   or the `.bin` is a *packed* representation despite its "linear" name).
2. To settle it, the shortest path is **dynamic/greybox**, not more static reading:
   (a) implement the two codec plugins' `ELQOpenDecoder/ELQDecode` per §10.4 and feed them
   the `.sde`-derived offsets; (b) or run `LoqTTS7.dll` under a debugger/Wine with a
   breakpoint on `ELQBinGetBuffer`/`ELQBinGetSmartBuffer` while the engine synthesises
   `\demosentence` for Ludoviko — the first calls reveal exactly which file/offset/size the
   codec is bound to and how `.sde` positions are converted to it.
3. Everything else needed to rebuild the acoustic core is specified: the plugin ABIs
   (§10.2, §10.4.1), the codec header/frame layout and de-obfuscation (§10.4.2/3), the
   random-access contract (§10.4.4), the CELP algorithm class with the exact functions and
   tables to port (§10.4.3, §10.5), the linguistic stack (`Fon*` procedures, SQLite
   lexicons, `.rex`, `.gpr`), and the prosody inputs (`BasePitch`, `BaseSpeed`,
   `Algorithm=Sequens`).

## 10.8 Where the codec's tables actually live (porting note)

Section layout of the shipped codecs (raw sizes matter):

| module | .text | .rdata | .data | other |
|---|---|---|---|---|
| `LTTS7CodecMsx.dll` | VA 0x10001000 / 0x14000 | VA 0x10015000 / **0x4000** | VA 0x10019000 vsize 0x31BC / **raw 0x2000** | .rsrc @0x1001D000, .reloc @0x1001E000 |
| `LTTS7Codec210.dll` | VA 0x10001000 / 0x20000 | VA 0x10021000 / **0xC000** | VA 0x1002D000 vsize 0x321C / **raw 0x2000** | .rsrc @0x10031000, .reloc @0x10032000 |

* Tables inside `.rdata` and inside the **raw** part of `.data`
  (VA 0x10019000–0x1001B000 for Msx, 0x1002D000–0x1002F000 for 210) are stored in the
  binaries and are provided ready to use in `codecmsx_rdata.bin`, `codecmsx_data.bin`
  (and the 210 equivalents), addressed by `VA − sectionVA`.
* Tables above the raw `.data` end (Msx: 0x1001B000–0x1001C1BC, e.g. `DAT_1001B038`,
  `DAT_1001B064`, `DAT_1001B080`, `DAT_1001C1A0…`) are **zero-initialised BSS filled at
  load time** ⇒ a re-implementation must port the *generating code* (the codec's
  initialisation functions, which build the quantiser/gain/codebook tables from the
  constants in `.rdata`), not copy those bytes.
* Same distinction applies to the float→int16 constants `_DAT_10015300/08/10`, which are
  stored in `.rdata` and are present in `codecmsx_rdata.bin` (offsets
  0x300/0x308/0x310 from VA 0x10015000).

---

# 11. Binary-free re-implementation: what is possible, and what is provably missing

## 11.1 Proof that the voice's acoustic module is not in this RAR

* `CatSdeData`, `CatVoiceVersion`, `GetSdeData` (the "dbunita" = unit-database plugin
  procedures) are referenced **only inside `LoqTTS7.dll`** (as `ELQPluginGetProc` names and
  in the log strings `Error loading dbunita from %s`,
  `Error loading GetSdeData procedure from %s`). A corpus-wide string/export/dispatch-table
  search over all 1 265 extracted binaries finds **no module that provides them**.
* The voice modules that *are* present implement a different slot set:
  * `LTTS7Ludoviko.dll` (voice, 57 344 B): `GetVersion`, `ELQGetPhonemes`,
    `ELQVoiceChannelOpen`, `ELQVoiceChannelClose` (dispatch table @VA 0x100086B0).
  * `LTTS7Esperanto.dll` / `LTTS7Spanish.dll` / `LTTS7German.dll` (language):
    `GetVersion`, `ELQGetGraphemes`, `ELQGetPhonemes`, `ELQGetLicenseMessage`,
    `Les*` (lexicon/morphology: `LesGetSymbolName`, `LesGetMorphTable`,
    `LesGetOrdinalStringTable`, `LesGetAbbreviazioni`, `LesGetNumeroAbbreviazioni`,
    `LesGetDefaultCurrency`, `LesWriteCateg`), `FonTrasParola`, `FonTrasConfini`,
    `FonAllofonoLingua`, `FonGetSamples`, `ELQLanguageChannelOpen/Close`,
    `ELQLanguageLoadReadOnlyData/UnloadReadOnlyData`.
  * Voice DLLs do **not** read files (their only imports are
    `ELQmalloc/ELQfree/ELQLogWrite/ELQSharedResource*`), so the sample-database I/O and the
    `.sde`→sample mapping live in the missing dbunita module.
* No file in the archive contains a voice-DB **codec header**: a full-corpus scan for the
  big-endian/little-endian header layout of §10.4.2 (legal sample rate at `+0x0C` followed by
  a legal bytes-per-frame at `+0x10`) over all 1 179 payload/engine files finds only two
  coincidences inside unrelated DLLs (`jaas_nt.dll`, `LTTS7jni.dll`) — none in any voice data
  file. The shipped `Ludoviko.16000.linear.256000.10.bin` contains no such header at any
  offset, in either endianness, and no legal sample-rate constant at all.
* ⇒ The acoustic model of the shipped voice (`dbunita` data + the code that consumes
  `Ludoviko.sde`) **is not part of `LTTSDirector7.rar`**. The `.sde` (text index) and the
  `.bin` are present, but their reader/authority is not, which is why no static mapping
  between `.sde` positions and `.bin` offsets can be derived from this archive alone
  (empirical tests in §10.7 agree).

## 11.2 What another agent *can* build today, with no Loquendo binary

A **functionally complete, binary-free TTS Director** is fully specified by this report:

1. **Application layer** — rebuild (or recompile from `src/`) the six jars: Director GUI,
   Manager, Engine client/server (RMI), Lexicon Manager, look&feel, utilities. Behavioural
   spec: §4 (interface), §4.2 (`read()` pipeline), §6 (GUI, menus, file formats, `.ltd`),
   §3 (launchers, install layout), §7 (policy files).
2. **Engine implementation** — implement the documented interfaces:
   * C API `tts_*` (`loqtts.h`, §5.2) and Java API `loquendo.tts.engine.*` (§5.1) with the
     same semantics, parameter ranges and event model; the JNI names to export are the 87
     `Java_loquendo_tts_engine_*` in `LTTS7jni.dll`.
   * Plugin interface struct used by the engine — procedures are resolved by
     `ELQPluginGetProc(plugin, "<name>", &slot)` and stored per module:
     `FonTrasConfini → +0x1C`, `FonGetSamples → +0x20`, `FonSetStile → +0x24`,
     `FonAllofonoLingua → +0x28`, plus `FonNewVoice`, `FonVidAllofonoVoce`,
     `FonVidIngloba`, `FonVidAllofonoAnalisi`, `FonVidMetaFonema`,
     `FonVidAnalisi2Sintesi`/`FonAnalisi2Sintesi`, `FonAllofonoAnalisi`,
     `FonTrasParola`, `FonIngloba`, `FonCommonIniChan`, `FonIniGlob`,
     `FonAllofonoVoce`, `FonOut`, and (dbunita module) `GetVersion`, `CatVoiceVersion`,
     `CatSdeData`, `GetSdeData`. A replacement module must export the *same names*
     (the engine looks them up by string) and fill the same slots.
   * Codec plugin ABI (7 entry points, §10.4.1) for whatever internal DB format the
     replacement engine uses.
   * **Substitute synthesis core**: rather than CELP with a missing DB, implement the
     allophone/unit layer with any backend (e.g., concatenate the shipped linear data if a
     DB is provided, or a formant/HMM/neural TTS), keeping the observable contract:
     sample rates/codings from `GetFrequencies`/`GetCodings`, per-voice `BasePitch`/
     `BaseSpeed`, LTD tags, prosody ranges, events, `saveCF`, EQ/DRC/mixer.
3. **Linguistic layer** — the data formats are known and reusable as-is:
   SQLite `.dbl` lexicons (§10.3, CSVs in `engine_re/`), regex `.rex`, `.lde/.lcf/.vde/.vcf/.ycf`
   descriptors, the `.sde` text unit index, and the `.gpr` rule data (needs its own format
   reverse, see §11.3). Unknown words then need a G2P implementation (rules, or a modern
   phonemiser mapped into the recovered SAMPA-like phoneme set, cf. `ttsGetPhonemeInfo`,
   `TTSLanguage.getPhonemeMap`, `ELQGetPhonemes`).
4. **Formats/behaviour to preserve for compatibility**: `.ltd` header keys, `.txt/.ssml`
   handling, `saveAudio` WAV/ASF, `\demosentence`, voice flavours → derived `.vcf`, RMI
   contract, registry keys and `LicenseCode`.

**Acceptance criteria for the binary-free build**
1. The Director GUI exposes the same commands/dialogs and speaks the text of any document
   with the same prosody controls; `.ltd` round-trips; WAV/ASF export works.
2. A stock client can `registerClient`, enumerate voices/languages, `read`, `stop`,
   `getOutBuffer`, `saveVoiceConfiguration`, `getPhoneticTranscription`,
   `GetSpeechAtomTree`, EQ calls — i.e. the RMI contract of §4.1 is honoured.
3. SAPI5 integration enumerates voices as SAPI tokens and speaks.
4. Lexicon editor round-trips `.dbl` (SQLite) lexicons; `.rex` normalisation and the
   `.lde`-driven language selection behave as specified.
5. Any module written for the plugin interfaces above can be dropped in and is picked up by
   `ELQPluginGetProc` naming (i.e. the plugin contract is honoured, not bypassed).

## 11.3 Remaining work for a *voice-identical* binary-free port

Two items, both bounded:

1. **Obtain (or capture) the dbunita module/DB.** Options: use a voice package that ships it
   (the packs in this RAR ship language data only — proven in §11.1), or run the original
   engine once under a debugger/Wine with a breakpoint on the dbunita `CatSdeData` and on
   `ELQBinGetBuffer`/`ELQBinGetSmartBuffer` while speaking `\demosentence`; the call log
   yields the DB file, its offset/size window and the exact `.sde`→frame mapping.
2. **Port the CELP/LPC decoder** from the already-decompiled codec sources
   (`decomp_codecmsx.txt`, `decomp_codec210.txt`): header parser (`FUN_10001160`),
   bit unpack (`FUN_10002070/90`), frame decode (`FUN_10001830/E0`), float→int16
   (`FUN_10001F90`), synth DSP (`FUN_100030C0`…`FUN_10005AB0`), with the tables from
   `codecmsx_rdata.bin`/`codecmsx_data.bin` and the runtime-built (BSS) tables ported from
   their generators (§10.8). Same for the `.gpr` G2P rule format if rule-based OOV
   pronunciation is required.

Neither item blocks the functional re-implementation in §11.2; both are required only for
bit-identical voice output of the original voices.

---

# 12. Authoritative description of the synthesis algorithm (vendor documentation)

The archive ships the vendor guides (`guides/ug/*` = Users Guide, `guides/pg/*` = Programmer's
Guide, `Loquendo_TTS_7_Java_Programmers_Guide.chm`; extractable with
`tools/7zz x -o<dir> <chm> -y`). The Users Guide states the algorithm verbatim:

> "The written text is first transcribed into a sequence of phonetic symbols, according to
> the grammar, the lexicon and the phonetic rules of the **Language**. Then, the phoneme
> sequences are mapped onto the **Vocal Database** of the **Voice**, which consists of a
> large collection of utterances recorded by a professional speaker and carefully labeled
> with phonetic and prosodic tags. The best matching speech fragments are extracted from the
> Vocal Database and concatenated to form the desired output speech. The fragments are chosen
> taking into account their intonation and their context."

and lists the processing chain:

1. split the character sequence into words and sentences (blanks, punctuation);
2. interpret/expand numbers, abbreviations, symbols and acronyms via tables and rules;
3. assign grammatical tags to words and resolve ambiguities from context;
4. assign pauses and intonation from punctuation and a minimal syntactic parse;
5. assign lexical stress and phonetic transcription per word (rules or lexicon);
6. transcribe the phrase in phonemes and assign prosodic labels;
7. **search the Vocal Database for the longest phoneme sequences** matching the
   transcription, taking context into account;
8. concatenate the corresponding signal fragments and apply signal processing for
   **concatenation smoothing and slight prosodic variations**.

This is the vendor's own confirmation of the decomposition derived in §10.2 — the engine is a
**unit-selection (concatenative) synthesizer** over a labeled speech database:

| Doc step | Recovered component |
|---|---|
| 1–2 | `FonTrasParola` / `FonTrasConfini`, `ELQToken*`, `ELQNum*` (118 number/date/telephone normalisers), `.rex` regex rules |
| 3 | `LTTS7Morphyzer.dll`, `LesGetMorphTable`/`LesGetSymbolName`, SQLite `.dbl` lexicon |
| 4, 6 | prosody/pause rules; `LTTS7GPR.dll` + `.gpr` data; `FonMetafonema` (metaphoneme mapping), SAMPA/SAMPA-2 phoneme alphabet |
| 5 | `.dbl` lexicon (`fonetica` column) + GPR rules for OOV |
| 7 | `FonAnalisi2Sintesi` (unit selection over `dbunita` = the `.sde` index), `ttsLocateSpeechAtomInventory`/`GetSpeechAtomTree` (speech atoms), `GetGilded` |
| 8 | `FonAllofono*`, `FonGetSamples`, `FonOut`; the codec decodes DB frames; per-frame smoothing/prosody |

Additional semantics confirmed by the Programmer's Guide: `BaseSpeed` is in **words/minute**,
`BasePitch` is in **hertz** (`Ludoviko.vde` ⇒ 95 Hz, `BaseSpeed=128`), `WinLangid` is the
Windows language id, SAMPA is the phonetic alphabet (`SampaSecondAccent` style flags in
`.ycf`), and the say-as family (generic/telephone/currency/code/hour/date/amount/
MasculineOrdinal/FeminineOrdinal) matches the Director's *Say As* menu; SAPI 5.1 XML
peculiarities (case-insensitive tags, `&amp;` escaping) are documented too.

**Consequence for re-implementation:** steps 1–6 are rebuildable from this archive (rules,
lexicon, descriptors, formats — §§10.3, 11.2). Step 7/8 are the acoustic core: they require a
labeled speech database. Because the shipped voice's database *authority* (the dbunita
module) is absent (§11.1), a binary-free port implements steps 7–8 over a **substitute**
database — either the shipped linear sample data if its layout is established by the runtime
trace of §11.3, or a new unit database built for the replacement engine, with the same
observable behaviour (longest-match selection, context-sensitive choice, concatenation
smoothing, slight prosodic variation).

---

# 13. SOLVED: the vocal-database (.bin) container and unit inventory (.sde) formats

The voice package `/run/media/.../Jorge - Spanish.exe` (Inno Setup 5.2.3, unpacked with the
freshly built `tools/innoextract-1.9/build/innoextract`) ships the *complete* runtime for one
Spanish voice: engine (`LoqTTS7.dll` 746 KiB, `LTTS7Util.dll` 551 KiB, codecs, all language
modules), the voice module `LTTS7Jorge.dll`, descriptors (`Jorge.vcf/.vde`, `JorgeGilded.gde`)
and the data: `Jorge.sde` (1 511 129 B), `Jorge.32000.LTTS7Codec210.44000.10.bin`
(29 144 430 B) plus two Gilded databases. Both data formats are now fully decoded.

## 13.1 `.bin` = `LOQUENDOTTS7` binary container (verified on 4 files)

```
offset  size   content
0       1      keyA                    (stored plain)
1       1      keyB                    (stored plain)
--- all following header bytes are XORed with  k = keyA ^ keyB -------------------
2       12     "LOQUENDOTTS7"           (signature)
14      2      u16 LE format version    (= 1)
16      2      u16 LE header_size
18      ...    TLV list up to header_size:
                 u16 LE tag, u16 LE size, size bytes (values are NUL-terminated ASCII)
                 tag 1 Name, 2 Label, 3 Comment, 4 Freq, 5 Coding, 6 BitRate, 7 Rank, 8 Version
-- from header_size on, the sub-header is plain, but the FRAMES are XOR-obfuscated ------------
   (corrected in S13.6: each 110-byte frame is byte-XORed with the key = sub-header byte 27)
hdr+0   28     7 x BE u32 sub-header:
                 [0] BitRate (bit/s)        [1] Rank
                 [2] samples per frame      [3] Freq (Hz)
                 [4] bytes per frame        [5] frame count
                 [6] (cookie/id)
hdr+28  n      frame_count * bytes_per_frame bytes of coded frames
```
Verified exactly (file size = header_size + 28 + frame_count * bytes_per_frame):

| file | key | hdr | Freq | Coding | BitRate | Rank | samples/fr | B/fr | frames | size |
|---|---|---|---|---|---|---|---|---|---|---|
| `Jorge.32000.LTTS7Codec210.44000.10.bin` | 0x02 | 122 | 32000 | LTTS7Codec210 | 44000 | 10 | 640 | 110 | 264 948 | 29 144 430 |
| `JorgeGildedPhrases...` | 0x7C | 148 | 32000 | LTTS7Codec210 | 44000 | 10 | 640 | 110 | 8 889 | 977 966 |
| `JorgeGildedParalinguistics...` | 0xE2 | 164 | 32000 | LTTS7Codec210 | 44000 | 10 | 640 | 110 | 9 958 | 1 095 572 |
| `vox.bin` (SDK Ludoviko voice, v7.3.0) | 0x39 | 125 | 16000 | linear | 256000 | 10 | – | – | – | 5 069 459 |

Sub-header check for Jorge: 122 + 28 + 264 948x110 = 122 + 28 + 29 144 280 = 29 144 430 ✔
(each coded frame is 20 ms of 32 kHz speech at 44 kbit/s; `640 samples/frame` is consistent
with `110 B/frame x 8 / 0.02 s = 44 000 bit/s`.)

Reproduction (no Loquendo code needed):
```python
d = open(path,'rb').read(); k = d[0]^d[1]
h = bytes(b^k for b in d[:256])
assert h[2:14] == b'LOQUENDOTTS7'
fmt, hdr_size = struct.unpack_from('<HH', h, 14)
# TLV from 0x12 to hdr_size, then 7 BE u32 at hdr_size, frames from hdr_size+28
```
This also retro-explains the earlier "0x7C header" hypothesis for the SDK voice: that number
came from the *per-file key byte* of `JorgeGildedPhrases` (0x7C), not from a header length.

## 13.2 `.sde` = unit inventory (bit-7-masked descriptor text)

`Jorge.sde` is plain text with bit 7 set on every character (newlines stay 0x0A):
`bytes(b & 0x7f)` yields 153 223 lines:

```
10,4
LTTSComponentVersion=7.0.0
N=3647,82007
U=# # @ @
L# !'E #-% "
R# #>E "
...
```
i.e. a component header (`<a>,<b>`, version), a unit count `N=<units>,<total>`, then per-unit
records `U=...` with left/right context records `L<n>/R<n>` whose numeric fields are written in
a printable alphabet. The reader lives in the engine/Util descriptor layer
(`ELQDataDescriptor*` / `ELQTagsDescriptor*`); details are being extracted in
`specs/SDE.md` (field-by-field decoding, cross-checked against the 264 948-frame geometry).

## 13.3 What this changes for the binary-free reimplementation

* The acoustic data of the shipped voice is **fully accessible without any Loquendo binary**:
  header rules, frame geometry, frame count and bit rate are all in the file, and the frames are
  stored unobfuscated (only the 122/148/164-byte header is XORed with a two-byte key).
* A reimplementation therefore needs: (1) a container reader (§13.1), (2) a `.sde` parser
  (§13.2), (3) the Codec210 decoder (§ specs/Codec210.md), (4) unit selection + concatenation,
  which is the engine/voice-module logic documented in §10 and specs/EngineBinding.md.
* The missing `dbunita`/`SdeDllMain` plugin (§11.1) is **not** needed: it is only used for
  "linked SDE" voices, selected by a `LinkedSde[...]= y` descriptor tag which the Jorge voice
  does not have; without it the engine reads `.sde`/`.bin` itself through `ELQSharedResource*`
  and the `ELQBin*` layer of `LTTS7Util.dll`.

## 13.4 Verified time base: 1 position unit = 10 microseconds

`JorgeGildedParalinguistics.sde` uses a second record type, `P=<name>|<start>|<end>`, with pipe-separated
fields. The 147 segments (`Aa, Aa_01..Aa_04, Ah, ..., Yawn_01..Yawn_04` - exactly the paralinguistic
"Extras" names of `JorgeGilded.gde`) are **contiguous** (`end[i] == start[i+1]`, zero gaps) and span
`0 .. 19 915 859`. The database holds 9 958 frames; `9 958 x 2000 = 19 916 000`. Hence:

```
1 frame = 2000 position units = 110 coded bytes = 640 samples = 20 ms   (32 kHz, 44 kbit/s)
1 position unit = 10 microseconds
```

converted back: `19 915 859 x 110 / 2000 = 1 095 372` bytes versus `1 095 572 - 164 (header) - 28
(sub-header) = 1 095 380` data bytes (the 8-byte difference is per-segment rounding at frame
granularity). This gives a *hard* consistency anchor for decoding the numeric fields of the main
`Jorge.sde` (positions there must lie below `264 948 x 2000 = 529 896 000`) and of
`JorgeGildedPhrases.sde` (below `8 889 x 2000 = 17 778 000`).

Record invariants extracted from the bit-7-cleared text (useful as parser self-checks):

| file | `N=` | `U=` records | L0..L9 / R0..R9 records | other |
|---|---|---|---|---|
| `Jorge.sde` | `3647,82007` | 3647 | 2584,2482,2379,2284,2160,2052,1911,1795,1676,1523 (each side) | 153 223 lines |
| `JorgeGildedPhrases.sde` | `261,2960` | 261 | 44,34,26,20,17,13,10,8,7,7 (each side) | 5 401 lines |
| `JorgeGildedParalinguistics.sde` | - | - | - | 147 `P=` cues |

## 13.5 `.sde` semantics (verified) and how units map to the database

`specs/SDE.md` + `tools/sde_parse.py` (agent "SdeFormat") decode the inventory from the decompiled
readers (`LoqTTS7.dll`) with every rule tied to a code address. Verified here independently:

* `N=3647,82007` = number of speech atoms / total `U=` tokens - re-counted exactly (3 647 atoms,
  82 007 tokens, 149 426 `L`/`R` records, 146 `S=`).
* `U=` line grammar: `<left-context> <p1..pK> <right-context>`; tokens are matched against the voice's
  phonetic table (`TabelleFonetiche` resource), `-` joins two phonemes into one token.
* `L<n>`/`R<n>` lines carry the atom's timeline in **base-93 printable numerals**
  (`while (c > 0x21) v = v*0x5d + (c-0x22)`, alphabet `"`=0 … `a`=63, `-` = digit 11 in this context);
  grammar `L<n> [!start] <dur> <val>`; slot `n` = 1-based phoneme inside the atom, `L` = left half
  (slot 2n), `R` = right half (slot 2n+1); only the first `L` of an atom carries an explicit `start`,
  later lines inherit the running end.
* Times are in the verified 10 us unit (S13.4). Max end = 529 894 060 vs `264 948 x 2000 = 529 896 000`
  (0.97 frame short) - the records tile the whole database in time order.
* **The atom times are NOT frame aligned**: `start % 2000` is uniformly distributed over 0..1999.
  So the engine must decode whole 110-byte records and splice at 10 us accuracy (the
  "concatenation smoothing and slight prosodic variations" of the vendor text, REPORT S12), rather
  than fetching whole frames per atom.
* `val` (10-bit field, observed 0..284, 207 distinct values) is per-half prosodic data shipped with the
  unit (pitch/period-like magnitude); `S=` sets a per-atom flag (Jorge: 146 x `I`; phrase DB: `e/i/f/x`).

**Consequence:** with §13.1 (container) + §13.5 (inventory) the only remaining unknown of the acoustic
path is the Codec210 frame decoder (`specs/Codec210.md`). Rendering then is: choose atoms by
phoneme+context match, decode the referenced 110-byte records to 640-sample frames, cut each half at
`start/2000` frames + `(start%2000)*0.32` samples, splice with smoothing.

## 13.6 CORRECTION: the coded frames are XOR-obfuscated (per-file key)

An earlier statement in this report ("the data region is not obfuscated") is correct **for the
container layer**: `ELQBin*` never transforms bytes (`specs/ELQBin.md` S4, proven at asm level), and
the 28-byte sub-header is stored in the clear. The *frame payload* after that sub-header is nevertheless
stored **XOR-obfuscated**, and it is the **codec** that un-XORs it (`LTTS7Codec210.dll`, jorge build):
`ELQDecode` (0x10004530) reads the sub-header with `ELQBinGetBuffer(bin, 122, 0x1c, 1, 0, &sub)` and then

```c
*(s16*)(decoder+0x11d0) = sub[19];   /* bytes_per_frame = 110 */
*(u8 *) (decoder+0x11e4) = sub[27];  /* XOR key = last byte of the cookie */
... per frame: for (i=0;i<110;i++) buf[i] ^= key;      /* FUN_10004290 */
```
and requests frame bytes as `ELQBinGetBuffer(bin, 110*frameIndex + 28 + header_size, 110, 1, …)`,
i.e. file offset `150 + 110*i` (matching the container layout of S13.1).

Independently re-verified here: de-obfuscating with `sub[27]` normalises the first byte of every frame
to the **same tag set `{0x38..0x3F}` in all three databases**, although their stored tags and keys differ:

| file | header key | sub[27] (frame key) | frame[0] as stored | frame[0] ^ key |
|---|---|---|---|---|
| `Jorge.32000.LTTS7Codec210.44000.10.bin` | 0x02 | 0x6D | 0x50..0x57 | 0x38..0x3F |
| `JorgeGildedPhrases…bin` | 0x7C | 0x15 | 0x28..0x2F | 0x38..0x3F |
| `JorgeGildedParalinguistics…bin` | 0xE2 | 0x91 | 0xA8..0xAF | 0x38..0x3F |

The most frequent payload bytes likewise converge (`0xc6/0xd7/0x92` -> `0xab/0xba` in file 1 and
`0xbe/0xaf` -> `0xab/0xba` in file 2). `tools/render_bin.py` de-obfuscates frames with this key
(`frame_plain()`); the frame tag set `0x38..0x3F` is a 3-bit mode field under a fixed 5-bit `00111`
marker, so the record-level bit layout starts at a fixed alignment.

Consequence for a reimplementation: frame bytes must be de-obfuscated before bit-unpacking; both keys
(header key `d[0]^d[1]` and frame key `sub[27]`) are readable from the file itself.

---

# 14. Engine ↔ voice binding, selection and the decoder contract (verified)

Full detail with code addresses: `specs/EngineBinding.md` (1 314 lines), `specs/SDE.md`,
`specs/ELQBin.md`. Summary of what a reimplementation must reproduce:

## 14.1 Descriptors and where the data files are found

* Descriptor family by type: `0 .rcf`, `1 .vcf`, `2 .lcf`, `3 .ycf`. A voice descriptor (`.vde`,
  named through the `.vcf` `BaseVoice` key, with `gdeInclude` -> `.gde`) registers up to 16 vocal
  databases.
* For each `VocalDBName[i]` the engine builds a `ELQBinaryHeaderLoadInfo(name, dir, log)` object
  (stored as `__BinInfo__[i]`): it **globs `*.bin` in the voice directory**
  (`LTTS7Util.dll FUN_10001fd0`: `ELQFileSearchIni(this,"*.bin")`) and matches the file's TLV tag
  `Label` case-insensitively against the name (`ELQstricmp(...,"Label")`). *Verified in
  `jorge_re/decomp_util_jorge.txt` at the cited lines.*
* The **variant** is chosen from the header tags `Freq`/`Coding`/`BitRate`/`Rank` compared with the
  `.vcf` keys `SetSampleRate`/`SetCoding`/`SetBitRate` (and the `Forced*` forms); with no match the
  coding name is forced to `built_in`.
* The **inventory** is a separate file: the engine appends the literal **`".sde"`** to
  `VocalDBPath[i]`/`VoicePath` (+`DataPath`) and registers it as a shared resource
  (`ELQSharedResourceAdd`, descriptor attribute `Id`). So `.sde` and `.bin` are opened by the engine
  itself; the optional `LinkedSde[...]` path (a `SdeDllMain` plugin) is not used by this voice.
* The engine's `.sde` reader handles **both generations with no version branch**: pass 1 reacts to
  `N`/`U`/`P`, pass 2 dispatches on tag characters `{A,D,L,R,F,S,U,P}`; `VERSION=` has no case and is
  skipped. Generation 1 (`LTTSComponentVersion=7.0.0`: `L<n>`/`R<n>` base-93 records, `S=`, `P=`) and
  the legacy generation (`VERSION=7`: `D=<order>,<S|D>,<start>,<end>,<pitch>` plain decimal) share
  the 10 us time unit and the same 8-byte half-slot pair `(start, (dur<<10)|pitch)`.

## 14.2 Per-unit synthesis path

* Per unit: `FUN_1001faa0` (driver) -> `FUN_1001ddd0` (reads the unit's `.bin` sub-header) ->
  `FUN_1001f580` (decoder request) -> `FUN_1001e3a0` (pitch-mark/PSOLA placement).
* Decoder ABI (codec plugin vtable `*(engine_sig + 0x1c)`):

```
int decode(openHandle, int startSample, int sampleCount, short *out, ELQBin binHandle);
```
  No frame index and no byte offset cross the boundary: the codec converts samples to frames/bytes
  itself (`frameIndex = samplePos / 640`, bytes at `150 + 110*frameIndex`, page 13.6) and un-XORs
  each frame with the sub-header key.
* Position conversion: `sample = pos * Fs / 100000` (10 us units), pre-roll/post-roll margin
  `Fs/500` samples (x4 for coding 2/4).
* Pitch and duration changes are **TD-PSOLA on the decoded signal** (marks placed from the recorded
  pitch marks, or uniformly at `Fs/125`, or at `Fs/pitchRatio`), never a resample.
* Voice module: single export (`Jorge` @ RVA 0x1170) dispatching an 8-entry `{name;proc}` table;
  `FonVidAllofonoVoce` is a no-op stub; `ELQVoiceChannelOpen/Close` provide the channel.
* Codec plugin: export @ RVA 0x4760 with an 8-name table; `ELQGetDecodedFileSize` always returns -1;
  `ELQBinGetSize(bin, which)` acts as a divisor (`1` -> byte size, `2` -> sample count);
  `ELQBinGetBuffer` always copies into a heap buffer; samples/frame = 160 @8 kHz, 320 @16 kHz,
  640 @32 kHz, with decoder lead-in 110/224/509 samples respectively.

**Worked example (paralinguistics unit `Aa`)**: `P=Aa|0|61846` -> start sample 0, length
`61846*32000/100000 = 19790` samples, decoder called `(handle, 0, 19854, out, bin)`
(19 790 + 0 pre-roll + 64 post-roll), i.e. frames 0..31 of `JorgeGildedParalinguistics…bin`.

## 13.7 Acceptance test already passing: inventory -> audio, binary-free

For the SDK voice (`engine_re/vox.bin`, `Coding=linear`, 16 kHz PCM; inventory `payload/Ludoviko.sde13`,
legacy generation) the whole chain was executed with only the tools in this repository:

```
sde_parse.parse(Ludoviko.sde13)  ->  units[i].d[] records (start/end in 10 us units)
sample = pos * Fs / 100000       ->  pcm[a:b]                       (render_bin.read_container/pcm_from_linear)
                                 ->  WAV
```
Observed for the first units:

| unit tokens | record | positions | samples | duration | RMS |
|---|---|---|---|---|---|
| `#` (pause marker) | `0,S,15769400,15779075` + `0,D,15779075,15794394` | 157.69 s .. 157.94 s | 1 548 + 2 451 = 3 999 | 0.250 s | **5.9** |
| `$` `#` | `0,D,2636850,2649844` | 26.37 s .. 26.50 s | 2 079 | 0.130 s | **609.9** |

The `#` unit (the alphabet's pause/silence symbol) cuts a near-silent segment (RMS 5.9) while a
voiced unit cuts an energetic one (RMS 609.9) - an end-to-end semantic check of the inventory
semantics, the 10 us time base and the container reader, with no Loquendo binary involved.

For the Jorge voice the identical code path runs once the Codec210 frame decoder exists
(`tools/render_bin.py` already de-obfuscates frames with the key from sub-header byte 27 and calls
`codec210.decode_frame`; frames are at `150 + 110*i`, 640 samples each).

---

# 15. Codec 210: ABI, frame layout, and verification against the real decoder

Full detail: `specs/Codec210.md` (599 lines), tables `tools/codec210_tables.json` (188 KiB),
prototype `tools/codec210.py`, table extractor `tools/codec210_extract.py`, and a **reference oracle**
`tools/codec210_oracle.py` that runs the *real* `LTTS7Codec210.dll` under Unicorn emulation to produce
ground-truth PCM.

* Plugin ABI: single export `LTTS7Codec210` (RVA 0x4760) = `{name;proc}` dispatcher over 8 entries
  (`LoadUtilSymbols`, `GetVersion`, `ELQOpenDecoder`, `ELQCloseDecoder`, `ELQGetDecodedFileSize`,
  `ELQGetDecoderDescription` = `"Loq210"`, `ELQDecoderFileChanged`, `ELQDecode`); the DLL imports only
  `KERNEL32` and binds the five Util entry points (`ELQBinGetBuffer`, `ELQLogWrite`, `ELQfree`,
  `ELQmalloc`, `ELQstricmp`) at load time.
* A frame is **880 bits = 110 bytes** with a layered sub-band CELP layout: 8 kHz core
  (`wideband` 1b, `mode8` 4b, 5x6b LSF order-10, 5b frame energy, 4x{7b pitch index, 7b lag, 3b,
  16x6b codebook}) + 16 kHz band (1b, 3b mode, 2x6b LSF, 4x{4b gain, 10x(1b sign + 7b index)})
  + 32 kHz refinement (1b, 3b, 2x6b LSF, 4x5b). The bit reader consumes **880/880 bits on every
  frame** (verified over whole blocks, including the last frame of the file) - a very strong check
  that the field layout is right.
* **Exact** (reproduced byte-for-byte against the decoder's own internals): container + sub-header,
  per-frame XOR key/length, bit reader, field layout, LSF VQ (order-10 5-stage and order-8 2-stage,
  with the documented ramp tables), LSF -> LPC (P/Q sum-difference with `cos`), and the float -> int16
  clamp/round.
* **Root cause of the remaining gap, located** (fresh jorge dump `jorge_re/decomp_codec210_jorge.txt`,
  created here): there is **no unidentified filter-bank stage**. In `FUN_1000e170` the two buffers the
  verified combine reads are produced 4 lines earlier by the polyphase interpolator itself:
  `+0x2c` = `+0x28` shifted by a lag, `+0x34` = output of the upper-band LPC synthesis, then
  `A = FUN_10003960(+0x2c, 0x100240a8)` and `B = FUN_10003960(+0x34, 0x100241a8)`, immediately followed by
  `FUN_1000c290(out, A, B)` = `out = clamp(round(2*(A-B)))` (correlation 1.000000 when fed the real
  buffers). `FUN_10003960` (jorge VA 0x10003960) is a 4-phase polyphase FIR with a delay line, a
  coefficient strip pair and a tail state carried across frames, i.e. exactly the stage that is still
  unported; porting it (plus the two input buffers) is the whole remaining work on the output path.
* **Still approximate** (being closed): the frame-energy/gain dequantiser (currently fitted),
  the 3-tap pitch/adaptive-codebook excitation, and the QMF band re-combine. Measured against the
  oracle on voiced frames (37..42 of the Jorge DB, key 0x6D): RMS is in the right ballpark
  (4934 vs 3890) but the waveform correlation is only ~0.02, i.e. the spectral envelope is right and
  the excitation is not yet.

**Verification harness (works now):**
```
/tmp/uv/bin/python tools/codec210_oracle.py 37 6 0x6d /tmp/ref2.raw      # ground truth from the real DLL
python3 tools/codec210.py                                                # prototype: RMS per 10 frames
```
Unicorn 2.1.4 + pefile are installed in the venv `/tmp/uv`; the oracle binds the five Util entry
points to Python stubs, fixes the x87 control word and replaces the MSVC CRT allocator entry points so
the unmodified DLL runs.

## 15.1 End-to-end commands that work today (binary-free)

```
# 1. inspect any voice database container
python3 tools/bin_dump.py jorge/pf/Loquendo/LTTS7/data/voices/Jorge/Jorge.32000.LTTS7Codec210.44000.10.bin

# 2. inventory -> audio for a `linear` (raw PCM) voice - fully exact, no decoder needed
python3 tools/render_unit.py engine_re/vox.bin payload/Ludoviko.sde13 2 /tmp/u2.wav

# 3. inventory -> audio for the Jorge voice (Codec210 decoder; excitation still approximate)
python3 tools/render_unit.py \
    jorge/pf/Loquendo/LTTS7/data/voices/Jorge/Jorge.32000.LTTS7Codec210.44000.10.bin \
    jorge/pf/Loquendo/LTTS7/data/voices/Jorge/Jorge.sde 1 /tmp/jorge_u1.wav
```
Observed: (2) unit `$`+`#` -> 2 079 samples, RMS 609.9; (3) unit `#`+`` `a ``+`#` -> 7 748 samples
(0.242 s @ 32 kHz), RMS 4081.3 - the vowel `a` cut out of the coded database by the pure-Python chain.

## 15.2 Decoder architecture as now established (jorge build)

`tools/codec210.py` implements the following chain; the stages marked *exact* were each validated
against the real DLL (either by reproducing the decoder's own intermediate buffers or by correlation
1.000000 against the emulated decoder):

```
ELQDecode
  per 110-byte frame: un-XOR with sub-header[27] (exact)
  bit reader, 880 bits/frame, 182 reads, err=0 (exact layout)
  dyadic cascade 8 kHz -> 16 kHz -> 32 kHz:
     8k core : pitch (FUN_10006bb0) + 2 x segmented fixed codebook
               desc {dim 5, count 8, bits 6, no sign, table 0x10021bd8}
     16k band: coded branch, 2 x fixed codebook
               desc {dim 8, count 5, bits 7, sign, table 0x10022470}
     32k band: NOISE branch (mode object +0x28 == 0): read(5) -> gain dequantiser
               FUN_10011aec + energy FUN_10002ec0 + noise source, ramp + tilt gain
  per-level LSF VQ + interpolation/stabilisation + LSF->LPC (exact)
  per-level LPC synthesis, transposed DF-II (exact)
  band filter FUN_10003960 = 4-phase polyphase interpolator with delay line and tail state
       (ported; reproduces the real output with correlation 1.000000, max abs diff 5e-4)
  combine FUN_1000c290: out[i] = clamp(round(2*(A[i]-B[i])))        (exact)
       A = band_filter(obj+0x2C, coeffTable 0x100240a8)   (the dominant path: corr(2A, out) = 0.991)
       B = band_filter(obj+0x34, coeffTable 0x100241a8)
```

Remaining (ordered, in `specs/Codec210.md` S10.2): 8k pitch + codebook excitation, the ring-window
addressing of `obj+0x2C` (currently correlation 0.958 with the previous level's A output), the 16k coded
branch, the 32k noise branch, and the exact 5-bit frame-energy dequantiser. With those ported the
decoder becomes sample-exact; the oracle (`tools/codec210_oracle.py`, Unicorn emulation of the real DLL)
supplies ground-truth PCM for any frame range so each stage can be checked individually.

**Current fidelity, stated plainly:** the pure-Python chain reproduces the coded *envelope* (RMS within
~2x, correct silence/speech segmentation, correct bit consumption) but not yet the waveform
(correlation 0.006 on voiced frames). The repository tools therefore render structurally correct audio
from the real database, while sample-exact reproduction of the original voice still needs the excitation
stages above.

---

# 16. What remains, exactly (handoff)

Everything below is the *complete* list of work left for a 1:1 binary-free reimplementation. Nothing
else is unknown: the application, the installer, the engine API, the voice/DB/inventory/language formats,
the engine<->voice binding, the unit->decoder path, the codec's bit layout, spectral model, band filter
and output combine are solved and verified (S1-S15, `specs/*.md`).

## 16.1 Codec 210 excitation chain (the only thing between us and sample-exact audio)

Ordered, each step validated against `tools/codec210_oracle.py` (ground truth from the unmodified DLL):

1. **8 kHz LTP/pitch - SOLVED EXACTLY** (this pass, by emulator instrumentation; zero residual on 12/12
   pitch calls across frames 20/38/60). `FUN_10006bb0` (jorge VA 0x10006bb0) is called from `0x10009c0d` per
   subframe with `(h, 17, 144, 0, pitchDesc 0x100237e4, 40, &lag, &gains, bitreader, scratch, 0, 0, 2.04, 0)`
   and computes, with `lag = first 7-bit field + 17`, `idx = second 7-bit field`,
   `g[k] = int8[0x10022150 + 3*idx + k]/64 + 0.5`:

   ```
   S      = buf[h-(lag+1) : h-(lag+1)+120]        # 120-float copy taken BEFORE the outputs are written
   out[i] = g[2]*S[i] + g[1]*S[40+i] + g[0]*S[80+i]     # i = 0..39, exact (err = 0.000)
   ```
   Buffer maintenance (also measured): the frame base is fixed, `h = base + 40*sf`, and at every 8 kHz frame
   start a 145-float `memmove` from `base+15` to `base-145` runs (from `0x100096fc`), i.e.
   `buf[base-145:base] = buf[base+15:base+160]` - the excitation is one running array with 145 floats of
   history. Proven gains/lags per frame: f20 lags 59/78/29/115; f38 71/66/94/93; f60 82/72/69/80.
   Probes kept in the repository: `tools/oracle_ltp_probe.py` (captures + verifies the model) and
   `tools/oracle_attrib.py` (reliable write->code attribution).

   *Instrumentation trap worth recording:* the EIP reported inside a `UC_HOOK_MEM_WRITE` callback is not
   reliable in this Unicorn setup (it mis-attributed the excitation writes to the wrong function), and
   `UC_HOOK_MEM_READ` barely fires; reliable attribution needs a global `UC_HOOK_CODE` hook keeping the last
   executed address, and call-site stack snapshots for arguments.

   *Original open question (kept for context):* the *geometry* is proven by direct
   emulation tracing (read watchpoint on a real pitch call: exactly 120 reads at 4 instructions, spanning
   `h-72 .. h+47` for a declared lag of 71 = `h-(lag+1)`, i.e. the three delayed windows at lag+1, lag,
   lag-1) and the history priming is identified (a 580-byte `memmove` of the previous frame's LTP tail,
   145 floats, at the start of every 8 kHz frame from `0x100096fc`). What is still missing is the **gain
   dequantiser / index mapping**: the table read gives ~-0.05 while the subframe output RMS is 431, and a
   free 3-tap least-squares fit over the traced windows reaches only 0.57-0.61, so the coefficient values
   are not the ones assumed. A numeric solve `dest = g0*w0 + g1*w1 + g2*w2` over the scratch blocks was run
   and **failed with residuals exceeding the signal**, which rules out the assumed tap-window model:
   the 120 traced reads are *120 consecutive floats* (h-72 .. h+47) copied as three 40-blocks, i.e. a
   **linearisation of a ~120-sample circular buffer**, and the FIR then combines the three linearised blocks
   at offsets that are not the lag-1/lag/lag+1 triple - so the taps read the *already written* samples of
   the current subframe. The remaining measurement is one direct observation, specified in
   `specs/Codec210.md` S10.4: single-step the FIR loop from `0x10006e20` and log (scratch source address,
   coefficient address) pairs, which yields the tap offsets and the coefficient stride with no hypothesis
   left; then the 32 kHz and 16 kHz excitation branches complete the chain.
1b. **Innovation stage (remaining blocker, state of the chase).** Verified by emulator instrumentation:
   the scale/gain helper `FUN_10002da0` is called at `0x10009da4` (CB1, dst `0x300125f0+0xa0*k`) and
   `0x10009fda` (CB2, dst `0x3000e0a4`) with the multiplier as the *second stack argument*; measured values for
   frame 38 are 1245.3 / 366.36 (ratio 3.399 = q[4]/q[1], and CB2/CB1 = 1/2.2), which pins the law
   `g = C(g8)*q[b3]` with `C(27) = 958.5 = 0.430*1.3305^27` (the previously fitted 0.5 factor is wrong and
   has been removed). `FUN_10002ec0` is a plain energy (`sum(p^2)`), `FUN_10011aec` is the MSVC CRT
   intrinsic dispatcher, *not* a dequantiser - the gain arithmetic must be read at the CB call sites.
   The 8k-core call graph is mapped (`0x100011d0` bit reader, `0x10002da0` scale, `0x10005520`/`0x10005390`
   LSF interp/stabilise, `0x100030e0` LPC synthesis at `0x1000a14a`, `0x10011aec` once/frame). Open: the
   **domain/scale in which the innovation is summed into the excitation** - the LPC-synth call arguments are
   `(0x30012870 LPC coeffs, 0x30011ea0 output, 40, 10, 0x30012930 [rms 125, varies: excitation candidate],
   0x300082e0 [rms 584.7 *constant across subframes*: not excitation], 0x30007fe0)`, while the LTP output
   buffer (`0x30012364`, rms 1273) is ~10x larger than the candidate excitation, i.e. the excitation appears
   to live in a normalised domain that the LPC gain restores. Next measurement: capture the multiplier at the
   CB call sites per call and least-squares-fit `exc ~ a*ltp + b*cb1 + c*cb2` against the true excitation
   buffer (see the correction below).
   *Correction and last verified facts:* the 8k LPC synthesis `FUN_100030e0` is a transposed-DF-II all-pole
   filter (`x = in[i] + state[0]; t = -x; state[k] = coef[k]*t + state[k+1]; state[order-1] = t*coef[order-1];
   out[i] = x`) and it runs **in place on the excitation buffer itself** - the write timeline below shows
   `0x1000a14a` (the synthesis call) as the last of six writers of `0x30012364+40*sf`. `0x30011ea0` and
   `0x300082e0` have *identical* rms across all subframes (4180.2 / 584.7) and were **not written at all**
   during frame 38, so they are coefficient/state-like arrays, **not** the excitation; the earlier candidate
   list and the stage-local gate built on them are void (an earlier argument-role fit that suggested
   `0x30011ea0` was the input is superseded by this timeline). Also the probed addresses `0x1000a14a` and
   `0x10009d9f` are *not* the call instructions (their first stack dword is an argument, not a return
   address), so argument maps taken there are shifted - hook the actual `call` opcodes found by disassembly.
   Method that worked for the LTP and should close this stage: hook the precise call, snapshot the arguments,
   re-implement the callee in Python from its decompilation, and brute-force which argument assignment
   reproduces the observed output exactly.
   *Decisive result:* the 8 kHz LPC-synthesis input is **exactly the LTP output** - a least-squares fit
   `exc = a*ltp + b*cb1 + c*cb2` returns `(1.0, 0, 0)` with residual ~1e-12 for all four subframes of frame
   38. So the innovation is **not** summed into the 8 kHz excitation; it must be folded into the
   **adaptive-codebook history** that the LTP copies from (`buf[h-(lag+1) : +120]`), which is also why a port
   that maintains its own history without that priming diverges immediately (the LTP formula was verified
   against the real emulator scratch, i.e. it is exact *given the real history*). The last link is therefore
   to find the write that primes that history region (reliable attribution: global UC_HOOK_CODE + last
   executed address), and the clean gate is to match the port's own 120-float LTP window against the
   emulator's per subframe (target corr >= 0.999) before measuring end-to-end.
   *Follow-up counter-evidence:* the excitation region (`0x30012364+160*sf`) has **three writers besides the
   pitch call** - the codebook-synthesis sites `0x10009b6f`, `0x10009f3e`, `0x10009ff1`, each reached with an
   argument frame carrying **two gains** (a common 215.763 plus 1245.3 / 566.02 / 2.7489 respectively; all
   with `ebx = 0x30012364`, `esi = 0x3000de20`). So the 8 kHz core writes the excitation region more than
   once per subframe - i.e. the innovation *is* accumulated into the excitation (most likely after the LTP),
   and the "`exc == LTP`" reading must have been taken at an instant before/after that accumulation. The
   correct next measurement is a write timeline at 0x30012364+160*sf: pitch-entry, pitch-exit, after each of
   the three codebook sites, and at the LPC entry - which shows exactly where and with which gain the
   innovation enters, after which the port's LTP window S can be matched against the emulator's per subframe.
   (The port's current S is ~50x too large because its LTP recurses on itself without that renewal, which is
   also what keeps the real predictor stable.)
   *Settled by the write timeline (hooked at 0x10009b6f / 0x10009f3e / 0x10009ff1 / 0x1000a14a, reading both
   0x30012364 and 0x30011ea0):* the 8k core **clears the excitation region sample by sample** at 0x10009b6f
   each subframe, then accumulates the two/three codebook passes **and** the LTP into that same region, and
   only afterwards copies it to the LPC input 0x30011ea0 (which therefore reads `exc == LTP` at the LPC call
   while the *history* the LTP copies from is the innovation-refreshed buffer). That clear+rebuild is exactly
   what a naive port omits, and it is what makes the real predictor stable. The remaining port work is to
   reproduce the sequence `clear -> CB1 -> CB2 -> LTP -> copy to LPC input` with the measured gains
   (215.763 / 1245.3 / 566.02), then re-run the S gate (port S vs emulator S, corr >= 0.999).
1c. **Status of the innovation mapping (gap still open, with a golden dataset).** The accumulation
   architecture is closed and the port now reaches **correlation +0.51** (independently re-verified: global
   corr 0.465 over frames 0..59, per-10-frame 0.70/0.36/0.51/0.61/0.20/0.82) with the RMS envelope tracking
   the reference. What is still wrong is the *shape* of the innovation contribution: measured per subframe
   (frame 38) the exact stage values are
   `exc_stages_frame38.json` in `jorge_re/` - arrays for each subframe: values after the clear, after the LTP
   write, after the CB1 accumulation and after the CB2 accumulation, plus the parsed 16 six-bit indices.
   Negative results (so the next attempt does not repeat them): the CB1/CB2 increments are **not** reproduced
   by "8 six-bit indices -> 8 concatenated 5-sample segments of table 0x10021bd8 scaled by 1/32" for any
   tested index split (first8/last8, last8/first8, evens/odds, odds/evens), sign (+-1) or scale
   (1/32, 1/64, 1/16, 1), nor is each 5-sample position explained by any single table segment
   (`tools/oracle_cb_probe.py` prints the best segment per position: residuals 0.4-4.7 relative, scales
   0.03-0.6). So the true mapping is of a different kind (e.g. filtered/interpolated codebook vectors, a
   different arrangement of the 40 samples, or the writes at 0x10009f3e/0x10009ff1 applying a
   multiply-accumulate rather than a plain add). The golden dataset above is the target to fit.
1d. **Consolidated state after the closing push** (all measured):
   * The innovation codebook mapping and the gain law are **exact**: with the golden dataset the measured
     CB1/CB2 increments equal `gain * codebook_vector` position by position (frame 38 sf0: port vector
     [-0.09,-2.12,0.16,1.09,0.22] x 1245 = the measured [-116.74,-2646.17,194.57,1362.0,272.4]), so the
     8 six-bit indices -> 8 concatenated 5-sample segments of table 0x10021bd8 at 1/32, times
     `gain = C(g8)*q[b3]`, is confirmed (my earlier negative result was a bad fit that ignored the known
     gain). The fitted `exc_scale` (3.5) is removed - the excitation now carries no fitted constant, and the
     output is correspondingly ~4x quiet, i.e. the missing gain is in the **output path**, not in the loop.
   * The real 8k history is **bounded and carried**, never reset (frames 30..41: history rms 0.6/0.7 ... 1336
     /1879/2434/1869 against excitation rms 0.6/0.7 ... 1866/2327/1786/1070), while a port that injects too
     much innovation diverges - the reason the fitted 3.5 was fatal inside the recursive loop.
   * Real A32/B32 amplitudes vs the port (agent measurement, frames 37/38/39): real
     rms(A32)=617.5/2382.0/2539.1, rms(B32)=83.2/53.3/30.6, rms(2(A-B))=1246.6/4765.1/5078.5 (matching the
     reference exactly => the combine is right) versus port pcm 675.9/1954.4/890.9 - i.e. 1.8x/2.4x/5.7x
     low **and not a constant ratio**, so the A path differs in *content* (the excitation residual), not by a
     gain. B32 is 3-13% of A32, so it is not the main error.
   * S gate (my measurement, frame 38, real window read at the pitch call's return): real window rms
     545/2509/2539/515 versus port 1234/1559/1542/1845 with corr 0.03-0.37 - the port's *window* differs
     because its per-subframe state has drifted; the full-buffer comparison after 38 frames gives corr 0.739
     (frame part) / 0.849 (history part) with no index shift, so the port tracks the real state but with a
     ~26% shape error that accumulates from the fitted gain law and the missing bands.
   * Port status: excitation vs golden corr 0.66/0.69/0.70/0.03 with matching rms; end-to-end corr 0.51 over
     frames 0..119; envelope tracks the reference. Ordered next steps: exact `C(g8)` (a table/derived law
     rather than the 0.2%-fit) to stop the state drift, the A-path amplitude (dump real A16 and check each
     band_filter stage's gain), then B32 and the 16k coded branch.
3. **32 kHz noise branch** - mode word `+0x28 == 0`: `read(5)` -> dequantiser `FUN_10011aec` +
   energy `FUN_10002ec0` + noise source + ramp `_DAT_100242f8` + tilt gain.
3. **16 kHz coded branch** - `read(4)` + 2x segmented codebook `FUN_100029c0` with descriptor
   `0x10023a5c` = {dim 8, count 5, bits 7, sign, table 0x10022470}.
4. **Exact 5-bit frame-energy dequantiser** (currently a fitted `A*B^g8` mapping) and the exact
   cross-frame state: the port and the oracle must agree from frame 0 (silence frames 0..36, ramp 37..42),
   not from a cold start mid-file.

Acceptance for 1-4: correlation >= 0.9 (target ~1.0) between `Codec210().decode_frame(raw, key)` and
`/tmp/uv/bin/python tools/codec210_oracle.py <first> <count> 0x6d out.raw` over frames 0..40, RMS within
+-5%. The A path dominates (`corr(2*A32, out) = 0.991/0.9997`), so step 1 alone should already lift the
end-to-end correlation sharply.

## 16.2 Linguistic leftovers (needed for OOV/foreign words and non-Spanish languages)

* `Spanish.lex` / `Spanish Automotive.lex` / `SISpanish.lex`** are compiled binary lexicons/rules
  (common 16-byte header `ca fe db 60 df e3 dc a4 c9 a5 85 f3 96 e4 97 fe`; neither bit-7 clearing nor
  XOR `d[0]^d[1]` yields text). They implement the regular grapheme->phoneme rules and the say-as styles
  (`AddressSpanishEs.ycf` -> `Spanish Automotive.lex`). A reimplementation can substitute a rule-based or
  statistical G2P producing the documented phoneme alphabet (`specs/SpanishLanguage.md`).
* Other languages' `.gpr` rule files (English/German/... present in the engine distribution) are an
  un-reversed format; Spanish ships none.

## 16.3 Optional fidelity items

* The `Patch.exe` voice-licensing crack (S8) - documented, not needed for a reimplementation.
* Director GUI pixel-detail: the behaviour, menus, dialogs and file formats are specified in S4/S6; the
  recovered Java sources in `src/` are the reference if exact widget fidelity is wanted.

## 16.4 CLOSED: the 8 kHz excitation chain is exact (this pass)

Two structural bugs were found and fixed in the port (`tools/codec210.py`), both by emulator measurement:

1. **The LTP window is three overlapping 40-float windows, not one contiguous 120-float slice.**
   Memory scans place the scratch's three blocks at `w0`, `w0+1`, `w0+2` (w0 = h-(lag+1)) for every
   subframe - i.e. the FIR is the plain 3-tap predictor at lags `lag+1, lag, lag-1`.
   Fix: `out[i] = g[2]*buf[w0+i] + g[1]*buf[w0+1+i] + g[0]*buf[w0+2+i]` (probe: `tools/oracle_find_window.py`).
2. **The exact innovation gain law** (`specs/GainLaw.md`): `gain = float32(EXC_Q[b3] * float32(exp(g8/3.5)))`
   with the real 8-entry Q table at VA 0x10023db8, second pass scaled by the exact double `5/11`
   (0.45454545454545453 at VA 0x10023ee8), and every stored sample rounded to float32.
   Verified to 9.8e-08 over 284 sub-frames.
3. **The missing 16 kHz level combine** (`out16 = 2*(A16-B16)`, APath task): band_filter has an intrinsic
   flat gain of 1/2 per call, so the port was exactly 2x low; fix adds `out16 = [2*v for v in a16]`
   (probe/evidence: `specs/APath.md`).

Results (pure-Python decoder vs the real DLL under Unicorn; harness `tools/verify_codec.py`):

| range | global corr | amplitude ratio |
|---|---|---|
| frames 0..119 | **+0.9925** | 0.983 |
| frames 0..299 | **+0.9894** | 0.983 |
| loud windows (e.g. 40-49) | **+0.9993** | 1.000 |
| quiet/noise windows (0-39) | 0.51-0.82 | ~0.4 |

The S gate (`tools/oracle_sgate.py`) now reports **corr +1.0000 on all four subframes** with window rms
matching to 0.05% - i.e. the adaptive-codebook history, the LTP, the innovation gains and the float32
rounding all reproduce the real decoder.

**Upper bands CLOSED (same pass, `specs/UpperBands.md`).** B16 (16 kHz coded) and B32 (32 kHz noise) are now
ported: 16 kHz gain `(E+1)*exp(g4*0.27027027-0.15556)/norm16` with `norm16=(d8+0.01)/(0.01+d16)`, codebook
desc 0x10023a5c (128x8 table 0x10022470, x1/32, sign, second pass x0.4), 32 kHz gain
`exp((idx5-10)*0.125)/norm32` with the noise `(-1)^i` ramp, x0.7, source `2*exc16` zero-interleaved, plus
the 16 kHz level combine `out16 = 2*(A16-B16)` and the first-frame LSF rule (obj[+0x1c]).  Every DLL buffer
is reproduced at corr 1.000000 (frames 37/38/39) and the patched port now measures:

| range | global corr | amplitude ratio |
|---|---|---|
| frames 0..119 | 0.9995 | 0.995 |
| frames 0..299 | **0.9975** | **0.991** |
| loud windows | 0.9949-1.0000 | 0.99-1.00 |
| silence windows 0..39 | 0.90-0.96 | 0.6-0.8 (dither level, +-1 int16 LSB) |

**Remaining residual:** 20 of 299 frames still show an 8 kHz-chain drift (worst window 120-129: 0.6538;
frames 119-129, 150-179).  The upper-band stages track the 8 kHz input at 0.999+ even there, so the drift is
in the 8 kHz LSF/interp/LPC path or its per-frame state (frame 119 exc8 = 0.948 but sig8 = 0.926, frame 120
exc8 = 0.922 and sig8 = 0.636 - i.e. the *synthesis* diverges more than the excitation).  This is the last
open item; a follow-up task targets exactly those frames (dump the real LSF/LPC arrays and the synthesis
state and diff against the port).

## 16.5 CLOSED: the 8 kHz LTP ring rule and the final acceptance numbers

The last drift (20 of 299 frames) was root-caused in `specs/DriftFrames.md`: the DLL's tap windows are a
**cyclic read of the `lag` samples ending just before the current sub-block** - the current (cleared)
sub-block is never read:

```
w0 = p-(lag+1)
RING[k] = buf[w0+k]                    for k <= lag
          buf[w0 + 1 + ((k-1) % lag)]  for k >  lag
out[i]  = g2*RING[i] + g1*RING[i+1] + g0*RING[i+2]
```
For `lag >= 41` the ring does not wrap inside the 42 taps used, which is why only `lag <= 40` sub-frames
drifted. Evidence: the DLL's own 120-float tap scratch (0x3000e0a4) - e.g. frame 118 sf1 (lag 20), tap k=21
equals `buf[w0+1]` while the plain form reads `buf[w0+21]`. LSF VQ, interp weights, stabilisation margin,
VQ ramps, LSF history, LPC state and layout were all checked and are **exact** (DLL arrays 0x300128a0 LSF,
0x30012870 LPC, 0x30012a20 tilt match at corr 1.000000 on every frame, including the drift frames); the
first diverging array was always the excitation, and inside it only the LTP (CB1/CB2 exact everywhere).
Boundary variants were measured (wrap threshold and modulus); the DLL-matching best is threshold `lag`,
modulus `lag` (global 0.99965 vs 0.99913 for modulus `lag+1`).

**Final acceptance (pure-Python decoder vs the real DLL under Unicorn, harness `tools/verify_codec.py`):**

| metric | value |
|---|---|
| global correlation, frames 0..299 | **0.99965** |
| amplitude ratio (rms) | **1.001** |
| speech 10-frame windows (>= frame 40) | min **0.9991**, median **1.00000**, **19 of 26 exactly 1.00000** |
| silence windows (frames 0..39) | 0.90-0.97 (dither level; +-1 int16 LSB floor) |
| stage-local gates | S gate 1.0000 (4/4 sub-frames); every band buffer 1.000000 (16 kHz/32 kHz) |

The remaining difference is float32 rounding in near-cancelling sums and the int16 clamp floor - i.e. the
codec is reproduced to the limit of the DLL's own arithmetic. All fitted constants are gone: the gain law,
Q table, ring rule, band gains, codebooks, tilt terms and ramp constants all come from measured DLL values
with their addresses recorded in `specs/GainLaw.md`, `specs/UpperBands.md` and `specs/DriftFrames.md`.

## 16.6 Closing the last gap: bit-exactness of the speech windows

After §16.5 the port was at 0.99965 with 19/26 speech windows exactly 1.00000; the seven that were not
(worst 160-169 = 0.99911) were traced to **ULP-level float differences in the recursive 8 kHz excitation**
plus **int16 rounding**, not to any remaining rule:

* frames 55-65 the excitation is **bit-exact** (0/160 differing samples vs the DLL's buffer 0x30012364);
  divergence starts around frame 66-70 and later frames fluctuate between 0 and ~50 differing samples with
  small magnitudes - i.e. a float-precision drift in a marginally stable recursion, re-synchronised whenever
  the fresh codebook terms dominate.
* the port's int16 conversion used `int(v+0.5)`, which truncates negatives; the DLL rounds to nearest (x87
  control word, `fistp`). Switching to `round(v)` (ties to even) cut the differing PCM samples over frames
  100-125 from 11874/16640 to 7814/16640 and made the **silence windows 0..39 exactly 1.0000**.
* remaining systematic error: the DLL's tilt (`0x30012a20`) differs from the port's by ~1e-4 relative on
  frame 120, i.e. the LPC coefficients are off at ~1e-5 relative - enough to produce the observed +-1 LSB on
  a large fraction of samples (frame 120: excitation 5/160 differing, PCM 334/640 differing, maxdiff 2).
* two sources of ULP/rounding mismatch identified for the fix: the codec uses the **MSVC CRT `exp`**
  (dispatcher 0x10011aec -> worker 0x10017b6a) rather than the platform libm, and the FIR/gain/synthesis code
  is **x87**, i.e. 64-bit-mantissa intermediates stored as float32 at specific points (`numpy.longdouble`
  reproduces that on this machine).

Two tasks are in flight on exactly this: `ExactExcitationArith` (CRT `exp` + x87 intermediates in the
excitation recursion; gate: excitation bit-exact on frames 150-170) and `ExactOutputChain` (LSF->LPC,
LPC synthesis, band filters, combines, int16; gate: every speech window exactly 1.00000 and global 1.000000).

## 16.7 CLOSED: bit-exact arithmetic — speech windows all exactly 1.000000

Both halves of the last gap were closed by measurement-driven patches (details in `specs/ExactArith.md`
and `specs/ExactOutput.md`):

**8 kHz excitation — bit-exact.** The FIR is
`out[i] = f32_x87( ((g0*R[i+2] + 1e-15) + g1*R[i+1]) + g2*R[i] )` where `R` is the 42-entry cyclic read of
the `lag` samples ending before the sub-block (`ring(j) = j` for `j <= lag`, else `1+((j-1)%lag)`, and
`R[j] = 0` beyond `2*lag+1`), every product/sum in x87 80-bit extended precision (`numpy.longdouble`,
64-bit mantissa) and a single direct 80->32 bit store. Verified: **0 / 48 000 differing samples over 300
frames** (was 12 112, worst frame 159/160). The CRT `exp` turned out *not* to need porting: `math.exp`
differs from the DLL's in the double for 8/80 reachable arguments but never after the float32 rounding,
and substituting exact emulated values changed no PCM sample. `FUN_10002ec0` uses a sequential float32
accumulator (1 ulp differences on 524/1200 sub-frames, no PCM effect).

**Output chain — bit-exact given its inputs.** `lpc_synth` must round `t = f32(in + mem[0])` and every
state word; `band_filter`'s four accumulators live in float32 *memory* and are rounded after each partial
product-sum, with `c1` accumulated before `c3`; the combine is `f32((A-B)*2)` clamped to
`[-32767, +32767]` (**not** -32768); int16 conversion is round-to-nearest-even. `lsf_to_lpc` uses the DLL's
own degree-6 cosine (`_cos_apx`, 0x10004af0, bit-exact on 4 784 calls) and the P/Q cascade of second-order
FIR sections with float32 state. Stage audits vs the DLL: **0 differing samples** in
`FUN_100030e0` (83 840), `FUN_10003960` (251 520) and `FUN_1000c290` (125 760).

**Final acceptance** (`tools/verify_codec.py`, 300 frames = 19.2 s of the shipped voice):

| metric | value |
|---|---|
| global correlation | **1.0000** |
| amplitude (rms) ratio | **1.000** |
| speech 10-frame windows exactly 1.000000 | **26 / 26** |
| silence windows | bit-exact (100 %) |
| worst per-sample deviation | **±2 int16 LSB** (54 of 30 windows ±1) |

The residual, where present, is ±1 LSB from the remaining 1-ulp difference in the `FUN_10005080`
P/Q cascade coefficients (333/4264 coefficients off by one float32 ulp) amplified near int16 rounding
boundaries - i.e. at the noise floor of the DLL's own arithmetic.
