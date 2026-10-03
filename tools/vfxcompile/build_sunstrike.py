"""Generate the Dota-style Sun Strike effects + projectile template for INVOKER_SUNSTRIKE (SpellType ProjectileStrike).

Look (user 2026-10-02: "Dota-style sunbeam" with a REAL delay):
  warning  (PositionEffect, plays at the target spot on Cast)  a plain gold ring (Moonbeam's ring decal), a converging circle and
           a soft glow on the ground, and the Blood of Lathander cutscene's sunlight shafts standing over the spot.
  streak   (projectile TrailFX)  a white-gold point of light streaks straight down from the sky, leaving a line of light.
  impact   (projectile ImpactFX)  a towering column of sunlight (vanilla VFX_Script_SunBeam_01 downward-energy cylinders,
           sparks, light; played slower and brighter) plus Flame Strike's impact flash, ring, refraction, scorch, camera
           shake and impact sound.
The projectile falls from straight above (spell Height/Angle 0), so the damage lands when the beam hits, ~1 s after
the cast, the way Dota's Sun Strike detonates after its warning.

Writes vfx_src/: VFX_Invoker_SunStrike_{Warn,Streak,Impact}_01.lsefx + bank_*.lsx + mei_INVOKER_SUNSTRIKE_WARN.lsx, and
the projectile RootTemplate into roottemplate_src/merged.lsx (between SUNSTRIKE PROJECTILE markers). repack.ps1 compiles.
Usage: python build_sunstrike.py
"""
import copy
import os
import shutil
import sys
import uuid
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_orb as B  # noqa: E402
import build_emp as E  # noqa: E402
import build_meteor as MT  # noqa: E402  (write_bank, projectile template layout)

FX = B.MODS + r"\Shared\Assets\Effects"
MOONBEAM_AURA = FX + r"\Status\VFX_Status_MoonBeam_Aura_01.lsefx"                       # plain ring + glow disc decals
BUFF_ROOT = FX + r"\Spells\Cast\Intent\Buff\VFX_Spells_Cast_Intent_Buff_TargetSingle_Impact_Root_01.lsefx"  # converging circle
SUNBEAM_SPELL = (B.MODS + r"\SharedDev\Assets\Effects\Spells\Cast\Damage\Radiant"
                 r"\VFX_Spells_Cast_Damage_Radiant_Sunbeam_CastFX_Textkey_01.lsefx")   # Sunbeam spell beam (looked wrong upright)
LATHANDER_BEAM = (B.MODS + r"\SharedDev\Assets\Effects\Cinematic\VFX_Cinematic_CRE_BloodOfLathander_Beam_01.lsefx")  # sunlight shafts
SUNBEAM = FX + r"\Script\VFX_Script_SunBeam_01.lsefx"
FLAMESTRIKE = FX + r"\Projectiles\VFX_Projectiles_Damage_Radiant_FlameStrike_Impact_01.lsefx"
FLAMESTRIKE_SOUND = FX + r"\Projectiles\VFX_Projectiles_Damage_Radiant_FlameStrike_Impact_Sound_01.lsefx"
SUNLIGHT_HUM = FX + r"\Script\VFX_Script_Sunlight_Beam_Thick_01.lsefx"   # sunlight-beam hum (Enter loop / Leave _Stop)

WARN_NAME = "VFX_Invoker_SunStrike_Warn_01"
STREAK_NAME = "VFX_Invoker_SunStrike_Streak_01"
IMPACT_NAME = "VFX_Invoker_SunStrike_Impact_01"
WARN_RES = str(uuid.uuid5(B.NS, "sunstrike_warn_resource"))
STREAK_RES = str(uuid.uuid5(B.NS, "sunstrike_streak_resource"))
IMPACT_RES = str(uuid.uuid5(B.NS, "sunstrike_impact_resource"))
WARN_MEI = str(uuid.uuid5(B.NS, "sunstrike_warn_mei"))
WARN_INFO = str(uuid.uuid5(B.NS, "sunstrike_warn_effectinfo"))
PROJ_ID = str(uuid.uuid5(B.NS, "sunstrike_projectile"))
PROJ_NAME = "INVOKER_Projectile_SunStrike"

# Timing (2026-10-03): roofs caught the 30 m sky projectile (no explosion, no damage). The invisible projectile now starts only
# HEIGHT metres above the target and crawls down in ~WARN_TIME, so the strike also works indoors.
HEIGHT = 3
PROJ_INITIAL_SPEED = 3.0     # m/s (slowest vanilla projectile templates: 4-5 m/s)
PROJ_ACCEL = 3.0
PROJ_SPEED = 3.0
WARN_TIME = 1.0              # expected fall time; the sigil's second flare is lined up with it

