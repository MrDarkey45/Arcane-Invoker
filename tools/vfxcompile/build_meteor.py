"""Generate the Chaos Meteor effects + projectile template for INVOKER_METEOR (SpellType ProjectileStrike).

The meteor is a real projectile: the engine drops it from the sky (spell Height/Angle, template speeds) and applies the
damage when it lands, so damage and impact are in sync. This script writes:
  VFX_Invoker_Meteor_Head_01    looping TrailFX carried by the projectile: Produce Flame shader flame + hell-red glows + core at
                                the origin, world-space trails (Fire_Burst flames, smoke, embers) left behind, fall whoosh sound.
  VFX_Invoker_Meteor_Impact_01  one-shot ImpactFX: vanilla's Tutorial Meteor impact (scaled by K_IMPACT), 3 flame plumes,
                                impact sounds, ground scorch decal.
  roottemplate_src/merged.lsx   projectile RootTemplate INVOKER_Projectile_ChaosMeteor (between the METEOR PROJECTILE markers).
into vfx_src/ (+ bank_*.lsx; repack.ps1 compiles them) and copies the .lsefx files to the Toolkit project for preview.
Usage: python build_meteor.py
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

TRAIL = B.MODS + r"\Shared\Assets\Effects\Projectiles\VFX_Projectiles_Tutorial_Meteor_01.lsefx"
SPHERE_RAM = B.MODS + (r"\Shared\Assets\Effects\Actions\Prepare\Damage\Fire"
                       r"\VFX_Actions_Prepare_Damage_Fire_TargetTouch_FlamingSphere_Ram_01.lsefx")
ROCK_MESH = "SPHERE_Flame_A_Boulder_A <56459e45-45d4-4c72-0b71-26f8b64c7a9a>"   # the Flaming Sphere's boulder (vanilla)
ROCK_MESH_DIAMETER = 1.4    # metres at scale 1 (vanilla offsets it by -0.7 = its radius; pivot is at the bottom)
ROCK_DIAMETER = 4.8         # metres: the solid rock inside the 12 m fireball (opaque, so smaller than the flames around it)
ROCK_RPM = (0.0, 20.0, 0.0)  # spin about the vertical axis only: the mesh pivot is at its bottom, so X/Z spin would swing the rock around

DEBRIS = B.MODS + r"\Shared\Assets\Effects\Script\VFX_Script_Chapel_Outside_Boulder_Impact_Floor_01.lsefx"
CHUNKS = [  # rock chunks thrown out when the meteor shatters (clones of the chapel boulder's "Stones" layer, mesh VFX_Static_Rock_01)
    # tag, count (min,max), size multiplier (vanilla 0.01-0.1), speed multiplier (vanilla 4-6 m/s)
    ("huge", (5, 7), 11.0, 1.0),      # the boulder itself breaking apart: a few heavy slabs that barely leave the crater
    ("big", (10, 14), 7.0, 1.8),
    ("small", (35, 45), 3.0, 2.4),
]

HEAD_NAME = "VFX_Invoker_Meteor_Head_01"        # looping trail effect carried by the projectile (TrailFX)
IMPACT_NAME = "VFX_Invoker_Meteor_Impact_01"    # one-shot effect played where it lands (ImpactFX)
OLD_FILES = ("VFX_Invoker_Meteor_01.lsefx", "bank_VFX_Invoker_Meteor_01.lsx")
MEI_ID = str(uuid.uuid5(B.NS, "meteor_mei"))              # position effect on INVOKER_METEOR (the visual-only falling boulder)
INFO_ID = str(uuid.uuid5(B.NS, "meteor_effectinfo"))
KF_MODEL = B.MODS + r"\Shared\Assets\Effects\Actions\Cast\Common\VFX_Actions_Cast_Common_Impact_Overlay_01.lsefx"   # a Model with Keyframed Position
KF_MODEL_MODULE = "7a790ae7-3b1c-463e-bb1f-5cc14980b78c"   # Model module "Keyframed Position" (property 37b047c1)
HEAD_RES = str(uuid.uuid5(B.NS, "meteor_head_resource"))
IMPACT_RES = str(uuid.uuid5(B.NS, "meteor_impact_resource"))
PROJ_ID = str(uuid.uuid5(B.NS, "meteor_projectile"))      # projectile RootTemplate (INVOKER_METEOR Template/Trajectories)
PROJ_NAME = "INVOKER_Projectile_ChaosMeteor"
ROOT_TEMPLATES = os.path.join(B.ROOT, "roottemplate_src", "merged.lsx")

# SPLIT (2026-10-03): roofs caught the sky projectile, so the spell only worked outdoors. Now the DAMAGE is carried by an invisible
# projectile that starts PROJ_HEIGHT above the target and takes ~FALL_TIME to reach it (fits under ceilings), and the burning
# boulder is a pure visual: a position effect that flies a keyframed path START -> END in FALL_TIME and passes through roofs.
# The impact effect is still the projectile's ImpactFX, so the explosion is always in sync with the damage.
PROJ_HEIGHT = 3             # INVOKER_METEOR Height (Angle 0)
PROJ_INITIAL_SPEED = 3.0    # m/s -> ~1 s for 3 m (slowest vanilla projectile templates: 4-5 m/s)
PROJ_SPEED = 3.0
PROJ_ACCEL = 3.0
FALL_TIME = 1.0                                       # seconds the boulder falls = the invisible damage projectile's flight (Height 3 / speed 3), so it slams down exactly as the ImpactFX explosion + damage land
# ROLL (2026-10-03, Dota-style): after landing the boulder keeps going along the ground in the direction it fell (+Z of the
# effect), burning, for ROLL_DISTANCE over ROLL_TIME, then bursts apart (the fire-summon death effect + rock chunks + dust) and is
# gone at once. Visual only: no collision, damage stays at the landing spot.
# NOTE the Hell/Flaming Sphere's own break-up (visual SPHERE_Flame_A_Boulder_A_Explode e62dc35a, template Unique_HellSphere_Destruct
# dd2a2d77) is a PHYSICS simulation on a creature, not a baked animation, so an effect cannot replay it - the burst here imitates it.
ROLL_DISTANCE = 0.0         # 2026-10-03: roll dropped (see memory meteor-roll-shelved) - the boulder no longer travels; it lands and explodes
ROLL_TIME = 0.0            # no dwell: the boulder shatters the instant it lands, synced to the explosion (roll shelved, see memory meteor-roll-shelved)
ROLL_SPIN = 0.55            # boulder tumble speed while rolling (rotations/sec); flip sign to tumble the other way
ROLL_DEG = -360             # degrees the boulder rolls over the whole roll (about the axle); flip the sign to roll the other way
ROLL_VEL_AXIS = "0,0,-1"    # roll travel direction (effect space): -Z = away from the caster (was +Z, which rolled toward the player)
BURST_TAIL = 2.4            # seconds the break-up particles need after the burst
ROCK_R = ROCK_DIAMETER / 2
START = (0.0, 19.0, 12.5)   # the boulder appears on the caster side (+Z) and falls toward -Z, so it keeps going away as it rolls
END = (0.0, ROCK_R, 0.0)    # landing: the boulder's centre, resting on the ground
ROLL_END = (0.0, ROCK_R, -ROLL_DISTANCE)
T_END = FALL_TIME + ROLL_TIME          # the moment it bursts
DEATH_FX = B.MODS + r"\Shared\Assets\Effects\Combat\VFX_Combat_Death_SummonFire_Lifetime_BodyFX_01.lsefx"   # Flaming/Hell Sphere death burst
DEATH_T0 = 0.35             # the vanilla death effect bursts 0.35 s in
SPHERE_DIAMETER = 1.5       # the vanilla sphere that effect was made for

AREA_RADIUS = 3.0           # INVOKER_METEOR AreaRadius / ExplodeRadius
FALL = 0.0                  # impact effect starts at t=0 (it is played by the projectile when it lands)
K_IMPACT = 0.9                            # vanilla impact at its native size (20 m glow rings); was 0.4 -> 0.65 (user: "so small", wants a stronger landing)
HEAD_DIAMETER = 6.8                  # metres, the visible rock (user 2026-10-02: "maybe 50m"). Glow quad is ~3x its visible core; 3.5 reads ~4 m wide
FALL_SCALE = 3.5 * HEAD_DIAMETER / 4.0   # multiplies every falling head/trail layer size (3.5 -> ~4 m, 43.75 -> ~50 m)
SCORCH_SIZE = 10.0          # metres (vanilla 3.9; was 5.5 -> 8)
SCORCH_SECONDS = 6.0
SHAKE = 1.7                                  # camera-shake strength multiplier (user 2026-10-03: impact felt bleak)
CAM_SHAKE_SECS = 0.45               # how long the ground rumble lasts (vanilla ~0.4)

SCALE_PROPS = {"ParticleSystem": ("02e6012f", "79ab5e9c", "b0e13a65", "f0d3e3dd"),   # scale, velocity, emitter radii
               "Billboard": ("04696f8f",), "Model": ("f80eefa7",), "Light": ("ba116247",)}
DROP_CLASSES = set()          # the vanilla impact Sound component is KEPT now (dropping it was why the impact was silent)
E.MATERIAL_PROPS = E.MATERIAL_PROPS + ("15864e49", "d15b1af4", "d9c8f8f4")   # Model meshes + Light template + Sound resource UUIDs are dependencies too


def sc(v):          # layer() scale/brightness get multiplied by build_orb's SIZE / BRIGHT; undo that for absolute values
    k = FALL_SCALE / B.SIZE
    return tuple(x * k for x in v) if isinstance(v, tuple) else v * k


TRAIL_SCALE = 0.5            # trail layers (flames/smoke/embers) are this fraction of the rock's scale factor (user: trails looked huge)


def st(v):         # like sc() but for the trail layers
    return tuple(x * TRAIL_SCALE for x in sc(v)) if isinstance(v, tuple) else v * TRAIL_SCALE * sc(1.0)


def br(v):
    return v / B.BRIGHT


def _head_fade(d):          # (fade-in end, burst) as fractions of the effect's duration: the fire burns until the boulder breaks up
    return 0.08 / d, T_END / d


def path_pos(t):
    """Boulder centre at time t (s): ease-in fall START -> END, then a decelerating roll END -> ROLL_END, then rest."""
    if t >= FALL_TIME:
        return END                                       # rests at the landing point (no roll)
    f = (t / FALL_TIME) ** 1.6                            # ease-in: accelerates as it falls
    return tuple(x + f * (y - x) for x, y in zip(START, END))


def path_keys(d):
    """Keyframes of path_pos over a component that lives d seconds (times normalised over d)."""
    n = max(int(round(d / 0.04)), 2)
    chans = ([], [], [])
    for i in range(n + 1):
        t = d * i / n
        for lst, v in zip(chans, path_pos(t)):
            lst.append((round(i / n, 5), round(v, 4)))
    return list(chans)


def place(c, pos, k=1.0):
    """Move a cloned particle layer to pos (its own offset is scaled by k first); adds the Position module if missing."""
    x, y, z = (float(v) * k for v in B.get_value(c, B.P["offset"]).split(","))
    B.set_value(c, B.P["offset"], f"{x + pos[0]:g},{y + pos[1]:g},{z + pos[2]:g}")
    ml = c.find("modules")
    if not any(m.get("id").lower() == B.M["position"] for m in ml):
        ET.SubElement(ml, "module", id=B.M["position"], muted="False", index=str(len(ml)))


FLAME_OV = {  # Produce Flame persistent flame: fade in over the Lead In, hold through the Loop (the flight), fade out after
    "bb1e9c04": lambda d: [[(0, 16777215), (_head_fade(d)[0], -1), (_head_fade(d)[1], -1), (1, 16777215)]],
    "1dc673ff": lambda d: [[(0, 1.0), (_head_fade(d)[0], 5.0), (_head_fade(d)[1], 5.0), (1, 1.0)]],
    "9984af4f": [[(0, 1.6 * FALL_SCALE), (1, 1.6 * FALL_SCALE)]],
    "b7f89b82": [[(0, 0.55), (1, 0.55)], [(0, 1.0), (1, 1.0)], [(0, 1.0), (1, 1.0)]],
}

FALL_LAYERS = [
    # name, spec. Trails are released into the world (space 2) so they hang in the air behind the moving head.
    B.layer("trail_smoke", "dust", B.argb(255, 70, 46, 32), br(0.9), st((1.0, 1.8)), (1.5, 2.5), 30, 50,
            alpha=[(0, 0.5), (1, 0)], spin=(0.05, 0.15), velocity=("0,1,0", 25, 0.2, 0.5), space=2),
    B.layer("trail_fire", scale=st((0.9, 1.4)), life=(2.25, 3.6), rate=30, max_count=40, space=2,
            clone=(B.MYRMIDON_FIRE, "Fire_Burst_02"),
            ov={"068cf735": [[(0, 0.1), (1, 0.1)]], "16f5adbb": [[(0, 0.06), (1, 0.06)]],
                "24fffa5e": [[(0, 0.1), (1, 0.1)]], "79ab5e9c": [[(0, 0.1), (1, 0.1)], [(0, 0.3), (1, 0.3)]]}),
    B.layer("head_aura", "glow", B.argb(255, 255, 45, 10), br(3.0), sc(3.2), 0.1, 60, 12, alpha=[(0, 0.8), (1, 0)]),   # hell red
    B.layer("head_halo", "glow", B.argb(255, 140, 15, 5), br(1.6), sc(5.5), 0.12, 40, 10, alpha=[(0, 0.5), (1, 0)]),    # dark red outer glow
    B.layer("head_flame", life=0.5, rate=0, max_count=1, space=1, persistent=True,
            clone=(B.PRODUCE_FLAME, "ProduceFlame_01"), ov=FLAME_OV),
    B.layer("head_core", "glow", B.argb(255, 255, 235, 180), br(6.0), sc(1.3), 0.1, 60, 12, alpha=[(0, 1), (1, 0.6)]),
    B.layer("trail_embers", "glow",
            [(0, B.argb(255, 255, 225, 130)), (0.5, B.argb(255, 255, 120, 30)), (1, B.argb(255, 120, 30, 10))],
            [(0, br(3.0)), (1, br(1.0))], st((0.05, 0.09)), (0.6, 1.2), 80, 80, alpha=[(0, 1), (1, 0)],
            velocity=("0,1,0", 180, 0.3, 1.2), space=2),
    # fire embers thrown off the boulder in every direction while it falls (user 2026-10-03: it "feels naked" without them);
    # released into the world so they hang and drift behind it. Much bigger/faster than trail_embers above.
    B.layer("head_embers", "glow",
            [(0, B.argb(255, 255, 240, 170)), (0.35, B.argb(255, 255, 150, 40)), (1, B.argb(255, 200, 50, 10))],
            [(0, br(6.0)), (0.5, br(4.0)), (1, br(1.5))], st((0.16, 0.38)), (0.5, 1.1), 150, 190,
            alpha=[(0, 1), (0.7, 0.9), (1, 0)], stretch=(0.7, 1.5, 1), velocity=("0,1,0", 180, 2.5, 6.5), space=2),
]


def head_components(duration):
    """The burning head, moved along the falling path by each emitter's Keyframed Offset."""
    glow_base = [c for c in B.xml(B.BASE).iter("component") if c.get("class") == "ParticleSystem"][1]
    el = dict(column=0, slot=2, phase=0)           # dummy: orbit_keys() path is overridden below
    out = []
    for L in FALL_LAYERS:
        c = B.make_emitter(glow_base, "meteor", el, L, duration)
        B.set_ramp(c, B.P["kf_offset"], path_keys(duration))
        c.set("instancename", str(uuid.uuid5(B.NS, f"meteor_fall_{L['name']}")))
        out.append(c)
    return out


