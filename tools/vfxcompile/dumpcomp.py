"""Dump the key settings of particle layers in a vanilla .lsefx whose Name contains a substring.
Usage: python dumpcomp.py <effect.lsefx> <name-substring> [--all-props]
Shows active modules and the commonly tuned properties (life, rate, scale, velocity, color, alpha, ...),
with ramp channels by name. Use it to copy how Larian built a look before reproducing it in build_orb.py.
"""
import os
import sys
import xml.etree.ElementTree as ET

CFG = r"E:\SteamLibrary\steamapps\common\Baldurs Gate 3\Data\Editor\Config\AllSpark"
KEEP = {"Lifespan", "Emit Rate", "Uniform Scale", "Initial Velocity", "Emit Velocity Axis", "Emit Velocity Angles",
        "Color", "Brightness", "Alpha", "Coordinate Space", "Maximum Particle Count", "Axis Scale", "Alignment",
        "Align To Velocity", "Velocity/Life", "Radius", "Initial Rotation Speed", "Initial Rotation", "Material GUID",
        "Keyframed Offset", "Radius Bottom", "Radius Top", "Height", "Arc", "Offset", "Acceleration", "Mesh GUID"}


def main():
    path, needle = sys.argv[1], sys.argv[2].lower()
    all_props = "--all-props" in sys.argv
    cd = ET.parse(os.path.join(CFG, "ComponentDefinition.xcd")).getroot()
    names = {p.get("id"): p.get("name") for comp in cd.iter("component") if comp.get("name") == "ParticleSystem"
             for p in comp.iter("property") if p.get("name")}
    chan = {c.get("id"): c.get("name") for c in cd.iter("channel")}
    mods = {}
    for m in ET.parse(os.path.join(CFG, "ModuleDefinition.xmd")).getroot().find("modules").findall("module"):
        mods[m.get("id").lower()] = (m.get("name"), {p.get("id") for p in m.iter("property")
                                                      if p.get("component") == "ParticleSystem"})
    for tr in ET.parse(path).getroot().iter("track"):
        for c in tr.findall("component"):
            if c.get("class") != "ParticleSystem":
                continue
            ps = c.find("properties")
            name = next(p for p in ps.iter("property") if p.get("id").startswith("ef1d7d1e")).find("data/datum").get("value")
            if needle not in (name or "").lower():
                continue
            active = [m.get("id").lower() for m in c.iter("module") if m.get("muted") != "True"]
            print(f"\n### {os.path.basename(path)} | {name} | track muted={tr.get('muted')} | t={c.get('start')}..{c.get('end')}")
            print("   modules:", ", ".join(mods.get(m, (m,))[0] for m in active))
            wanted = set().union(*(mods[m][1] for m in active if m in mods)) if active else set()
            for p in ps.iter("property"):
                n = names.get(p.get("id"), p.get("id")[:8])
                if p.get("id") not in wanted or (not all_props and n not in KEEP):
                    continue
                d = p.find("data/datum")
                if d is not None and len(d) == 0:
                    v = d.get("value")
                else:
                    v = "; ".join(f"{chan.get(ch.get('id'), '')} " + " ".join(f"{k.get('time')}:{k.get('value')}"
                                  for k in ch.iter("keyframe")) for ch in p.iter("rampchannel"))
                print(f"    {n} = {(v or '')[:150]}")


if __name__ == "__main__":
    main()
