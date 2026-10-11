# Spanish language data layer (Loquendo TTS 7, voice "Jorge")

Source tree: `jorge/pf/Loquendo/LTTS7/data/` (`Jorge.vcf`, `SpanishEs.lcf`, `languages/Spanish/*`)
plus `jorge/pf/Loquendo/LTTS7/bin/LTTS7Spanish.dll`. Language module descriptor
`languages/Spanish/SpanishEs.lde`:

```
; LTTSComponentVersion=7.3.0
"BaseDescription" = "Castilian Spanish generic descriptor file"
"Library"         = "LTTS7Spanish, Spanish"
"Language"        = "SpanishEs,es-ES,ES,Castilian,es,Spanish"
"WinLangid"       = "1034"
"LexicalDB"       = "SpanishEs.dbl"
"DefaultVariant"  = "yes"
;"RegExp"         = "Spanish.rex"          <- commented out: no regex rules shipped for es
"Lexicon"         = "Spanish.lex"
"sayas[address]"  = "AddressSpanishEs"
```
`SpanishEs.lcf` (language configurator): `BaseLanguage=SpanishEs`, `LanguagePath=languages/Spanish`,
`Built-in=Yes`. The `.lde` `Library` value is exactly how the engine builds the plugin name:
`ELQPluginIni(..., "LTTS7Spanish", ...)` then resolves `Les*`/`Fon*`/`ELQ*` procedures by name.

## Files and roles (observed in the Jorge package)

| file | size | role |
|---|---|---|
| `SpanishEs.lde` | 395 B | language descriptor (plain text, keys above) |
| `SpanishEs.dbl` | 261 120 B | **lexicon database: SQLite**, table `lessico` |
| `Spanish.lex` | 4 361 B | compiled binary lexicon (see below) |
| `Spanish Automotive.lex`, `American Spanish Automotive*.lex`, `SISpanish.lex` | 2–17 KB | style/domain lexicons referenced as `"lexicon[i]"` by `.ycf` style files |
| `SpanishEs.lcf` | – | language configurator (plain text) |
| `AddressSpanishEs.ycf` etc. | – | **say-as/style configurator (plain text)**, e.g. `"lexicon[0]" = "languages/Spanish/Spanish Automotive.lex"` |
| `SpanishAm/Ar/Cl/Mx.dbl` + `.lde` | 261 120 B each | the 5 Spanish variants (Am/Ar/Cl/Mx/Es) |
| `languages/*/…gpr`, `*.rex` | – | rule/regex data for other languages (Spanish ships none; G2P is lexicon+compiled rules) |

## Lexicon database (`SpanishEs.dbl`)

SQLite, one table (Italian column names, latin-1 text):
`lessico(grafemica, fonetica, grammaticale, specgramm, gennum, tempomodo, abbreviazione, gradoaccentuale)`

* 5 381 rows; 1 690 with a non-NULL `fonetica` (the DB holds irregular/foreign/number forms;
  regular words are produced by the compiled rules in `Spanish.lex`).
* `grammaticale` values with counts: `SOST` 1372, `VERBO` 1323, `AGG` 429, `AVV` 174, `PRON` 62,
  `VERBOE` 52, `VERBOA` 50, `PREPS` 26, `CONG` 22, `OMOGRAFO` 8, `PRONR` 8, `PRONPC` 7,
  `ARTPRON` 4, `ARTIC` 4, `PREPA` 2, `NONVERBO` 1, `PRONCLI` 1 (empty 1836).
* sample rows (`grafemica` -> `fonetica`):
  `abiogenesia -> a BH i o x e n `e s j a`, `adagio -> a DH `a Y j o`,
  `advanced -> a DH BH `a n s e DH`, `aeromexico -> a e hr o m `e x i k o`,
  `interregional -> i N tt e hr r: e x j o n `a l`, `telefonicaonline -> tt e l e f `o n i k a o n l `a i n`

### Phoneme inventory actually used (35 symbols; from `fonetica`)

Most frequent tokens: `s` 830, `i` 784, `e` 693, `hr` 659, `a` 555, `` `e `` 549, `tt` 545,
`n` 538, `l` 509, `k` 502, `` `a `` 430, `m` 403, `o` 359, `` `i `` 295, `` `o `` 281, `p` 275,
`b` 244, `u` 221, `f` 189, `` `u `` 169, `x` 157, `BH` 147, `DH` 144, `w` 132, `dd` 116.

Symbol list (as printed by `LTTS7Spanish.dll` at file offset 0x26918, preceded by example words
`mancha, noche, kama, pizza, Genova, chocolate, show, desde, consejo, yemas, caballo, llegada,
guerra, escudo, toldo, amaba, bueno, isla, hasta, giro, caja, loco, tarde, capa, cuatro, rabia,
comprar, retorica, denos, Educador`):

