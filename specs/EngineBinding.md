# Engine ↔ voice binding in Loquendo TTS 7 (voice "Jorge")

Scope: how the engine `LoqTTS7.dll` (jorge build) registers/loads the voice databases, how the
`.vde/.vcf/.gde/.ycf/.lcf` descriptors drive that registration, what the voice module
`LTTS7Jorge.dll` exposes, and the exact code path from a selected unit to a decoder request.

All addresses below are **VA (image base 0x10000000)**. Unless stated otherwise they are from the
**jorge** build, decompiled with Ghidra 12.1.2 into
`jorge_re/decomp_loqtts_jorge.txt` (engine), `jorge_re/decomp_jorge_voice.txt` +
`jorge_re/decomp_jorge_funcs.txt` (voice module) and `jorge_re/decomp_util_jorge.txt` (Util).
The older `engine_re/` build is quoted only where it is clearer/verified; old addresses are given as
`FUN_10024ff0 (old)`.

## 0. Build map (old `engine_re` → jorge)

| role | old build | jorge build |
|---|---|---|
| register DB list (`VocalDBName[i]` loop, 16 slots) | `FUN_10024ff0` | `FUN_100444d0` |
| register one DB via `ELQSharedResourceAdd` (".sde") | `FUN_10024ad0` | `FUN_10043f50` |
| register one DB via `LinkedSde[...]` plugin (`SdeDllMain`) | `FUN_10024ba0` | `FUN_10044040` |
| accessor: is there a `VocalDBName[0]`? | `FUN_10024f70` | `FUN_10044450` |
| `ELQLoadFileData` (loads .vcf/.vde/.lcf/.lde, gdeInclude, `__BinInfo__[i]`) | `FUN_1001b140` | `FUN_10052380` |

The engine never calls the `LTTS7Util.dll` API directly; it resolves every symbol through a
name→pointer table and calls `(*DAT_…)(…)`. The table was recovered from the DLL image (base
`0x100b2460`, 441 × `{char *name; void *slot}` pairs); the full dump is in
`tools/enginebind_symtab.txt`. Examples used below:

```
DAT_100b7054 = ELQBinClose        DAT_100b7058 = ELQBinGetBuffer     DAT_100b7064 = ELQBinGetSize
DAT_100b706c = ELQBinOpen         DAT_100b7070 = ELQBinSeek          DAT_100b73d0 = ELQDataDescriptorGetAttribute
DAT_100b73e0 = ELQDataDescriptorLoadFile                             DAT_100b73e4 = ELQDataDescriptorSetAttribute
DAT_100b70c4 = ELQFileFullName    DAT_100b70c8 = ELQFileResolveSymbolicName
DAT_100b7324 = ELQSharedResourceAdd                                  DAT_100b7148 = ELQLogWrite
DAT_100b72d8 = ELQPluginGetProc   DAT_100b72e0 = ELQPluginIni        DAT_100b72c4 = ELQPluginGetVersion
DAT_100b74fc = ELQBinaryHeaderLoadInfo                               DAT_100b7504 = ELQBinaryHeaderGetValue
DAT_100b750c = ELQBinaryHeaderIsPresent                              DAT_100b7410 = ELQmalloc
DAT_100b747c = ELQBufferAlloc     DAT_100b74b0 = ELQBufferFill       DAT_100b74c0 = ELQBufferInfoSetData
DAT_100b7090 = ELQConfigurationSetValue                              DAT_100b7080 = ELQConfigurationGetValue
```

## 1. Voice / language / database registration

### 1.1 The shipped descriptors (verbatim)

`jorge/pf/Loquendo/LTTS7/data/Jorge.vcf` (voice *configurator* — selects the DBs):

```
"Description"       = "Castilian Spanish male voice"
"BaseVoice"         = "Jorge"
"VoicePath"        = "voices/Jorge"
"VocalDBName[0]"    = "Jorge"
"VocalDBName[1]"    = "JorgeGildedPhrases"
"VocalDBName[2]"    = "JorgeGildedParalinguistics"
"Built-in"          = "Yes"
```

`jorge/pf/Loquendo/LTTS7/data/voices/Jorge/Jorge.vde` (voice *descriptor* — carries `Library`,
prosody defaults and the gilded include):

```
"BaseDescription"   = "Castilian Spanish male voice"
"Library"           = "LTTS7Jorge, Jorge"
"BaseSpeed"         = "128"
"BasePitch"         = "85"
"Gender"            = "Male"
"Age"               = "40"
"GildedTTS"         = "yes"
"gdeInclude"        = "JorgeGilded.gde"
"MotherTongue"      = "SpanishEs"
"MotherTongueAliases" = "SpanishEs,es-ES,ES,Castilian,es,Spanish"
```

`JorgeGilded.gde` defines the speech-act / paralinguistic phrase inventories
(`"Gilded[0]"="SpeechActs>~Extras>"`, `"SpeechActs[0]"="Apologies>~Approval>~…"`,
`"Extras[0]"="Aa>~Ah>~Aha>~…"`, and per-phrase text lists `"Apologies[0]"="Perdona!~…"`).

`Jorge.32000.LTTS7Codec210.44000.10.bin` is the acoustic DB of DB 0, and
`JorgeGildedPhrases.*` / `JorgeGildedParalinguistics.*` are the DBs of slots 1 / 2.

### 1.2 Constants resolved from the jorge DLL image

Resolved by mapping the VA through the PE section table and reading the bytes (script used:
eval cell "Read constant strings"; reproducible with `read` docs / the section table
`(.text 0x1000/0x400, .rdata 0x6E000/0x6C800, .data 0xB1000/0xAF200, imagebase 0x10000000)`):

| VA (jorge) | bytes | string | used as |
|---|---|---|---|
| `0x10097388` | `49 64 00` | `"Id"` | attribute name passed to `ELQDataDescriptorGetAttribute` in `FUN_10043f50` — **the DB name key** |
| `0x1009f3c4` | `2e 73 64 65 00` | `".sde"` | suffix appended to `VocalDBName[i]` in `FUN_100444d0` |
| `0x1009f3c8` | `00` | NUL | terminator written after `".sde"` |
| `0x1009f3c0` | `2f 00` | `"/"` (u16) | path separator appended before `VocalDBName[i]` |
| `0x1009f1e8` | `4c 54 54 53 37 00` | `"LTTS7"` | default LinkedSde plugin label |
| `0x1009f1f0` | `53 64 65 00` | `"Sde"` | suffix appended to `VocalDBName` → plugin/export name `<name>Sde` |
| `0x1009f234` | `37 2e 30 2e 31 00` | `"7.0.1"` | **engine SDE API version** compared with the SDE plugin version |
| `0x1009b248` | `62 75 69 6c 74 5f 69 6e 00` | `"built_in"` | forced coding name when no DB matches |
| `0x1009b1e8` / `0x1009b508` | `"Freq"` / `"Rank"` | | `ELQBinaryHeaderGetValue` tag names (with literal `"Coding"`,`"BitRate"`) |
| `0x100a1f6c` | `2e 64 6c 6c 00` | `".dll"` | appended to the `Library` DLL name |
| `0x100a1f74` / `0x100a1f88` | | `"FullLibraryName"` / `"LibraryVersion"` | attributes set from `Library` |
| `0x100a1f34` / `0x100a1f3c` | `".vde"` / `".lde"` | | voice / language descriptor suffixes |
| `0x9dbc4`→VA `0x1009f3c4` | `".sde"` | | (file-offset cross-check) |

Other extension literals in the engine `.rdata`: `.epd`, `.vad`, `.rcf` (`0x9…`), `.vcf` (RVA
`0x…`, file off 0xa06b0), `.lcf` (0xa06b8), `.ycf` (0xa06c0), `.vde` (0xa0734), `.lde` (0xa073c),
`.dll` (0xa076c).

**Correction to `specs/CONTEXT.md` §D:** the suffix constant is **`".sde"`, not `".bin"`**, and the
attribute name is **`"Id"`**, not an opaque tag. In the *old* build these live at
`DAT_1008eec0 = ".sde"` / `DAT_1008eec4 = 00` / `DAT_1008eec8 = "/"` and `DAT_10088a0c = "Id"`
(verified by reading `engine_re/LoqTTS7.dll` at RVA 0x8eec0 / 0x88a0c: bytes
`2e 73 64 65 00 00 00 00 2f 00 00 00 4c 69 6e 6b…` = `".sde\0\0\0\0/\0\0\0LinkedSde[%d]"` and
`49 64 00 00 4c 61 6e 67…` = `"Id\0\0Language=%s,…"`). Mapping those RVAs into the *jorge* DLL
yields unrelated data (the jorge `.rdata` layout differs), so the jorge values above were resolved
by content, not by RVA.

### 1.3 `FUN_10044450` — does DB 0 exist? (old `FUN_10024f70`)

```c
void FUN_10044450(void)
{
  int *unaff_ESI;
  char *local_28;
  char local_24 [32];
  …
  if (((unaff_ESI != (int *)0x0) && ((code *)*unaff_ESI == FUN_10043980)) && (unaff_ESI[1] != 0)) {
    _sprintf(local_24,"VocalDBName[%d]",0);
    (*DAT_100b73d0)(unaff_ESI[1],local_24,&local_28,0);   /* ELQDataDescriptorGetAttribute */
    if ((local_28 != (char *)0x0) && (*local_28 != '\0')) {
      …return;
    }
  }
  …
}
```

Binds DB index 0 in the *voice object* (`unaff_ESI[1]` = the descriptor), i.e. it is the predicate
"this voice has a speech-unit DB".

### 1.4 `FUN_10043f50` — fallback registration of one DB (old `FUN_10024ad0`)

```c
void __cdecl FUN_10043f50(undefined4 param_1)         /* param_1 = the .vcf/.vde descriptor   */
{
  char cVar1; int iVar2; int unaff_ESI;               /* unaff_ESI = session object           */
  undefined1 *local_410; undefined4 uStack_40c;
  undefined1 auStack_408 [4]; undefined1 auStack_404 [512]; undefined1 auStack_204 [512];
  …
  iVar2 = *(int *)(unaff_ESI + 8);
  (*DAT_100b73d0)(param_1,&DAT_10097388,&local_410,0);            /* GetAttribute(desc,"Id")    */
  (*DAT_100b70c4)(auStack_404);                                   /* ELQFileFullName(dir)       */
  if (local_410 == (undefined1 *)0x0) {
    local_410 = &DAT_100967df;                                    /* "" */
  }
  (*DAT_100b70c8)(auStack_204,0x200,auStack_404,local_410,0,0);   /* ELQFileResolveSymbolicName */
  cVar1 = (*DAT_100b73d0)(*(undefined4 *)(unaff_ESI + 4),"debug",auStack_408,0);
  iVar2 = (*DAT_100b7324)(*(undefined4 *)(iVar2 + 8),&uStack_40c,auStack_204,0,0,0); /* ELQSharedResourceAdd */
  if (iVar2 != 0) {
    if (cVar1 == '\0') goto LAB_10044024;
    uStack_40c = 0;
  }
  *(undefined4 *)(unaff_ESI + 0x18 + (uint)*(byte *)(unaff_ESI + 0x5b8) * 4) = uStack_40c;
  *(undefined1 *)(*(byte *)(unaff_ESI + 0x5b8) + 0x98 + unaff_ESI) = 1;
LAB_10044024:
  …
}
```