def rock_component(duration):
    """The falling boulder (model): vanilla meteor head Model with the Flaming Sphere boulder mesh. Fall only - it tumbles in
    place about the vertical (its offset is on that axis, so no swing) and fades out at the landing; the roll is a separate
    mesh particle (rock_roll_component) because a model can only spin about its base pivot, not its own centre."""
    base = next(c for c in B.xml(TRAIL).iter("component") if c.get("class") == "Model" and E.comp_name(c) == "Projectile_Head")
    c = copy.deepcopy(base)
    k = ROCK_DIAMETER / ROCK_MESH_DIAMETER
    B.set_value(c, "ef1d7d1e", "meteor_rock")
    B.set_value(c, "15864e49", ROCK_MESH)
    B.set_ramp(c, "2bea542b", [B.const(1.0)] * 3)                       # Axis Scale
    B.set_ramp(c, "f80eefa7", [B.const(k)])                             # Uniform Scale
    u_land = FALL_TIME / duration
    B.set_ramp(c, "e5ece95a", [B.const(0.0),
                               [(0, ROCK_RPM[1]), (u_land, ROCK_RPM[1]), (min(u_land + 0.03, 1), 0.0), (1, 0.0)], B.const(0.0)])  # tumble while falling, still on the ground
    B.set_ramp(c, "00910be4", [[(0, 1.0), (u_land, 1.0), (1, 0.0)]])     # solid all the way down, then shatters into the blast over ~0.25s
    if not E.has_prop(c, "47a42cb9"):                                   # Offset lives with the Position module
        src = next(m for m in B.xml(SPHERE_RAM).iter("component") if m.get("class") == "Model" and E.has_prop(m, "47a42cb9"))
        c.find("properties").append(copy.deepcopy(B.prop(src, "47a42cb9")))
    B.set_value(c, "47a42cb9", f"0,{-ROCK_DIAMETER / 2:g},0")          # centre the bottom-pivot mesh on the fireball
    ml = c.find("modules")
    if not any(m.get("id").lower() == B.M["position"] for m in ml):
        ET.SubElement(ml, "module", id=B.M["position"], muted="False", index=str(len(ml)))
    src = next(m for m in B.xml(KF_MODEL).iter("component") if m.get("class") == "Model" and E.has_prop(m, "37b047c1"))
    for pid in ("37b047c1", "7787b338", "94689e2e", "8c59c30a"):       # Keyframed Position + its X/Y/Z modifiers
        if not E.has_prop(c, pid):
            c.find("properties").append(copy.deepcopy(B.prop(src, pid)))
    B.set_ramp(c, "37b047c1", path_keys(duration))                      # flies the fall path
    for pid in ("7787b338", "94689e2e", "8c59c30a"):
        B.set_value(c, pid, 1)
    if not any(m.get("id").lower() == KF_MODEL_MODULE for m in ml):
        ET.SubElement(ml, "module", id=KF_MODEL_MODULE, muted="False", index=str(len(ml)))
    E.retime(c, 0, duration)
    c.set("instancename", str(uuid.uuid5(B.NS, "meteor_rock")))
    return c


