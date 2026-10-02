"""Print an AllSpark .lsefx in readable form: components, their ACTIVE modules, and property NAMES + values
(the file itself only stores GUIDs, and carries data for every module even when the module is off).
Usage: python annotate.py <effect.lsefx> [--all]   (--all = also list properties of inactive modules)
"""
import sys
import xml.etree.ElementTree as ET

CFG = r"E:\SteamLibrary\steamapps\common\Baldurs Gate 3\Data\Editor\Config\AllSpark"


def load_defs():
    prop_names, chan_names = {}, {}
    for comp in ET.parse(CFG + r"\ComponentDefinition.xcd").getroot().iter("component"):
        for p in comp.iter("property"):
            if p.get("id") and p.get("name"):
                prop_names[(comp.get("name"), p.get("id"))] = p.get("name")
                prop_names.setdefault((None, p.get("id")), p.get("name"))
            for ch in p.iter("channel"):
                chan_names[ch.get("id")] = ch.get("name")
    modules = {}  # module id -> (name, {(component, property id)})
    for m in ET.parse(CFG + r"\ModuleDefinition.xmd").getroot().find("modules").findall("module"):
        props = {(p.get("component"), p.get("id")) for p in m.iter("property")}
        modules[m.get("id").lower()] = (m.get("name"), props)
    return prop_names, chan_names, modules


def summarize(prop, chan_names):
    datums = prop.findall("./data/datum")
    if datums and all(len(d) == 0 for d in datums):
        return " | ".join(d.get("value", "") for d in datums)
    parts = []
    for ch in prop.iter("rampchannel"):
        keys = " ".join(f"{k.get('time')}:{k.get('value')}" for k in ch.iter("keyframe"))
        if keys:
            parts.append(f"{chan_names.get(ch.get('id'), 'ch')}[{ch.get('type')}] {keys}")
    return "; ".join(parts) or "(complex)"


def main():
    show_all = "--all" in sys.argv
    prop_names, chan_names, modules = load_defs()
    root = ET.parse(sys.argv[1]).getroot()
    for ph in root.iter("data"):
        if ph.get("definitionid"):
            print(f"phase dur={ph.get('duration')} playcount={ph.get('playcount')}")
    for track in root.iter("track"):
        for comp in track.findall("component"):
            cls = comp.get("class")
            active = [m.get("id").lower() for m in comp.iter("module") if m.get("muted") != "True"]
            print(f"\n[{cls}] t={comp.get('start')}..{comp.get('end')} track='{track.get('name')}' muted={track.get('muted')}")
            print("   modules: " + ", ".join(modules.get(m, (m,))[0] for m in active))
            wanted = set().union(*(modules[m][1] for m in active if m in modules)) if active else set()
            for prop in comp.iter("property"):
                pid = prop.get("id")
                if not show_all and wanted and (cls, pid) not in wanted:
                    continue
                name = prop_names.get((cls, pid)) or prop_names.get((None, pid)) or pid
                print(f"   {name} <{pid[:8]}>: {summarize(prop, chan_names)}")


if __name__ == "__main__":
    main()
