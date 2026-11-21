# FE4 (Fire Emblem: Seisen no Keifu) level-up growth race fix  -  v1.0
#
# Bug (original 1996 game, also in translations that keep its code):
#   The holy-blood growth bonus routine $84:A649 (called by all 8 growth getters during a
#   level-up) keeps its running total in direct page $00/$02, and its helper $84:A5C0 uses $00.
#   The NMI handler sets D = 0 and also uses $00-$03 as scratch, sometimes without restoring
#   them. If an NMI lands while $84:A649 runs, the total is overwritten (e.g. -7708 / $E1E4);
#   the growth rate is clamped to 0 % and that stat cannot grow (a large positive value would
#   instead make it grow for sure). Arena fights pre-empt the main thread heavily, so the
#   level-up spans about 3 frames and the collision becomes frequent.
#
# Fix: $84:A649 runs with a private direct page. On entry 16 bytes are reserved on the stack
#   and D is pointed at them (D = S+1); on exit D and the stack are restored.
#   - NMI writes to $0000-$0003 (with D = 0) no longer hit the level-up's scratch.
#   - NMI pushes go below S, so they cannot reach the reserved bytes either.
#   Entry and exit are redirected:
#     $84:A649 (PHB PHP PHK PLB)        -> JML entry stub
#     $84:A69A (PLY PLX PLP PLB RTL)    -> JML exit stub
#   All 8 callers enter with 16-bit A (LDA #$000k / JSL $84A649); the routine itself uses no
#   SEP/REP and no stack-relative addressing, so the stack-relative slot $11,S is the saved A.
#   Stubs: 38 bytes at $86:FFA0 (unused space, zero in the original ROM).
#
# Target: Japanese original, 4 MB HiROM, CRC32 DC0D8CF9 (headerless). Works on any ROM whose
#   bytes at the two sites and the free space match (checked before patching), e.g. the
#   Chinese translation. Saves are unaffected.
# Usage: python3 fe4_growth_race_fix.py in.(sfc|smc) out.(sfc|smc)
import sys

BASE = 0x86FFA0
ENTRY_SITE = 0x84A649
EXIT_SITE = 0x84A69A

def off(a): return ((a >> 16) & 0x3f) << 16 | (a & 0xffff)

def build():
    H = bytes.fromhex
    entry = b''.join([
        H('8B'), H('08'), H('0B'),            # PHB ; PHP ; PHD
        H('48'),                              # PHA            (all callers are 16-bit A)
        H('3B'), H('38'), H('E91000'), H('1B'),  # TSC ; SEC ; SBC #16 ; TCS   (reserve 16 bytes)
        H('1A'), H('5B'),                     # INC A ; TCD    (D = reserved area)
        H('A311'),                            # LDA $11,S      (argument back)
        H('F48484'), H('AB'), H('AB'),        # PEA $8484 ; PLB ; PLB   (DB = $84, as PHK PLB did)
        H('5C') + (ENTRY_SITE + 4).to_bytes(3, 'little')])   # JML $84A64D
    exit_ = b''.join([
        H('7A'), H('FA'),                     # PLY ; PLX
        H('8311'),                            # STA $11,S      (result into the saved-A slot)
        H('3B'), H('18'), H('691000'), H('1B'),  # TSC ; CLC ; ADC #16 ; TCS   (release area)
        H('68'), H('2B'), H('28'), H('AB'), H('6B')])        # PLA ; PLD ; PLP ; PLB ; RTL
    return entry, exit_

def apply(rom):
    entry, exit_ = build()
    E = BASE; X = BASE + len(entry)
    o = off(BASE); assert all(b == 0 for b in rom[o:o + len(entry) + len(exit_)]), 'free space not empty'
    assert off(BASE + len(entry) + len(exit_) - 1) >> 16 == o >> 16
    s = off(ENTRY_SITE); assert rom[s:s + 4] == bytes.fromhex('8B084BAB'), rom[s:s + 4].hex()
    t = off(EXIT_SITE); assert rom[t:t + 5] == bytes.fromhex('7AFA28AB6B'), rom[t:t + 5].hex()
    rom[o:o + len(entry)] = entry; rom[o + len(entry):o + len(entry) + len(exit_)] = exit_
    rom[s:s + 4] = b'\x5C' + E.to_bytes(3, 'little')
    rom[t:t + 4] = b'\x5C' + X.to_bytes(3, 'little')
    return len(entry) + len(exit_)

def fix_checksum(rom):
    rom[0xFFDC:0xFFE0] = b'\xff\xff\x00\x00'
    cs = sum(rom) & 0xffff
    rom[0xFFDE:0xFFE0] = cs.to_bytes(2, 'little'); rom[0xFFDC:0xFFDE] = (cs ^ 0xffff).to_bytes(2, 'little')
    return cs

if __name__ == '__main__':
    d = bytearray(open(sys.argv[1], 'rb').read()); hdr = 512 if len(d) % 1024 == 512 else 0
    rom = d[hdr:]; n = apply(rom); cs = fix_checksum(rom)
    open(sys.argv[2], 'wb').write(bytes(d[:hdr]) + bytes(rom))
    print('growth race fix: %d bytes at $%06X, internal checksum %04X' % (n, BASE, cs))