def rock_roll_component():
    """The rolling boulder (mesh PARTICLE, not a model): particles spin about their own centre, so this tumbles like a real
    rock rolling instead of swinging around a bar. One long-lived particle, spawned at the landing spot, carried along the
    ground by its own velocity (ROLL_VEL_AXIS) for ROLL_TIME, tumbling, then gone when the burst fires."""
    base = next(c for c in B.xml(DEBRIS).iter("component") if c.get("class") == "ParticleSystem" and E.comp_name(c) == "Stones")
    c = copy.deepcopy(base)
    k = ROCK_DIAMETER / ROCK_MESH_DIAMETER
    B.set_value(c, "ef1d7d1e", "meteor_roll")
    B.set_value(c, "9cfd15fe", ROCK_MESH)                               # the same boulder mesh as the falling model (particle Mesh GUID)
    B.set_ramp(c, "02e6012f", [B.const(k), B.const(0)])                 # Uniform Scale (const, no size variation)
    B.set_value(c, B.P["init_count"], "1,1")                            # exactly one boulder
    B.set_value(c, B.P["max_count"], 1)
    B.set_ramp(c, B.P["emit_rate"], [B.const(0)])
    B.set_ramp(c, B.P["emit_stutter"], [B.const(0)])
    B.set_ramp(c, B.P["lifespan"], [B.const(ROLL_TIME), B.const(ROLL_TIME)])
    B.set_value(c, B.P["coord_space"], 2)                               # World (emit local): the particle rides its own velocity
    B.set_value(c, B.P["offset"], f"0,{ROCK_R:g},0")                    # spawn at the landing point, centre at ground+radius
    B.set_value(c, B.P["vel_axis"], ROLL_VEL_AXIS)
    B.set_ramp(c, B.P["vel_angle"], [B.const(0), B.const(0)])
    v = ROLL_DISTANCE / ROLL_TIME
    B.set_ramp(c, B.P["init_vel"], [B.const(v), B.const(v)])
    B.set_ramp(c, B.P["rot_angle"], [B.const(0), B.const(0)])           # no random start angle
    # The base particle spins via "Rotation Rate Over Life", which for a mesh particle turns about a fixed VERTICAL axis
    # (the leftover top). Zero it, and drive the roll with "Rotation Over Life" (ba01543e), which turns about the particle's
    # own normal - and we locked that normal to the axle above - so this is a clean forward roll.
    B.set_ramp(c, "51cb5783", [B.const(0), B.const(0)])                     # kill the base vertical spin
    ml = c.find("modules")
    if not any(m.get("id").lower().startswith("ca00908f") for m in ml):
        ET.SubElement(ml, "module", id="ca00908f-840d-47ed-9dc2-8ab4372ee17c", muted="False", index=str(len(ml)))
    B.set_ramp(c, "ba01543e", [[(0, 0.0), (1, float(ROLL_DEG))]])           # one roll about the locked axle over the particle's life
    # Lock the spin to the horizontal axle ACROSS the path (world X) so it rolls forward instead of spinning like a top.
    # A mesh particle spins about its orientation/axis-lock vector (00951f0a); without this it defaults to a vertical spin.
    for pid, val in (("00951f0a", "1,0,0"),       # Initial Orientation / Axis Lock = the across-path axle
                     ("ba86eab9", 0),             # Use Random Orientation = false (so the lock applies)
                     ("8918e423", 0), ("30c62052", 0),   # Align To Velocity off (would make it spin about the travel line = drill)
                     ("d2019da1", 0)):            # Align To Camera off
        if E.has_prop(c, pid):
            B.set_value(c, pid, val)
    B.set_ramp(c, B.P["alpha"], [[(0, 1.0), (0.9, 1.0), (1, 0.0)]])
    B.set_value(c, "40a5b37b", 0)                                       # Show Emitter off
    E.retime(c, FALL_TIME, T_END)
    c.set("instancename", str(uuid.uuid5(B.NS, "meteor_roll")))
    return c


