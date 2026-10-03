"""PREVIEW-ONLY sound sampler for picking Sun Strike sounds (user 2026-10-02). Writes VFX_Invoker_Sound_Sampler.lsefx into the
Toolkit project ONLY (not vfx_src, so it never ships in the pak). Open it in the Effect Editor and play: each candidate sound is
its own Sound track, named "NN <label>" in the timeline, played one after another with a gap. Loops get a longer window and
their _Stop event (if any) as the Leave event.
GUIDs: effect .lsefx Sound components ("Name <guid>") or the sound resource banks (Shared/SharedDev Content/Assets/Sounds/
Spells/[PAK]_*/_merged.lsf, resource ID).  Usage: python build_sound_sampler.py
"""
import copy
import os
import sys
import uuid
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_orb as B  # noqa: E402
import build_emp as E  # noqa: E402
import build_sunstrike as S  # noqa: E402

NAME = "VFX_Invoker_Sound_Sampler"
LOOP_SECONDS = 2.5
SHOT_SECONDS = 2.0
GAP = 0.6

# (label, sound "Name <guid>", stop event or None, is_loop)
SOUNDS = [
    # aiming / charging buzz
    ("BUZZ BlastTrap scan", "SE_CRE_BlastTrap_Scan <942ac48f-df75-4ecf-86fe-90886a677f26>", None, False),
    ("BUZZ BlastTrap scan loop", "SE_CRE_BlastTrap_ScanLoop <68ac96af-4506-4055-a766-63fa84c6af0a>",
     "SE_CRE_BlastTrap_ScanLoopStop <5b3c150d-88ff-4c87-87e9-1483b3fb0ddf>", True),
    ("BUZZ BlastTrap activate", "SE_CRE_BlastTrap_Activate <835f046c-b4db-4444-b13e-2e9b470aa0f2>", None, False),
    ("BUZZ Supernova prepare", "CrSpell_Prepare_SkeletalDragon_SuperNova <5c334e2a-31d8-41b2-a3c4-57bc09e16d7a>", None, False),
    ("BUZZ Supernova loop", "CrSpell_Loop_SkeletalDragon_SuperNova <de28ae7a-5316-448b-8827-a4e43982ebc3>", None, True),
    ("BUZZ Lathander crystal laser", "CRE_BloodOfLathander_GyroCrystalLaser_Loop <70062e1d-24ec-4a01-8b13-8aaaafb6427d>",
     "CRE_BloodOfLathander_GyroCrystalLaser_Loop_Stop <30e779ab-86b3-4f15-9061-f3b2782adc1f>", True),
    ("BUZZ Sunbeam prepare", "Spell_Prepare_Damage_Radiant_Sunbeam_L6to8 <0dfd8c32-45ed-4421-a7be-55d6118a4cb4>", None, False),
    ("BUZZ Sunbeam loop", "Spell_Loop_Damage_Radiant_Sunbeam_L6to8 <87ae3df1-e1ea-4ec1-a405-7d22ac038975>", None, True),
    ("BUZZ Radiant charge", "Spell_Prepare_Damage_Radiant_Gen_L1to3 <1fd96b04-59a3-bf97-74cf-998bdad3a135>", None, False),
    ("BUZZ Radiant charge loop", "Spell_Prepare_Damage_Radiant_Gen_L1to3_Loop <315e049c-278c-eac4-d3b6-d8f5507efda2>", None, True),
    ("BUZZ Gith mind probe", "CRE_GithInfirmary_Device_MindProbe_Stronger_Loop <ae57d103-8dc6-4f2f-89f3-fbc9109bff4a>", None, True),
    ("BUZZ Sunlight concentrate", "VFX_Script_Sunlight_Concentrate_Beam <c28cb2c7-98d6-4e12-bd7f-84675223ad30>", None, True),
    ("BUZZ current: Sunlight beam hum", "VFX_Sunlight_Beam_Thick <262b6e82-1139-4d61-a665-c2b3b2c93ea5>",
     "VFX_Sunlight_Beam_Thick_Stop <0805d965-e118-48a5-8a4d-a7b348a66c28>", True),
    # strike / explosion
    ("BLAST BlastTrap impact", "SE_CRE_BlastTrap_Impact <c91f470b-0bc4-4f46-9150-d13d407105a7>", None, False),
    ("BLAST Supernova cast", "CrSpell_Cast_SkeletalDragon_SuperNova <e41d0d01-6293-4316-a389-9348b43532d3>", None, False),
    ("BLAST Nightsong lunar smite", "CrSpell_Impact_Nightsong_LunarSmite <d9b50700-2264-42ae-aaee-27e064d07c76>", None, False),
    ("BLAST Sunbeam impact", "Spell_Impact_Damage_Radiant_Sunbeam_L6to8 <5ba53ab4-9b61-4711-a880-994e0157248d>", None, False),
    ("BLAST Destructive Wave radiant", "Spell_Impact_Cleric_DestructiveWaveRadiant_L4to5 <83d2757a-4045-4f0f-9d9a-b7d7bec095cf>",
     None, False),
    ("BLAST Nautiloid guns explosion", "END_HighHall_Arrival_GunsExplosion <2d71fa74-a98f-473f-a872-441e8550ff98>", None, False),
    ("BLAST Ketheric generals wrath", "CrSpell_Projectile_Ketheric_GeneralsWrath <e9a02f04-fed3-4c83-89bf-394622157ab7>", None, False),
    ("BLAST Bombardment", "CrSpell_Impact_BombardmentHorde <bef71c08-925d-4019-a480-b10e342d3bb1>", None, False),
    ("BLAST Orthon mine explosion", "CrSpell_Impact_Orthon_MineExplosion <1a37d6af-ec37-4385-b7ae-dcf04a3dc321>", None, False),
    ("BLAST current: Flame Strike impact", "Spell_Impact_Damage_FlameStrike_L4to5 <298955b1-e8ea-49f3-a388-0af7b796f891>",
     None, False),
]


