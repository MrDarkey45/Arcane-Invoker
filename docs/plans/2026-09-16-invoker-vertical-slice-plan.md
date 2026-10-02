# Invoker Vertical Slice — Implementation Plan

**Goal:** Ship a playable 3-combo vertical slice of the Invoker kit as a Wizard subclass, built in
parts that each load and verify in-game independently.

**Architecture:** Orb statuses (input) → Invoke container spell with orb-count conditions (routing)
→ combo spells (output), all delivered by the "Arcane Invoker" Wizard subclass. Hand-authored
stats `.txt` + LSX files placed in the Toolkit's loose-file folders so the game/Toolkit reads them
directly (packed to `.pak` only later for distribution).

**Tech stack:** BG3 stats syntax (`.txt`), LSX (Progressions/ClassDescriptions/ActionResources),
BG3 localization XML. No Script Extender dependency in v1.

**Who does what:** The author writes all files; each in-game check is run by hand (BG3 can't be
launched from tooling). We do not start the next part until the current part's check passes.

**Key on-disk locations** (module = `InvokerAbilities_39a130d8-8e3d-6d6c-5a20-ae216d580752`):
- Stats: `Data/Public/<mod>/Stats/Generated/Data/*.txt`
- Progression/subclass: `Data/Public/<mod>/Progressions/Progressions.lsx`, `.../ClassDescriptions/ClassDescriptions.lsx`
- Action resources: `Data/Public/<mod>/ActionResourceDefinitions/ActionResourceDefinitions.lsx`
- Localization: `Data/Mods/<mod>/Localization/English/*.xml`

---

## Part 1 — Subclass shell loads
**Build:** `ClassDescriptions.lsx` (Arcane Invoker subclass of Wizard) + empty `Progressions.lsx`
rows for it + localization for the subclass name/description.
**In-game check:** Create or level a Wizard → "Arcane Invoker" appears as a selectable subclass,
no crash, name/description show correctly (not raw handles).
**Proves:** LSX + localization pipeline works before anything depends on it.

## Part 2 — Orbs (input layer)
**Build:** `Status_BOOST.txt` — `INVOKER_ORB_QUAS/WEX/EXORT` (stacking, StackId, placeholder icons).
`Spell_Shout.txt` — Quas/Wex/Exort abilities (each applies 1 stack of its orb, cap 3 total),
plus `INVOKER_DISPEL_ORBS`. Grant these to the subclass via Progressions.
**In-game check:** Arcane Invoker Wizard has Quas/Wex/Exort + Dispel. Casting orbs stacks up to 3
(visible status icons); a 4th is blocked; Dispel clears them.
**Proves:** Orb state machine.

## Part 3 — Invoke container + condition gating (STUBS)
**Build:** `Spell_Shout.txt` — `INVOKER_INVOKE` container listing 3 child combo spells. Children are
**stubs** (apply a harmless marker / 1 token damage) but carry the REAL `RequirementConditions`:
Sun Strike=`ExortStack==3`, Cold Snap=`QuasStack==3`, Deafening Blast=one of each.
**In-game check:** Hold EEE → only Sun Strike enabled in Invoke; QQQ → only Cold Snap; QWE → only
Deafening Blast; wrong orbs → greyed out.
**Proves:** The hardest, most bug-prone piece (orb-count routing) in isolation, before real effects.

## Part 4 — Sun Strike (EEE) real effect
**Build:** Flesh out to a ground-targeted delayed fire nuke (small radius) reusing Flame Strike-style
fire functors + a detonation status.
**In-game check:** With EEE, Invoke → Sun Strike hits the target area for fire damage.

## Part 5 — Cold Snap (QQQ) real effect
**Build:** Cold DoT status (damage per turn) + brief freeze/stun on the target.
**In-game check:** With QQQ, Invoke → target takes cold damage over time and is briefly frozen.

## Part 6 — Deafening Blast (QWE) real effect
**Build:** Cone: thunder damage + knockback + short disarm debuff (Thunderwave-style).
**In-game check:** With QWE, Invoke → enemies in the cone take thunder damage, are pushed, and lose
their weapon action briefly.

## Part 7 — Economy & polish
**Build:** `ActionResourceDefinitions.lsx` for the Invoke resource/cooldown; confirm orbs are
free-action; finalize tooltips showing the QWE recipe on each combo; tidy icons/descriptions.
**In-game check:** Full loop in a real fight — build orbs (free), Invoke (costs Action, on
cooldown), orbs persist after Invoke. All three combos usable in one encounter.

---

## Notes / known risk areas
- **Localization:** if names show as raw handles in-game, the loca XML wasn't picked up — fixable,
  flagged early by Part 1's check.
- **Icons:** using existing in-game icon references as placeholders (custom icons deferred).
- **True FIFO orb ordering** intentionally omitted (needs Script Extender) — using 3-cap + Dispel.
- Exact stats/LSX syntax is authored per-part when we build it; this plan fixes scope, order, and
  the verification gate for each part.