def chunk_components(t0=None, pos=None, prefix="meteor_chunks"):
    t0 = FALL if t0 is None else t0
    base = next(c for c in B.xml(DEBRIS).iter("component") if c.get("class") == "ParticleSystem" and E.comp_name(c) == "Stones")
    out = []
    for tag, (lo, hi), size, speed in CHUNKS:
        c = copy.deepcopy(base)
        B.set_value(c, "ef1d7d1e", f"{prefix}_{tag}")
        E.scale_ramp(c, "02e6012f", size)                  # Uniform Scale
        E.scale_ramp(c, "79ab5e9c", speed)                 # Initial Velocity
        B.set_value(c, B.P["init_count"], f"{lo},{hi}")
        B.set_value(c, B.P["max_count"], hi)
        B.set_value(c, "40a5b37b", 0)                      # Show Emitter off
        E.retime(c, t0, t0 + 1.0)
        if pos is not None:
            place(c, pos)
        c.set("instancename", str(uuid.uuid5(B.NS, f"{prefix}_{tag}")))
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
            E.retime(c, FALL, FALL + CAM_SHAKE_SECS)       # longer rumble
        E.shift(c, FALL)
        if cls.endswith("Force"):
            E.retime(c, float(c.get("start")), FALL + 3.5)
        if cls == "Sound":
            E.retime(c, FALL, FALL + 4.0)
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


