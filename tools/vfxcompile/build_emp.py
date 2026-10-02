"""Generate the Dota-style EMP ground effect for INVOKER_EMP (PositionEffect).

Look (user 2026-10-02: "Dota's EMP", Wex violet-blue): a ground ring CHARGES at the target point, then an electric shockwave
bursts outward with sparks and a flash. Built from vanilla assets, no new textures:
  burst  = the active layers of the Automaton's "Static Overdrive" (Cast_02): ground decal Ramp_Shockwave_Lightning_01, two
           Shockwave_01 rings, Sparks_03 flare, glow-circle sparks, glow billboard. Dirt spikes / smoke swirl / camera shake /
           screen blur / sound are dropped (EMP isn't an earth-kicking attack, and PostProcess would blur the whole screen).
  charge = the PolarUV_UVDistortion_04 ring decal + Glow_Circle_01 disc from the Ranger Volley prepare effect.
Everything is scaled by K to EMP's 4 m AreaRadius (Static Overdrive's decal is 16 m wide) and recoloured to the Wex palette.

Writes into vfx_src/ (repack.ps1 compiles/converts them): VFX_Invoker_EMP_01.lsefx, bank_VFX_Invoker_EMP_01.lsx,
mei_INVOKER_EMP_POSITION.lsx. Also copies the .lsefx to the Toolkit project for Effect Editor preview (mannequins at the
centre and at the 4 m edge, on muted tracks, to judge the radius).
Usage: python build_emp.py
"""
import copy
import os
import re
import shutil
import sys
import uuid
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_orb as B  # noqa: E402  (paths, ids, ramp helpers shared with the orb builder)

STATIC = B.MODS + r"\Shared\Assets\Effects\Enemies\VFX_Enemies_Automaton_StaticOverdrive_Cast_02.lsefx"
VOLLEY = B.MODS + r"\SharedDev\Assets\Effects\Spells\Prepare\Ranger\VFX_Spells_Prepare_Ranger_Target_Volley_Root_01.lsefx"

NAME = "VFX_Invoker_EMP_01"
RES_ID = str(uuid.uuid5(B.NS, "emp_resource"))
MEI_ID = str(uuid.uuid5(B.NS, "emp_mei"))
INFO_ID = str(uuid.uuid5(B.NS, "emp_effectinfo"))

AREA_RADIUS = 4.0           # INVOKER_EMP AreaRadius (metres)
DECAL_DIAMETER = 9.0        # a little over 2 x AREA_RADIUS so the ring edge lands near 4 m
K = DECAL_DIAMETER / 16.0   # vanilla Static Overdrive decal is 16 m wide -> scale factor for everything else
CHARGE = 0.7                # seconds of charging ring before the burst starts
RAISE = 0.35                # metres to lift the burst's rings/flash/sparks off the ground (user: "too low"); decals stay on the floor

MAIN = (125, 90, 255)       # Wex violet-blue
BRIGHT = (205, 185, 255)    # sparks / hot highlights

DROP_CLASSES = {"PostProcess", "CameraShake", "Sound", "Light"}
DROP_NAMES = {"BG", "DirtSpikes", "Fake atmosphere"}
TINT_BRIGHT = {"Flare", "Impact_HighFrequencyDetails"}   # everything else kept from the burst uses MAIN

# colour properties by component class (ARGB ramps; alpha is preserved, only RGB is replaced)
COLOR_PROPS = {"ParticleSystem": ("93b34a52", "bb1e9c04"), "Decal": ("2c9b4a60",), "Billboard": ("2bd3e2db",)}
SCALE_PROPS = {"ParticleSystem": ("02e6012f", "79ab5e9c"), "Decal": ("3fb4512b",), "Billboard": ("04696f8f",)}
MATERIAL_PROPS = ("f01fec2b", "d17bfe9f", "df08d1dc",   # particle / decal / billboard material
                  "9cfd15fe", "2b83bf1b")                # particle Mesh GUID / Mesh Proxy GUID (spark shapes are meshes)


def comp_name(c):
    for p in c.find("properties").iter("property"):
        if p.get("id").startswith("ef1d7d1e"):
            return p.find("data/datum").get("value") or ""
    return ""