Semantics: `ELQLoadFileData`/`FUN_100444d0` first built the file name and stored it in the "Id"
attribute of the descriptor being loaded; here the engine takes that `Id`, resolves it against the
directory of the current descriptor, and registers the file as a **shared resource**; the returned
handle goes into the session's DB-handle array at `session+0x18+i*4` and the flag byte
`session[0x98+i] = 1` marks *this* DB slot as "loaded from a file" (as opposed to "from a plugin",
which `FUN_10044040` clears to 0). `"debug"` allows a failed Add to be tolerated.

### 1.5 `FUN_10044040` — LinkedSde plugin registration (old `FUN_10024ba0`)

```c
void __cdecl FUN_10044040(int param_1,char *param_2)     /* param_2 = VocalDBName[i] */
{
  …
  piVar2 = *(int **)(param_1 + 8);
  uVar7 = *(undefined4 *)(*piVar2 + 0xc00);               /* log handle */
  local_604 = DAT_1009f1e8;                               /* "LTTS"  */
  local_600 = DAT_1009f1ec;                               /* "7\0"   → local_604 = "LTTS7" */
  … copy param_2 (the DB name) to the end of the label buffer …
  *puVar12 = DAT_1009f1f0;                                /* append "Sde" → "<name>Sde"    */
  iVar5 = (*DAT_100b72e0)(param_1 + 0x58 + (uint)*(byte *)(param_1 + 0x5b8) * 4,uVar7,&local_604,
                          *piVar2 + 0x400,"SdeDllMain",0,0);          /* ELQPluginIni */
  if (iVar5 == 0) {
    (*DAT_100b72c8)(…, *(undefined4 *)(*(int *)(param_1 + 8) + 0x10)); /* ELQPluginLoadUtilSymbols */
    cVar3 = (*DAT_100b72c4)(…,uVar7,abStack_404);                      /* ELQPluginGetVersion */
    if (cVar3 == '\0') { … "Missing version information in sde dynamic library\n" … }
    … strcmp(abStack_404, &DAT_1009f234 /* "7.0.1" */) …
    if (iVar5 == 0) {
      … ELQPluginGetProc(…,"GetVersion",…); (*(code*)…)(abStack_404) …
      … ELQPluginGetProc(…,"CatVoiceVersion",&pcStack_60c); (*pcStack_60c)(abStack_204) …
      … ELQPluginGetProc(…,"CatSdeData",&pcStack_610);
      uVar7 = (*DAT_100b72d0)(…);                       /* ELQPluginGetFileName */
      iVar5 = (*pcStack_610)(param_1 + 0x18 + (uint)*(byte *)(param_1 + 0x5b8) * 4);
      if (iVar5 != 0) (*DAT_100b7148)(1,local_614,"Error loading dbunita from %s\n",uVar7);
      …
```

`LinkedSde[ALL]` (or `LinkedSde[i]`) = `y`/`Y` selects this path: the module
`<prefix><VocalDBName>+"Sde"` is loaded as an ELQ plugin whose entry point must be the export
`SdeDllMain`, and which must export `GetVersion`, `CatVoiceVersion` (voice version must compare
equal), `CatSdeData` (returns the dbunita handle written to `session+0x18+i*4`) — the log string is
`"Error loading dbunita from %s"` and the version mismatch message is
`"%s voice version (%s) is not compatible with voice version (%s)"`; the engine's own SDE API
version is `"7.0.1"`. **No shipped module exports `SdeDllMain` and the Jorge descriptors contain no
`LinkedSde` tag, so Jorge always uses the fallback path (1.6).**

### 1.6 `FUN_100444d0` — the 16-slot DB registration loop (old `FUN_10024ff0`)

```c
void __thiscall FUN_100444d0(void *this,int param_1)      /* this = descriptor, param_1 = session */
{
  …
  bVar1 = *(byte *)(param_1 + 0x5b8);                     /* DB slot counter, starts at 0 */
  while (bVar1 < 0x10) {
    bVar3 = false;
    (*DAT_100b73d0)(this,"LinkedSde[ALL]",&local_634,0);
    if ((local_634 == (char *)0x0) || ((*local_634 != 'y' && (*local_634 != 'Y')))) {
      _sprintf(acStack_624,"LinkedSde[%d]",(uint)*(byte *)(param_1 + 0x5b8));
      (*DAT_100b73d0)(this,acStack_624,&local_634,0);
      if ((local_634 != (char *)0x0) && ((*local_634 == 'y' || (*local_634 == 'Y')))) goto LAB_1004457b;
    } else {
LAB_1004457b: bVar3 = true;
    }
    _sprintf(acStack_624,"VocalDBName[%d]",(uint)*(byte *)(param_1 + 0x5b8));
    (*DAT_100b73d0)(this,acStack_624,&local_634,0);
    if ((local_634 == (char *)0x0) || (*local_634 == '\0')) {
      if (*(char *)(param_1 + 0x5b8) == '\0') {
        (*DAT_100b7148)(2,…,"* SYSTEM: No speech unit database has been defined for this voice\n");
      }
      goto LAB_10044819;
    }
    if (bVar3) { iVar5 = FUN_10044040(param_1,local_634); }        /* plugin path (§1.5) */
    else {
      _sprintf(acStack_624,"VocalDBPath[%d]",(uint)*(byte *)(param_1 + 0x5b8));
      (*DAT_100b73d0)(this,acStack_624,&pcStack_630,0);
      if ((pcStack_630 == (char *)0x0) || (*pcStack_630 == '\0')) {
        (*DAT_100b73d0)(this,"VoicePath",&pcStack_630,0);          /* fall back to VoicePath */
        …build "dir/" + VocalDBName…   *(undefined2 *)pcVar10 = DAT_1009f3c0;  /* "/" */
      } else { …same, base = VocalDBPath[i]… }
      (*DAT_100b73d0)(this,"DataPath",&pcStack_628,0);             /* fetched into acStack_204 */
      …
      *(undefined4 *)((int)puVar7 + 1) = DAT_1009f3c4;             /* append ".sde"  */
      *(undefined1 *)((int)puVar7 + 5) = DAT_1009f3c8;             /* NUL            */
      iVar5 = FUN_10043f50(this);                                 /* §1.4: register the file */
    }
    if (iVar5 != 0) goto LAB_10044819;
    pcVar10 = (char *)((uint)*(byte *)(param_1 + 0x5b8) * 0x51 + 0xa8 + param_1);
    pcVar9 = local_634;
    do { cVar2 = *pcVar9; *pcVar10 = cVar2; pcVar9++; pcVar10++; } while (cVar2 != '\0');
    *(char *)(param_1 + 0x5b8) = *(char *)(param_1 + 0x5b8) + '\x01';   /* next slot */
    bVar1 = *(byte *)(param_1 + 0x5b8);
  }
  (*DAT_100b7148)(1,…,"Too many speech unit databases (max %d)\n",0x10);
LAB_10044819: …
}
```

Facts:
* loop over `i = 0…15`, reading `LinkedSde[ALL]`, `LinkedSde[i]`, `VocalDBName[i]`,
  `VocalDBPath[i]`, `VoicePath`, `DataPath` from the **descriptor**;
* per slot it builds the path `VocalDBPath[i] | VoicePath` + `"/"` + `VocalDBName[i]` and appends
  **`".sde"`** → for `Jorge.vcf` that is `voices/Jorge/Jorge.sde`,
  `voices/Jorge/JorgeGildedPhrases.sde`, `voices/Jorge/JorgeGildedParalinguistics.sde` — exactly the
  three shipped inventories;
* the DB **name** (`VocalDBName[i]`) is stored per slot in the session at `session + 0xa8 + i*0x51`
  (0x51 = 81-byte name field) and the resource handle at `session + 0x18 + i*4`;
* `0xa8` (jorge) vs `0xa4` (old) and `0x18/0x98` vs `0x14/0x94` are the only struct shifts between
  builds.
* The path derivation copies `VoicePath`/`VocalDBPath[i]` into +0x604-relative buffer and the final
  `".sde"` string into an overlapping 512-byte buffer at `ebp-0x404`; Ghidra renders these two
  buffers with overlapping names (`acStack_604`, `uStack_405/auStack_400`, `acStack_204`), so the
  *exact* destination of the last copy is ambiguous in the decompilation. `DataPath` is read from
  the descriptor and copied into a local in every branch but is never referenced afterwards in the
  decompiled body — **[INFERENCE]** it is the fallback directory when the descriptor has neither
  `VocalDBPath[i]` nor `VoicePath` (the engine also logs `"DataPath not found in voice descriptor\n"`
  from another function), but the code as decompiled does not show that use.

### 1.6b `FUN_10043cb0` — release of all registered DBs

