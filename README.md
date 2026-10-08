# Arcane Invoker

> # ⚠️ DISCLAIMER
> **Arcane Invoker is an UNOFFICIAL, FAN-MADE mod inspired by the Invoker hero from Dota 2. It is NOT affiliated with, endorsed by, or sponsored by Valve Corporation or Larian Studios. Dota 2, Invoker and all related names are trademarks of Valve. Baldur's Gate 3 is a trademark of Larian Studios. No Valve assets are included.**

A Baldur's Gate 3 mod that adds the **Arcane Invoker**, a Wizard subclass (chosen at Wizard level 2).
Unofficial fan work, inspired by the Invoker hero from Dota 2.

Hold up to three **reagent orbs** (Quas, Wex, Exort), then cast **Invoke** to unleash the one spell that
matches the orbs you hold. Orbs cost no action; each combo costs an action, and most cost a spell slot. Ten combo spells, orb passives,
an at-will Arcane Strike cantrip, and the Arcane Invoker's Gauntlets item.

| Orb | Passive (per orb held, up to 3) |
|---|---|
| Quas | +1 HP regenerated per turn during combat |
| Wex | movement costs 10% less, +1 Initiative |
| Exort | +1 force damage on attacks and Arcane Strike |

Combos: Cold Snap (QQQ), Ghost Walk (QQW), Ice Wall (QQE), EMP (WWW), Tornado (QWW), Deafening Blast (QWE),
Alacrity (WWE), Sun Strike (EEE), Chaos Meteor (WEE), Forge Spirit (QEE).

Slot costs: Cold Snap is at-will; Ghost Walk, Ice Wall and Deafening Blast cost a level 1 slot; EMP, Tornado, Alacrity and Forge Spirit a level 2 slot;
Sun Strike and Chaos Meteor a level 3 slot. Any combo that costs a slot can be cast with a higher-level slot. Each level above the spell's own adds
+1d10 to Sun Strike, +1d8 to Chaos Meteor, EMP and Deafening Blast, and +1d6 per turn to Tornado and Ice Wall. Ghost Walk, Alacrity and Forge Spirit
gain nothing from a higher slot.

## Compatible with Expansion (Levels 13–20)

Works with [Expansion: Level 13-20 (Configurable)](https://www.nexusmods.com/baldursgate3/mods/279), but does not need it (the base game caps at level 12). With a raised level cap:

- Combo damage continues to level 20 (levels 19–20: Sun Strike 16d10, Chaos Meteor impact 12d8, EMP 11d8, Deafening Blast 7d8); damage-over-time effects, Ice Wall and Forge Spirits gain tiers at levels 13 and 17.
- Level 14 **Elemental Attunement**: resistance to Cold, Fire and Lightning.
- Level 16 **Invoker's Reserves**: one extra 3rd-level and one extra 2nd-level spell slot.
- Level 18 **Triple Resonance**: while you hold 3 orbs, +2 AC and +2 to all saving throws.
- Level 20 **Grand Invoker**: Intelligence +2 (max 22) and +5 Initiative.

Load order: Mod Configuration Menu, then Expansion, then InvokerAbilities. Tested through level 20.

Choosing the subclass also grants one extra 3rd-level and two extra 2nd-level spell slots (long-rest refresh) for the slot-gated combos.

## Layout

- `source/` - the mod as it ships (`Mods/` and `Public/` roots, stats, level maps, progressions, localization, effects).
- `roottemplate_src/` - editable item/creature templates, converted to `.lsf` at build time.
- `tools/` - packer (`pakbuild`), extractor, the orb effect generator (`vfxcompile/build_orb.py`), and `generate_upcasts.py`, which writes the higher-slot spell versions (`Spell_Upcast.txt`, `Status_Upcast.txt`; rerun it after changing a base combo).
- `docs/plans/` - design notes.
- `repack.ps1` - builds `InvokerAbilities.pak` and installs it into the game's `Mods` folder.
- `mod-description-bbcode.txt`, `mod-details-page.html` - store page text.

## Building

Requires the .NET 8 SDK, Python 3, the BG3 Toolkit, and LSLib (ships with BG3 Mod Manager). Edit the `$lib`
path at the top of `repack.ps1`, then:

```powershell
python tools\vfxcompile\build_orb.py   # regenerates orb effects into vfx_src/
.\repack.ps1                           # packs and installs (close BG3 and the Toolkit first)
```

The Script Extender is optional. It gives the gauntlets item once and lets Sun Strike split its damage between everything it hits (without it, Sun Strike hits the centre for full damage and enemies in a wider ring for less).

## Disclaimer

**This is an unofficial fan project. It is not affiliated with, endorsed by, or sponsored by Valve Corporation or Larian Studios. Dota 2 and Invoker are Valve's; Baldur's Gate 3 is Larian's. Base-game assets are referenced by ID and are not redistributed.**

## License

Original content in this repository is licensed under [CC BY-NC 4.0](LICENSE): free to share and adapt with credit,
**not for commercial use**. This does not cover Valve's or Larian's content (see the disclaimer above).
