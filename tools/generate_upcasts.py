"""Generate the higher-level ("upcast") versions of the Invoke combos.

The base game does this with DATA, not with an engine rule (checked against vanilla: Fireball 4-9, Haste 4-6, Shield, Mage Armour,
Misty Step ...). A higher-level version of a spell is its own stat entry: the base spell's text, a bigger slot cost
(SpellSlotsGroup:1:1:<slot>), `RootSpellID <base spell>`, `PowerLevel <slot>`, and, for spells that scale, more damage. The base `Level` is left alone.
Spells without a version for a slot level cannot be cast with that slot.

Reads the BASE spells from the hand-written stat files and writes two fully generated files into Stats/Generated/Data/:
    Spell_Upcast.txt    every higher-level spell entry
    Status_Upcast.txt   the helper statuses some of them need
Never edit those two by hand. After changing a base spell (cost, damage, requirements ...) run:   python tools/generate_upcasts.py

Rule (user decision 2026-10-07): vanilla amount, +1 die of the spell's own die type per slot level above its base level.
  Sun Strike +1d10 | Chaos Meteor +1d8 | EMP +1d8 | Deafening Blast +1d8 | Tornado +1d6 per turn | Ice Wall +1d6 per tick
  Alacrity, Forge Spirit and Ghost Walk get plain copies (no extra effect); Cold Snap is at-will and has no versions.
Slots 7-9 only exist with a level-cap mod such as Expansion (Levels 13-20); without one those entries are never selectable.
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = glob.glob(os.path.join(ROOT, "source", "Public", "Invoker*", "Stats", "Generated", "Data"))[0]
OUT_SPELLS = os.path.join(DATA, "Spell_Upcast.txt")
OUT_STATUS = os.path.join(DATA, "Status_Upcast.txt")
MAX_SLOT = 9
NL = "\n"

# name, base slot level, die size, level map, damage type  (direct-hit spells: extra dice are added to the level-map dice)
DIRECT = [
    ("INVOKER_SUNSTRIKE", 3, 10, "InvokerSunStrike", "Fire"),
    ("INVOKER_METEOR", 3, 8, "InvokerMeteor", "Thunder"),
    ("INVOKER_EMP", 2, 8, "InvokerEMP", "Lightning"),
    ("INVOKER_DEAFENINGBLAST", 1, 8, "InvokerDeafeningBlast", "Thunder"),
]
SUNSTRIKE_SE = ("INVOKER_SUNSTRIKE_SE", 3, 10, "InvokerSunStrike", "Fire")   # damage is dealt by BootstrapServer.lua (reads the marker's slot)
PLAIN = [("INVOKER_ALACRITY", 2), ("INVOKER_FORGESPIRIT", 2), ("INVOKER_GHOSTWALK", 1)]   # castable with a higher slot, no extra effect
TORNADO = ("INVOKER_TORNADO", 2, 6)     # extra force damage each turn from a second aura status
ICEWALL = ("INVOKER_ICEWALL", 1, 6)     # extra fire damage from an extra aura status on the wall pieces

GENERATED = {"Spell_Upcast.txt", "Status_Upcast.txt"}
_files = {}


def load_all():
    for path in glob.glob(os.path.join(DATA, "*.txt")):
        name = os.path.basename(path)
        if name in GENERATED:
            continue
        _files[name] = open(path, encoding="utf-8", errors="ignore").read().replace("\r\n", NL)


def block(name):
    """Body text (the lines after `new entry`) of a stat entry, comment lines removed."""
    for text in _files.values():
        m = re.search(r'new entry "%s"\n(.*?)(?=\nnew entry|\n// =====|\Z)' % re.escape(name), text, re.S)
        if m:
            lines = [ln for ln in m.group(1).split(NL) if not ln.startswith("//")]
            return NL.join(lines).strip(NL) + NL
    sys.exit("base entry not found: " + name)


def field(body, key):
    m = re.search(r'^data "%s" "(.*)"$' % key, body, re.M)
    return m.group(1) if m else None


def entry(name, body):
    return 'new entry "%s"' % name + NL + body.rstrip(NL) + NL


def upcast(name, slot, body):
    """Copy of a spell body with a bigger slot cost and a link back to the base spell."""
    body, n = re.subn(r"SpellSlotsGroup:1:1:\d+", "SpellSlotsGroup:1:1:%d" % slot, body)
    assert n == 1, (name, "UseCosts")
    # PowerLevel tells the UI which slot level this version belongs to. Without it every version sits on the base level's button
    # (the picker showed seven "III" buttons) and the Invoke menu picked an arbitrary one as the default.
    return body.rstrip(NL) + NL + 'data "RootSpellID" "%s"' % name + NL + 'data "PowerLevel" "%d"' % slot + NL


def add_dice(body, level_map, extra, die):
    plus = "+%dd%d" % (extra, die)
    before = body.count("LevelMapValue(%s)" % level_map)
    body = body.replace("LevelMapValue(%s)/2" % level_map, "(LevelMapValue(%s)%s)/2" % (level_map, plus))
    body = body.replace("LevelMapValue(%s)," % level_map, "LevelMapValue(%s)%s," % (level_map, plus))
    assert before >= 1 and body.count(plus) == before, (level_map, before, body.count(plus))
    return body


def status_body(name):
    return block(name)


def main():
    load_all()
    spells, statuses = [], []
    existing = set()
    for text in _files.values():
        existing |= set(re.findall(r'new entry "([^"]+)"', text))
    made = []

    def emit_spell(name, text):
        assert name not in existing and name not in made, "name clash: " + name
        made.append(name)
        spells.append(text)

    def emit_status(name, text):
        assert name not in existing and name not in made, "name clash: " + name
        made.append(name)
        statuses.append(text)

    # ---- direct-hit spells: extra dice of the spell's own die per slot level above the base level
    for name, base, die, level_map, dtype in DIRECT:
        src = block(name)
        assert "SpellSlotsGroup:1:1:%d" % base in src and field(src, "Level") == str(base), (name, "base slot")
        spells.append("// ---- %s: slot %d-%d, +1d%d %s per slot level above %d" % (name, base + 1, MAX_SLOT, die, dtype, base) + NL)
        for slot in range(base + 1, MAX_SLOT + 1):
            emit_spell("%s_%d" % (name, slot), entry("%s_%d" % (name, slot), upcast(name, slot, add_dice(src, level_map, slot - base, die))))

    # ---- Sun Strike, Script Extender variant: same, but the damage is the marker's job. One marker status per slot level.
    name, base, die, level_map, dtype = SUNSTRIKE_SE
    src = block(name)
    marker_src = status_body("INVOKER_SUNSTRIKE_SPLIT_FULL")
    spells.append("// ---- %s: slot %d-%d (the marker status carries the slot level to the script)" % (name, base + 1, MAX_SLOT) + NL)
    statuses.append("// ---- Sun Strike (Script Extender) markers, one per slot level: INVOKER_SUNSTRIKE_SPLIT_FULL_<slot>" + NL)
    for slot in range(base + 1, MAX_SLOT + 1):
        body = add_dice(src, level_map, slot - base, die)
        body, n = re.subn(r"ApplyStatus\(INVOKER_SUNSTRIKE_SPLIT_FULL,100,1\)", "ApplyStatus(INVOKER_SUNSTRIKE_SPLIT_FULL_%d,100,1)" % slot, body)
        assert n == 1, "SE marker"
        emit_spell("%s_%d" % (name, slot), entry("%s_%d" % (name, slot), upcast(name, slot, body)))
        mark = re.sub(r'data "StackId" "[^"]+"', 'data "StackId" "INVOKER_SUNSTRIKE_SPLIT_FULL_%d"' % slot, marker_src)
        emit_status("INVOKER_SUNSTRIKE_SPLIT_FULL_%d" % slot, entry("INVOKER_SUNSTRIKE_SPLIT_FULL_%d" % slot, mark))

    # ---- Tornado: a second, invisible aura on the same anchor adds n d6 force damage each turn
    name, base, die = TORNADO
    src = block(name)
    aura_src, hit_src = status_body("INVOKER_TORNADO_AURA"), status_body("INVOKER_TORNADO_HIT")
    display = field(aura_src, "DisplayName")
    hit_display, hit_desc, hit_icon = field(hit_src, "DisplayName"), field(hit_src, "Description"), field(hit_src, "Icon")
    assert "SpellSlotsGroup:1:1:%d" % base in src
    spells.append("// ---- %s: slot %d-%d, +1d%d force damage per turn per slot level above %d" % (name, base + 1, MAX_SLOT, die, base) + NL)
    statuses.append("// ---- Tornado bonus damage: INVOKER_TORNADO_BONUS_AURA_<n> / _HIT_<n>, n = slot level - %d" % base + NL)
    for slot in range(base + 1, MAX_SLOT + 1):
        n = slot - base
        body, count = re.subn(r"(INVOKER_TORNADO_AURA(?:_\d+)?)\)", r"\1,INVOKER_TORNADO_BONUS_AURA_%d)" % n, src)
        assert count >= 5, ("tornado summons", count)
        emit_spell("%s_%d" % (name, slot), entry("%s_%d" % (name, slot), upcast(name, slot, body)))
        emit_status("INVOKER_TORNADO_BONUS_AURA_%d" % n, entry("INVOKER_TORNADO_BONUS_AURA_%d" % n, NL.join([
            'type "StatusData"', 'data "StatusType" "BOOST"', 'data "DisplayName" "%s"' % display,
            'data "StackId" "INVOKER_TORNADO_BONUS_AURA_%d"' % n, 'data "StackType" "Ignore"', 'data "AuraRadius" "3"',
            'data "AuraStatuses" "TARGET:IF(Character() and not Dead() and Enemy()):ApplyStatus(INVOKER_TORNADO_BONUS_HIT_%d,100,-1)"' % n,
            'data "StatusPropertyFlags" "DisableOverhead;DisableCombatlog;DisablePortraitIndicator"'])))
        emit_status("INVOKER_TORNADO_BONUS_HIT_%d" % n, entry("INVOKER_TORNADO_BONUS_HIT_%d" % n, NL.join([
            'type "StatusData"', 'data "StatusType" "BOOST"', 'data "DisplayName" "%s"' % hit_display, 'data "Description" "%s"' % hit_desc,
            'data "Icon" "%s"' % hit_icon, 'data "StackId" "INVOKER_TORNADO_BONUS_HIT_%d"' % n, 'data "StackType" "Ignore"',
            'data "TickType" "StartTurn"', 'data "TickFunctors" "DealDamage(%dd%d,Force)"' % (n, die)])))

    # ---- Ice Wall: each variant uses its own wall status, which also applies an extra n d6 fire status
    name, base, die = ICEWALL
    src = block(name)
    wall_src, hit_src = status_body("INVOKER_ICEWALL_WALL"), status_body("INVOKER_ICEWALL_HIT")
    hit_display, hit_desc, hit_icon = field(hit_src, "DisplayName"), field(hit_src, "Description"), field(hit_src, "Icon")
    assert field(src, "ItemWallStatus") == "INVOKER_ICEWALL_WALL" and "SpellSlotsGroup:1:1:%d" % base in src
    spells.append("// ---- %s: slot %d-%d, +1d%d fire damage per slot level above %d (own wall status per version)" % (name, base + 1, MAX_SLOT, die, base) + NL)
    statuses.append("// ---- Ice Wall: INVOKER_ICEWALL_WALL_<slot> (copy of the wall status + a bonus burn) and INVOKER_ICEWALL_BONUS_<n>, n = slot level - %d" % base + NL)
    for slot in range(base + 1, MAX_SLOT + 1):
        n = slot - base
        body = src.replace('data "ItemWallStatus" "INVOKER_ICEWALL_WALL"', 'data "ItemWallStatus" "INVOKER_ICEWALL_WALL_%d"' % slot)
        assert body != src
        emit_spell("%s_%d" % (name, slot), entry("%s_%d" % (name, slot), upcast(name, slot, body)))
        wall = re.sub(r'data "StackId" "[^"]+"', 'data "StackId" "INVOKER_ICEWALL_WALL_%d"' % slot, wall_src)
        wall, count = re.subn(r'(data "AuraStatuses" "[^"]*ApplyStatus\(DIFFICULT_TERRAIN,100,-1\))"', r'\1;ApplyStatus(INVOKER_ICEWALL_BONUS_%d,100,-1)"' % n, wall)
        assert count == 1, "ice wall aura"
        emit_status("INVOKER_ICEWALL_WALL_%d" % slot, entry("INVOKER_ICEWALL_WALL_%d" % slot, wall))
        emit_status("INVOKER_ICEWALL_BONUS_%d" % n, entry("INVOKER_ICEWALL_BONUS_%d" % n, NL.join([
            'type "StatusData"', 'data "StatusType" "BOOST"', 'data "DisplayName" "%s"' % hit_display, 'data "Description" "%s"' % hit_desc,
            'data "Icon" "%s"' % hit_icon, 'data "StackId" "INVOKER_ICEWALL_BONUS_%d"' % n, 'data "StackType" "Ignore"',
            'data "OnApplyFunctors" "DealDamage(%dd%d,Fire)"' % (n, die), 'data "TickType" "StartTurn"',
            'data "TickFunctors" "DealDamage(%dd%d,Fire)"' % (n, die)])))

    # ---- castable with a higher slot, no extra effect (what vanilla does for Haste, Shield, Mage Armour ...)
    for name, base in PLAIN:
        src = block(name)
        assert "SpellSlotsGroup:1:1:%d" % base in src and field(src, "Level") == str(base), (name, "base slot")
        spells.append("// ---- %s: slot %d-%d, same effect (only lets you spend a higher slot)" % (name, base + 1, MAX_SLOT) + NL)
        for slot in range(base + 1, MAX_SLOT + 1):
            emit_spell("%s_%d" % (name, slot), entry("%s_%d" % (name, slot), upcast(name, slot, src)))

    head = ("// GENERATED by tools/generate_upcasts.py - do not edit by hand. Re-run the script after changing a base spell.\n"
            "// Higher-level versions of the Invoke combos (vanilla pattern: own entry + bigger slot cost + RootSpellID).\n\n")
    for path, parts in ((OUT_SPELLS, spells), (OUT_STATUS, statuses)):
        text = head + NL.join(parts)
        open(path, "w", encoding="utf-8", newline="").write(text.replace(NL, "\r\n"))
    n_spell = len([n for n in made if not n.startswith(("INVOKER_TORNADO_BONUS", "INVOKER_ICEWALL_WALL", "INVOKER_ICEWALL_BONUS", "INVOKER_SUNSTRIKE_SPLIT"))])
    print("wrote %s (%d spell versions) and %s (%d statuses)" % (os.path.basename(OUT_SPELLS), n_spell, os.path.basename(OUT_STATUS), len(made) - n_spell))


if __name__ == "__main__":
    main()