def has_prop(c, pid):
    return any(p.get("id").startswith(pid) for p in c.find("properties").iter("property"))


def scale_ramp(c, pid, k):
    """Multiply every keyframe value by k, leaving times/types/tangent data alone."""
    for ch in B.prop(c, pid).iter("rampchannel"):
        for kf in ch.iter("keyframe"):
            kf.set("value", f"{float(kf.get('value')) * k:.6g}")


def tint(c, pid, rgb):
    """Replace RGB of every packed-ARGB keyframe, keeping alpha."""
    for ch in B.prop(c, pid).iter("rampchannel"):
        for kf in ch.iter("keyframe"):
            u = int(float(kf.get("value"))) & 0xFFFFFFFF
            v = (u & 0xFF000000) | (rgb[0] << 16) | (rgb[1] << 8) | rgb[2]
            kf.set("value", str(v - (1 << 32) if v >= 1 << 31 else v))


def shift(c, dt):
    s, e = float(c.get("start")) + dt, float(c.get("end")) + dt
    c.set("start", f"{s:g}")
    c.set("end", f"{e:g}")
    B.set_value(c, B.P["time"], f"{s:g},{e:g}")


def retime(c, start, end):
    c.set("start", f"{start:g}")
    c.set("end", f"{end:g}")
    B.set_value(c, B.P["time"], f"{start:g},{end:g}")


def raise_component(c, dy):
    """Lift a particle/billboard layer by dy metres (Offset / Position property); add the Position module if it's missing,
    otherwise the offset is ignored. Ground decals are NOT raised - they project onto the floor."""
    pid = {"ParticleSystem": "726ea55f", "Billboard": "743865b1"}[c.get("class")]
    x, y, z = (float(v) for v in B.get_value(c, pid).split(","))
    B.set_value(c, pid, f"{x:g},{y + dy:g},{z:g}")
    ml = c.find("modules")
    pos = B.M["position"]
    if not any(m.get("id").lower() == pos for m in ml):
        ET.SubElement(ml, "module", id=pos, muted="False", index=str(len(ml)))


def burst_components():
    out = []
    for tr in ET.parse(STATIC).getroot().iter("track"):
        c = tr.find("component")
        if c is None or tr.get("muted") == "True":
            continue
        cls, nm = c.get("class"), comp_name(c)
        if cls in DROP_CLASSES or nm in DROP_NAMES or cls == "Model" or cls == "BoundingSphere":
            continue
        c = copy.deepcopy(c)
        for pid in SCALE_PROPS.get(cls, ()):
            if has_prop(c, pid):
                scale_ramp(c, pid, K)
        rgb = BRIGHT if nm in TINT_BRIGHT else MAIN
        for pid in COLOR_PROPS.get(cls, ()):
            if has_prop(c, pid):
                tint(c, pid, rgb)
        shift(c, CHARGE)
        if cls in ("ParticleSystem", "Billboard"):
            raise_component(c, RAISE)
        if cls.endswith("Force"):                 # forces only need to outlast the longest spark (emitted <= 1.0 s, life <= 2 s)
            retime(c, float(c.get("start")), 3.0)
        c.set("instancename", str(uuid.uuid5(B.NS, f"emp_burst_{len(out)}_{cls}_{nm}")))
        out.append(c)
    return out