```
HRB Dg uw r: hr GL Gl GN Gn N M Y Hh Th Zg T$ Ts J dd tt DH GH Hr BH `u `o `i `e `a @ # ^
```
Interpretation (SAMPA-like, Loquendo dialect): `a e i o u` vowels; `` `x `` = stressed vowel;
`$` secondary stress; `:` lengthening (`r:`); `hr` trill, `r` tap; `tt`/`dd` = voiceless/voiced
alveolar stops (Spanish /t/, /d/); `BH`/`DH`/`GH` = spirantised allophones of b/d/g;
`Hh`/`Th`/`Ts`/`Zg`/`Dg`/`HRB`/`GL`/`Gl`/`GN`/`Gn` = context variants; `N` = [ŋ], `J` = [ɲ],
`L` = [ʎ], `Y` = [ʝ], `x` = [x], `M`, `T$`, `w`, `j` glides; `@ # ^` = internal markers.

## Compiled lexicon `.lex` (open item)

All `.lex` files share the header
`ca fe db 60 df e3 dc a4 c9 a5 85 f3 96 e4 97 fe` and are **not** text under bit-7 clearing nor
under XOR with `d[0]^d[1]` (= 0x34). They are therefore a compiled rule/lexicon program
(consistent with `Lessico`/rule-based G2P); reversing them is a separate pass. `AddressSpanishEs.ycf`
shows how styles select them (`lexicon[0]`, `lexicon[1]`, …).

## The voice's phonetic table (`LTTS7Jorge.dll`)

The voice module embeds its own phoneme table (the one the engine asks for as resource
`TabelleFonetiche`). In `jorge/…/bin/LTTS7Jorge.dll` at file offset ~0x82c0..0x8450 it appears as a list
of **example words** followed by **symbols**, in the voice's own order:

```
examples: ayuda llegada guerra escudo toldo amaba bueno caja loco tarde capa causa rey capitulo cura
          soldado coche retorica silla denos pesca llamar caro
symbols : r:  hr  GL Gl l GN Gn N M n m Y Th x Zg $ vs s f T$ Ts J HG g Hdd dd HB b k tt p
          HGH HBH HDH DH GH BH j w u `u o `o i `i e `e a `a @ # ^
```

* This is exactly the symbol set seen in the lexicon's `fonetica` column (base vowels/consonants,
  `hr`/`r:`/`r` rhotics, `BH`/`DH`/`GH` spirantised allophones, `Hdd`/`dd`/`tt` stops, `GL/Gl GN/Gn`
  palatals, `N`, `J`, `L`, `Y`, `x`, `Th`, `Zg`, `T$`, `Ts`, `$`, `vs`), so the `.sde` `U=` tokens and
  the lexicon transcriptions share one alphabet.
* `#`, `@`, `^` are internal markers (silence / boundary) - the first atoms of `Jorge.sde` are
  `U=# # @ @`, i.e. marker context + markers.
* Example words give the pronunciation intent of each symbol (e.g. `LL`-like `Gl`/`GL` from *llegada/
  llamar*, `J` from *caja*?, `Y` from *rey/ayuda*), which is enough to map the alphabet onto IPA for a
  reimplementation (mapping still `[INFERENCE]` where ambiguous).
* `LTTS7Spanish.dll` carries a *similar* table (examples + symbols) for the language layer; the engine's
  reader converts `U=` tokens through the voice table by exact string match (see `specs/SDE.md` S3).

## Say-as / style layer

The `.ycf` files are tiny plain-text *Style Configurator Files* that only name the compiled lexicons used
by a style, e.g. `AddressSpanishEs.ycf`:

```
; Style Configurator File for Loquendo TTS
"lexicon[0]" = "languages/Spanish/Spanish Automotive.lex"
```
(`SMSItalian.ycf` -> `languages/Italian/SMSItalian.lex`, etc.). So the say-as behaviours of the
Director's *Say As* menu (address, SMS, currency, ...) are implemented by **compiled `.lex` binaries**,
not by readable rules: `AddressSpanishEs` uses `Spanish Automotive.lex`; the language default uses
`Spanish.lex` (`.lde` key `Lexicon`). A binary-free reimplementation must re-create these say-as
grammars itself (a generic implementation is a valid substitute, as the interface is
`ttsReadString` with a `sayas`/style parameter).

## Reimplementation notes

* A binary-free Spanish front end needs: the `.dbl` lexicon (drop-in: SQLite, latin-1), a rule G2P
  for regular words equivalent to `Spanish.lex`, and this phoneme alphabet as its output symbols.
* The engine resolves the language procedures through the module dispatcher
  (`ELQPluginGetProc("LesGetSymbolName"|"ELQGetGraphemes"|"ELQGetPhonemes"|"FonTrasParola"|…, …)`);
  `LesGetSymbolName` is the symbol-id -> name map for exactly the alphabet above.
