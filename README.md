# Arcane Invoker

> # ⚠️ DISCLAIMER
> **Arcane Invoker is an UNOFFICIAL, FAN-MADE mod inspired by the Invoker hero from Dota 2. It is NOT affiliated with, endorsed by, or sponsored by Valve Corporation or Larian Studios. Dota 2, Invoker and all related names are trademarks of Valve. Baldur's Gate 3 is a trademark of Larian Studios. No Valve assets are included.**

A Baldur's Gate 3 mod that adds the **Arcane Invoker**, a Wizard subclass (chosen at Wizard level 2).
Unofficial fan work, inspired by the Invoker hero from Dota 2.

Hold up to three **reagent orbs** (Quas, Wex, Exort), then cast **Invoke** to unleash the one spell that
matches the orbs you hold. Orbs cost no action; each Invoke costs an action. Ten combo spells, orb passives,
an at-will Arcane Strike cantrip, and the Arcane Invoker's Gauntlets item.

| Orb | Passive (per orb held, up to 3) |
|---|---|
| Quas | +1 HP regenerated per turn during combat |
| Wex | movement costs 10% less, +1 Initiative |
| Exort | +1 force damage on attacks and Arcane Strike |

Combos: Cold Snap (QQQ), Ghost Walk (QQW), Ice Wall (QQE), EMP (WWW), Tornado (QWW), Deafening Blast (QWE),
Alacrity (WWE), Sun Strike (EEE), Chaos Meteor (WEE), Forge Spirit (QEE).

## Layout

- `source/` - the mod as it ships (`Mods/` and `Public/` roots, stats, level maps, progressions, localization, effects).
- `roottemplate_src/` - editable item/creature templates, converted to `.lsf` at build time.
- `tools/` - packer (`pakbuild`), extractor, and the orb effect generator (`vfxcompile/build_orb.py`).
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

The Script Extender is optional and only used to give the gauntlets item once.

## Disclaimer

**This is an unofficial fan project. It is not affiliated with, endorsed by, or sponsored by Valve Corporation or Larian Studios. Dota 2 and Invoker are Valve's; Baldur's Gate 3 is Larian's. Base-game assets are referenced by ID and are not redistributed.**

## License

Original content in this repository is licensed under [CC BY-NC 4.0](LICENSE): free to share and adapt with credit,
**not for commercial use**. This does not cover Valve's or Larian's content (see the disclaimer above).