def charge_components():
    """Ground ring + glow disc that build up before the burst (cloned from the Ranger Volley prepare decals)."""
    out = []
    want = [("PolarUV_UVDistortion_04", MAIN, 3.0, 1.0), ("Glow_Circle_01", MAIN, 1.2, 0.55)]
    seen = set()
    for c in ET.parse(VOLLEY).getroot().iter("component"):
        if c.get("class") != "Decal":
            continue
        mat = B.get_value(c, "d17bfe9f") or ""
        for key, rgb, bright, peak in want:
            # the 5 m, 1.5 s variants (Coordinate Space 0 = world, a ground decal that stays put)
            if key in mat and key not in seen and B.get_value(c, "e2fa17bd") == "0":
                seen.add(key)
                c = copy.deepcopy(c)
                B.set_ramp(c, "3fb4512b", [B.const(DECAL_DIAMETER), B.const(DECAL_DIAMETER)])       # Dimensions W,H
                tint(c, "2c9b4a60", rgb)
                B.set_ramp(c, "590ace0d", [B.const(bright)])                                          # Brightness
                # Dynamic Value channels X,Y,Z,W - W is the fade envelope over the component's life
                life = CHARGE + 0.35
                B.set_ramp(c, "85d7b13f", [B.const(0), B.const(0), B.const(0),
                                           [(0, 0.0), (CHARGE / life * 0.85, peak), (CHARGE / life, peak), (1, 0.0)]])
                retime(c, 0, life)
                c.set("instancename", str(uuid.uuid5(B.NS, f"emp_charge_{key}")))
                out.append(c)
                break
    assert len(out) == 2, f"charge decals not found: {seen}"
    return out


def preview_models(duration):
    """Mannequin at the centre and at the 4 m edge (+ sand floor), muted tracks forced visible in the Effect Editor."""
    out = []
    for c in B.xml(B.COLD_ORB).iter("component"):
        if c.get("class") != "Model":
            continue
        mesh = B.get_value(c, B.P["model_mesh"]) or ""
        spots = []
        if "Proxy_HUM_M_Fullbody" in mesh:
            spots = [("0,0,0", "centre"), (f"{AREA_RADIUS:g},0,0", "edge")]
        elif "Floor_01_Sand" in mesh:
            spots = [("0,0,0", "floor")]
        for off, tag in spots:
            m = copy.deepcopy(c)
            m.set("start", "0")
            m.set("end", f"{duration:g}")
            m.set("instancename", str(uuid.uuid5(B.NS, f"emp_preview_{tag}")))
            B.set_value(m, B.P["time"], f"0,{duration:g}")
            B.set_value(m, B.P["model_pos"], off)
            out.append(m)
    assert len(out) == 3, "preview models not found"
    return out


def material_guids(comps):
    g = set()
    for c in comps:
        for pid in MATERIAL_PROPS:
            if has_prop(c, pid):
                m = re.search(r"<([0-9a-f-]{36})>?", B.get_value(c, pid) or "")
                if m:
                    g.add(m.group(1))
    return sorted(g)


def write_bank(duration, deps):
    dep_xml = "".join(f"""
								<node id="DependentResource">
									<attribute id="Object" type="FixedString" value="{d}" />
								</node>""" for d in deps)
    text = f"""<?xml version="1.0" encoding="utf-8"?>
<!-- GENERATED by tools/vfxcompile/build_emp.py - do not edit by hand -->
<save>
	<version major="4" minor="0" revision="7" build="200" lslib_meta="v1,bswap_guids,lsf_keys_adjacency" />
	<region id="EffectBank">
		<node id="EffectBank">
			<children>
				<node id="Resource">
					<attribute id="ID" type="FixedString" value="{RES_ID}" />
					<attribute id="Name" type="LSString" value="{NAME}" />
					<attribute id="SourceFile" type="LSString" value="Public/{B.MOD}/Assets/Effects/Effects_Banks/Invoker/{NAME}.lsfx" />
					<attribute id="EffectName" type="FixedString" value="{NAME}" />
					<attribute id="BoundsMin" type="fvec3" value="-6 -6 -6" />
					<attribute id="BoundsMax" type="fvec3" value="6 6 6" />
					<attribute id="CullingDistance" type="float" value="0" />
					<attribute id="Duration" type="float" value="{duration:g}" />
					<attribute id="Looping" type="bool" value="False" />
					<attribute id="InterruptionMode" type="uint32" value="0" />
					<children>
						<node id="Dependencies">
							<children>{dep_xml}
							</children>
						</node>
					</children>
				</node>
			</children>
		</node>
	</region>
</save>
"""
    with open(os.path.join(B.OUT_DIR, f"bank_{NAME}.lsx"), "w", encoding="utf-8") as f:
        f.write(text)


