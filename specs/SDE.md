# `.sde` — Loquendo TTS 7 unit inventory ("speech atom" table)

Scope: the unit-inventory files shipped with the Jorge voice package
(`jorge/pf/Loquendo/LTTS7/data/voices/Jorge/`):

| file | bytes | header | records |
|---|---|---|---|
| `Jorge.sde` | 1 511 129 | `10,4` / `LTTSComponentVersion=7.0.0` / `N=3647,82007` | 3647 `U=`, 149 426 `L`/`R`, 146 `S=` |
| `JorgeGildedPhrases.sde` | 53 534 | `10,4` / `LTTSComponentVersion=7.0.0` / `N=261,2960` | 261 `U=`, 4 876 `L`/`R`, 260 `S=` |
| `JorgeGildedParalinguistics.sde` | 3 809 | **none** | 147 `P=` only |
| `payload/Ludoviko.sde13` (legacy gen., §12) | 186 290 | `14,1` / `VERSION=7` / `N=3482,6953,6578` | 3482 `U=`, 6577 `D=` |

Everything below is derived from the decompiled readers (addresses in §9). Two builds were
used: the older `engine_re/LoqTTS7.dll` dumps (`decomp_loqtts.txt`,
`decomp_util.txt`) and the newer jorge build `jorge/pf/…/bin/LoqTTS7.dll`
(`jorge_re/decomp_loqtts_jorge.txt`), plus `jorge_re/decomp_util_jorge.txt` for
`LTTS7Util.dll`. Both builds contain the same parser; address pairs are tabulated in §9.

---

## 1. Layer 0 — bit-7 obfuscation (auto-detected per file)

`Jorge.sde` and `JorgeGildedPhrases.sde` are stored with **bit 7 set on every single byte
except the line feed**. Byte histogram of `Jorge.sde`:

```
bit7 set : 1 357 907 bytes        bit7 clear: 153 222 bytes
number of 0x0A (LF) bytes: 153 222     →  the two sets are disjoint
```

so `b & 0x7F` = the real character and the only unmasked byte is `0x0A`.
`JorgeGildedParalinguistics.sde` is stored **plain** (bit 7 clear everywhere).

The reader auto-detects the masked form from the *first character of the first line*
(jorge `FUN_10049f10`, `0x10049f10`; old `FUN_1002a890`, `0x1002a890`):

```c
/* first line is read with fgets(buffer+1, 0x32, fp) -- so the line starts at index 1 */
(*DAT_100b73f0)(acStack_d11 + 1, 0x32, iStack_1d68);
uStack_1d48 = CONCAT31(uStack_1d48._1_3_, 0x7f < (byte)acStack_d11[1]);
...
if ((char)uStack_1d48 == '\0') {          /* unmasked  -> plain, set built-in defaults */
    (*DAT_100b7418)(iStack_1d68);         /* ELQrewind */
    ...
} else {                                  /* masked    -> copy with -0x80 */
    do {
      cVar6 = acStack_d11[uVar14 + 1];
      if (cVar6 == '\0' || cVar6 == '\r' || cVar6 == '\n') break;
      *(char *)((int)puVar7 + uVar14 + 0x30) = cVar6 + -0x80;   /* clear bit 7 */
      uVar14++;
    } while (uVar14 < 0x4f);              /* first line, max 79 chars */
}
```

Who applies it: the **generator** writes the whole file masked; the **reader** detects it
once (from line 0, char 0) and clears bit 7 while copying. The same convention is used by the `LTTSComponentVersion=` reader in
`LTTS7Util.dll` (`FUN_1000d030` `0x1000d030` in the jorge build, `FUN_1000a390`
`0x1000a390` in the old one; public wrapper `ELQGetComponentVersion` `0x1000d180` jorge /
`0x1000a4f0` old), which
builds the key with `cVar1 + -0x80` and accepts *either* `"LTTSComponentVersion="` or its
bit-7-set copy, normalising the copied value with `cVar1 + -0x80`.

