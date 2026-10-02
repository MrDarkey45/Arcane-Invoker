"""Generate the Chaos Meteor sky-fall ground effect for INVOKER_METEOR (PositionEffect).

Look (user 2026-10-02): the meteor FALLS FROM THE SKY onto the target spot, "molten fire boulder":
  fall   (0 - FALL s)  a burning head (Produce Flame shader flame + orange glow + white-hot core) travels down a steep diagonal;
                       world-space trail layers (Fire_Burst flipbook flames with vanilla 2.25-3.6 s life, dark smoke, embers) are left hanging
                       in the air behind it.
  impact (FALL s on)   vanilla's unused Tutorial Meteor impact (fire swirl, flash, shockwave, 20 m glow rings -> scaled by K_IMPACT to the
                       spell's 3 m radius, smoke, refraction sphere, light, camera shake at 60%) plus its ground scorch decal (6 s).
The vanilla impact is already orange-red (255,40-56,0), so nothing is recoloured. Sound component dropped (the spell has its own sounds).

Writes into vfx_src/: VFX_Invoker_Meteor_01.lsefx, bank_VFX_Invoker_Meteor_01.lsx, mei_INVOKER_METEOR_POSITION.lsx (repack.ps1 compiles
them) and copies the .lsefx to the Toolkit project for Effect Editor preview. Usage: python build_meteor.py
"""
import copy
import os
import shutil
import sys
import uuid
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_orb as B  # noqa: E402
import build_emp as E  # noqa: E402  (component helpers shared with the EMP builder)

IMPACT = B.MODS + r"\Shared\Assets\Effects\Projectiles\VFX_Projectiles_Tutorial_Meteor_Impact_01.lsefx"
GROUND = B.MODS + r"\Shared\Assets\Effects\Projectiles\VFX_Projectiles_Tutorial_Meteor_Impact_Ground_01.lsefx"

NAME = "VFX_Invoker_Meteor_01"
RES_ID = str(uuid.uuid5(B.NS, "meteor_resource"))
MEI_ID = str(uuid.uuid5(B.NS, "meteor_mei"))
INFO_ID = str(uuid.uuid5(B.NS, "meteor_effectinfo"))

AREA_RADIUS = 3.0           # INVOKER_METEOR AreaRadius
FALL = 0.6                  # seconds the meteor spends falling before the impact
START = (-4.0, 15.0, -9.5)  # where the head begins (effect-local metres, relative to the target point); steep ~57 deg drop
END = (0.0, 0.4, 0.0)
K_IMPACT = 0.65             # vanilla impact is sized for ~20 m glow rings (was 0.4 - user: "looks small in the preview")
FALL_SCALE = 1.5            # multiplies the falling head/trail layer sizes (same feedback)
SCORCH_SIZE = 8.0           # metres (vanilla 3.9; was 5.5)
SCORCH_SECONDS = 6.0
SHAKE = 0.6                 # camera-shake strength multiplier

SCALE_PROPS = {"ParticleSystem": ("02e6012f", "79ab5e9c", "b0e13a65", "f0d3e3dd"),   # scale, velocity, emitter radii
               "Billboard": ("04696f8f",), "Model": ("f80eefa7",), "Light": ("ba116247",)}
DROP_CLASSES = {"Sound"}
E.MATERIAL_PROPS = E.MATERIAL_PROPS + ("15864e49", "d15b1af4")   # Model meshes + Light template UUIDs are dependencies too


def sc(v):          # layer() scale/brightness get multiplied by build_orb's SIZE / BRIGHT; undo that for absolute values
    k = FALL_SCALE / B.SIZE
    return tuple(x * k for x in v) if isinstance(v, tuple) else v * k


def br(v):
    return v / B.BRIGHT


def path_keys():
    """Falling path: ease-in (accelerating) straight line from START to END, normalised over the fall component's life."""
    xs, ys, zs = [], [], []
    for i in range(9):
        u = i / 8
        f = u ** 1.6
        xs.append((u, round(START[0] + f * (END[0] - START[0]), 4)))
        ys.append((u, round(START[1] + f * (END[1] - START[1]), 4)))
        zs.append((u, round(START[2] + f * (END[2] - START[2]), 4)))
    return [xs, ys, zs]


