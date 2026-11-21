# FE4 Arena Growth Fix — NMI / Direct Page race in level-up

**English** | [中文](README.zh-TW.md)

A bug fix for *Fire Emblem: Genealogy of the Holy War* (ファイアーエムブレム 聖戦の系譜, SFC 1996).

Players have long said that **levelling up in the arena gives worse stat growths**. It's true, and it's a bug. The cause is a race condition between the level-up code and the NMI (vblank) handler. This patch fixes it.

## The bug

During a level-up, the holy-blood growth bonus routine `$84:A649` loops over the 13 bloodlines and keeps its running total in direct page `$02`. Its helper `$84:A5C0` uses `$00`.

The NMI handler (entry `$80:81B6`) sets D = 0 and also uses `$00–$03` as scratch. It does not always restore them. If an NMI lands while `$84:A649` is running, the half-finished total is overwritten:

```
before NMI   $02 = 0000            (correct partial sum)
after NMI    $02 = E1D0  (−7728)   (NMI's own scratch value)
+ Od +20     $02 = E1E4  (−7708)   → growth rate clamped to 0 %, the stat does not grow
```

This was captured with a debug ROM in snes9x: Chulainn (Holyn), HP growth 90 % + minor Od +20 % (should be 110 %, a guaranteed +1). HP did not grow.

- In the map battle we tested (chapter 4, Sigurd attacking an adjacent pirate, 200 level-ups), the level-up is calculated right after the attack is confirmed, still on the map screen. It starts around scanline 20–50 and finishes by scanline 214, before that frame's NMI at line 225. None of the 200 level-ups were hit, and the original and fixed ROMs gave identical results. Other maps, enemy-phase counterattacks and staff level-ups haven't been tested.
- In the arena, the main thread gets little CPU time. A level-up takes about 3 frames, so any of the 8 growth calculations can be interrupted.
- **Every character is affected**, with or without holy blood: `$84:A649` always clears `$02`, runs the loop and returns `$02`.
- The bug is in the original Japanese ROM. Translations that keep this code have it too.

## Results

161 winning arena fights (Chulainn, chapter 2), replayed frame-for-frame in snes9x. Only the level-up differs between columns. The baseline is 2,000 runs of the level-up routine on the same memory state, without NMI.

| Stat | Original | Fixed | Baseline |
|---|---|---|---|
| HP | 100% | 100% | 100% |
| Str | 31% | 34% | 32% |
| Mag | 3% | 6% | 6% |
| Skl | 72% | 80% | 80% |
| Spd | 26% | 27% | 31% |
| Def | **11%** | 30% | 31% |
| Res | 4% | 5% | 5% |
| Luck | 16% | 16% | 21% |
| Stats gained per level | 2.63 | 2.98 | 3.05 |

In the original, Defence is about 5.4 standard errors below baseline, far beyond normal sampling noise. Skill is about 2.4 SE below, pointing the same way. After the fix, all stats return to near the baseline. Strength is slightly above it (34 % vs 32 %), but there is no systematic increase. That points to the original calculation being restored, not growths simply being raised.

With fixed RNG and no NMI, the patched routine gives results identical to the original: 500 runs on the Chinese ROM, 300 on the Japanese ROM.

## The fix

`$84:A649` now runs with a private direct page. On entry, it reserves 16 bytes on the stack and sets D = S+1. On exit, it restores D and the stack.

- NMI writes to `$0000–$0003` (with D = 0) no longer hit the level-up's scratch.
- NMI pushes go below S, so they cannot reach the reserved bytes either.

| SNES address | File offset (headerless) | Original | Patched |
|---|---|---|---|
| `$84:A649` | `0x04A649` | `8B 08 4B AB` | `5C A0 FF 86` (JML entry stub) |
| `$84:A69A` | `0x04A69A` | `7A FA 28 AB` | `5C B7 FF 86` (JML exit stub) |
| `$86:FFA0–FFC5` | `0x06FFA0` | all `00` (unused) | 38-byte stubs |
| header checksum | `0x00FFDC` | — | recalculated |

The full commented source of the stubs is in [`fe4_growth_race_fix.py`](fe4_growth_race_fix.py).