AREA_RADIUS = 2.0            # INVOKER_SUNSTRIKE AreaRadius
GOLD = (255, 196, 80)
WHITE_GOLD = (255, 236, 180)
RING_DIAMETER = 4.6          # plain gold ring: its edge sits just outside the 2 m damage radius
DISC_DIAMETER = 4.4          # soft gold glow inside the ring, brightening toward the hit
CONVERGE_DIAMETER = 7.0      # converging circle that closes in during the warning
WARN_BEAM_WIDTH = 0.04       # pinpoint-thin warning column (user 2026-10-02; was 0.25) - thickness vs the vanilla sunbeam cylinders (impact uses full width)
WARN_BEAM_LENGTH = 1.0       # multiplier on their length (Axis Scale Y)
WARN_BEAM_BRIGHT = 5.0       # brightness multiplier on the warning column (user: brighter; was 1)
RAY_UP_DEGREES = -90.0       # Initial Rotation Y that tips the shafts upright; flip the sign if they point down
BEAM_WIDTH = 1.0             # multiplier on the sunbeam cylinders' width (vanilla ~2.75 m radius vs our 2 m damage radius)
BEAM_STRETCH = 1.6           # sunbeam plays this much slower (vanilla: 1 s)
BEAM_BRIGHT = 1.8
COLOR_PROPS = dict(E.COLOR_PROPS, Model=("4dd77ddd",))
E.MATERIAL_PROPS = E.MATERIAL_PROPS + ("3cc17729", "83f4fce2")   # Sound Resume / Leave events are dependencies too


def gold_tint(c, rgb=GOLD):
    for pid in COLOR_PROPS.get(c.get("class"), ()):
        if E.has_prop(c, pid):
            E.tint(c, pid, rgb)


def stretch_time(c, k, offset=0.0):
    s, e = float(c.get("start")), float(c.get("end"))
    E.retime(c, offset + s * k, offset + e * k)
    if c.get("class") == "ParticleSystem" and E.has_prop(c, "352fac77"):
        E.scale_ramp(c, "352fac77", k)


def vanilla_components(path, skip=("BoundingSphere",)):
    for tr in B.xml(path).iter("track"):
        c = tr.find("component")
        if c is None or tr.get("muted") == "True" or c.get("class") in skip:
            continue
        yield copy.deepcopy(c)


def _find(path, cls, name):
    for c in vanilla_components(path):
        if c.get("class") == cls and E.comp_name(c) == name:
            return c
    raise KeyError((path, name))


def _decal(path, name, tag, diameter, rgb, bright, alpha, end):
    """Re-time a vanilla ground decal to 0..end: Dimensions, gold colour, Brightness and the Dynamic Value W fade envelope."""
    c = _find(path, "Decal", name)
    B.set_ramp(c, "3fb4512b", [B.const(diameter), B.const(diameter)])
    E.tint(c, "2c9b4a60", rgb)
    B.set_ramp(c, "590ace0d", [bright])
    dyn = [[(k.get("time"), k.get("value")) for k in ch.iter("keyframe")] for ch in B.prop(c, "85d7b13f").iter("rampchannel")]
    B.set_ramp(c, "85d7b13f", [[(float(t), float(v)) for t, v in ch] for ch in dyn[:3]] + [alpha])
    E.retime(c, 0, end)
    c.set("instancename", str(uuid.uuid5(B.NS, f"sunstrike_warn_{tag}")))
    return c


def warn_beam(end):
    """Warning beam = the downward-energy cylinders of vanilla VFX_Script_SunBeam_01 (Capless_Cylinder_Downward_Energy
    07/08/07_B; built upright with the energy flowing down, so no rotation), made thin and gold, brightening to the hit.
    (The Blood of Lathander ray meshes only render pointing up - flipping them made them vanish, 2026-10-02.)"""
    hit = WARN_TIME / end
    out = []
    for c in vanilla_components(SUNBEAM):
        if c.get("class") != "Model":
            continue
        ch = list(B.prop(c, "2bea542b").iter("rampchannel"))
        for i in (0, 2):                                         # X and Z = thickness; Y (height) and Offset stay vanilla
            for kf in ch[i].iter("keyframe"):
                kf.set("value", f"{float(kf.get('value')) * WARN_BEAM_WIDTH:.6g}")
        peak = 1.0                                               # full opacity (vanilla peaks 0.3-0.75: too faint when pinpoint-thin)
        B.set_ramp(c, "00910be4", [[(0, 0.0), (0.25, peak * 0.5), (hit, peak), (1, 0.0)]])   # fade in, strongest at the hit
        if E.has_prop(c, "6cbb9e51"):
            E.scale_ramp(c, "6cbb9e51", WARN_BEAM_BRIGHT)
        E.tint(c, "4dd77ddd", GOLD)
        E.retime(c, 0, end)
        c.set("instancename", str(uuid.uuid5(B.NS, f"sunstrike_warn_column_{E.comp_name(c)}")))
        out.append(c)
    assert len(out) == 3, [E.comp_name(c) for c in out]
    return out


