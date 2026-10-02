# Invoker Abilities — BG3 Mod Design (v1)

**Date:** 2026-09-16
**Status:** Validated design (finalized under Auto Mode; user may redirect any call).
**Goal:** Port Dota 2's Invoker (orb reagents + Invoke combos) into BG3 via the official Toolkit,
with combos that are *easy to cast* inside BG3's turn-based action economy.

---

## 1. Locked decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Combo casting | **Hybrid** | Orb system preserved; Invoke container makes firing a combo one click. |
| 2 | Delivery | **Wizard subclass** ("Arcane Invoker") | INT-based arcane "genius" fits Invoker; subclass inherits progression/UI; unlocks at Wizard L2. Orb/invoke system is self-contained so it can be re-hosted later. |
| 3 | Scope | **3-combo vertical slice** | Sun Strike, Cold Snap, Deafening Blast — proves the pipeline across recipe types before doing all 10. |
| 4 | Fidelity | **Lean v1, architected for orb-level scaling** | No passive orb buffs / two-spell hold in v1; spell power parametrized by orb investment so scaling can switch on later. |
| 5 | Orb ordering | **3-cap + manual dispel (not true FIFO)** | True time-ordered orb replacement needs Script Extender; v1 stays pure-data. |

---

## 2. Architecture

```
Subclass (delivery)  →  Orb State Machine (input)  →  Invoke Container (output)
 "Arcane Invoker"        Quas/Wex/Exort statuses        reads orbs → matching combo
```

The orb + invoke system is self-contained and does not depend on the subclass, so it could later be
moved to an item or a base class without a rewrite.

---

## 3. Orb system (input)

- **Three near-free abilities:** Quas (ice), Wex (storm), Exort (fire). Each cast applies 1 stack of
  its own orb-status: `INVOKER_ORB_QUAS`, `INVOKER_ORB_WEX`, `INVOKER_ORB_EXORT`.
- **Cap = 3 orbs total** across all types. At 3 held, casting another orb is blocked (tooltip:
  "Invoke or Dispel first").
- **Dispel Orbs** utility clears all orb stacks.
- **Cost model:** orbs cost **no action** (mimic Dota's instant orbs); Invoke costs your **Action**.
  Result: one turn = arrange up to 3 orbs (free) + Invoke once. Turn-based friendly and balanced.
- **Deferred (architected-for):** per-orb passive buffs (Quas regen / Wex haste / Exort damage) and
  orb-level scaling of combo power.

### Orb-tracking implementation
Three separate stacking statuses (one per orb type), each 0–3, enforced total ≤ 3.
Combo conditions read exact stack counts (see §4).

---

## 4. Invoke container (output — the hybrid)

- **Invoke** = container spell listing the combos. Each combo child has a `RequirementCondition`
  checking exact orb stacks:
  - Sun Strike (EEE): `ExortStack == 3`
  - Cold Snap (QQQ): `QuasStack == 3`
  - Deafening Blast (QWE): `QuasStack == 1 && WexStack == 1 && ExortStack == 1`
- Player builds orbs → opens Invoke → **only the matching combo is enabled** → one click fires it.
- Orbs **persist** after Invoke (Dota-faithful). Invoke uses a short **cooldown / custom action
  resource** so it isn't spammed and doesn't consume the Wizard's normal spell slots.

---

## 5. Vertical slice — 3 combos

| Recipe | Spell | BG3 realization (remix existing effects; custom VFX avoided) |
|---|---|---|
| **EEE** | Sun Strike | ground-targeted delayed fire nuke, small radius (Flame Strike–style fire functor + detonation status) |
| **QQQ** | Cold Snap | cold DoT status + brief freeze/stun on the target |
| **QWE** | Deafening Blast | cone: thunder damage + knockback + short disarm (Thunderwave-style) |

Covers single-orb-type recipes (EEE, QQQ) and an all-different recipe (QWE) → validates the full
condition system. Remaining 7 combos are added in later passes.

---

## 6. Planned Toolkit file structure (to be created when building)

Within module `InvokerAbilities` (UUID `39a130d8-8e3d-6d6c-5a20-ae216d580752`):
- **Spells** — `Spell_Shout` (orbs, dispel), `Spell_Target/Projectile` (Sun Strike, Cold Snap),
  `Spell_Zone/Shout` (Deafening Blast cone), plus the Invoke container spell.
- **Statuses** — `INVOKER_ORB_QUAS/WEX/EXORT` (stacking), combo effect statuses (cold DoT, freeze,
  disarm, Sun Strike detonation).
- **Action resource** — custom "Invoke" resource (or per-spell cooldown).
- **Progression** — Wizard subclass LSX granting orbs + Invoke at the subclass level.
- **Localization** — spell/status names + descriptions (tooltips show the QWE recipe).

---

## 7. Open / future work
- Confirm whether Invoke should be Action vs Bonus Action once tested in-engine.
- Add remaining 7 combos.
- Enable orb passive buffs + orb-level scaling (already architected for).
- Evaluate Script Extender for true FIFO orb ordering (optional fidelity upgrade).

---

## 8. Next step
Build the vertical slice in the Toolkit project, starting with the orb statuses + the three orb
abilities + the Invoke container, then the three combo spells. Do not begin until the user greenlights
building (design phase is complete).