# ---- crumbling (2026-10-03): fragments shed during the fall, a dust burst at the landing, rubble left smoking on the scorch ----
CRUMBLE_RATE = 30            # fragments per second breaking off the falling boulder
CRUMBLE_SIZE = 4.0           # size multiplier on the vanilla stone particles (0.01-0.1)
CRUMBLE_LIFE = (0.5, 0.9)    # seconds a fragment tumbles in the wake
DUST_LAYERS = ("Clouds_Up", "Clouds_Ground_Thick")   # vanilla chapel-boulder dust clouds
DUST_SCALE = 2.6
RUBBLE = [  # x, z, diameter (m) of the rocks left in the crater
    (0.3, -0.2, 1.3), (-1.3, 0.6, 0.9), (1.5, 0.9, 0.8), (0.9, -1.6, 0.7), (-0.8, -1.4, 0.6),
    (-2.2, -0.4, 0.5), (2.3, -0.5, 0.45), (-0.4, 2.0, 0.55),
]
RUBBLE_START, RUBBLE_END = 0.12, 6.0      # seconds after the landing; the rocks fade/shrink away over the last part
RUBBLE_SMOKE = [(0.3, -0.2), (-1.3, 0.6), (1.5, 0.9)]


def crumble_component(duration):
    """Rock fragments shed by the boulder on the way down: the chapel boulder's stone particles, emitted continuously from
    the moving head and released into the world so they tumble behind it."""
    base = next(c for c in B.xml(DEBRIS).iter("component") if c.get("class") == "ParticleSystem" and E.comp_name(c) == "Stones")
    c = copy.deepcopy(base)
    B.set_value(c, "ef1d7d1e", "meteor_crumble")
    E.scale_ramp(c, "02e6012f", CRUMBLE_SIZE)
    E.scale_ramp(c, "79ab5e9c", 0.3)                               # slow drift away from the boulder
    B.set_ramp(c, B.P["vel_angle"], [B.const(180), B.const(0)])     # in every direction
    B.set_ramp(c, B.P["emit_rate"], [B.const(CRUMBLE_RATE)])
    B.set_value(c, B.P["init_count"], "0,0")
    B.set_value(c, B.P["max_count"], int(CRUMBLE_RATE * CRUMBLE_LIFE[1]) + 8)
    B.set_ramp(c, B.P["lifespan"], [B.const(CRUMBLE_LIFE[0]), B.const(CRUMBLE_LIFE[1])])
    B.set_value(c, B.P["coord_space"], 2)
    B.set_value(c, B.P["offset"], "0,0,0")
    B.set_value(c, "40a5b37b", 0)
    E.retime(c, 0, T_END)                                           # sheds through the fall and the roll, until the burst
    B.set_ramp(c, B.P["kf_offset"], path_keys(T_END))
    ml = c.find("modules")
    if not any(m.get("id").lower() == B.M["kf_position"] for m in ml):
        ET.SubElement(ml, "module", id=B.M["kf_position"], muted="False", index=str(len(ml)))
    c.set("instancename", str(uuid.uuid5(B.NS, "meteor_crumble")))
    return c