# Sounds picked by the user from the sound sampler (tools/vfxcompile/build_sound_sampler.py, 2026-10-02): #06 buzz, #16 blast.
WARN_SOUND = ("CRE_BloodOfLathander_GyroCrystalLaser_Loop <70062e1d-24ec-4a01-8b13-8aaaafb6427d>",
              "CRE_BloodOfLathander_GyroCrystalLaser_Loop_Stop <30e779ab-86b3-4f15-9061-f3b2782adc1f>")
BLAST_SOUND = "CrSpell_Impact_Nightsong_LunarSmite <d9b50700-2264-42ae-aaee-27e064d07c76>"
# Effect Sound components have no volume setting (gain lives in the Wwise events), so loudness is raised by LAYERING: each Sun
# Strike sound plays SOUND_LAYERS times at once (2 ~= +3..6 dB, user asked +40%). If Wwise caps instances per event, extra layers do nothing.
SOUND_LAYERS = 2


def _sound(tag, enter, leave, start, end):
    c = _find(SUNLIGHT_HUM, "Sound", "Sound")              # vanilla Sound component used as the template
    B.set_value(c, "d9c8f8f4", enter)                       # Enter
    B.set_value(c, "3cc17729", enter)                       # Resume
    B.set_value(c, "83f4fce2", leave or "")                 # Leave
    E.retime(c, start, end)
    c.set("instancename", str(uuid.uuid5(B.NS, f"sunstrike_{tag}")))
    return c


def warn_hum():
    """Aiming buzz: the Blood of Lathander crystal laser loop from the cast until the strike lands (Leave = its _Stop tail)."""
    return [_sound(f"warn_hum{'' if i == 0 else i}", WARN_SOUND[0], WARN_SOUND[1], 0, WARN_TIME) for i in range(SOUND_LAYERS)]


def warn_components():
    """Dota-style warning: a plain gold ring, a converging circle and a soft glow on the ground, and Sunbeam's beam of
    light standing over the spot - all building up until the strike lands (~WARN_TIME)."""
    end = WARN_TIME + 0.25
    hit = WARN_TIME / end
    return [
        _decal(MOONBEAM_AURA, "Spike_Slow", "ring", RING_DIAMETER, GOLD,
               [(0, 2.0), (hit * 0.9, 12.0), (hit, 25.0), (1, 2.0)], [(0, 0.0), (0.12, 0.8), (hit, 0.9), (1, 0.0)], end),
        _decal(MOONBEAM_AURA, "Glow_Center", "disc", DISC_DIAMETER, GOLD,
               [(0, 0.5), (hit, 4.0), (1, 1.0)], [(0, 0.0), (hit, 1.0), (1, 0.0)], end),
        _decal(BUFF_ROOT, "CircleGoingIn_01", "converge", CONVERGE_DIAMETER, WHITE_GOLD,
               [(0, 3.0), (hit, 15.0), (1, 1.0)], [(0, 0.0), (0.1, 1.0), (hit, 1.0), (1, 0.0)], WARN_TIME),
    ] + warn_beam(end) + warn_hum()


STREAK_LEAD_IN, STREAK_LOOP, STREAK_LEAD_OUT = 0.05, 1.0, 0.4