def main():
    base = S._find(S.SUNLIGHT_HUM, "Sound", "Sound")
    comps, t = [], 0.0
    for i, (label, snd, stop, loop) in enumerate(SOUNDS, 1):
        c = copy.deepcopy(base)
        dur = LOOP_SECONDS if loop else SHOT_SECONDS
        B.set_value(c, "ef1d7d1e", f"{i:02d} {label}")
        B.set_value(c, "d9c8f8f4", snd)                 # Enter
        B.set_value(c, "3cc17729", snd)                 # Resume
        B.set_value(c, "83f4fce2", stop or "")          # Leave
        E.retime(c, t, t + dur)
        c.set("instancename", str(uuid.uuid5(B.NS, f"sound_sampler_{i}")))
        comps.append((c, label, t))
        t += dur + GAP
    root = copy.deepcopy(B.xml(B.BASE))
    for child in list(root.find("phases")):
        root.find("phases").remove(child)
    tgs = root.find("trackgroups")
    for tg in list(tgs):
        tgs.remove(tg)
    tg = ET.SubElement(tgs, "trackgroup", name="Sun Strike sound sampler")
    ET.SubElement(ET.SubElement(tg, "ids"), "id", value="2")
    bounds = copy.deepcopy(next(c for c in B.xml(B.BASE).iter("component") if c.get("class") == "BoundingSphere"))
    bounds.set("instancename", str(uuid.uuid5(B.NS, "sound_sampler_bounds")))
    E.retime(bounds, 0, t)
    for c in [bounds] + [c for c, _, _ in comps]:
        ET.SubElement(tg, "track", name="Track", muted="False", locked="False", mutestateoverride="None").append(c)
    out = os.path.join(B.PREVIEW_DIR, NAME + ".lsefx")
    ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=True)
    print(f"{out}  ({t:.1f} s)")
    for i, (_, label, st) in enumerate(comps, 1):
        print(f"  {st:5.1f}s  {i:02d} {label}")


if __name__ == "__main__":
    main()