def dust_components(t0=None, pos=None, prefix="meteor_dust"):
    t0 = FALL if t0 is None else t0
    out = []
    for name in DUST_LAYERS:
        base = next(c for c in B.xml(DEBRIS).iter("component") if c.get("class") == "ParticleSystem" and E.comp_name(c) == name)
        c = copy.deepcopy(base)
        B.set_value(c, "ef1d7d1e", f"{prefix}_{name}")
        E.scale_ramp(c, "02e6012f", DUST_SCALE)
        E.scale_ramp(c, "79ab5e9c", DUST_SCALE)
        B.set_value(c, "40a5b37b", 0)
        E.shift(c, t0)
        if pos is not None:
            place(c, pos)
        c.set("instancename", str(uuid.uuid5(B.NS, f"{prefix}_{name}")))
        out.append(c)
    return out


def burst_components():
    """The boulder breaking apart at the end of its roll: the Flaming/Hell Sphere death burst (flash, flare, flames, sparks)
    scaled up to the boulder, plus rock slabs/chunks, dust, gravity for the pieces and a boom."""
    k = ROCK_DIAMETER / SPHERE_DIAMETER
    out = []
    for tr in B.xml(DEATH_FX).iter("track"):
        c = tr.find("component")
        if c is None or tr.get("muted") == "True" or c.get("class") != "ParticleSystem":
            continue
        c = copy.deepcopy(c)
        for pid in SCALE_PROPS["ParticleSystem"]:
            if E.has_prop(c, pid):
                E.scale_ramp(c, pid, k)
        B.set_value(c, "40a5b37b", 0)
        E.shift(c, T_END - DEATH_T0)
        place(c, ROLL_END, k)
        c.set("instancename", str(uuid.uuid5(B.NS, f"meteor_burst_{len(out)}_{E.comp_name(c)}")))
        out.append(c)
    ground = (ROLL_END[0], 0.0, ROLL_END[2])
    out += chunk_components(T_END, ROLL_END, "meteor_burst_chunks")
    out += dust_components(T_END, ground, "meteor_burst_dust")
    for tr in B.xml(DEBRIS).iter("track"):                 # gravity + ground deflector so the pieces arc and land
        c = tr.find("component")
        if c is None or tr.get("muted") == "True" or c.get("class") not in ("GravityForce", "Deflector"):
            continue
        c = copy.deepcopy(c)
        E.retime(c, T_END, T_END + BURST_TAIL)
        c.set("instancename", str(uuid.uuid5(B.NS, f"meteor_burst_force_{len(out)}")))
        out.append(c)
    out += sound_components([("CrSpell_Impact_HellfireMissiles", "497c1e7a-919e-4b55-857e-79dbfc570d5f", T_END, T_END + BURST_TAIL)],
                            "meteor_burst_sound")
    return out