def streak_components(duration):
    """A white-gold star falling straight down, leaving a short line of light in the air (space 2 = left behind)."""
    glow_base = [c for c in B.xml(B.BASE).iter("component") if c.get("class") == "ParticleSystem"][1]
    br = lambda v: v / B.BRIGHT
    sz = lambda v: tuple(x / B.SIZE for x in v) if isinstance(v, tuple) else v / B.SIZE
    layers = [
        B.layer("halo", "glow", B.argb(255, *GOLD), br(4.0), sz(2.2), 0.12, 50, 12, alpha=[(0, 0.8), (1, 0)]),
        B.layer("core", "glow", B.argb(255, 255, 250, 230), br(12.0), sz(0.8), 0.1, 60, 12, alpha=[(0, 1), (1, 0.6)]),
        B.layer("line", "glow", B.argb(255, *WHITE_GOLD), br(8.0), sz(0.55), 0.3, 160, 80, alpha=[(0, 0.9), (1, 0)], space=2),
        B.layer("motes", "glow", B.argb(255, *GOLD), br(6.0), sz((0.06, 0.12)), (0.4, 0.8), 60, 50, alpha=[(0, 1), (1, 0)],
                velocity=("0,1,0", 180, 0.3, 1.2), space=2),
    ]
    out = []
    for L in layers:
        c = B.make_emitter(glow_base, "sunstrike", dict(column=0, slot=2, phase=0), L, duration)
        B.set_ramp(c, B.P["kf_offset"], [[(0, 0.0), (1, 0.0)]] * 3)
        c.set("instancename", str(uuid.uuid5(B.NS, f"sunstrike_streak_{L['name']}")))
        out.append(c)
    return out


def impact_components():
    out = []
    for c in vanilla_components(SUNBEAM):                       # the column of sunlight
        cls = c.get("class")
        if cls == "Model" and BEAM_WIDTH != 1.0:
            ch = list(B.prop(c, "2bea542b").iter("rampchannel"))
            for i in (0, 2):                                    # X and Z width, keep Y (height)
                for kf in ch[i].iter("keyframe"):
                    kf.set("value", f"{float(kf.get('value')) * BEAM_WIDTH:.6g}")
        if cls == "Model" and E.has_prop(c, "6cbb9e51"):
            E.scale_ramp(c, "6cbb9e51", BEAM_BRIGHT)
        if cls == "ParticleSystem" and E.has_prop(c, "7b01f163"):
            E.scale_ramp(c, "7b01f163", BEAM_BRIGHT)
        stretch_time(c, BEAM_STRETCH)
        c.set("instancename", str(uuid.uuid5(B.NS, f"sunstrike_beam_{len(out)}_{cls}_{E.comp_name(c)}")))
        out.append(c)
    for c in vanilla_components(FLAMESTRIKE):                   # flash, ring, refraction, scorch, shake
        c.set("instancename", str(uuid.uuid5(B.NS, f"sunstrike_flash_{len(out)}_{c.get('class')}_{E.comp_name(c)}")))
        out.append(c)
    out += [_sound(f"blast{'' if i == 0 else i}", BLAST_SOUND, None, 0, 3.0) for i in range(SOUND_LAYERS)]   # strike blast: Nightsong's lunar smite (was Flame Strike's impact)
    return out


def preview(duration, tag):
    out = []
    for m in E.preview_models(duration):
        m = copy.deepcopy(m)
        if "edge" in m.get("instancename", "") or B.get_value(m, B.P["model_pos"]).startswith(f"{E.AREA_RADIUS:g}"):
            B.set_value(m, B.P["model_pos"], f"{AREA_RADIUS:g},0,0")
        m.set("instancename", str(uuid.uuid5(B.NS, f"sunstrike_preview_{tag}_{len(out)}")))
        out.append(m)
    return out


def write_effect(name, tag, comps, duration, phases=None):
    root = copy.deepcopy(B.xml(B.BASE))
    ph = root.find("phases")
    for child in list(ph):
        ph.remove(child)
    for defid, dur, count in (phases or ()):
        obj = ET.SubElement(ph, "object", {"class": "", "classid": "00000000-0000-0000-0000-000000000000", "assembly": ""})
        ET.SubElement(obj, "data", id=str(uuid.uuid5(B.NS, f"sunstrike_{tag}_phase_{defid}")), duration=f"{dur:g}",
                      playcount=str(count), definitionid=defid)
    bounds = copy.deepcopy(next(c for c in B.xml(SUNBEAM).iter("component") if c.get("class") == "BoundingSphere"))
    bounds.set("instancename", str(uuid.uuid5(B.NS, f"sunstrike_{tag}_bounds")))
    E.retime(bounds, 0, duration)
    B.set_value(bounds, "ba2ee0f9", 32)
    tgs = root.find("trackgroups")
    for tg in list(tgs):
        tgs.remove(tg)
    prev = ET.SubElement(tgs, "trackgroup", name="Preview only (muted)")
    ET.SubElement(ET.SubElement(prev, "ids"), "id", value="1")
    for m in preview(duration, tag):
        ET.SubElement(prev, "track", name="Track", muted="True", locked="False", mutestateoverride="Unmuted").append(m)
    tg = ET.SubElement(tgs, "trackgroup", name=f"Invoker Sun Strike {tag}")
    ET.SubElement(ET.SubElement(tg, "ids"), "id", value="2")
    for c in [bounds] + comps:
        ET.SubElement(tg, "track", name="Track", muted="False", locked="False", mutestateoverride="None").append(c)
    out = os.path.join(B.OUT_DIR, name + ".lsefx")
    ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=True)
    if os.path.isdir(B.PREVIEW_DIR):
        shutil.copy2(out, B.PREVIEW_DIR)
    return E.material_guids(comps)