FLAME_OV = {  # Produce Flame persistent flame: fade in, hold, fade out over the fall; steady size
    "bb1e9c04": lambda d: [[(0, 16777215), (0.08, -1), (0.94, -1), (1, 16777215)]],
    "1dc673ff": lambda d: [[(0, 1.0), (0.08, 5.0), (0.94, 5.0), (1, 1.0)]],
    "9984af4f": [[(0, 1.6 * FALL_SCALE), (1, 1.6 * FALL_SCALE)]],
    "b7f89b82": [[(0, 0.55), (1, 0.55)], [(0, 1.0), (1, 1.0)], [(0, 1.0), (1, 1.0)]],
}

FALL_LAYERS = [
    # name, spec. Trails are released into the world (space 2) so they hang in the air behind the moving head.
    B.layer("trail_smoke", "dust", B.argb(255, 70, 46, 32), br(0.9), sc((1.0, 1.8)), (1.5, 2.5), 30, 50,
            alpha=[(0, 0.5), (1, 0)], spin=(0.05, 0.15), velocity=("0,1,0", 25, 0.2, 0.5), space=2),
    B.layer("trail_fire", scale=sc((0.9, 1.4)), life=(2.25, 3.6), rate=30, max_count=40, space=2,
            clone=(B.MYRMIDON_FIRE, "Fire_Burst_02"),
            ov={"068cf735": [[(0, 0.1), (1, 0.1)]], "16f5adbb": [[(0, 0.06), (1, 0.06)]],
                "24fffa5e": [[(0, 0.1), (1, 0.1)]], "79ab5e9c": [[(0, 0.1), (1, 0.1)], [(0, 0.3), (1, 0.3)]]}),
    B.layer("head_aura", "glow", B.argb(255, 255, 110, 20), br(3.0), sc(3.2), 0.1, 60, 12, alpha=[(0, 0.8), (1, 0)]),
    B.layer("head_flame", life=0.5, rate=0, max_count=1, space=1, persistent=True,
            clone=(B.PRODUCE_FLAME, "ProduceFlame_01"), ov=FLAME_OV),
    B.layer("head_core", "glow", B.argb(255, 255, 235, 180), br(6.0), sc(1.3), 0.1, 60, 12, alpha=[(0, 1), (1, 0.6)]),
    B.layer("trail_embers", "glow",
            [(0, B.argb(255, 255, 225, 130)), (0.5, B.argb(255, 255, 120, 30)), (1, B.argb(255, 120, 30, 10))],
            [(0, br(3.0)), (1, br(1.0))], sc((0.05, 0.09)), (0.6, 1.2), 80, 80, alpha=[(0, 1), (1, 0)],
            velocity=("0,1,0", 180, 0.3, 1.2), space=2),
]


def fall_components():
    glow_base = [c for c in B.xml(B.BASE).iter("component") if c.get("class") == "ParticleSystem"][1]
    el = dict(column=0, slot=2, phase=0)           # dummy: orbit_keys() path is overridden below
    out = []
    for L in FALL_LAYERS:
        c = B.make_emitter(glow_base, "meteor", el, L, FALL)
        B.set_ramp(c, B.P["kf_offset"], path_keys())
        c.set("instancename", str(uuid.uuid5(B.NS, f"meteor_fall_{L['name']}")))
        out.append(c)
    return out


def impact_components():
    out = []
    for tr in B.xml(IMPACT).iter("track"):
        c = tr.find("component")
        if c is None or tr.get("muted") == "True":
            continue
        cls = c.get("class")
        if cls in DROP_CLASSES or cls == "BoundingSphere":
            continue
        c = copy.deepcopy(c)
        for pid in SCALE_PROPS.get(cls, ()):
            if E.has_prop(c, pid):
                E.scale_ramp(c, pid, K_IMPACT)
        if cls == "CameraShake":
            E.scale_ramp(c, "cd5bbe05", SHAKE)
        E.shift(c, FALL)
        if cls.endswith("Force"):
            E.retime(c, float(c.get("start")), FALL + 3.5)
        c.set("instancename", str(uuid.uuid5(B.NS, f"meteor_impact_{len(out)}_{cls}_{E.comp_name(c)}")))
        out.append(c)
    # ground scorch decal(s)
    for tr in B.xml(GROUND).iter("track"):
        c = tr.find("component")
        if c is None or tr.get("muted") == "True" or c.get("class") != "Decal":
            continue
        c = copy.deepcopy(c)
        E.scale_ramp(c, "3fb4512b", SCORCH_SIZE / 3.9)
        E.shift(c, FALL)
        E.retime(c, FALL, FALL + SCORCH_SECONDS)
        c.set("instancename", str(uuid.uuid5(B.NS, f"meteor_scorch_{len(out)}")))
        out.append(c)
    return out


