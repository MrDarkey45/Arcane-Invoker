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
DECAL_DIAMETER = 12.0       # ground ring / shockwave decal width (was 9: user 2026-10-02 "doesn't seem visible" -> remade bigger)
K = DECAL_DIAMETER / 16.0   # vanilla Static Overdrive decal is 16 m wide -> scale factor for everything else
CHARGE = 1.0                # seconds the energy ball + ground ring charge before the burst (was 0.7)
RAISE = 0.6                 # metres to lift the burst's rings/flash/sparks off the ground; decals stay on the floor
BURST_STRETCH = 2.5         # vanilla burst layers last 0.15-0.4 s (a blink): play them this much slower
BURST_BRIGHT = 2.0          # brightness multiplier on the burst's particle layers
BALL_Y = 1.6                # height of the charging energy ball
BALL_SIZE = 2.4             # metres (aura)
LINGER = 1.6                # seconds the crackling arcs keep going after the burst
ARC_RING = 2.6              # radius of the ring of lingering arcs

# Damage delay (user 2026-10-02): INVOKER_EMP is a ProjectileStrike. An invisible projectile drops from PROJ_HEIGHT straight down in
# ~CHARGE seconds (HEIGHT = v0*t + a*t^2/2), so the damage lands with the burst instead of at the cast. The ground effect stays the
# spell's PositionEffect (it plays on Cast and bursts at CHARGE).
PROJ_ID = str(uuid.uuid5(B.NS, "emp_projectile"))
PROJ_NAME = "INVOKER_Projectile_EMP"
PROJ_HEIGHT = 3             # 2026-10-03: was 30 - roofs caught the projectile; now it starts just above the target (works indoors)
PROJ_INITIAL_SPEED = 3.0    # m/s -> ~1 s for 3 m (slowest vanilla projectile templates: 4-5 m/s)
PROJ_ACCEL = 3.0
PROJ_SPEED = 3.0
ROOT_TEMPLATES = os.path.join(B.ROOT, "roottemplate_src", "merged.lsx")

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
        st0, en0 = float(c.get("start")), float(c.get("end"))
        if cls in ("ParticleSystem", "Billboard", "Decal"):        # slow the blink-short burst down
            retime(c, CHARGE + st0, CHARGE + st0 + (en0 - st0) * BURST_STRETCH)
            if cls == "ParticleSystem":
                scale_ramp(c, "352fac77", BURST_STRETCH)           # particle lifespan
                scale_ramp(c, "7b01f163", BURST_BRIGHT)
        else:
            shift(c, CHARGE)
        if cls in ("ParticleSystem", "Billboard"):
            raise_component(c, RAISE)
        if cls.endswith("Force"):                 # forces only need to outlast the longest spark (emitted <= 1.0 s, life <= 2 s)
            retime(c, float(c.get("start")), CHARGE + 3.5)
        c.set("instancename", str(uuid.uuid5(B.NS, f"emp_burst_{len(out)}_{cls}_{nm}")))
        out.append(c)
    return out


def charge_components():
    """Ground ring + glow disc that build up before the burst (cloned from the Ranger Volley prepare decals)."""
    out = []
    want = [("PolarUV_UVDistortion_04", MAIN, 7.0, 1.0), ("Glow_Circle_01", MAIN, 3.0, 0.8)]
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
    assert len(out) == 2, f"charge decals not found: {seen}"  # noqa
    return out


def _abs(v):          # layer() scales are multiplied by build_orb's SIZE; give absolute metres
    return tuple(x / B.SIZE for x in v) if isinstance(v, tuple) else v / B.SIZE


def _emit(tag, L, start, end, pos):
    glow_base = [c for c in B.xml(B.BASE).iter("component") if c.get("class") == "ParticleSystem"][1]
    c = B.make_emitter(glow_base, "emp", dict(column=0, slot=2, phase=0), L, end - start)
    B.set_ramp(c, B.P["kf_offset"], [[(0, pos[0]), (1, pos[0])], [(0, pos[1]), (1, pos[1])], [(0, pos[2]), (1, pos[2])]])
    B.set_value(c, B.P["name"], f"emp_{tag}")
    retime(c, start, end)
    c.set("instancename", str(uuid.uuid5(B.NS, f"emp_{tag}")))
    return c