def rubble_components():
    """Broken rocks left on the scorch mark, smoking and glowing, then fading out. Visual only."""
    base = next(c for c in B.xml(TRAIL).iter("component") if c.get("class") == "Model" and E.comp_name(c) == "Projectile_Head")
    pos_src = next(m for m in B.xml(SPHERE_RAM).iter("component") if m.get("class") == "Model" and E.has_prop(m, "47a42cb9"))
    out = []
    for i, (x, z, dia) in enumerate(RUBBLE):
        c = copy.deepcopy(base)
        k = dia / ROCK_MESH_DIAMETER
        B.set_value(c, "ef1d7d1e", f"meteor_rubble_{i}")
        B.set_value(c, "15864e49", ROCK_MESH)
        B.set_ramp(c, "2bea542b", [B.const(1.0), B.const(0.75), B.const(1.0)])              # Axis Scale: squashed, half-buried look
        B.set_ramp(c, "f80eefa7", [[(0, 0.0), (0.03, k), (0.8, k), (1, 0.0)]])              # pops up at the landing, shrinks away at the end
        B.set_ramp(c, "e5ece95a", [B.const(0.0)] * 3)                                       # no spin
        B.set_ramp(c, "00910be4", [[(0, 1.0), (0.75, 1.0), (1, 0.0)]])                      # Alpha
        if not E.has_prop(c, "47a42cb9"):
            c.find("properties").append(copy.deepcopy(B.prop(pos_src, "47a42cb9")))
        B.set_value(c, "47a42cb9", f"{x:g},-0.05,{z:g}")                                    # mesh pivot is at its bottom: sits on the ground
        ml = c.find("modules")
        if not any(m.get("id").lower() == B.M["position"] for m in ml):
            ET.SubElement(ml, "module", id=B.M["position"], muted="False", index=str(len(ml)))
        E.retime(c, FALL + RUBBLE_START, FALL + RUBBLE_END)
        c.set("instancename", str(uuid.uuid5(B.NS, f"meteor_rubble_{i}")))
        out.append(c)
    glow_base = [c for c in B.xml(B.BASE).iter("component") if c.get("class") == "ParticleSystem"][1]
    el = dict(column=0, slot=2, phase=0)
    secs = RUBBLE_END - RUBBLE_START - 0.8
    for i, (x, z) in enumerate(RUBBLE_SMOKE):
        layers = [
            B.layer(f"rubble_smoke{i}", "dust", B.argb(255, 60, 52, 46), br(0.9), (0.8 / B.SIZE, 1.5 / B.SIZE), (1.6, 2.6), 5, 18,
                    alpha=[(0, 0.0), (0.15, 0.45), (1, 0)], spin=(0.03, 0.1), velocity=("0,1,0", 18, 0.4, 0.9), space=2),
            B.layer(f"rubble_glow{i}", "glow", B.argb(255, 255, 110, 25), br(2.2), 1.3 / B.SIZE, (0.5, 0.9), 5, 8,
                    alpha=[(0, 0.0), (0.5, 0.5), (1, 0)]),
        ]
        for L in layers:
            c = B.make_emitter(glow_base, "meteor", el, L, secs)
            B.set_ramp(c, B.P["kf_offset"], [[(0, x), (1, x)], [(0, 0.35), (1, 0.35)], [(0, z), (1, z)]])
            E.retime(c, FALL + RUBBLE_START, FALL + RUBBLE_START + secs)
            c.set("instancename", str(uuid.uuid5(B.NS, f"meteor_{L['name']}")))
            out.append(c)
    return out


PLUME_OV = {   # Produce Flame column at the impact: fade in fast, hold, fade out (ramp times normalised over the plume's life)
    "bb1e9c04": [[(0, 16777215), (0.06, -1), (0.65, -1), (1, 16777215)]],
    "1dc673ff": [[(0, 1.0), (0.06, 6.0), (0.65, 6.0), (1, 1.0)]],
}
PLUMES = [  # x, z, uniform scale, width, seconds  - a fat central column plus two flanking ones
    (0.0, 0.0, 5.5, 0.75, 1.8),
    (-2.0, 1.0, 4.2, 0.6, 1.5),
    (2.0, -1.0, 4.2, 0.6, 1.5),
]
WHOOSH = ("CrSpell_Projectile_HellfireMissiles", "bdda05fc-232b-4855-8a54-01d94a5f98f7")       # head effect: fall whoosh
SOUNDS = [  # impact effect: resource name, GUID (vanilla sound resources), start, end (clones of the vanilla impact's Sound)
    ("CrSpell_Impact_HellfireMissiles", "497c1e7a-919e-4b55-857e-79dbfc570d5f", FALL, FALL + 3.8),          # landing boom
]


def plume_components():
    glow_base = [c for c in B.xml(B.BASE).iter("component") if c.get("class") == "ParticleSystem"][1]
    el = dict(column=0, slot=2, phase=0)
    out = []
    for i, (x, z, scale, width, secs) in enumerate(PLUMES):
        ov = dict(PLUME_OV)
        ov["9984af4f"] = [[(0, scale), (1, scale)]]
        ov["b7f89b82"] = [[(0, width), (1, width)], [(0, 1.0), (1, 1.0)], [(0, 1.0), (1, 1.0)]]
        L = B.layer(f"plume{i}", life=0.5, rate=0, max_count=1, space=1, persistent=True,
                    clone=(B.PRODUCE_FLAME, "ProduceFlame_01"), ov=ov)
        c = B.make_emitter(glow_base, "meteor", el, L, secs)
        B.set_ramp(c, B.P["kf_offset"], [[(0, x), (1, x)], [(0, 0.0), (1, 0.0)], [(0, z), (1, z)]])   # fixed spot on the ground
        E.retime(c, FALL, FALL + secs)
        c.set("instancename", str(uuid.uuid5(B.NS, f"meteor_plume_{i}")))
        out.append(c)
    return out


def sound_components(sounds=None, prefix="meteor_sound"):
    sounds = SOUNDS if sounds is None else sounds
    base = next(c for tr in B.xml(IMPACT).iter("track") if (c := tr.find("component")) is not None
                and c.get("class") == "Sound")
    out = []
    for i, (res, guid, start, end) in enumerate(sounds):
        c = copy.deepcopy(base)
        B.set_value(c, "d9c8f8f4", f"{res} <{guid}>")
        E.retime(c, start, end)
        c.set("instancename", str(uuid.uuid5(B.NS, f"{prefix}_{res}")))
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