def write_mei():
    # mirrors vanilla CallLightning_PositionEffect (de5e4e60): no bone, pivot = the target point, detached, starts on the Cast textkey
    text = f"""<?xml version="1.0" encoding="utf-8"?>
<!-- GENERATED by tools/vfxcompile/build_emp.py - do not edit by hand -->
<save>
	<version major="4" minor="0" revision="7" build="200" lslib_meta="v1,bswap_guids,lsf_keys_adjacency" />
	<region id="MultiEffectInfos">
		<node id="MultiEffectInfos">
			<attribute id="UUID" type="guid" value="{MEI_ID}" />
			<attribute id="Name" type="LSString" value="INVOKER_EMP_PositionEffect" />
			<children>
				<node id="EffectInfo">
					<attribute id="UUID" type="guid" value="{INFO_ID}" />
					<attribute id="EffectResourceGuid" type="guid" value="{RES_ID}" />
					<attribute id="DetachSource" type="bool" value="True" />
					<attribute id="DetachTarget" type="bool" value="True" />
					<attribute id="KeepRotation" type="bool" value="True" />
					<attribute id="UseOrientDirection" type="bool" value="False" />
					<attribute id="UseDistance" type="bool" value="False" />
					<attribute id="UseScaleOverride" type="bool" value="False" />
					<attribute id="KeepScale" type="bool" value="False" />
					<attribute id="MainHand" type="bool" value="False" />
					<attribute id="OffHand" type="bool" value="False" />
					<attribute id="MinDistance" type="float" value="0" />
					<attribute id="MaxDistance" type="float" value="0" />
					<attribute id="BindSourceTo" type="FixedString" value="SourceEntity" />
					<attribute id="BindTargetTo" type="FixedString" value="TargetEntity" />
					<attribute id="Pivot" type="FixedString" value="Target" />
					<attribute id="DamageType" type="uint32" value="0" />
					<attribute id="VerbalIntent" type="uint32" value="0" />
					<attribute id="StartTextKey" type="LSString" value="Cast" />
					<attribute id="Enabled" type="bool" value="True" />
				</node>
			</children>
		</node>
	</region>
</save>
"""
    with open(os.path.join(B.OUT_DIR, "mei_INVOKER_EMP_POSITION.lsx"), "w", encoding="utf-8") as f:
        f.write(text)


def main():
    root = copy.deepcopy(B.xml(STATIC))
    bounds = copy.deepcopy(next(c for c in root.iter("component") if c.get("class") == "BoundingSphere"))
    burst, charge = burst_components(), charge_components()
    comps = charge + burst
    duration = round(max(float(c.get("end")) for c in comps) + 0.1, 3)

    for child in list(root.find("phases")):          # single-shot effect: no Lead In / Loop / Lead Out
        root.find("phases").remove(child)
    tgs = root.find("trackgroups")
    for tg in list(tgs):
        tgs.remove(tg)
    prev = ET.SubElement(tgs, "trackgroup", name="Preview only (muted)")
    ET.SubElement(ET.SubElement(prev, "ids"), "id", value="1")
    for m in preview_models(duration):
        ET.SubElement(prev, "track", name="Track", muted="True", locked="False", mutestateoverride="Unmuted").append(m)

    bounds.set("instancename", str(uuid.uuid5(B.NS, "emp_bounds")))
    retime(bounds, 0, duration)
    B.set_value(bounds, "ba2ee0f9", AREA_RADIUS + 3)   # BoundingSphere Radius
    tg = ET.SubElement(tgs, "trackgroup", name="Invoker EMP")
    ET.SubElement(ET.SubElement(tg, "ids"), "id", value="2")
    for c in [bounds] + comps:
        ET.SubElement(tg, "track", name="Track", muted="False", locked="False", mutestateoverride="None").append(c)

    out = os.path.join(B.OUT_DIR, NAME + ".lsefx")
    ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=True)
    deps = material_guids(comps)
    write_bank(duration, deps)
    write_mei()
    if os.path.isdir(B.PREVIEW_DIR):
        shutil.copy2(out, B.PREVIEW_DIR)
    print(f"{NAME}: {len(charge)} charge + {len(burst)} burst components, duration {duration:g}s, scale K={K:.3f}, "
          f"{len(deps)} materials; MEI {MEI_ID}")


if __name__ == "__main__":
    main()