def ball_components():
    """New (remake): a crackling energy ball hangs over the target while the ring charges, detonates into a big flash,
    and arcs keep crackling across the area afterwards - so the EMP reads from the normal BG3 camera distance."""
    import math
    br = lambda v: v / B.BRIGHT
    arcs = lambda lo, hi, rate: B.layer("arcs", color=B.argb(255, 185, 140, 255), bright=br(14.0), scale=_abs((lo, hi)),
                                        life=(0.08, 0.18), rate=rate, max_count=14, spin=(0, 0),
                                        clone=(B.LIGHTNING_ORB, "04x02_Lightning_01"))
    centre = (0.0, BALL_Y, 0.0)
    out = [
        # charging ball
        _emit("ball_aura", B.layer("aura", "glow", B.argb(255, *MAIN), br(4.0), _abs(BALL_SIZE), 0.25, 40, 16,
                                   alpha=[(0, 0.8), (1, 0)]), 0, CHARGE + 0.1, centre),
        _emit("ball_core", B.layer("core", "glow", B.argb(255, 235, 225, 255), br(9.0), _abs(BALL_SIZE * 0.4), 0.12, 60, 12,
                                   alpha=[(0, 1), (1, 0.6)]), 0, CHARGE + 0.1, centre),
        _emit("ball_arcs", arcs(BALL_SIZE * 0.8, BALL_SIZE * 1.3, 22), 0, CHARGE + 0.1, centre),
        _emit("ball_sparks", B.layer("sparks", "glow", B.argb(255, *BRIGHT), br(8.0), _abs((0.06, 0.12)), (0.3, 0.6), 50, 40,
                                     alpha=[(0, 1), (1, 0)], velocity=("0,1,0", 180, 1.0, 3.0), space=2),
              0, CHARGE + 0.1, centre),
        # detonation flash
        _emit("flash_aura", B.layer("flash", "glow", B.argb(255, *MAIN), br(8.0), _abs(DECAL_DIAMETER * 0.9), (0.4, 0.6), 20, 10,
                                    alpha=[(0, 0.9), (1, 0)]), CHARGE, CHARGE + 0.35, (0.0, 1.0, 0.0)),
        _emit("flash_core", B.layer("flashcore", "glow", B.argb(255, 240, 235, 255), br(14.0), _abs(DECAL_DIAMETER * 0.35),
                                    (0.25, 0.4), 20, 8, alpha=[(0, 1), (1, 0)]), CHARGE, CHARGE + 0.25, (0.0, 1.0, 0.0)),
        _emit("flash_sparks", B.layer("flashsparks", "glow", B.argb(255, *BRIGHT), br(10.0), _abs((0.08, 0.16)), (0.5, 1.0),
                                      160, 120, alpha=[(0, 1), (1, 0)], velocity=("0,1,0", 180, 3.0, 8.0), space=2),
              CHARGE, CHARGE + 0.4, (0.0, 1.0, 0.0)),
    ]
    # lingering arcs: one in the middle + a ring of six
    spots = [(0.0, 1.0, 0.0)] + [(ARC_RING * math.cos(math.radians(a)), 0.9, ARC_RING * math.sin(math.radians(a)))
                                 for a in range(0, 360, 60)]
    for i, pos in enumerate(spots):
        out.append(_emit(f"linger_arcs_{i}", arcs(1.6, 2.6, 12), CHARGE, CHARGE + LINGER, pos))
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
                m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", B.get_value(c, pid) or "")
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
					<attribute id="BoundsMin" type="fvec3" value="-10 -10 -10" />
					<attribute id="BoundsMax" type="fvec3" value="10 10 10" />
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