def write_bank(name, res_id, duration, deps, looping):
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
					<attribute id="ID" type="FixedString" value="{res_id}" />
					<attribute id="Name" type="LSString" value="{name}" />
					<attribute id="SourceFile" type="LSString" value="Public/{B.MOD}/Assets/Effects/Effects_Banks/Invoker/{name}.lsfx" />
					<attribute id="EffectName" type="FixedString" value="{name}" />
					<attribute id="BoundsMin" type="fvec3" value="-40 -5 -40" />
					<attribute id="BoundsMax" type="fvec3" value="40 40 40" />
					<attribute id="CullingDistance" type="float" value="0" />
					<attribute id="Duration" type="float" value="{duration:g}" />
					<attribute id="Looping" type="bool" value="{looping}" />
					<attribute id="InterruptionMode" type="uint32" value="{2 if looping else 0}" />
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
    with open(os.path.join(B.OUT_DIR, f"bank_{name}.lsx"), "w", encoding="utf-8") as f:
        f.write(text)


def write_mei():
    # position effect at the target point (same structure as the EMP / Sun Strike position effects)
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
					<attribute id="EffectResourceGuid" type="guid" value="{HEAD_RES}" />
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


def write_projectile_template():
    """Invisible delay projectile (no TrailFX): drops the last PROJ_HEIGHT metres onto the target, applies the damage and
    plays ImpactFX where it lands. Replaced in place between the markers."""
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
    begin, end = "<!-- METEOR PROJECTILE BEGIN (generated) -->\n", "<!-- METEOR PROJECTILE END -->\n"
    s = open(ROOT_TEMPLATES, encoding="utf-8", newline="").read().replace("\r\n", "\n")
    if begin in s:                                   # drop the previous copy
        s = s[:s.index(begin)] + s[s.index(end) + len(end):]
    close = s.rfind("</children>", 0, s.rfind("</region>"))          # closes the Templates node's children
    close = s.rfind("\n", 0, close) + 1
    s = s[:close] + begin + node + end + s[close:]
    with open(ROOT_TEMPLATES, "w", encoding="utf-8", newline="") as f:
        f.write(s)


def write_effect(root, name, tag, comps, duration, preview):
    tgs = root.find("trackgroups")
    for tg in list(tgs):
        tgs.remove(tg)
    bounds = copy.deepcopy(next(c for c in B.xml(IMPACT).iter("component") if c.get("class") == "BoundingSphere"))
    prev = ET.SubElement(tgs, "trackgroup", name="Preview only (muted)")
    ET.SubElement(ET.SubElement(prev, "ids"), "id", value="1")
    for m in preview:
        ET.SubElement(prev, "track", name="Track", muted="True", locked="False", mutestateoverride="Unmuted").append(m)
    bounds.set("instancename", str(uuid.uuid5(B.NS, f"meteor_{tag}_bounds")))
    E.retime(bounds, 0, duration)
    B.set_value(bounds, "ba2ee0f9", 40)
    tg = ET.SubElement(tgs, "trackgroup", name=f"Invoker Chaos Meteor {tag}")
    ET.SubElement(ET.SubElement(tg, "ids"), "id", value="2")
    for c in [bounds] + comps:
        ET.SubElement(tg, "track", name="Track", muted="False", locked="False", mutestateoverride="None").append(c)
    out = os.path.join(B.OUT_DIR, name + ".lsefx")
    ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=True)
    if os.path.isdir(B.PREVIEW_DIR):
        shutil.copy2(out, B.PREVIEW_DIR)
    return E.material_guids(comps)


def main():
    for d in (B.OUT_DIR, B.PREVIEW_DIR):                 # the old single position effect is replaced by head + impact
        for f in OLD_FILES:
            if os.path.isfile(os.path.join(d, f)):
                os.remove(os.path.join(d, f))

    # 1) boulder: one-shot position effect (visual only): falls START -> END, rolls to ROLL_END, bursts apart at T_END
    duration = round(T_END + BURST_TAIL, 3)
    root = copy.deepcopy(B.xml(IMPACT))
    for child in list(root.find("phases")):
        root.find("phases").remove(child)
    comps = ([rock_component(T_END + 0.05)] + head_components(T_END + 0.3)
             + [crumble_component(duration)] + burst_components()
             + sound_components([WHOOSH + (0.0, T_END)]))
    pm = preview_models(duration)
    deps = write_effect(root, HEAD_NAME, "head", comps, duration, pm)
    write_bank(HEAD_NAME, HEAD_RES, duration, deps, False)
    write_mei()
    print(f"{HEAD_NAME}: {len(comps)} components, duration {duration:g}s (one-shot position effect, MEI {MEI_ID}), {len(deps)} dependencies")

    # 2) impact: one-shot effect played where the projectile lands
    root = copy.deepcopy(B.xml(IMPACT))
    for child in list(root.find("phases")):
        root.find("phases").remove(child)
    comps = (impact_components() + chunk_components() + dust_components() + plume_components()    # rubble_components() removed: the
             # rocks left shrinking on the scorch looked odd (user 2026-10-03); the boulder now rolls on and bursts instead
             + sound_components())
    duration = round(max(float(c.get("end")) for c in comps) + 0.1, 3)
    deps = write_effect(root, IMPACT_NAME, "impact", comps, duration, preview_models(duration))
    write_bank(IMPACT_NAME, IMPACT_RES, duration, deps, False)
    print(f"{IMPACT_NAME}: {len(comps)} components, duration {duration:g}s, {len(deps)} dependencies")

    write_projectile_template()
    print(f"projectile template {PROJ_NAME} {PROJ_ID}")


if __name__ == "__main__":
    main()