def preview_models(duration):
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
            m.set("instancename", str(uuid.uuid5(B.NS, f"meteor_preview_{tag}")))
            B.set_value(m, B.P["time"], f"0,{duration:g}")
            B.set_value(m, B.P["model_pos"], off)
            out.append(m)
    assert len(out) == 3
    return out


def write_bank(duration, deps):
    dep_xml = "".join(f"""
								<node id="DependentResource">
									<attribute id="Object" type="FixedString" value="{d}" />
								</node>""" for d in deps)
    text = f"""<?xml version="1.0" encoding="utf-8"?>
<!-- GENERATED by tools/vfxcompile/build_meteor.py - do not edit by hand -->
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
					<attribute id="BoundsMin" type="fvec3" value="-18 -2 -18" />
					<attribute id="BoundsMax" type="fvec3" value="18 18 18" />
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
    # mirrors vanilla CallLightning_PositionEffect (de5e4e60); same structure as the EMP position effect
    text = f"""<?xml version="1.0" encoding="utf-8"?>
<!-- GENERATED by tools/vfxcompile/build_meteor.py - do not edit by hand -->
<save>
	<version major="4" minor="0" revision="7" build="200" lslib_meta="v1,bswap_guids,lsf_keys_adjacency" />
	<region id="MultiEffectInfos">
		<node id="MultiEffectInfos">
			<attribute id="UUID" type="guid" value="{MEI_ID}" />
			<attribute id="Name" type="LSString" value="INVOKER_METEOR_PositionEffect" />
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
    with open(os.path.join(B.OUT_DIR, "mei_INVOKER_METEOR_POSITION.lsx"), "w", encoding="utf-8") as f:
        f.write(text)


def main():
    root = copy.deepcopy(B.xml(IMPACT))
    bounds = copy.deepcopy(next(c for c in root.iter("component") if c.get("class") == "BoundingSphere"))
    comps = fall_components() + impact_components()
    duration = round(max(float(c.get("end")) for c in comps) + 0.1, 3)

    for child in list(root.find("phases")):
        root.find("phases").remove(child)
    tgs = root.find("trackgroups")
    for tg in list(tgs):
        tgs.remove(tg)
    prev = ET.SubElement(tgs, "trackgroup", name="Preview only (muted)")
    ET.SubElement(ET.SubElement(prev, "ids"), "id", value="1")
    for m in preview_models(duration):
        ET.SubElement(prev, "track", name="Track", muted="True", locked="False", mutestateoverride="Unmuted").append(m)
    bounds.set("instancename", str(uuid.uuid5(B.NS, "meteor_bounds")))
    E.retime(bounds, 0, duration)
    B.set_value(bounds, "ba2ee0f9", 18)
    tg = ET.SubElement(tgs, "trackgroup", name="Invoker Chaos Meteor")
    ET.SubElement(ET.SubElement(tg, "ids"), "id", value="2")
    for c in [bounds] + comps:
        ET.SubElement(tg, "track", name="Track", muted="False", locked="False", mutestateoverride="None").append(c)

    out = os.path.join(B.OUT_DIR, NAME + ".lsefx")
    ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=True)
    deps = E.material_guids(comps)
    write_bank(duration, deps)
    write_mei()
    if os.path.isdir(B.PREVIEW_DIR):
        shutil.copy2(out, B.PREVIEW_DIR)
    print(f"{NAME}: {len(FALL_LAYERS)} fall layers + {len(comps) - len(FALL_LAYERS)} impact/scorch components, "
          f"duration {duration:g}s, {len(deps)} dependencies; MEI {MEI_ID}")


if __name__ == "__main__":
    main()