def write_projectile_template():
    """Invisible delay projectile (no TrailFX / ImpactFX): its only job is to carry the damage down after ~CHARGE seconds."""
    node = f"""                <node id="GameObjects">
					<attribute id="Acceleration" type="float" value="{PROJ_ACCEL:g}" />
					<attribute id="CameraOffset" type="fvec3" value="0 0 0" />
					<attribute id="CastBone" type="FixedString" value="Dummy_CastFX" />
					<attribute id="Flag" type="int32" value="0" />
					<attribute id="GroupID" type="uint32" value="0" />
					<attribute id="HasGameplayValue" type="bool" value="False" />
					<attribute id="ImpactFX" type="FixedString" value="" />
					<attribute id="InitialSpeed" type="float" value="{PROJ_INITIAL_SPEED:g}" />
					<attribute id="LevelName" type="FixedString" value="" />
					<attribute id="MapKey" type="FixedString" value="{PROJ_ID}" />
					<attribute id="Name" type="LSString" value="{PROJ_NAME}" />
					<attribute id="ParentTemplateId" type="FixedString" value="" />
					<attribute id="PhysicsTemplate" type="FixedString" value="" />
					<attribute id="PreviewPathImpactFX" type="FixedString" value="VFX_UI_DestinationBeam_Projectile_01" />
					<attribute id="PreviewPathMaterial" type="FixedString" value="312a1494-a0e2-c215-cf51-bda58a6b2341" />
					<attribute id="PreviewPathRadius" type="float" value="0.1" />
					<attribute id="RotateImpact" type="bool" value="False" />
					<attribute id="Speed" type="float" value="{PROJ_SPEED:g}" />
					<attribute id="TrailFX" type="FixedString" value="" />
					<attribute id="TrajectoryType" type="uint8" value="0" />
					<attribute id="Type" type="FixedString" value="projectile" />
					<attribute id="VelocityMode" type="uint8" value="1" />
					<attribute id="VisualTemplate" type="FixedString" value="" />
					<attribute id="_OriginalFileVersion_" type="int64" value="144115200960758167" />
					<children>
						<node id="Bounds" />
						<node id="GameMaster" />
					</children>
				</node>
"""
    begin, end = "<!-- EMP PROJECTILE BEGIN (generated) -->\n", "<!-- EMP PROJECTILE END -->\n"
    s = open(ROOT_TEMPLATES, encoding="utf-8", newline="").read().replace("\r\n", "\n")
    if begin in s:
        s = s[:s.index(begin)] + s[s.index(end) + len(end):]
    close = s.rfind("</children>", 0, s.rfind("</region>"))
    close = s.rfind("\n", 0, close) + 1
    s = s[:close] + begin + node + end + s[close:]
    with open(ROOT_TEMPLATES, "w", encoding="utf-8", newline="") as f:
        f.write(s)


def main():
    root = copy.deepcopy(B.xml(STATIC))
    bounds = copy.deepcopy(next(c for c in root.iter("component") if c.get("class") == "BoundingSphere"))
    burst, charge = burst_components(), charge_components() + ball_components()
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
    B.set_value(bounds, "ba2ee0f9", DECAL_DIAMETER)   # BoundingSphere Radius
    tg = ET.SubElement(tgs, "trackgroup", name="Invoker EMP")
    ET.SubElement(ET.SubElement(tg, "ids"), "id", value="2")
    for c in [bounds] + comps:
        ET.SubElement(tg, "track", name="Track", muted="False", locked="False", mutestateoverride="None").append(c)

    out = os.path.join(B.OUT_DIR, NAME + ".lsefx")
    ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=True)
    deps = material_guids(comps)
    write_bank(duration, deps)
    write_mei()
    write_projectile_template()
    if os.path.isdir(B.PREVIEW_DIR):
        shutil.copy2(out, B.PREVIEW_DIR)
    print(f"{NAME}: {len(charge)} charge + {len(burst)} burst components, duration {duration:g}s, scale K={K:.3f}, "
          f"{len(deps)} materials; MEI {MEI_ID}")


if __name__ == "__main__":
    main()