```c
/* decomp_loqtts_jorge.txt */
void FUN_10043cb0(void)
{
  byte bVar1; uint uVar2; int unaff_ESI;
  if (unaff_ESI != 0) {
    while (*(char *)(unaff_ESI + 0x5b8) != '\0') {
      bVar1 = *(char *)(unaff_ESI + 0x5b8) - 1;
      *(byte *)(unaff_ESI + 0x5b8) = bVar1;
      uVar2 = (uint)bVar1;
      if (*(int *)(unaff_ESI + 0x18 + uVar2 * 4) != 0) {
        if (*(char *)(uVar2 + 0x98 + unaff_ESI) == '\0') {
          (*DAT_100b72cc)(*(undefined4 *)(unaff_ESI + 0x58 + uVar2 * 4));      /* ELQPluginDelete */
          *(undefined4 *)(unaff_ESI + 0x58 + (uint)*(byte *)(unaff_ESI + 0x5b8) * 4) = 0;
        }
        else {
          (*DAT_100b7334)(*(undefined4 *)(*(int *)(unaff_ESI + 8) + 8),
                          **(undefined4 **)(unaff_ESI + 0x18 + uVar2 * 4),0);  /* ELQSharedResourceRemove */
          *(undefined4 *)(unaff_ESI + 0x58 + (uint)*(byte *)(unaff_ESI + 0x5b8) * 4) = 0;
        }
      }
    }
  }
}
```
This confirms the two handle kinds and the flag's polarity: `session[0x98+i] == 0` → the slot is a
*plugin* handle (`session+0x58+i*4`, freed with `ELQPluginDelete`); `== 1` → the slot is an
*ELQ shared-resource* handle whose first dword (`**handle`) is passed to `ELQSharedResourceRemove`
(together with the session's resource set at `*(session+8)+8`). So the `.sde` registered in §1.4 is
a shared resource, not a plugin.

### 1.7 What actually opens the `.bin`: `FUN_10052380` (`ELQLoadFileData`)

`FUN_10052380(param_1, param_2, param_3, param_4, param_5)` is the generic descriptor loader used
for voices and languages (`param_5` picks the extension pair: voice → `.vcf` + `.vde`,
language → `.lcf` + `.lde`; the constants `".vde"`=`0x100a1f34`, `".lde"`=`0x100a1f3c`,
`".dll"`=`0x100a1f6c`). Core of it:

```c
  puVar5 = FUN_10052340();                                     /* returns the configurator suffix */
  _sprintf(acStack_804,"%s%s",param_2,puVar5);
  (*DAT_100b70c4)(acStack_604,param_4,acStack_804);            /* resolve <base><.vcf> */
  cVar2 = (*DAT_100b73e0)();                                   /* ELQDataDescriptorLoadFile */
  if (cVar2 == '\0') { …"Unable to open %s configurator file \"%s\"\n"… }
  if ((param_5 != 1) && (param_5 != 2)) { … }
  …
  (*DAT_100b70c4)(acStack_604,acStack_404,pcStack_86c);        /* the "gdeInclude" value, if any */
  cVar2 = (*DAT_100b73d0)();                                   /* GetAttribute(…,"gdeInclude"…) */
  if ((cVar2 != '\0') && (iStack_864 != 0)) {
      (*DAT_100b70c4)(acStack_604,acStack_404,iStack_864);
      cVar2 = (*DAT_100b73e0)();                               /* ELQDataDescriptorLoadFile */
      if (cVar2 == '\0') { pcVar3 = "Unable to open gilded descriptor file \"%s\"\n"; … }
  }
  iVar4 = 0;
  _sprintf(acStack_804,"VocalDBName[%d]",0);
  cVar2 = (*DAT_100b73d0)();
  while ((cVar2 != '\0' && (iStack_870 != 0))) {
    _sprintf(acStack_804,"VocalDBPath[%d]",iVar4);
    cVar2 = (*DAT_100b73d0)();
    if ((cVar2 == '\0') || (iStack_858 == 0)) { …acStack_604 = acStack_404 (the .vcf's dir)… }
    else { (*DAT_100b70c4)(acStack_604,local_860,iStack_858); }
    iVar7 = (*DAT_100b74fc)(iStack_870,acStack_604,uVar1);     /* ELQBinaryHeaderLoadInfo(name,dir,log) */
    if (iVar7 == 0) {
      _sprintf(acStack_804,"BINLoad[%d]",iVar4);
      cVar2 = (*DAT_100b73d0)();
      if (((cVar2 == '\0') || (iStack_85c == 0)) ||
         (iVar7 = (*DAT_100b7428)(iStack_85c,&DAT_100976e4 /* "no" */), iVar7 != 0)) {
        (*DAT_100b7148)(1,uVar1,"ELQLoadFileData: no binary data for %s in %s\n",iStack_870,acStack_604);
        goto LAB_10052b50;
      }
    }
    _sprintf(acStack_804,"__BinInfo__[%d]",iVar4);
    (*DAT_100b73e4)();                                         /* SetAttribute("__BinInfo__[i]",hdr) */
    iVar4 = iVar4 + 1;
    _sprintf(acStack_804,"VocalDBName[%d]",iVar4);
    cVar2 = (*DAT_100b73d0)();
  }
  … same loop again for "VocalAddOn[%d]" (continuing the __BinInfo__ indices) …
  … and, when the descriptor has "Library", get the DLL name + "FullLibraryName" + "LibraryVersion" …
```

So per `VocalDBName[i]`:
1. the directory is `VocalDBPath[i]` (resolved with `ELQFileResolveSymbolicName` against the
   descriptor's own directory) or, absent that, the directory of the `.vcf`;
2. `ELQBinaryHeaderLoadInfo(name, dir, log)` **globs `<dir>/*.bin`** and keeps every file whose
   header tag `Label` equals `name` **case-insensitively** (see §1.8). It is *not* a file-name
   lookup: `VocalDBName[i]` is the **`Label` TLV of the `.bin`**, and all matching variants
   (different `Freq`/`Coding`/`BitRate`/`Rank`) are collected;
3. the resulting object is stored in the descriptor as `__BinInfo__[i]`;
4. `BINLoad[i]` (`no`/`false`/`ignore` disables) is a switch that suppresses the hard error.

`FUN_10022a50` (the "signal processor" voice loader, `FUN_100225e0` calls it) then *chooses* one of
the collected headers: it reads `SetSampleRate`/`SetCoding`/`SetBitRate` (or
`ForcedSampleRate`/`ForcedCoding`/`ForcedBitRate`) from the descriptor, defaults
`0xac44` = 44100 when the `debug`/`freq` keys are present, and for every `__BinInfo__[i]` calls

```c
  cVar3 = (*DAT_100b7504)(iStack_a6c,&DAT_1009b1e8 /*"Freq"*/,&local_a78,&DAT_10096814,1);  /* ELQBinaryHeaderGetValue */
  cVar3 = (*DAT_100b7504)(iStack_a6c,"Coding",&local_a70,&DAT_10096814,1);
  cVar3 = (*DAT_100b7504)(iStack_a6c,"BitRate",&local_a60,&DAT_10096814,1);
  cVar3 = (*DAT_100b7504)(iStack_a6c,&DAT_1009b508 /*"Rank"*/,&local_a58,&DAT_10096814,1);
  …
  uVar5 = iVar8 * (iVar7 / 100) * (iVar6 / 100);   /* score: freq × coding% × bitrate% ; keep max */
```

and stores the winner's `Freq` in `session+…` (`param_1+0xc`) and `BitRate` in `param_1+0xd`
(see `FUN_100225e0`: `FUN_10022a50(local_404,param_1,local_204,(uint *)(param_1 + 0xc),param_1 + 0xd)`).
Failure logs `"* SIGNAL PROCESSOR: Unable to find a vocal db for this voice. Check %s.vcf file's
content"` — i.e. selection is driven by the **`.vcf` keys vs the `.bin` header tags**.

### 1.8 `ELQBinaryHeaderLoadInfo` — the `*.bin` matcher (Util, jorge VA 0x100026d0)

```c
undefined4 * __cdecl ELQBinaryHeaderLoadInfo(byte *param_1,void *param_2,int *param_3)
                                              /* param_1 = wanted Label, param_2 = directory */
{
  …
  puVar5 = _malloc(8);                       /* {ELQBuffer *list; int count} */
  *puVar5 = 0; puVar5[1] = 0;
  iVar6 = ELQBufferInit(puVar5);
  …
  local_c = FUN_10001fd0(param_2,&local_18);          /* glob, pattern "*.bin" */
  while (local_14 < local_c) {
      pcVar7 = (char *)ELQBufferGetString(puVar4);
      iVar6 = FUN_10003510(&local_18,'d',param_3,pcVar7,0,'\0');   /* ELQBinOpenNoCache */
      if (iVar6 == 0) {
        uVar8 = FUN_10002550(pcVar7,param_3);                      /* ReadHeader + TLV parse */
        if ((char)uVar8 != '\0' && local_1c != 0 && (code *)*local_1c == ELQDataDescriptorIni) {
          for (puVar5 = local_1c[2]; puVar5 != 0; puVar5 = puVar5[4]) {
            iVar6 = ELQstricmp((byte *)*puVar5,(byte *)"Label");
            if (iVar6 == 0) {
              if ((byte *)puVar5[1] != 0 &&
                  (iVar6 = ELQstricmp((byte *)puVar5[1],param_1), puVar5 = local_10, iVar6 == 0)) {
                iVar6 = ELQBufferCatRaw((int *)*local_10,&local_1c,4,0);   /* collect the descriptor */
                …
                puVar5[1] = puVar5[1] + 1;
                goto LAB_10002804;
              }
              break;
            }
          }
        }
        ELQDataDescriptorDelete(piVar3);
LAB_10002804:
        ELQBinClose(local_18);
        …advance the name buffer…
      } else {
        ELQLogWrite(8,param_3,"ELQBinaryHeaderLoadInfo: error opening %s file.");
      }
      local_14 = local_14 + 1;
  }
  ELQBufferFree(puVar4);
  return puVar5;
}
```

(The older build shows the glob pattern literally: `uVar3 = FUN_10004cf0(&local_14,"*.bin",param_3);`
then `pcVar4 = (char *)ELQBufferGetString(local_14); ELQBinOpenNoCache(&local_10,'d',param_3,pcVar4,0);`
… `ELQDataDescriptorGetAttribute(local_18,(byte *)"Label",&local_8,0); … ELQstricmp(local_8,param_1)` —
quoted verbatim in §"old utility" below.)

```c
/* decomp_util.txt, ELQBinaryHeaderLoadInfo @ 100051f0 (older Util) */
        uVar3 = FUN_10004cf0(&local_14,"*.bin",param_3);
        local_c = 0; local_4 = uVar3;
        if (uVar3 != 0) {
          do {
            pcVar4 = (char *)ELQBufferGetString(local_14);
            iVar2 = ELQBinOpenNoCache(&local_10,'d',param_3,pcVar4,0);
            if (iVar2 == 0) {
              uVar3 = FUN_10005100(pcVar4,param_3);        /* ReadHeader */
              if (((((char)uVar3 == '\0') ||
                   (uVar5 = ELQDataDescriptorGetAttribute(local_18,(byte *)"Label",&local_8,0), …
                     iVar2 = ELQstricmp(local_8,param_1), iVar2 != 0)) {
                ELQDataDescriptorDelete(local_18);
              } else {
                iVar2 = ELQBufferCatRaw((int *)*puVar1,&local_18,4,0);
                … puVar1[1] = puVar1[1] + 1; …
              }
              ELQBinClose(local_10);
              ELQBufferDeleteString(local_14);
```

## 2. Descriptor semantics relevant to the DB

The configurator extension is chosen by a descriptor *type* through `FUN_10052340`:

```c
undefined1 * FUN_10052340(void)          /* in_EAX = type */
{
  undefined4 in_EAX;
  switch(in_EAX) {
  case 0: return &DAT_100a1ea8;          /* ".rcf" */
  case 1: return &DAT_100a1eb0;          /* ".vcf" */
  case 2: return &DAT_100a1eb8;          /* ".lcf" */
  case 3: return &DAT_100a1ec0;          /* ".ycf" */
  default: return &DAT_100967df;         /* ""     */
  }
}
```
and `FUN_10052380(...,param_5)` is called with `param_5 = 1` (voice), `2` (language) or `3`
(other/"general"; see the callers at dump lines 9181 / 9495 / 10187). Only `param_5 == 1` reaches the
`gdeInclude` + `VocalDBName[i]`/`VocalAddOn[i]` registration block (`LAB_10052808`), and both 1 and 2
load their descriptor via `".vde"`/`".lde"` plus the `Library` keys. `"BaseVoice"` (VA `0x100a1f18`)
and `"BaseLanguage"` (`0x100a1f28`) name the *base* configurator the current file inherits from.

| extension | role (evidence) | keys that matter for the DB |
|---|---|---|
| `.vcf` (type 1) | voice *configurator* | `BaseVoice`, `VoicePath`, `VocalDBName[i]`, `VocalDBPath[i]`, `Built-in`, `SetSampleRate`/`SetCoding`/`SetBitRate` (+`Forced*`), `BINLoad[i]` |
| `.vde` | voice *descriptor*, appended via `&DAT_100a1f34` (`.vde`, `"voice"`/`"language"` log wording), guarded by the `Library` key (`"Unable to find \"library\" key in descriptor file \"%s\""`) | `Library` (=`<dll>,<name>`), `FullLibraryName`, `LibraryVersion`, `gdeInclude`, `GildedTTS`, `BaseSpeed`, `BasePitch`, `MotherTongue*` |
| `.lcf` (type 2) | language configurator | language `DataPath`, `BaseLanguage` |
| `.lde` | language *descriptor* (`&DAT_100a1f3c`) | `Library` |
| `.rcf` (type 0), `.ycf` (type 3) | other configurators (same loader, no VDB registration) | — |
| `.gde` | *gilded* descriptor, pulled in by `gdeInclude` from the `.vde` (`"Unable to open gilded descriptor file \"%s\"\n"`, old dump `FUN_1001b140` lines 22505+) | `Gilded[0]="SpeechActs>~Extras>"`, `SpeechActs[i]`, `Extras[i]`, and the phrase lists (`Apologies[0]`, `Greetings[0]`, … `_\<Name\>` entries for the paralinguistics) |
| `.sde` | unit inventory; the suffix appended in §1.6, registered as an ELQ shared resource named by the descriptor's `Id` | opened via `ELQSharedResourceAdd`, handle in `session+0x18+i*4` |
| `.bin` | acoustic DB; found by `ELQBinaryHeaderLoadInfo` (§1.8) via `*.bin` glob + header `Label` == `VocalDBName[i]`; selected by `Freq`/`Coding`/`BitRate`/`Rank` (§1.7) | TLV tags `Name/Label/Comment/Freq/Coding/BitRate/Rank/Version` |

* **Which keys select a DB**: `VocalDBName[i]` (+ optional `VocalDBPath[i]`) selects the *label*;
  `SetSampleRate`/`SetCoding`/`SetBitRate` (or the `Forced*` variants) select the *variant* of that
  label; `BINLoad[i]="no"` skips it. Rank is read and folded into the score.
* **Gilded mechanism**: `GildedTTS="yes"` + `gdeInclude="JorgeGilded.gde"` in the `.vde` make the
  engine load the `.gde` into the same descriptor (`ELQDataDescriptorLoadFile`), which then carries
  the speech-act/paralinguistic phrase inventories. Those phrases are *separate text units*, and
  their audio comes from additional `VocalDBName[1..2]` entries (`JorgeGildedPhrases`,
  `JorgeGildedParalinguistics`) — the `.gde` names are exactly the `P=<name>|…` names in
  `JorgeGildedParalinguistics.sde` (`Aa`, `Aa_01`, … `Yawn_04`) and the `\_<Name>` entries of
  `JorgeGildedPhrases.sde`. So a gilded/speech-act unit enters selection by (a) the `.gde` mapping
  text→phrase name and (b) that name selecting DB slot 1/2 through the same
  `VocalDBName[i]`/`__BinInfo__[i]` machinery; `FonVidAllofonoVoce` (§3) is only consulted for
  normal (non-gilded) phone→voice mapping.
* `Library` is parsed by taking the first token up to `' '`, `','` or `';'` (`LTTS7Jorge`), appending
  `".dll"`, recording it as `FullLibraryName` and its version (`ELQGetComponentVersion`) as
  `LibraryVersion` (old dump `FUN_1001b140`):

```c
    /* decomp_loqtts.txt, FUN_1001b140 (jorge: FUN_10052380, same logic) */
    cVar2 = ELQDataDescriptorGetAttribute(param_1,"Library",&local_6bc,0);
    if ((cVar2 != '\0') && (local_6bc != (char *)0x0)) {
      …copy up to ' ' / ',' / ';' into local_6a4…
      ELQFileFullName(local_204,local_6b8,local_6a4);
      _sprintf(local_6a4,"%s%s",local_204,&DAT_1008b9c0);        /* ".dll" */
      … ELQDataDescriptorSetAttribute(param_1,"FullLibraryName",iVar4,1,ELQfree);
      cVar2 = ELQGetComponentVersion(local_6a4,local_654,0x50);
      … ELQDataDescriptorSetAttribute(param_1,"LibraryVersion",iVar4,1,ELQfree);
    }
    …
    cVar2 = ELQDataDescriptorGetAttribute(param_1,"gdeInclude",&local_6b4,0);
    if ((cVar2 != '\0') && (local_6b4 != 0)) {
      ELQFileFullName(local_604,local_404,local_6b4);
      cVar2 = ELQDataDescriptorLoadFile(param_1,local_604,1);
      if (cVar2 == '\0') { pcVar3 = "Unable to open gilded descriptor file \"%s\"\n"; goto LAB_1001b8aa; }
    }
```

`Library = "LTTS7Jorge, Jorge"` therefore means: DLL `<voices/Jorge>/LTTS7Jorge.dll`, and the second
token `Jorge` is the module's **export name** used with `ELQPluginIni(...,"Jorge",...)` (§3).

## 3. The voice module interface (`LTTS7Jorge.dll`)

The DLL has exactly **one export**, named **`Jorge`**, at **RVA 0x1170** (VA `0x10001170`) —
verified from the PE export directory (`nfunc=1, nname=1, dllname=LTTS7Jorge.dll`). It is a
name-dispatch entry point:

```c
/* jorge_re/decomp_jorge_voice.txt, function "Jorge" @ 10001170 */
undefined * __cdecl Jorge(byte *param_1)                  /* param_1 = requested procedure name */
{
  byte bVar1; byte *pbVar2; int iVar3; byte *pbVar4; int iVar5; bool bVar6;
                    /* 0x1170  1  Jorge */
  if ((param_1 == (byte *)0x0) || (DAT_10008868 != -0x55)) {   /* must equal 0xFFFFFFAB at run time */
    return (undefined *)0x0;
  }
  iVar5 = 0;
  do {
    pbVar4 = (&PTR_s_GetVersion_10008878)[iVar5 * 2];        /* name string */
    pbVar2 = param_1;
    do {
      bVar1 = *pbVar2;
      bVar6 = bVar1 < *pbVar4;
      if (bVar1 != *pbVar4) {
LAB_100011b0:
        iVar3 = (1 - (uint)bVar6) - (uint)(bVar6 != 0);
        goto LAB_100011b5;
      }
      if (bVar1 == 0) break;
      bVar1 = pbVar2[1];
      bVar6 = bVar1 < pbVar4[1];
      if (bVar1 != pbVar4[1]) goto LAB_100011b0;
      pbVar2 = pbVar2 + 2;
      pbVar4 = pbVar4 + 2;
    } while (bVar1 != 0);
    iVar3 = 0;
LAB_100011b5:
    if (iVar3 == 0) {
      return (&PTR_LAB_1000887c)[iVar5 * 2];                 /* target procedure */
    }
    iVar5 = iVar5 + 1;
    if (7 < iVar5) {
      return (undefined *)0x0;
    }
  } while( true );
}
```

`DAT_10008868` is an initialisation magic: its bytes in the file are `ab b1 fe de …`, but the check
compares the dword with `0xFFFFFFAB`, so the value is patched during load before any
`ELQPluginGetProc` call can succeed; every other function in the module is therefore unreachable
until the DLL has been initialised.

### 3.1 The complete name table

Read from the DLL image at VA `0x10008878` (16 dwords = 8 × `{char *name; void *proc}`,
terminated by `iVar5 > 7` in the dispatcher):

| # | name (VA of string) | proc VA | jorge body |
|---|---|---|---|
| 0 | `GetVersion` (`0x100081f4`) | `0x10001150` | copies `"7.1.0"` into the caller buffer |
| 1 | `ELQGetPhonemes` (`0x100081e4`) | `0x10001060` | `*out = 0x100087a0` (phoneme inventory) |
| 2 | `FonVidAllofonoVoce` (`0x100081d0`) | `0x100011e0` | stub: `xor eax,eax; ret` (= `return 0`) |
| 3 | `FonVidAllofonoAnalisi` (`0x100081b8`) | `0x10001260` | allophone→unit-code analysis |
| 4 | `FonVidMetaFonema` (`0x100081a4`) | `0x100013b0` | archiphoneme substitution (delegates to `FUN_100011f0`) |
| 5 | `FonVidAnalisi2Sintesi` (`0x1000818c`) | `0x100013d0` | unit-code remap table |
| 6 | `ELQVoiceChannelOpen` (`0x10008178`) | `0x10001070` | allocate channel (0x18) + resource |
| 7 | `ELQVoiceChannelClose` (`0x10008160`) | `0x10001100` | free channel + resource |

Additional strings in the module: `LTTSComponentVersion=7.1.0` (file off 0x88b8),
`Out of memory for ELQJorgeChannelType` (0x88d4), `Out of memory for FonJorgeChannelType`
(0x8138). Imports: `ELQLogWrite`, `ELQmalloc`, `ELQfree`, `ELQSharedResourceIni`,
`ELQSharedResourceDelete` from `LTTS7Util.dll`.

### 3.2 Recovered bodies and signatures

`GetVersion` — `int GetVersion(char *buf)` (dest = `param_1`; the referenced literal is VA
`0x100088CD`, the `"7.1.0"` tail of the `LTTSComponentVersion=7.1.0` string at `0x100088B8`, while
the sibling Ludoviko module's identical function copies the whole `LTTSComponentVersion=7.4.0`):
```c
undefined4 FUN_10001150(int param_1)          /* param_1 = destination buffer */
{
  char cVar1; char *pcVar2;
  pcVar2 = "7.1.0";
  do {
    cVar1 = *pcVar2;
    pcVar2[param_1 + -0x100088cd] = cVar1;   /* dest = param_1 (Ghidra's base arithmetic) */
    pcVar2 = pcVar2 + 1;
  } while (cVar1 != '\0');
  return 0;
}
```
The engine only tests the return value (`iVar5 = (*(code *)auStack_608)(abStack_404); … iVar5 == 0`)
and compares the produced string with the SDE plugin's `CatVoiceVersion` output in the `LinkedSde`
path.

`ELQGetPhonemes` — `int ELQGetPhonemes(void **outTable)`; returns the module's static phoneme
inventory structure (VA `0x100087A0`, an array of `{char *allophone; …}` entries; the example-word
strings `cuatro, rabia, colcha, calle, cola, pido, coro, cinco, infierno, mancha, noche, kama,
pizza, cocido, Genova, chocolate, show, desde, consejo, juzgar, facil, conyuge, ayuda, llegada,
guerra, escudo, toldo, amaba, bueno, caja, loco, tarde, capa, causa, rey, capitulo, cura, soldado,
coche, retorica, silla, pidenos, pesca, llamo, caro` live at VA `0x10008200…0x10008380` and are the
per-phoneme example words of that table):
```c
undefined4 FUN_10001060(undefined4 *param_1)   /* *param_1 = out table */
{
  *param_1 = &PTR_PTR_100087a0;
  return 0;
}
```

`ELQVoiceChannelOpen` — `int ELQVoiceChannelOpen(void *voiceCtx)`, `voiceCtx+0x4` = out channel,
`voiceCtx+0x10` = engine, `voiceCtx+0x14` = log handle; returns 0 or 5 (`Out of memory`):
```c
int FUN_10001070(int param_1)
{
  undefined4 *puVar1; int iVar2;
  puVar1 = (undefined4 *)ELQmalloc(0x18);                  /* ELQJorgeChannelType, 24 bytes */
  if (puVar1 == (undefined4 *)0x0) {
    ELQLogWrite(1,*(undefined4 *)(param_1 + 0x14),"Out of memory for ELQJorgeChannelType\n");
    return 5;
  }
  puVar1[2] = 0; puVar1[1] = 0; *puVar1 = 0; puVar1[4] = 0; puVar1[5] = 0;
  ELQSharedResourceIni(puVar1 + 5,0,0);                    /* channel+0x14 = shared-resource object */
  iVar2 = FUN_10001000(*(int *)(param_1 + 0x10),puVar1 + 2);  /* allocate FonJorgeChannelType (4B) */
  if (iVar2 == 0) {
    *(undefined4 **)(param_1 + 4) = puVar1;
  }
  return iVar2;
}
```
```c
undefined4 __cdecl FUN_10001000(int param_1,int *param_2)   /* param_2 = &channel[2] */
{
  int iVar1;
  iVar1 = ELQmalloc(4);                     /* FonJorgeChannelType */
  *param_2 = iVar1;
  if (iVar1 == 0) {
    ELQLogWrite(1,*(undefined4 *)(param_1 + 0x14),"Out of memory for FonJorgeChannelType\n");
    return 5;
  }
  *(int *)(param_1 + 0x48) = iVar1;         /* engine-side back pointer */
  return 0;
}
```
Channel layout (**FonJorgeChannelType**) is the `0x18` window anchored at `channel+0xc`, stride
`0x18` per output unit (`*(byte *)(channel + 0xc + i*0x18)`), i.e. 24 bytes per unit, first byte at
`+0xc` = unit/variant code, the remaining 23 bytes are set by the engine.

`ELQVoiceChannelClose` — `int ELQVoiceChannelClose(void *voiceCtx)`:
```c
undefined4 __cdecl FUN_10001100(int param_1)
{
  int iVar1,iVar2,iVar3,iVar4; undefined4 *puVar5;
  if ((param_1 != 0) && (iVar1 = *(int *)(param_1 + 4), iVar1 != 0)) {
    iVar3 = *(int *)(iVar1 + 8);            /* FonJorgeChannelType */
    iVar2 = *(int *)(param_1 + 0x10);       /* engine */
    iVar4 = iVar1 + 0x10;
    puVar5 = (undefined4 *)(iVar1 + 0x14);
    FUN_10001040(iVar2,iVar3);              /* ELQfree(FonJorgeChannelType); engine[0x48]=0 */
    ELQSharedResourceDelete(*(undefined4 *)(iVar1 + 0x14),iVar2,iVar3,iVar4,puVar5);
    ELQfree(iVar1);
    *(undefined4 *)(param_1 + 4) = 0;
  }
  return 0;
}
```

`FonVidAllofonoVoce` — **a no-op in this voice**:
```c
undefined4 FUN_100011e0(void) { return 0; }        /* bytes at 0x100011e0: 33 c0 c3 (xor eax,eax; ret) */
```
The engine still binds it (see 3.3) but for Jorge the allophone→voice-unit decision is entirely
driven by `FonVidAllofonoAnalisi` + the SDE.

`FonVidAllofonoAnalisi(channel, inUnits, inIndex*, table*)` — maps the incoming allophone stream to
**unit variant codes** written into the channel's 24-byte-per-unit array:
```c
undefined4 FUN_10001260(int param_1,int *param_2,int *param_3,int *param_4)
{
  int iVar1,iVar2,iVar3,iVar4; uint uVar5;
  iVar1 = *(int *)(param_1 + 4);            /* channel */
  iVar2 = *param_3;                         /* out index */
  iVar3 = *param_2;                         /* in index  */
  iVar4 = *(int *)(param_1 + 0x10);         /* in array  */
  uVar5 = *(uint *)(*(int *)(iVar4 + iVar3 * 4) + 4);   /* inUnit->tag */
  if (uVar5 < 0x1100405) {
    if (uVar5 == 0x1100404) {
      if ((iVar3 != 0) && (*(int *)(*(int *)(iVar4 + -4 + iVar3 * 4) + 4) == 0x10104)) {
        *(undefined1 *)(iVar1 + 0xc + iVar2 * 0x18) = 0x15;
        *param_3 = iVar2 + 1; *param_2 = *param_2 + 1; return 0;
      }
    }
    else if (uVar5 == 0x1002404) { … *(…)= 0x14; … }
    else if ((uVar5 == 0x1008404) && iVar3 != 0 && (…prev/next tags 0x10104/0x28/0x18…)) { …= 0x13; … }
  } else if ((uVar5 == 0x3008014) && (iVar3 == 0)) { …= 0x1c; … }
  FUN_100011f0(param_3,param_4);            /* default: look up in the caller's table */
  return 0;
}
```
Default lookup (`FUN_100011f0`) walks a caller-supplied table of 16-byte entries
`{…, +4:byte unitCode, +8:int allophoneTag, …}` and writes the matching entry's `+4` byte into the
unit slot, else writes `1`:
```c
undefined4 __fastcall FUN_100011f0(int *param_1,int *param_2)   /* param_1=index, param_2=table */
{
  int in_EAX; uint uVar1; int *unaff_ESI; int *piVar2;
  uVar1 = 0;
  if (param_2[1] != 0) {
    piVar2 = (int *)(*param_2 + 8);
    do {
      if (*piVar2 == *(int *)(*(int *)(*(int *)(in_EAX + 0x10) + *unaff_ESI * 4) + 4)) {
        *(undefined1 *)(*(int *)(in_EAX + 4) + 0xc + *param_1 * 0x18) =
             *(undefined1 *)(uVar1 * 0x10 + 4 + *param_2);
        *param_1 = *param_1 + 1; *unaff_ESI = *unaff_ESI + 1; return 0;
      }
      uVar1 = uVar1 + 1;
      piVar2 = piVar2 + 4;
    } while (uVar1 < (uint)param_2[1]);
  }
  *(undefined1 *)(*(int *)(in_EAX + 4) + 0xc + *param_1 * 0x18) = 1;   /* fallback code 1 */
  *param_1 = *param_1 + 1; *unaff_ESI = *unaff_ESI + 1; return 0;
}
```

`FonVidMetaFonema(a,b,index*,table*)` — archiphoneme/metaphoneme resolution, same default lookup:
```c
undefined4 FUN_100013b0(undefined4 param_1,undefined4 param_2,int *param_3,int *param_4)
{ FUN_100011f0(param_3,param_4); return 0; }
```

`FonVidAnalisi2Sintesi(uchar code) -> uchar` — pure remap of analysis codes to synthesis codes:
```c
undefined1 FUN_100013d0(undefined1 param_1)
{
  switch(param_1) {
  case 0x13: return 0x12;
  case 0x14: return 0x10;
  case 0x15: return 0x11;
  case 0x1a: return 0x19;
  case 0x1c: return 0x1b;
  case 0x1e: return 0x1d;
  case 0x24: param_1 = 0x23;
  }
  return param_1;
}
```

### 3.3 Engine-side call sites

The engine binds the module with `ELQPluginIni(...,"Jorge",...)` and stores each resolved procedure
into a fixed slot of the **voice object**:

```c
/* decomp_loqtts_jorge.txt, FUN_1002d730 (voice channel init), 32346-32390 */
  iVar4 = (*DAT_100b72d0)(*(undefined4 *)(in_EAX + 0x14));      /* ELQPluginGetFileName */
  if (iVar4 != 0) {
    uVar3 = *(undefined4 *)(*(int *)(*(int *)(in_EAX + 4) + 4) + 0xc00);
    iVar5 = FUN_1002cf20(uVar3);                               /* validate VoicePhonemeTable */
    if (iVar5 == 0) {
      piVar1 = (int *)(in_EAX + 0x1c);
      piVar2 = (int *)(in_EAX + 0x20);
      *(undefined4 *)(in_EAX + 0x18) = 0;   *piVar1 = 0;   *piVar2 = 0;
      *(undefined4 *)(in_EAX + 0x24) = 0;   *(undefined4 *)(in_EAX + 0x28) = 0;
      if (*(int *)(in_EAX + 0x14) == 0) {
        *piVar1 = (int)&LAB_1002d100;  *piVar2 = (int)&LAB_1002d100;  return 0;
      }
      iVar5 = (*DAT_100b72d8)(*(int *)(in_EAX + 0x14),"FonVidAllofonoVoce",
                              (undefined4 *)(in_EAX + 0x18));
      if (iVar5 != 0) {
        (*DAT_100b7148)(1,uVar3,"Error loading FonAllofonoVoce procedure from %s\n",iVar4);
        return iVar5;
      }
      iVar5 = (*DAT_100b72d8)(*(undefined4 *)(in_EAX + 0x14),"FonVidIngloba",
                              (undefined4 *)(in_EAX + 0x28));
      if (iVar5 == 0) {
        iVar5 = (*DAT_100b72d8)(*(undefined4 *)(in_EAX + 0x14),"FonVidAllofonoAnalisi",piVar1);
        if (iVar5 == 0) {
          if (*piVar1 == 0) { *piVar1 = (int)&LAB_1002d100; }
          iVar5 = (*DAT_100b72d8)(*(undefined4 *)(in_EAX + 0x14),"FonVidMetaFonema",piVar2);
          if (iVar5 != 0) { (*DAT_100b7148)(1,uVar3,"Error loading FonMetafonema procedure from %s\n",iVar4); return iVar5; }
          if (*piVar2 == 0) { *piVar2 = (int)&LAB_1002d100; }
          iVar5 = (*DAT_100b72d8)(*(undefined4 *)(in_EAX + 0x14),"FonVidAnalisi2Sintesi",
                                  in_EAX + 0x24);
          if (iVar5 == 0) { return 0; }
          (*DAT_100b7148)(1,uVar3,"Error loading FonAnalisi2Sintesi procedure from %s\n",iVar4);
          return iVar5;
        }
        pcVar6 = "Error loading FonAllofonoAnalisi procedure from %s\n";
      }
      else { pcVar6 = "Error loading FonIngloba procedure from %s\n"; }
```

| voice-object slot | procedure | jorge target | default if absent |
|---|---|---|---|
| `+0x14` | plugin instance (HINSTANCE) | — | — |
| `+0x18` | `FonVidAllofonoVoce` | `0x100011e0` (stub) | required (error logged) |
| `+0x1c` | `FonVidAllofonoAnalisi` | `0x10001260` | `&LAB_1002d100` |
| `+0x20` | `FonVidMetaFonema` | `0x100013b0` | `&LAB_1002d100` |
| `+0x24` | `FonVidAnalisi2Sintesi` | `0x100013d0` | required (error logged) |
| `+0x28` | `FonVidIngloba` | **absent in Jorge** | lookup tolerated |
| `+0x248` | plugin HINSTANCE used for `ELQPluginGetProc` | — | — |
| `+0x24c` / `+0x250` | `ELQVoiceChannelOpen` / `ELQVoiceChannelClose` | `0x10001070` / `0x10001100` | — |

The other call sites (verbatim):

```c
/* decomp_loqtts_jorge.txt, voice channel set-up */
8663:  iVar4 = (*DAT_100b72d8)(*(int *)(unaff_EDI + 0x248),"ELQVoiceChannelOpen",unaff_EDI + 0x24c);
8670:  iVar4 = (*DAT_100b72d8)(*(undefined4 *)(unaff_EDI + 0x248),"ELQVoiceChannelClose", …);
8679:  iVar4 = (*DAT_100b72d8)(*(undefined4 *)(unaff_EDI + 0x248),"ELQGetPhonemes",&pcStack_208);
8367:  iVar4 = (*DAT_100b72d8)(*(undefined4 *)(param_1 + 0x230),"ELQGetPhonemes",&pcStack_60c);   /* language module */
32302:  iVar4 = (*DAT_100b72d8)(*(undefined4 *)(in_EAX + 0x10),"FonAllofonoLingua", …);           /* language module */
```
```c
/* ELQGetPhonemes usage: the returned handle is stored in the phonetic modules */
  iVar4 = (*DAT_100b72d8)(*(undefined4 *)(unaff_EDI + 0x248),"ELQGetPhonemes",&pcStack_208);
  if ((iVar4 != 0) || (pcStack_208 == (code *)0x0)) {
    pcVar8 = "Unable to find phoneme table in dynamic voice library\n"; … }
  iVar4 = (*pcStack_208)(&iStack_20c);
  …
  piVar2 = *(int **)(unaff_EDI + 0x218);
  if ((piVar2 != (int *)0x0) && ((code *)*piVar2 == FUN_1002b0f0)) { piVar2[3] = iStack_20c; }
  piVar2 = *(int **)(unaff_EDI + 0x21c);
  if ((piVar2 != (int *)0x0) && ((code *)*piVar2 == FUN_10043980)) { piVar2[3] = iStack_20c; }
  piVar2 = *(int **)(unaff_EDI + 0x220);
  if ((piVar2 != (int *)0x0) && ((code *)*piVar2 == FUN_10021230)) { piVar2[5] = iStack_20c; }
```

The phoneme table returned by `ELQGetPhonemes` is validated by the engine before use — records of
16 (`0x10`) bytes with the code byte at `+4` equal to the record index:

```c
/* decomp_loqtts_jorge.txt, FUN_1002cf20 */
undefined4 __cdecl FUN_1002cf20(undefined4 param_1)
{
  uint uVar1; int *in_EAX; uint uVar2; ushort uVar3;
  if (in_EAX == (int *)0x0) return 4;
  uVar1 = in_EAX[1]; uVar3 = 0;
  if (uVar1 != 0) { uVar2 = 0;
    do {
      if (uVar3 != *(byte *)(uVar2 * 0x10 + 4 + *in_EAX)) {
        (*DAT_100b7148)(1,param_1,"Corrupted index in VoicePhonemeTable: i=%d cod=%d len=%d\n",
                        (uint)uVar3,*(undefined1 *)((uint)uVar3 * 0x10 + 4 + *in_EAX),uVar1);
        return 4; }
      uVar3 = uVar3 + 1; uVar2 = (uint)uVar3;
    } while (uVar2 < uVar1); }
  return 0;
}
```

The error strings `"Error loading FonAllofonoVoce procedure from %s"`,
`"Error loading FonAllofonoAnalisi procedure from %s"`,
`"Error loading FonAnalisi2Sintesi procedure from %s"`, `"Error loading FonIngloba procedure from %s"`
and `"Unable to find phoneme table in dynamic voice library"` show which procedures the engine
requires. The engine also probes `FonAllofonoLingua` on the *language* module
(`in_EAX+0x10`), which the Jorge voice module does not export.

## 4. Unit → frame mapping (what reaches the codec)

### 4.1 The codec plugin ABI

`LTTS7Codec210.dll` (jorge) has one export `LTTS7Codec210` at RVA 0x4760 (old build 0x4760 too,
see `decomp_codec210.txt`). Its name table is at file offset 0x22090 (VA `0x10022C90`) and contains
`ELQDecode`, `DecoderFileChanged`, `GetDecodedFileSize`, `ELQCloseDecoder`, `ELQOpenDecoder`,
`GetVersion`, plus `LoadUtilSymbols`. The engine binds it with

```c
/* decomp_loqtts_jorge.txt, FUN_10022890 */
int __cdecl FUN_10022890(undefined4 param_1)     /* param_1 = log handle; in_EAX = decoder struct */
{
  int *in_EAX; int iVar1;
  if (*in_EAX == 0) { (*DAT_100b7148)(1,param_1,"Error in accessing decoder functions\n"); return 0; }
  iVar1 = (*DAT_100b72d8)(*in_EAX,"ELQOpenDecoder",in_EAX + 3);      /* slot [3] */
  if (iVar1 != 0) { …"Error in detecting \"OpenDecoder\" function\n"… }
  iVar1 = (*DAT_100b72d8)(*in_EAX,"ELQDecode",in_EAX + 1);           /* slot [1] */
  …
  iVar1 = (*DAT_100b72d8)(*in_EAX,"ELQGetDecodedFileSize",in_EAX + 2);/* slot [2] */
    iVar1 = (*DAT_100b72d8)(*in_EAX,"ELQCloseDecoder",in_EAX + 4);    /* slot [4] */
      iVar1 = (*DAT_100b72d8)(*in_EAX,"ELQDecoderFileChanged",in_EAX + 5); /* slot [5] */
```
So the decoder object is `{ [0]=plugin handle, [1]=ELQDecode, [2]=ELQGetDecodedFileSize,
[3]=ELQOpenDecoder, [4]=ELQCloseDecoder, [5]=ELQDecoderFileChanged }` (the 7-entry ABI of CONTEXT §C,
slot 6 being the plugin's own state) and, e.g.,

```c
/* FUN_10022560 (open) and FUN_100225e0 (close) */
      iVar2 = (*(code *)piVar1[9])(&local_4,(short)unaff_ESI[0x8d], *(undefined4 *)(*(int *)unaff_ESI[6] + 0xc00));
      if (iVar2 != 0) { (*DAT_100b7148)(1,…,"Error opening decoder\n"); return iVar2; }
      unaff_ESI[0x91] = local_4;                      /* decoder handle kept in the Sig object */
      …
    if ((unaff_EDI[0x91] != 0) && ((code *)piVar1[10] != (code *)0x0)) {
      (*(code *)piVar1[10])(unaff_EDI[0x91]);         /* CloseDecoder(handle) */
    }
```

### 4.2 One voice unit → one decoder request

`FUN_1001faa0` is the per-unit synthesis driver:

```c
/* decomp_loqtts_jorge.txt, FUN_1001faa0 (param_1 = Sig/sequencer, param_2 = state, param_3 = unit) */
int __cdecl FUN_1001faa0(int *param_1,int param_2,int *param_3)
{
  …
  iVar3 = *param_1;
  if (*(int *)(iVar3 + 0x20) == 0) {
    uVar2 = (*DAT_100b7064)(param_1[0xb],2);            /* ELQBinGetSize(bin,2) */
    *(undefined4 *)(param_2 + 0x130c) = uVar2;
  }
  else {
    uVar2 = (*DAT_100b7064)(param_1[0xb],1,param_2 + 0x130c);   /* ELQBinGetSize(bin,1,out) */
    (**(code **)(iVar3 + 0x20))(uVar2);
  }
  FUN_1001f790(param_3[0x52],(char *)param_3[1]);
  FUN_1001ddd0((int)auStack_28,(int)param_3,*(uint *)(param_2 + 0x130c));   /* read unit's .bin sub-header */
  iVar3 = FUN_1001f580(param_1,(int)param_3);           /* ★ the decoder request ★ */
  if (iVar3 == 0) {
    if (((char)param_3[4] != '\x02') && ((char)param_3[4] != '\x03')) {
      FUN_1001e3a0((int)param_1,(int)param_3);          /* pitch-mark placement / PSOLA stretch */
      …
    }
    FUN_1001deb0(param_2);
    FUN_1001ea60(…, (short)param_3[0x51]);
    …
    iVar3 = FUN_1001f8e0((int)param_1);
```

and the request itself:

```c
/* decomp_loqtts_jorge.txt, FUN_1001f580 (param_1 = Sig, param_2 = unit descriptor) */
int __cdecl FUN_1001f580(int *param_1,int param_2)
{
  …
  uVar5 = ((*(ushort *)(unaff_ESI + 0x4c1) / 10) * 400) / 20000;      /* = Fs/500 samples margin */
  if ((*(int *)(param_2 + 0xc) == 2) || (*(int *)(param_2 + 0xc) == 4)) {
    uVar5 = uVar5 * 4;
  }
  unaff_ESI[0x4b8] = 0;
  local_4 = uVar5;
  if (unaff_ESI[0x4b9] == 0) { local_4 = 0; }
  if ((*(char *)(param_2 + 0x10) == '\x02') || (*(char *)(param_2 + 0x10) == '\x03')) {
    iVar6 = param_1[0x54c] - param_1[0x54b];
    iVar4 = (iVar6 + local_4 + uVar5) * 2;
    …
    iVar2 = (*DAT_100b747c)(unaff_ESI[2],iVar4);            /* ELQBufferAlloc(outBuf,n) */
    if (iVar2 == 0) {
      iVar2 = (*DAT_100b74b0)(unaff_ESI[2],0,iVar4);        /* ELQBufferFill */
      …
      goto LAB_1001f731;
    }
  }
  else {
    iVar6 = unaff_ESI[0x4ba] - unaff_ESI[0x4b9];            /* ★ unit length in samples */
    iVar4 = iVar6 + local_4 + uVar5;                        /* + pre-roll + post-roll  */
    iVar2 = (*DAT_100b747c)(unaff_ESI[2],iVar4 * 2 + 400);
    if (iVar2 == 0) {
      if (*(code **)(*param_1 + 0x1c) == (code *)0x0) {
        pcVar3 = "Error. Decoder function is missing.\n";
      }
      else {
        iVar2 = (**(code **)(*param_1 + 0x1c))              /* ★★ the decoder call ★★ */
                          (param_1[0x91],                    /* 1: ELQOpenDecoder handle      */
                           unaff_ESI[0x4b9] - local_4,       /* 2: start position (samples-pre)*/
                           iVar4,                            /* 3: sample count (incl. margins)*/
                           *(undefined4 *)unaff_ESI[2],      /* 4: out buffer (short[])        */
                           param_1[0xb]);                    /* 5: ELQBin handle of the DB     */
        if (iVar2 == 0) {
          (*DAT_100b74c0)((undefined4 *)unaff_ESI[2],*(undefined4 *)unaff_ESI[2],iVar4 * 2, iVar4 * 2);
          *(bool *)(unaff_ESI + 400) = *(char *)(param_2 + 0x150) == '0';
          goto LAB_1001f731;
        }
        param_1[0x91] = 0;
        pcVar3 = "Error decoding signal.\n";
      }
      (*DAT_100b7148)(1,*(undefined4 *)(*(int *)param_1[6] + 0xc00),pcVar3);
      iVar2 = 4;
    }
  }
  return iVar2;
}
```

**Conclusion:** the decoder receives **(handle, start-in-samples, count-in-samples, short* out,
ELQBin handle of the .bin)**. Neither a frame index nor a byte offset crosses this boundary. The
samples→frame→byte conversion happens **inside the codec**, quoted in §4.5 below; also:
`ELQGetDecodedFileSize` always returns `-1` ("unknown"), and `ELQBinGetSize(bin,which)` is a
**divisor** (`which=1` → byte size, `which=2` → size/2 = 16-bit sample count) — which is why
`FUN_1001faa0` calls `ELQBinGetSize(param_1[0xb],2)` when it wants a sample count for the output
buffer. Engine-side `ELQBin*` access exists only for non-codec containers (e.g. WAV:
`FUN_10018150` does `ELQBinGetSize(url,1)` + `ELQBinGetBuffer(url,0,min(size,0x400),1,0,&out)` and
parses `RIFF/WAVE`).

### 4.3 Position scaling — SDE positions are 10 µs units

`FUN_1001e3a0` converts the unit's start/end (fields at `param_1+0x155c` / `param_1+0x1564`) into
samples, and places the pitch marks:

```c
/* decomp_loqtts_jorge.txt, FUN_1001e3a0 (head) */
  uVar14 = *(uint *)(param_1 + 0x155c);              /* unit start */
  uVar16 = *(uint *)(param_1 + 0x1564);              /* unit end   */
  if (uVar16 == uVar14) { return; }
  uVar1 = *(ushort *)(param_1 + 0x234);              /* sample rate, e.g. 32000 */
  uVar13 = (uint)uVar1;
  uVar18 = ((uVar14 % 100000) * (uVar13 / 10)) / 10000;
  iVar4 = (uVar14 / 100000) * uVar13 + uVar18;       /* start sample = pos * Fs / 100000 */
  uVar18 = ((uVar16 / 100000 - uVar14 / 100000) * uVar13 +
           ((uVar16 % 100000) * (uVar13 / 10)) / 10000) - uVar18;   /* length in samples */
  iVar11 = **(int **)(param_1 + 0x250) + *(int *)(param_1 + 0x25c) * 2;   /* pitch-mark source (short*) */
  if (*(char *)(param_2 + 0x150) != '0') {
    if (*(char *)(param_2 + 0x150) == 'u') {
      uVar14 = uVar1 / 0x7d;                          /* Fs/125 → target pitch period */
      uVar16 = uVar18 / uVar14;
      *(int *)(param_1 + 0x1128) = iVar4;
      local_5c = 1;
      … place pitch marks: *(int *)(param_1 + 0x1128 + local_5c*4) = iVar4 …
    }
    goto LAB_1001ea01;
  }
  if (*(uint *)(param_2 + 0x140) == 0) {
     … pitch-mark picker over the waveform (peak search, window 0x32..0xc6 samples …
  } else {
    local_48 = (uint)uVar1 / *(uint *)(param_2 + 0x140);    /* Fs / pitch-ratio */
  }
```

i.e. **`sample = pos × Fs / 100000`**, i.e. **1 position unit = 100000⁻¹ s = 10 µs** (a 20 ms frame
= 2000 units = 640 samples @ 32 kHz). The pitch-mark array (`param_1+0x1128`, one dword per mark,
count `local_5c`) is then filled by TD-PSOLA-style period selection: either from the recorded
pitch-mark waveform (`param_2+0x150 == '0'`, peak search in the window `0x32…0xc6` samples from
`param_2+0x140 == 0`) or at a target period `Fs / (param_2+0x140)` (pitch scaling), and with
`param_2+0x150 == 'u'` (uniform/voiced) at `Fs/125`. This is where **pitch and duration
stretching** happen (the decoded signal is never resampled; marks are re-spaced and the segments
re-overlapped-add); `param_2+0x150/'u'`, `param_2+0x140` and `param_2+0x10c` (coding) are the prosody
inputs.

### 4.4 Worked example (real unit: `Aa` of the paralinguistics DB)

`.sde` → descriptor. `JorgeGildedParalinguistics.sde` (bit-7-cleared) begins:

```
P=Aa|0|61846
P=Aa_01|61846|150218
P=Aa_02|150218|258078
…
P=Yawn_04|19325121|19915859
```

For `P=Aa|0|61846` the engine holds start = `0`, end = `61846` (10 µs units) in
`param_1+0x155c` / `param_1+0x1564` and the unit's name `Aa` (the `param_2+0x118` string copied in
`FUN_1001f580`/`FUN_1001f8e0`). The paralinguistics DB
`JorgeGildedParalinguistics.32000.LTTS7Codec210.44000.10.bin` is 1095572 B = header 164 + 28 +
9958 × 110 B, i.e. 640 samples/frame @ 32000 Hz, 110 B/frame.

`FUN_1001e3a0` computes (Fs = 32000):

* start sample = `0 / 100000 * 32000 + (0 % 100000) * 3200 / 10000` = **0**
* length      = `(61846/100000)*32000 + (61846 % 100000)*(3200)/10000` − 0 = `197907200/10000` = **19790 samples**
  (= 0.6183 s ✓ vs 61846 × 10 µs)

`FUN_1001f580` then calls the decoder with (margin `local_4`; `unaff_ESI[0x4b9] == 0` ⇒ margin 0,
post-roll `uVar5 = Fs/500 = 64`):

| argument | value | unit |
|---|---|---|
| 1 decoder handle | from `ELQOpenDecoder` | — |
| 2 offset | `0 − 0` = **0** | samples (into the decoded stream of the DB) |
| 3 count | `19790 + 0 + 64` = **19854** | samples |
| 4 out buffer | `ELQBufferAlloc(out, 19854*2 + 400)` = 40108 B | int16 PCM |
| 5 DB handle | `param_1[0xb]` = ELQBin handle registered by `ELQBinaryHeaderLoadInfo` (header `Label` = `JorgeGildedParalinguistics`, `Freq`=32000, `Coding`=LTTS7Codec210, `BitRate`=44000, `Rank`=10) | — |

**Which SDE fields are read for this unit:** the record is the `P=` line, whose three fields are
`name | start | end`; the *positions* are the only numeric fields, they are 10 µs units, and they are
consumed as `param_1+0x155c` (start) / `param_1+0x1564` (end) by `FUN_1001e3a0` and as the sample
cursor `unaff_ESI[0x4b9]`/`[0x4ba]` by `FUN_1001f580`. The `name` (`Aa`) is the phrase key that the
`.gde` maps from the speech-act/paralinguistic text and it is carried in the unit descriptor as the
string at `param_2+0x118` (`FUN_1001f8e0`: `pcVar3 = (char *)(in_EAX + 0x118); … copy into
unaff_ESI+0x628-relative buffer`).
*[INFERENCE]*: the `.sde` **record parser itself** (which reads the bit-7-set text and fills
`+0x155c`/`+0x1564`) is not present in the engine dump under any of the names used here; the
identification of the `P=name|start|end` fields with those two slots rests on (a) the field set being
the only numeric content of the record, (b) the range check `max(end) = 19915859 ≤ 9958 × 2000 =
19916000 = frames × 2 ms`, and (c) the exact `pos × Fs / 100000` conversion in `FUN_1001e3a0`. The
byte-level `.sde` encoding is `SdeFormat`'s remit.

The codec converts `sample 0 → frame 0` and `19854 samples → 19854/640 = 31.02 → 32 frames` using
the 28-byte BE sub-header of the `.bin` (`[BitRate=44000, Rank=10, samples_per_frame=640,
Freq=32000, bytes_per_frame=110, frame_count=9958, cookie]`) and fetches the compressed bytes itself
with `ELQBinGetBuffer(bin, 110·i + 28 + 122, 110, 1, 0, &eof)` = file offset `164 + 110·i`
(§4.5), un-XORing each frame with the cookie LSB `0x91` before bit-unpacking. If instead the unit
were taken from the main DB (`Jorge.sde`, Fs = 32000, 264948 frames, 110 B/frame, frame *i* at
150 + i·110, frame XOR key `d[27] = 0x6D`), a start of e.g. 2000 units would give offset
`2000*32000/100000 = 640` samples = frame 1, and a length of 2000 units → 704 samples incl. the
64-sample post-roll.

### 4.5 Inside the codec: the exact byte request, and per-frame obfuscation

`LTTS7Codec210.dll` (jorge) exports one symbol `LTTS7Codec210` @ RVA **0x4760** (VA `0x10004760`),
an 8-entry dispatcher over `{name; handler}` pairs at VA `0x1002e028`:

| # | name | handler VA | role |
|---|---|---|---|
| 0 | `LoadUtilSymbols` | `0x10004130` | `GetProcAddress(utilLib,…)` for 5 names into slots at `0x1002f624…` |
| 1 | `GetVersion` | `0x100041f0` | writes `"7.14.0"` (6 bytes) — verified constant `0x372e31342e30` at `0x10022db8` |
| 2 | `ELQOpenDecoder` | `0x100045e0` | allocate + sample-rate tables |
| 3 | `ELQCloseDecoder` | `0x10004730` | free |
| 4 | `ELQGetDecodedFileSize` | `0x10004220` | `*out = 0xffffffff` (−1 "unknown") |
| 5 | `ELQGetDecoderDescription` | `0x100041c0` | returns `"Loq210"` |
| 6 | `ELQDecoderFileChanged` | `0x100041d0` | `*(u8*)(dec+0x11e5)=0; *(u32*)(dec+0x4c)=arg` → resets the header state and sets the payload offset |
| 7 | `ELQDecode` | `0x10004530` | decode N samples |

The five Util names the codec itself resolves (`LoadUtilSymbols`) are
`ELQBinGetBuffer → DAT_1002f624`, `ELQLogWrite → DAT_1002f628`, `ELQfree → DAT_1002f62c`,
`ELQmalloc → DAT_1002f630`, `ELQstricmp → DAT_1002f634` — i.e. **the codec's only file access is
`ELQBinGetBuffer`**.

`ELQOpenDecoder(out, sampleRate, log)` (`codec_handlers.txt`, verbatim):

```c
undefined4 FUN_100045e0(undefined4 *param_1,int param_2,int param_3)
{
  int *_Dst; …
  _Dst = (int *)(*DAT_1002f630)(0x11e8);                 /* ELQmalloc(0x11e8) */
  *param_1 = _Dst;
  if (_Dst == (int *)0x0) { return 5; }
  _memset(_Dst,0,0x11e8);
  … param_2 == 8000:  *(u16*)((int)_Dst+0x11d2) = 0xa0;  _Dst[0xd] = 0x6e;  _Dst[0xe] = 3;  …
  … param_2 == 16000: *(u16*)((int)_Dst+0x11d2) = 0x140; _Dst[0xd] = 0xe0;  _Dst[0xe] = 3;  …
  … param_2 != 32000: (*DAT_1002f628)(1,param_3,"Unable to create LoqCodec210 decoder (SampleRate not supported)\n");
                      (*DAT_1002f62c)(_Dst); return 4;
  *(undefined2 *)((int)_Dst + 0x11d2) = 0x280;           /* 640 samples/frame @32 kHz */
  _Dst[0xd] = 0x1fd;                                     /* 509 = lead-in samples (+0x34) */
  _Dst[0xe] = 6;                                         /* +0x38 = re-prime depth          */
  _Dst[9] = (int)&PTR_PTR_10023b2c;                      /* model table                     */
  …
  _Dst[0xc] = param_2;                                   /* +0x30 sample rate  */
  _Dst[0xb] = param_3;                                   /* +0x2c log handle   */
  _Dst[0x477] = -2; _Dst[0x478] = -2;                    /* +0x11dc/+0x11e0 cursors */
  FUN_100012e0(_Dst);                                    /* bit-reader buffer */
  return 0;
}
```

`ELQDecode(decoder, samplePos, nSamples, dstInt16, bin)` (`codec_handlers.txt`, verbatim):

```c
undefined4 __thiscall
FUN_10004530(uint3 param_1,int param_2,uint param_3,uint param_4,int param_5,int param_6)
{                                       /* param_2=decoder, param_3=samplePos, param_4=nSamples,
                                           param_5=dst buffer, param_6=bin handle */
  …
  if (param_2 == 0) return 4;
  if (param_4 == 0) return 0;
  if (param_5 == 0) return 4;
  if (param_6 == 0) return 4;
  if (*(char *)(param_2 + 0x11e5) == '\0') {            /* first call: parse sub-header */
    iVar2 = (*DAT_1002f624)(param_6,*(undefined4 *)(param_2 + 0x4c),0x1c,1,0,(int)&uStack_4 + 3);
    *(short *)(param_2 + 0x11d0) = (short)*(char *)(iVar2 + 0x13);   /* sub-header byte 19 → 110 B/frame */
    *(undefined1 *)(param_2 + 0x11e4) = *(undefined1 *)(iVar2 + 0x1b);/* sub-header byte 27 → frame XOR key */
    *(undefined1 *)(param_2 + 0x11e5) = 1;
  }
  iVar2 = *(int *)(param_2 + 0x34);                     /* lead-in: 509 @32 kHz */
  param_3 = param_3 + iVar2;                            /* samplePos += lead-in */
  do {
    uVar3 = FUN_10004340((uint3)iVar2,&param_5,&param_3,uVar3,iVar1);
    iVar2 = extraout_ECX;
  } while (uVar3 != 0);
  return 0;
}
```

i.e. `ELQBinGetBuffer(bin, 0x4c-field, 0x1c, 1, 0, &subHeader)` fetches the 28-byte BE sub-header,
whose **byte 19** gives `bytes_per_frame` (110) and **byte 27** the per-frame XOR key. Then the
per-frame reader (`codec210_new.txt`, jorge VA `0x10004340`, verbatim):

```c
uint __thiscall FUN_10004340(uint3 param_1,int *param_2,uint *param_3,uint param_4,undefined4 param_5)
{
  int in_EAX; uint uVar1,uVar2,uVar3; int iVar4; void *_Dst,*_Src; undefined4 uStack_4;
  uVar2 = (uint)*(short *)(in_EAX + 0x11d2);            /* samples/frame = 640 */
  uVar3 = *param_3;                                     /* samplePos */
  uVar1 = uVar3 / uVar2;                                /* ★ frameIndex = samplePos / 640 */
  …
      iVar4 = (*DAT_1002f624)(param_5,(int)*(short *)(in_EAX + 0x11d0) * uVar1 + 0x1c +
                                      *(int *)(in_EAX + 0x4c),(int)*(short *)(in_EAX + 0x11d0),1,0,
                              (int)&uStack_4 + 3);      /* ★ ELQBinGetBuffer(bin, off, 110, 1, 0, &eof) */
      if (uStack_4._3_1_ == '\x01') {                   /* eof flag → silence */
        _memset(*(void **)(in_EAX + 0x11d4),0,*(short *)(in_EAX + 0x11d2) * 2);
        *(uint *)(in_EAX + 0x11dc) = uVar1; return param_4; }
      if (iVar4 != 0) { FUN_10004290(); }               /* ★ un-XOR + bit-unpack + model decode */
      *(uint *)(in_EAX + 0x11dc) = uVar1;
      return param_4;
```
so the exact request is

```
byteOffset = bytes_per_frame(110) * frameIndex + 28 + *(u32*)(decoder+0x4c)
byteLength = bytes_per_frame(110), elemSize = 1
```
with `frameIndex = samplePos / 640` and `*(decoder+0x4c) = 122` (payload offset, set by
`ELQDecoderFileChanged`) ⇒ `byteOffset = 150 + 110·frameIndex`, matching the container layout
(`110·264948 + 28 + 122 = 29144430` = file size). Cache: the decoder keeps the current frame and the
previous one (`+0x11d4` / `+0x11d8`, 640 int16 each) and only re-reads when `frameIndex` changes;
a random seek re-primes from `frameIndex - 6` (`*(decoder+0x38) = 6`, the `_Dst[0xe]` above).

**Per-frame obfuscation (verified, contradicts the "data region is not obfuscated" premise).**
`FUN_10004290` XORs every byte of the fetched frame with the key read from sub-header byte 27 before
the bit-unpacker/model run; for the three shipped Jorge DBs the keys are 0x6d / 0x15 / 0x91 and

| file | header key `d[0]^d[1]` | header size | frame byte-0 raw set | after `^key` |
|---|---|---|---|---|
| `Jorge.32000.LTTS7Codec210.44000.10.bin` | 0x02 | 122 | `{0x50…0x57}` | `{0x38…0x3F}` |
| `JorgeGildedPhrases.…bin` | 0x7c | 148 | `{0x28…0x2F}` | `{0x38…0x3F}` |
| `JorgeGildedParalinguistics.…bin` | 0xe2 | 164 | `{0xA8…0xAF}` | `{0x38…0x3F}` |

All three normalise to the *same* tag set `0x38…0x3F` only after XOR with their own cookie LSB, so
the payload is byte-XORed per frame with that key; treating the payload as plaintext yields noise.

### 4.6 `ELQBin*` semantics (Util, jorge)

```c
/* ELQBinGetSize @ 0x10003b00 — 2nd arg is a DIVISOR */
uint ELQBinGetSize(int *bin, uint which) {
  if (bin == 0 || (code *)bin[0] != ELQBinOpen) return 0;
  if (which != 0 && (t=BYTE(bin+9), t=='d'||t=='m'||t=='r') && bin[3] != 0)
      return *(uint *)bin[3] / which;          /* which=1 → bytes, which=2 → 16-bit samples */
  return 0; }
/* ELQBinGetRawData @ 0x10003110 — zero-copy base pointer; 0 for access type 'd' */
int ELQBinGetRawData(int *bin) {
  if (bin && (code*)bin[0]==ELQBinOpen && *(char*)((int)bin+9) != 'd') return bin[1];
  return 0; }
/* ELQBinSeek @ 0x10003fc0 — shifts the window by delta*elemSize */
/* ELQBinGetBuffer @ 0x10003f90 → FUN_10003ba0: byteOffset = offset*elemSize, byteLen = count*elemSize;
   every path memcpy()s/fread()s into a heap buffer and returns that pointer (never a pointer into the
   mapping); minimum internal capacity 0x2800 bytes. */
```
Access types: `'d'` = lazy disk cache (`FILE*` + `fseek/fread`), `'m'` = memory-mapped file,
`'r'` = whole file read into RAM, `'s'` = shell. `ELQBinInitSmartBuffer` = `malloc(8)` giving
`{void *data; uint capacity;}`; `ELQBinGetSmartBufferCore` returns `*data`; `ELQBinResizeSmartBuffer`
grows it; the "smart buffer" is **not** offset-keyed — it is just the caller-owned destination
buffer, so the caller (the codec) does the frame caching itself. The engine opens the voice DB with
`ELQBinOpen(&bin, 'd'=100, log, filename)` (`FUN_1001e0e0`) and only ever calls `ELQBinSeek` once,
with `delta = 0`.

## 5. Verification status / open points

* Verified against the jorge DLLs: the dispatch table and all eight procedure bodies (§3,
  `jorge_re/decomp_jorge_funcs.txt` was produced by `tools/EngineBindDumpFuncs.java`, which creates
  the functions Ghidra had missed; the dispatcher/`FUN_10001000/40/1100/11f0` bodies are also in
  `jorge_re/decomp_jorge_voice.txt`), `FUN_10044450`/`FUN_10043f50`/`FUN_10044040`/`FUN_100444d0`/
  `FUN_10043cb0`, `FUN_10052380`, `FUN_10052340`, `ELQBinaryHeaderLoadInfo`, the constants of §1.2,
  and the whole §4.1–4.6 code (the codec handler bodies are quoted from
  `codec_handlers.txt`/`codec210_new.txt`, produced by the codec-side disassembly).
* Cross-check: the older sibling module `LTTS7Ludoviko.dll` (`decomp_ludoviko.txt`) exports a 4-entry
  dispatcher and its `FUN_10001150` copies `"LTTSComponentVersion=7.4.0"` — the same
  `LTTSComponentVersion=` scheme, at a different version, confirming the chain.
* `DataPath`'s exact use in `FUN_100444d0` is not visible in the decompilation (see §1.6 note).
* `FUN_1001e0e0` (Sig "set database") resolves and `ELQBinOpen`s the chosen `.bin` per type 1/2/3
  (`ELQBinOpen(&handle,100,log,path)` then a virtual call `(**(code**)(*self+0x2c))(decoder,0,path)`)
  and `FUN_1001e3a0`/`FUN_1001f580` write/fill the arrays consumed above; the Sig object layout
  beyond the offsets named here (0x91 decoder handle, 0xb bin handle, 0x2c/0x1c vtable slots,
  0x4b9/0x4ba sample cursors, 0x1128 pitch marks, 0x155c/0x1564 SDE positions, 0x234 sample rate,
  0x4c1 sample rate copy) is not fully reconstructed.
* The `.sde` byte-level record parser is not identifiable in the engine dump by name (see §4.4);
  the `.bin` TLV→`ELQDataDescriptor` mapping inside `FUN_10002550`/`FUN_10005100` (ReadHeader) is in
  `ELQBinContainer`'s remit.
* Who sets `*(decoder+0x4c)` (the `.bin` payload offset = 122) is not proven: it is set only by
  `ELQDecoderFileChanged` (codec handler #6), whose engine-side call site is not visible in the
  dump; the resulting reads nevertheless match the container (`150 + 110·i`) exactly, and
  `FUN_1001e0e0` hands the just-opened bin's `ELQBinaryHeaderIsPresent` value to the decoder drive
  slot `+0x2c`, which is the most likely source.