Uniform over the file: **yes** — every byte except LF. It does **not** cover "binary
fields" because the format has none: after unmasking the payload is pure printable
ASCII (bytes `0x20`–`0x7E`); even the numeric fields are digits of a printable numeral
system (§4). `JorgeGildedParalinguistics.sde` proves the detection is a real branch: it
starts with `P` (0x50), is stored plain, and is parsed unharmed.

Line 0 is additionally *opaque*: it is read once with `fgets(…,0x32,…)` and stored
verbatim at reader-state `+0x30` (max 79 chars). For the unmasked branch the engine
substitutes a compiled-in default string — in `engine_re/LoqTTS7.dll` at `0x10088858`
the bytes are `"332198,21119"`, i.e. the engine writes a `<int>,<int>` pair there and
the shipped files write `10,4`. **The two numbers of line 0 are not interpreted by any
code path we found** (not used as a count, version or offset); treat as opaque.

---

## 2. Line / record grammar

All lines are LF-terminated; the first character of a line is the record tag.
The reader dispatches on it (jorge `FUN_10049f10`, switch on `acStack_d11[1]`,
which is the file's first character because the buffer starts at +1):

```
<file>  := <line0> LF [ "LTTSComponentVersion=" <ver> LF ] [ "N=" <a> "," <b> LF ]
           { record LF }*
record  := 'U' '=' <atom-tokens>          -- speech atom: phoneme sequence
         | 'L' <n> ["!"<start>] " " <dur> " " <val>     -- left  ('S', Sinistra) half
         | 'R' <n> ["!"<start>] " " <dur> " " <val>     -- right ('D', Destra)   half
         | 'S' '=' <flag-char>             -- per-atom boundary-class flag
         | 'P' '=' <name> "|" <begin> "|" <end> [ "|" ... ]   -- numeric range record
         | 'A' '=' <name>                  -- extra name for the current atom  (unused here)
         | 'F' '=' <name>                  -- extra name (2nd array)           (unused here)
         | 'D' <n> "," <S|D> "," <start> "," <end> "," <pitch>  -- explicit part (unused here)
```

* `U=`, `A=`, `F=` all delimit atoms: the atom index is bumped by the *next* such record
  (jorge `FUN_10049f10`, `case 'A'/'U'`: `if (local_1d71) { uStack_1d58++; local_1d71 = 0; }`).
* An atom's `L`/`R`/`S` records follow its `U=` record. In all shipped files every atom
  has exactly one `U=`, one `S=` (except in `Jorge.sde`, where only 146 do), and
  `L1 R1 L2 R2 … LK RK` for the atom's K phonemes.
* `JorgeGildedParalinguistics.sde` has no header lines at all and only `P=` records; the
  reader tolerates this (the `N=`/`U=`/`P=` branch is inside the record loop).

`N=<a>,<b>` (jorge `FUN_100493b0` @ `0x100493b0`, old `FUN_10028b80` @ `0x10028b80`;
`_atol` before and after the comma, stored at state `+0x10` and `+0x18` = `puVar5[4]`
and `puVar5[6]`):

* **`a` = number of `U=` atoms** → 3647 (verified: exactly 3647 `U=` lines).
* **`b` = total number of atom tokens** (= size of the engine's 2-byte-per-token frame
  code array, `puVar5[5]`) → 82007 (verified by re-implementing the tokenizer: the token
  count equals 82007 exactly). 82007 − 69339 space-separated fields = 12668 diphone
  joins written with `-`.

`N2` is *not* the codec frame count: the `.bin` has 264 948 frames while `N2` is 82 007.

---

## 3. `U=` records — speech-atom phoneme sequence

Parser: jorge `FUN_10049c10` @ `0x10049c10`, old `FUN_10029230` @ `0x10029230`.
(Logging in the jorge build calls these "speech atoms": *"Too many speech atoms in file
\"%s\" at line %d"*.)

```c
    bVar2 = unaff_EDI[iVar5];
    do {
        if (((bVar2 == 0x2d) || (bVar2 == 0)) || (4 < iVar4)) break;   /* stop at '-', NUL, 5 chars */
        iVar5 = iVar5 + 1;
        local_c[iVar4] = bVar2;      /* token, max 5 chars */
        bVar2 = unaff_EDI[iVar5];
        iVar4 = iVar4 + 1;
    } while (bVar2 != 0x20);
    if (local_10 != 0)
      *param_2 = ((unaff_EDI[iVar5] != '-') - 1U & 0xf7) + 0xf;   /* 0x06 after '-', else 0x0f */
    uVar3 = FUN_100190c0(table, local_c);      /* phoneme symbol -> id (old FUN_100190c0) */
    *param_4 = (char)uVar3;
```

* Fields are separated by **space**; `-` is a second separator that joins two phonemes
  of one slot (a diphone): the first token gets flag `0x06` ("joined to next"), the
  second `0x0f`. Tokens are at most 5 characters.
* Each token is a **phoneme/allophone symbol** looked up by exact string match in the
  voice's phonetic table (`*(int**)(state+0xc)`, the "TabelleFonetiche" shared resource
  registered by old `FUN_10024470`); the lookup returns the phoneme id (byte). `Jorge.sde`
  uses **44 distinct phoneme symbols**:
  ``# $ @ BH DH GH GL GN Gl Gn J M N T$ Th Ts Y Zg `a `e `i `o `u a b dd e f g hr i j k
  l m n o p r: s tt u w x``
  (the single-character tokens `#`, `@`, `$` are special/non-phonemic symbols); the 832 distinct
  space-separated fields come from ~788 diphone spellings such as `s-DH`, `o-DH`, `e-l`, `a-k`.