def write_warn_mei():
    text = f"""<?xml version="1.0" encoding="utf-8"?>
<!-- GENERATED by tools/vfxcompile/build_sunstrike.py - do not edit by hand -->
<save>
	<version major="4" minor="0" revision="7" build="200" lslib_meta="v1,bswap_guids,lsf_keys_adjacency" />
	<region id="MultiEffectInfos">
		<node id="MultiEffectInfos">
			<attribute id="UUID" type="guid" value="{WARN_MEI}" />
			<attribute id="Name" type="LSString" value="INVOKER_SUNSTRIKE_PositionEffect" />
			<children>
				<node id="EffectInfo">
					<attribute id="UUID" type="guid" value="{WARN_INFO}" />
					<attribute id="EffectResourceGuid" type="guid" value="{WARN_RES}" />
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
    with open(os.path.join(B.OUT_DIR, "mei_INVOKER_SUNSTRIKE_WARN.lsx"), "w", encoding="utf-8") as f:
        f.write(text)


def write_projectile_template():
    node = f"""                <node id="GameObjects">
					<attribute id="Acceleration" type="float" value="{PROJ_ACCEL:g}" />
					<attribute id="CameraOffset" type="fvec3" value="0 0 0" />
					<attribute id="CastBone" type="FixedString" value="Dummy_CastFX" />
					<attribute id="Flag" type="int32" value="0" />
					<attribute id="GroupID" type="uint32" value="0" />
					<attribute id="HasGameplayValue" type="bool" value="False" />
					<attribute id="ImpactFX" type="FixedString" value="{IMPACT_NAME}" />
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
    begin, end = "<!-- SUNSTRIKE PROJECTILE BEGIN (generated) -->\n", "<!-- SUNSTRIKE PROJECTILE END -->\n"
    s = open(MT.ROOT_TEMPLATES, encoding="utf-8", newline="").read().replace("\r\n", "\n")
    if begin in s:
        s = s[:s.index(begin)] + s[s.index(end) + len(end):]
    close = s.rfind("</children>", 0, s.rfind("</region>"))
    close = s.rfind("\n", 0, close) + 1
    s = s[:close] + begin + node + end + s[close:]
    with open(MT.ROOT_TEMPLATES, "w", encoding="utf-8", newline="") as f:
        f.write(s)


def main():
    comps = warn_components()
    d = round(max(float(c.get("end")) for c in comps) + 0.1, 3)
    deps = write_effect(WARN_NAME, "warn", comps, d)
    MT.write_bank(WARN_NAME, WARN_RES, d, deps, False)
    write_warn_mei()
    print(f"{WARN_NAME}: {len(comps)} components, {d:g}s, {len(deps)} deps; MEI {WARN_MEI}")

    d = STREAK_LEAD_IN + STREAK_LOOP + STREAK_LEAD_OUT
    comps = streak_components(d)
    deps = write_effect(STREAK_NAME, "streak", comps, d,
                        zip(B.PHASE_DEFS, (STREAK_LEAD_IN, STREAK_LOOP, STREAK_LEAD_OUT), (1, -1, 1)))
    MT.write_bank(STREAK_NAME, STREAK_RES, d, deps, True)
    print(f"{STREAK_NAME}: {len(comps)} components, {d:g}s looping, {len(deps)} deps")

    comps = impact_components()
    d = round(max(float(c.get("end")) for c in comps) + 0.1, 3)
    deps = write_effect(IMPACT_NAME, "impact", comps, d)
    MT.write_bank(IMPACT_NAME, IMPACT_RES, d, deps, False)
    print(f"{IMPACT_NAME}: {len(comps)} components, {d:g}s, {len(deps)} deps")

    write_projectile_template()
    print(f"projectile template {PROJ_NAME} {PROJ_ID}")


if __name__ == "__main__":
    main()