## How to apply

**You need your own ROM. This repository does not contain any ROM data.**

| ROM | Identify | Use |
|---|---|---|
| Japanese original | 4 MB HiROM, title `FIREEMBLEM4`, headerless CRC32 `DC0D8CF9` | `fe4_growth_race_fix_jp.ips` with any IPS patcher → CRC32 `CE39F90C` |
| Chinese translation (火花天龍劍 V1.1) | `0052.SMC`, 512-byte header, headerless CRC32 `C16D614E` | `fe4_growth_race_fix.py` |
| Other versions, or ROMs with other patches | — | `fe4_growth_race_fix.py` |

```
python3 fe4_growth_race_fix.py input.sfc output.sfc
```

- Needs Python 3. No other packages.
- `.smc` files with a 512-byte copier header are handled automatically.
- Before writing, the script checks the original bytes at both sites and that `$86:FFA0` is free. If anything doesn't match, it stops without changing the file.
- Save format is unchanged. Existing saves work.
- If you combine this with other patches, make sure they don't use `$86:FFA0–FFC5` or modify `$84:A649` / `$84:A69A`.

`make_ips.py` builds an IPS from an original and a patched ROM: `python3 make_ips.py original.sfc patched.sfc out.ips`.

## Scope and limitations

- Only the holy-blood growth bonus during level-up is fixed. `$84:A5C0` has 4 other callers (`$80:BCB4`, `$84:A0BA`, `$84:F695`, `$89:90C2`; status screen, battle stats, etc.). In theory, they could race with NMI as well. This hasn't been observed and isn't fixed.
- Other routines that use `$00–$0F` across frames may have the same kind of problem. Only the level-up path was checked.
- The statistics come from one character (Chulainn), one save and one low-win-rate arena match. Rates for other characters and other arenas weren't measured; map battles were tested in one scene only.
- **Not tested on real SNES hardware.** Tested in snes9x (core), SuperZSNES and a custom 65816 emulator. The Japanese IPS was checked to boot to the title screen in snes9x. The Chinese version, combined with other personal patches, was replayed through all 161 fights and played for several turns in SuperZSNES.
- Not tested with the English fan translation. The script checks the bytes before patching, so it will refuse rather than damage an incompatible ROM. Reports are welcome.

## Myths, checked

| Claim | Verdict |
|---|---|
| Arena level-ups grow worse than normal | **True**. Caused by this bug, not a special arena rule. |
| Even 100 % growths can fail | **True, but rare**. Happens when the bonus is overwritten with a large negative value. Not seen for HP in the 161 test fights. |
| Press B before the final blow, choose to continue, then finish the fight, to get normal growths | **True, if the timing is right**. Pressing B brings up the arena keeper's prompt; choosing Continue resumes the fight. Tested on the same 161 fights: interrupting just before the final exchange gave results identical to the fixed ROM in all 161 fights. Interrupting about 2.5 s earlier helped only partly (Def 23 %), and about 5 s earlier had no effect at all. The reason: during the battle animation, the NMI handler takes about 190 of the 262 scanlines each frame and uses `$00–$03`, so the level-up calculation stretches over 2–3 frames and gets hit. Right after resuming, the animation hasn't restarted yet; the NMI finishes in about 4 scanlines without touching `$00–$03`, and the calculation completes within one frame (166 vs 561 scanlines, measured on an instrumented ROM). Fight length itself doesn't matter (correlation −0.07). |

## Credits

- Research, testing and release: chucheemeng-creator
- Disassembly, debug ROM, statistical analysis and patch code were done with the help of Claude (Anthropic's AI assistant). No AI-generated artwork is included.
- Tested with snes9x (via stable-retro) and SuperZSNES.
- The patch also works on the Chinese translation by 火花天龍劍 (V1.1). No part of their work is included or modified by this patch.

## License

The patch code and documentation in this repository are released under the [MIT License](LICENSE).
*Fire Emblem: Genealogy of the Holy War* is © Nintendo / Intelligent Systems. This repository contains no ROM data. Please don't open issues asking for ROMs.