* **Arity: `U=<left-context> <p1> … <pK> <right-context>`.** The atom holds `K = tokens−2`
  phonemes; token 0 and the last token are the left/right **context** phonemes. The atom
  occupies K+2 frame slots `[S, S+K+2)` of the global token/frame-code array, where `S`
  is the running token counter (`puVar5[3][atom].start = local_1d2c`). *Proof:* for
  all 3647 + 261 atoms in both files, `#L == #R == #(tokens) − 2` (0 mismatches), and the
  `n` of the `L`/`R` records runs exactly `1,1,2,2,…,K,K`.
* The context pairs in `Jorge.sde` are `('#','@')` ×1891 and `('#','#')` ×1756; in
  `JorgeGildedPhrases.sde` `('#','@')` ×261 (all of them) — `#`/`@` are the
  silence/pause-type context symbols.

Frame codes: the token ids are written into the 2-byte-per-slot array as
`[phoneme-id, flag]` (flag `0x0f` normal, `0x06` diphone-join). Then
old `FUN_10029930` / jorge twin rewrites the *edge* slots of each atom with boundary
codes (`0x02,0x04,0x05,0x08…0x0d`) while preserving the `0x06` join flags; the `S=` flag
is the second argument of that call (`if (param_1 == 'I')` chooses the alternative code).

---

## 4. Layer 1 — printable base-93 numerals (`L`/`R` fields)

Decoder: jorge `FUN_100436f0` @ `0x100436f0`, old `FUN_10024440` @ `0x10024440`:

```c
int FUN_10024440(int len, byte *p) {
  i = 0; b = *p;
  while (0x21 < b) { p++; i = i * 0x5d + (uint)(byte)(b - 0x22); b = *p; }
  return i;
}
```

* Big-endian, **base 0x5D = 93**, digit = `byte − 0x22` ⇒ alphabet `"`(0) `#`(1) `$`(2)
  … `~`(92). Field ends at space (`0x20`), `!` (`0x21`) or NUL.
* `-` (0x2D) is **a digit (11)** here (only `U=`'s tokenizer treats it as a separator).
* So e.g. `#`=1, `$`=2, `0`=14, `a`=63, `'E`=5·93+35=500, `#-%`=(1·93+11)·93+3=9675.

This is why the file "looks like base-94ish digits": all `.sde` numerals are such
byte strings; there is no bit-packing inside a field.

---

## 5. `L<n>` / `R<n>` records — atom timeline

Parser: jorge `FUN_10048e30` @ `0x10048e30`, old `FUN_100285b0` @ `0x100285b0`.
Grammar (all four fields are base-93 numerals, §4):

```
L<n> [ "!"<start> ] SP <dur> SP <val>
R<n> [ "!"<start> ] SP <dur> SP <val>
```

Decompiled control flow (old build, `unaff_EDI` = the line content, i.e. from the `n` char):

```c
  /* field 1 -> param_1  ("phoneme order") */
  iVar3 = FUN_10024440(uVar5, unaff_EDI);  *param_1 = (short)iVar3;
  /* optional '!' introduces an explicit start value */
  if (unaff_EDI[uVar8] == 0x21) { uVar7 = FUN_10024440(len2, unaff_EDI+uVar5); }
  else                          { uVar7 = *in_EAX; }        /* else: previous end */
  *param_2 = uVar7;                                          /* start */
  /* duration field */
  iVar3 = FUN_10024440(param_1, pbVar4);  uVar5 = iVar3 + *param_2;
  *in_EAX = uVar5;                          /* running end -> next line's start */
  if (*param_2 <= uVar5) {                                  /* "Negative duration" otherwise */
     uVar8 = FUN_10024440(len4, ...);                       /* low 10-bit value */
     param_2[1] = uVar8 & 0xffff | (uVar5 - uVar7) * 0x400; /* packed (dur<<10)|val */
  }
```

Field meaning (verified numerically on the shipped files):

| field | meaning |
|---|---|
| `n` | 1-based index of the phoneme inside the atom; `1..K`, `K = tokens−2`. |
| `!<start>` | explicit absolute start of this half-segment. It is written **only on the first `L` record of each atom** (verified: exactly one `!` per atom in both files). |
| `<dur>` | duration of the half-segment. |
| `<val>` | 10-bit acoustic parameter of the half-segment (values 0…284 in `Jorge.sde`, 0…250 in `Phrases`); 0 = unvoiced/first sample. `[INFERENCE]` it fits a pitch-period/voicing code in samples, but the exact acoustic meaning is not proven by the code (the reader stores `(dur<<10)|val` and later recomputes `end = start + (packed>>10)`). |

* Position unit: `start`/`dur` are in **10 µs ticks**. *Proof (consistency, not fitting):*
  the last end position of `Jorge.sde` is **529 894 060** while the DB has 264 948 frames
  of 20 ms ⇒ `264948 × 2000 = 529 896 000` (Δ 0.0019 s). Independently
  `JorgeGildedPhrases.sde`: max end 17 776 419 vs `8889 × 2000 = 17 778 000`, and
  `JorgeGildedParalinguistics.sde`: 19 915 859 vs `9958 × 2000 = 19 916 000`. The sum of
  all durations (526 255 963) is within 0.7 % of the whole timeline ⇒ the records tile
  the acoustic database in time order.
* Side: `L` is stored as part `'S'` (Sinistra/left) and `R` as `'D'` (Destra/right)
  (`local_1d59 = ((local_1d69 != 0x52) - 1U & 0xf1) + 0x53;`); the engine writes the
  left half into frame slot `2·(atom.start + n)` and the right half into `2·(atom.start+n)+1`
  (`iVar10 = (((n) - unit.field4) + runningTokenCount) * 2; if (part=='D') iVar10++;`).
* The `R` records never carry `!`; they inherit the accumulator from the preceding `L`.
* Timeline continuity is checked by the engine (`local_1d1c = start + (packed>>10)`) —
  mismatches produce an `ELQLogWrite` warning but do not reject the file.

---

## 6. `S=` records — per-atom flag

`case 'S': *(char *)(puVar7[3] + 6 + uStack_1d58*8) = acStack_d11[3];`

Sets one character of the atom (state `+6`); the `U=` record pre-sets it to `'D'`.
Observed values: `Jorge.sde` only `I` (146 atoms, atoms #3307…#3646 — the tail of the
file); `JorgeGildedPhrases.sde` `e`×180, `i`×67, `f`×7, `x`×6. The character is later
passed as `param_1` into the frame-code builder (`FUN_10029930`, old build), which takes
a different branch when `param_1 == 'I'`; it is therefore a **boundary-class selector**
for the atom's edge frames (exact enumeration of the classes not needed for parsing).

---

## 7. `P=` records — numeric range records

Parser: old `FUN_10029300` @ `0x10029300` (`'|'`-separated, `_atol`), jorge
`FUN_10049de0`. Format `P=<name>|<begin>|<end>[|...]`, plain **decimal**, no base-93:

```
P=Aa|0|61846
P=Aa_01|61846|150218
...
```

Only `JorgeGildedParalinguistics.sde` uses them (147 records, names = the
paralinguistic extras of `JorgeGilded.gde`: `Aa, Aa_01, Ah, Breath, …`); the reader
requires `end > begin` (`"Negative duration"` otherwise) and stores
`{name, begin, end}` (16-byte entries, `state[10]`), count in `state[0xb]`.
`begin`/`end` are again **10 µs ticks** (max end 19 915 859 ≈ 9958 frames × 2000).

---

## 8. Summary of every field

| position | who | value |
|---|---|---|
| line 0 | — | opaque `<int>,<int>` string, e.g. `10,4` |
| `LTTSComponentVersion=` | — | component version string `7.0.0` (also present masked in `.bin` headers) |
| `N=a,b` | `FUN_100493b0` | `a` = #atoms, `b` = #atom tokens (frame-code slots) |
| `U=` field i | `FUN_10049c10` + phonetic table | phoneme/allophone **symbol** (i=0 left context, i=last right context, middle = atom phonemes) |
| `U=` `-` | same | joins two phonemes into one diphone token (flag 0x06) |
| `L<n>`/`R<n>` field 1 | `FUN_10048e30`/`FUN_100436f0` | `n` = phoneme index 1..K |
| `!<start>` | idem | absolute start, 10 µs ticks, first L of atom only |
| `<dur>` | idem | duration, 10 µs ticks |
| `<val>` | idem | 10-bit parameter (0..~284) |
| `S=` | reader `case 'S'` | 1-char boundary-class flag (default `D`) |
| `P=` | `FUN_10049de0` | name, begin, end (decimal, 10 µs ticks) |

---

## 9. Functions (address table)

| role | old `engine_re/LoqTTS7.dll` | jorge `bin/LoqTTS7.dll` |
|---|---|---|
| `.sde` reader (mask detect, dispatch, atom table) | `FUN_1002a890` `0x1002a890` | `FUN_10049f10` `0x10049f10` |
| `N=` parser (`_atol`,`_atol`) | `FUN_10028b80` `0x10028b80` | `FUN_100493b0` `0x100493b0` |
| `U=` tokenizer | `FUN_10029230` `0x10029230` | `FUN_10049c10` `0x10049c10` |
| base-93 ≤5-char numeral decoder | `FUN_10024440` `0x10024440` | `FUN_100436f0` `0x100436f0` |
| `L`/`R` field parser | `FUN_100285b0` `0x100285b0` | `FUN_10048e30` `0x10048e30` |
| `D` record parser (`_atol`) | `FUN_10028700` `0x10028700` | `FUN_10048f90` `0x10048f90` |
| `P` record parser (`\|`,`_atol`) | `FUN_10029300` `0x10029300` | `FUN_10049de0` `0x10049de0` |
| phonetic symbol table lookup | `FUN_100190c0` `0x100190c0` | (same design; table ptr at state `+0xc`) |
| atom edge frame-code builder | `FUN_10029930` `0x10029930` | vtable slot `state+0x10` |
| phonetic-table shared-resource loader | `FUN_10024470` `0x10024470` | — |

---

## 10. The descriptor / tags layer (`LTTS7Util.dll`) and its relation to `.sde`

`.sde` is **not** parsed by `ELQTagsDescriptor*`: the engine opens the file itself
(`ELQfopen`/`ELQFileValidfgets` in `FUN_10049f10`) and parses the tags in §2. The
`ELQTagsDescriptor*` API is the generic tag-file layer that reads the voice's **descriptor**
files `Jorge.vde` and `JorgeGilded.gde` (`"key" = "value"` lines, `~`-separated lists,
`;` comments), and `ELQDataDescriptor*` is the generic key/value descriptor used for
`.bin` header fields and voice attributes.

`LTTS7Util.dll` jorge build (`jorge_re/decomp_util_jorge.txt`):

| export | addr | behaviour |
|---|---|---|
| `ELQTagsDescriptorIni` | `0x100293b0` | `malloc(0x58)`; installs default delimiter set (from `.rdata` `0x10064378…`), magic = `ELQTagsDescriptorDelete`, `[0x15]` = predefined-tag table, state `[0x14]=0` |
| `ELQTagsDescriptorDelete` | `0x10029450` | frees name buffer `[0x11]` |
| `ELQTagsDescriptorSetTagDelim` | `0x10029490` | sets `[1]`/`[3]`; defaults `'\' (0x5c)` / `'(' (0x28)`; guarded by `[0x14]<2` |
| `ELQTagsDescriptorSetQuoteDelim` | `0x10029640` | sets `[6]`/`[7]`; default `'"'` both |
| `ELQTagsDescriptorMalformedTags` | `0x100297f0` | stores a **bool at `+0x40`** = "accept malformed tags" (API-sequence guarded) |
| `ELQTagsDescriptorSetListOfPreDefinedUserTags` | `0x10029990` | user-tag name list |
| `ELQTagsDescriptorSetIsUserTagNameFunction(s)` | `0x10029ba0` / `0x10029d30` | user-tag predicate callbacks |
| `ELQTagsDescriptorCheck` | `0x10029ec0` | locks the configuration (`[0x14]=1`) |
| `ELQTagsDescriptorGetTagEffect` | `0x1002a040` | linear search (stride `0x44`) in the tag table, returns effect `1`/`2` or `0` |

Default delimiters seen in `.rdata` (code points): escape `'\'`, pair `'('`,`')'`,
`'"'`,`'"'`, `';'`,`';'`, `','`, `'='`,`'='`, `'+'`,`'-'`.

`ELQDataDescriptor*` (`0x10004d60` Ini, `0x10005070` LoadFile, `0x10005200` GetNext,
`0x100052a0` GetCount, `0x10004ec0` GetAttribute, `0x10004f40` SetAttribute,
`0x10004e20`/`0x10004e90` Set/GetName, `0x10004d90` Delete) is an ordered
`name=value` attribute list (used by `ELQBinaryHeaderGetValue`/`LoadInfo` for the
`.bin` TLV header and by the engine to fetch voice paths).

Note the `MalformedTags` flag is about tag *syntax*, not about the bit-7 masking of
`.sde`; the bit-7 handling is exclusively the first-character test in §1 (and the
equivalent `-0x80` normalisation inside `ELQGetComponentVersion`).

---

## 11. Consistency checks that back this spec

1. `#U=` = 3647 = `N`[0]; token count = 82007 = `N`[1] (tokenizer re-implemented exactly).
2. For all 3647 (Jorge) and 261 (Phrases) atoms: `#L = #R = #tokens − 2`; the `n`
   sequence is `1,1,2,2,…,K,K`.
3. `#L` index characters are exactly `'#'…'a'` = base-93 values `1…63` (max 63 phonemes/atom).
4. Exactly one `!`-prefixed (explicit start) `L` record per atom; every `L`/`R` line has
   3 fields (`n dur val`) except those 3647/261 first-`L` lines which have 4 (`n !start dur val`).
5. `max(end)` = 529 894 060 ≈ `264948×2000`; Phrases 17 776 419 ≈ `8889×2000`;
   Paralinguistics 19 915 859 ≈ `9958×2000` ⇒ 10 µs ticks.
6. Byte histogram: every non-LF byte of a masked file has bit 7 set.
7. `JorgeGildedParalinguistics.sde` (plain, `P=`-only, no header) parses with the same
   reader, proving the auto-detection and the optional header.
8. Legacy generation (`payload/Ludoviko.sde13`): `#U=` = 3482 = `N`[0]; `#D=` = 6577 and
   `N`[2] = 6578 = `#D + 1`; every `D` record has a valid `part ∈ {S,D}`, `end ≥ start`,
   `pitch ≥ 0` (the three conditions `FUN_10028700` enforces) — 0 violations.
9. `N`[1] of the legacy file (6953) = raw token count (6962) minus the 9 tokens that
   follow the first occurrence of the one token whose phonetic-table index is 0
   (`` Oe ``/`` `Oe ``; both candidate tokens reproduce exactly 9).
10. Shared time base: Jorge max end 529 894 060 ≈ 264 948 × 2000; legacy max end
    15 829 000 ≈ 158.29 s ≈ the companion PCM's 2 534 653 samples @16 kHz (158.42 s).

## 12. Legacy generation (`VERSION=7`) — e.g. `payload/Ludoviko.sde13`

The SDK voice ships an **older `.sde` generation** whose grammar is distinct but which
is consumed by the *same* engine reader. Example: `payload/Ludoviko.sde13`
(186 290 B, 10 063 lines, bit-7 masked like the Jorge files; decoded copy kept at
`engine_re/Ludoviko.sde.txt`).

```
14,1                        <- line 0, same opaque <int>,<int> convention as Jorge's "10,4"
VERSION=7                   <- generation marker (instead of LTTSComponentVersion=)
N=3482,6953,6578            <- THREE numbers
U=#                         <- atom, no context tokens
D=0,S,15769400,15779075,0   <- part record, PLAIN DECIMAL, comma separated
D=0,D,15779075,15794394,0
U=@
...
```

Record inventory of the file: 3482 `U=`, 6577 `D=`, no `L`/`R`/`S`/`P`.

### 12.1 `D=` records

Parsed by the *old-build* `D` case of the reader (`FUN_10028700` `0x10028700`, jorge
`FUN_10048f90` `0x10048f90`), which I verified line by line:

```c
  uVar3 = _atol(unaff_EDI);                     /* field 1: "phoneme order" */
  if ((int)uVar3 < 0) -> "Error in phoneme order";
  *param_1 = (short)uVar3;
  cVar1 = unaff_EDI[uVar6 + 1];  *param_2 = cVar1;      /* field 2: part letter */
  if (cVar1 != 'S' && cVar1 != 'D') -> "Unknown phoneme part";
  ... field 3 "start" (empty field => *in_EAX accumulator) -> *param_3
  ... field 4 "end"  -> *in_EAX ;  if (end < start) -> "Negative duration"
  ... field 5 "pitch";  if (pitch < 0) -> "Pitch negative"
  param_3[1] = (end - start) * 0x400 | pitch & 0xffff;
```

Grammar: **`D=<order>,<S|D>,<start>,<end>,<pitch>`**, all fields plain `_atol` decimal
(contrast with the base-93 numerals of the Jorge generation). The engine stores
`(start, ((end-start)<<10) | pitch&0xffff)` — i.e. the *same 8-byte per half-slot pair*
as an `L<n>`/`R<n>` record, with `dur = end − start`.

* `order` is a **0-based token index** into the atom's `U=` list (the same quantity the
  Jorge `n` carries, but 0-based because the legacy `U=` line has no context tokens):
  the reader computes `slot = ((order - atomSlotCount) + runningSlotCount) * 2`
  (`+1` when `part == 'D'`), which equals `(atomStart + order) * 2 (+1)`.
* `part` = `'S'` (left half, `Sinistra`) or `'D'` (right half, `Destra`) — the value the
  Jorge generation expresses implicitly by choosing an `L` or `R` line.
* `start`/`end` are the explicit bounds (the Jorge generation writes `start` only on the
  first line and a `dur` afterwards).
* Observed fields: `order ∈ {0,1}`; `(order 0, part D)` ×3300, `(order 1, part S)` ×3275,
  `(order 0, part S)` ×2; `pitch` is 0 in every one of the 6577 records.

### 12.2 `N=` with three numbers

`N=3482,6953,6578`:

| # | value | meaning | evidence |
|---|---|---|---|
| 1 | 3482 | #atoms | = exact `U=` count |
| 2 | 6953 | slot/frame count as computed by the reader | see below |
| 3 | 6578 | #`D` records + 1 | 6577 records present |

The reader (`FUN_100493b0`/`FUN_10028b80`) parses only the **first two** numbers (two
`_atol` calls, stored at state `+0x10`/`+0x18`); the third is never read — it is a
generator-side note. Number 3 being exactly `#D + 1` (one more than the records present)
is consistent with a counted terminating boundary.

Number 2: the raw grammatical token count of the `U=` lines is **6962** (3480 atoms with
2 tokens + 2 atoms with 1 token), but the reader's counter is
`strlen()` of the per-token id-byte buffer (`local_1d30 = strlen(local_a04)` in the first
pass; the consume loop in the second pass also stops at a 0 byte). `FUN_100190c0` returns
the phonetic-table *index*, and **index 0 is written as a 0 byte**, truncating the rest of
that line's count. Brute-forcing every token of the file: exactly two tokens —
`` Oe `` and `` `Oe `` (which never co-occur in a line and appear in identical position
patterns, 6 lines each) — reproduce a loss of exactly 9 tokens (6962 − 9 = 6953). So
exactly one of them is phonetic-table entry 0 in the Ludoviko table. (This is the same
mechanism that makes `N`[1] exact for Jorge, where no token decodes to index 0.)

### 12.3 Time base — shared with the Jorge generation

Positions are in the same **10 µs** unit:
max `end` in the file = 15 829 000 → **158.29 s**, and the companion PCM container
`payload/Ludoviko.16000.linear.256000.10.bin12` (5 069 459 B, header 125+28 = 153 B,
16-bit mono) holds `(5069459−153)/2 = 2 534 653` samples @16 kHz = **158.42 s**
= 15 841 581 ten-µs units (independently reported as 2 534 667 samples = 158.417 s).
The two agree to 0.08 %, so the 10 µs position unit is **shared by both `.sde`
generations**.

### 12.4 Generation routing

* The two generations are distinguishable by the header line:
  `LTTSComponentVersion=<ver>` (Jorge, `7.0.0`) vs **`VERSION=<n>`** (legacy, `7`).
  Both files also carry the same opaque `<int>,<int>` line 0 (`10,4` / `14,1`).
* **`jorge LoqTTS7.dll` handles both, and there is no version branch.** The literal
  `"VERSION="` does not occur anywhere in `LoqTTS7.dll`, `LTTS7Util.dll` or `LTTS7DB.dll`
  (byte search of all three jorge **and** old binaries: 0 hits), so the line is an
  *unknown tag* that the reader skips. Concretely, in the reader
  (`FUN_10049f10` jorge / `FUN_1002a890` old):
  * pass 1 reacts only to `'N'` (`FUN_100493b0`), `'U'` and `'P'` — `VERSION=7` and `D=`
    lines are ignored;
  * pass 2 dispatches on the tag character with cases
    `'A' 'D' 'L' 'R' 'F' 'S' 'U' 'P'` — `'D'` is the case that parses the legacy part
    records, and `'V'` has no case and is dropped.
  * The only tag with an explicit version branch is `LTTSComponentVersion=`, and even
    that is just "skip one extra header line" (`local_1d45 = 1`); it is *not* required for
    the file to load.

  So the same reader loads both the Jorge `U/L/R/S` files and the legacy `U/D` file;
  route by the header *for our own parsing*, not because the engine does.

---

## 13. Tool

`tools/sde_parse.py` implements §1–§7 and §12 and prints header fields, the first N atoms
with their decoded `L`/`R` (or `D`) records, record counts vs `N=`, the `U=` field
distribution, and the max timeline position. It auto-detects the generation from the
`VERSION=` / `LTTSComponentVersion=` header marker and the mask from byte 0.

Verified counts:

| file | `U=` | `L`/`R` | `D=` | `S=` | `P=` | `N=` | max end |
|---|---|---|---|---|---|---|---|
| `Jorge.sde` | 3647 | 149 426 | 0 | 146 | 0 | 3647, 82007 | 529 894 060 |
| `JorgeGildedPhrases.sde` | 261 | 4 876 | 0 | 260 | 0 | 261, 2960 | 17 776 419 |
| `JorgeGildedParalinguistics.sde` | 0 | 0 | 0 | 0 | 147 | (absent) | 19 915 859 |
| `payload/Ludoviko.sde13` | 3482 | 0 | 6577 | 0 | 0 | 3482, 6953, 6578 | 15 829 000 |


