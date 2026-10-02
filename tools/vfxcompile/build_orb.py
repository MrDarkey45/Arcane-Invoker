"""Generate the orbiting-orb status effects for the Invoker orbs (Quas / Wex / Exort).

Layouts: holding N orbs of one element shows N orbs evenly spaced (N=1: one; N=2: 180 deg apart; N=3: 120 deg apart).
Each (element, N, i) is its own effect + visual-only status INVOKER_ORBFX_<E>_<N>_<i>; the orb spells clear the element's
visual statuses and apply the layout for the new count, so all orbs of an element restart together and stay in step.

For every (element, N, i) this writes three masters into vfx_src/ (repack.ps1 compiles/converts them into the pak):
  VFX_Invoker_Orb_<E>_<N>of<i>.lsefx     effect source (also copied to the Toolkit project for Effect Editor preview)
  bank_VFX_Invoker_Orb_<E>_<N>of<i>.lsx  EffectResource (Duration + material Dependencies derived from the layers)
  mei_INVOKER_ORBFX_<E>_<N>_<i>.lsx      MultiEffectInfo: attaches the effect to Dummy_BodyFX
plus vfx_src/orbfx_statuses.txt: the 18 visual-only StatusData entries, spliced into Status_BOOST.txt between markers.

How it moves: every particle EMITTER follows the same keyframed circle (Keyframed Position module -> "Keyframed
Offset", ramp over the component's life) and the Loop phase replays exactly one revolution forever. Particles are
re-emitted continuously at the emitter's position, so the orb tracks the circle; longer-lived layers form the trail.
Elements orbit at different heights/radii so orbs cast at different times never sit on top of each other.

Layers either restyle a plain vanilla glow particle (template = Bladesinger Song of Defense glow) or CLONE a vanilla
particle component wholesale (keeps its flipbook / gradient-map / orientation setup) and only override what we need.

Preview helpers: proxy human + sand floor on MUTED tracks forced visible in the Effect Editor (not compiled).
Offset 0,-1,0 = vanilla BodyFX convention (Dummy_BodyFX sits ~1 m above the feet).

Usage: python build_orb.py
"""
import copy
import math
import random
import os
import shutil
import sys
import uuid
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(ROOT, "vfx_src")
MOD = "InvokerAbilities_39a130d8-8e3d-6d6c-5a20-ae216d580752"
PREVIEW_DIR = (r"E:\SteamLibrary\steamapps\common\Baldurs Gate 3\Data\Editor\Mods" + "\\" + MOD
               + r"\Assets\Effects\Invoker")
MODS = r"E:\SteamLibrary\steamapps\common\Baldurs Gate 3\Data\Editor\Mods"
BASE = MODS + r"\GustavX\Assets\Effects\Status\VFX_Status_Wizard_Bladesinger_SongOfDefense_BodyFX_01.lsefx"
COLD_ORB = MODS + r"\Shared\Assets\Effects\Projectiles\VFX_Projectiles_Damage_Cold_ChromaticOrb_Projectile_01.lsefx"
LIGHTNING_ORB = MODS + r"\Shared\Assets\Effects\Projectiles\VFX_Projectiles_Damage_Lightning_ChromaticOrb_Projectile_01.lsefx"
PRODUCE_FLAME = MODS + r"\Shared\Assets\Effects\Status\VFX_Status_ProduceFlame_HandFX_01.lsefx"
MYRMIDON_FIRE = MODS +r"\SharedDev\Assets\Effects\Enemies\VFX_Enemies_Myrmidon_Fire_VFX_Status_NeckFX_01.lsefx"

MAT = {  # vanilla particle materials ("Name <guid>" is how the editor stores them)
    "glow": "VFX_ParticleSystem_AlphaBlend_Unlit_Emissive_TwoSided_Glow_Circle_02 <f7fc084b-d098-0d9a-8033-1cb61c3beb37>",
    "flakes": "VFX_ParticleSystem_AlphaBlend_Unlit_Emissive_PolarUV_UVDistortion_Sundog_Flakes_05 "
              "<3d5fa2b7-a18b-b6cf-48b0-8713484e64dc>",
    "dust": "VFX_ParticleSystem_AlphaBlend_Unlit_Emissive_TwoSided_Shape_Dust_01 <705bcdca-a937-9dfa-983f-25238afab834>",
}


def argb(a, r, g, b):
    """AllSpark colors are packed ARGB stored as a signed 32-bit int."""
    v = (a << 24) | (r << 16) | (g << 8) | b
    return v - (1 << 32) if v >= 1 << 31 else v


def layer(name, mat=None, color=None, bright=None, scale=None, life=None, rate=10, max_count=20, alpha=None,
          spin=None, velocity=None, clone=None, ov=None, space=1, stretch=None, persistent=False):
    """scale/life: number or (min, max). velocity: (axis 'x,y,z', cone degrees, min m/s, max m/s).
    color/bright: a constant, or [(t, value), ...] over the particle's life.
    space: Coordinate Space 0=World 1=Local (rides with the orbiting emitter) 2=World(Emit Local) (released into the
    world where emitted, then moves on its own - use for embers/sparks that should drift, not be dragged along).
    stretch: (x, y, z) Axis Scale, e.g. (0.6, 1.6, 1) for an upward-elongated ember.
    clone: (vanilla .lsefx, material substring) to copy that particle component instead of the glow template.
    ov: {property-id prefix: value | [channel keys...] | callable(effect_duration) -> either} raw overrides applied last.
    persistent: one particle that lives for the whole effect (Infinite Lifespan) - for shader-animated flames."""
    return dict(name=name, mat=mat, color=color, bright=bright, scale=scale, life=life, rate=rate,
                max_count=max_count, alpha=alpha, spin=spin, velocity=velocity, clone=clone, ov=ov or {},
                space=space, stretch=stretch, persistent=persistent)


# Exort's flame body (user 2026-09-30: the Fire_Burst flipbook flames looked jittery like electricity).
#  "produceflame": the Produce Flame cantrip's hand flame - ONE persistent particle drawn by a panning/UV-distorted
#                  gradient-map shader (no flipbook to flicker) - the steadiest flame in the game's assets.
#  "burst":        the old Fire_Burst_02 flipbook, but with vanilla's 2.25-3.6 s particle life (the flipbook animation is
#                  stretched over the particle's life; our 0.45-0.7 s life played it ~5x too fast = the flicker).
FLAME_STYLE = "produceflame"
FLAME_SCALE = 0.80          # produceflame: uniform scale (= vanilla hand flame; was 0.55, user asked for a bit bigger)
FLAME_WIDTH = 0.55
FLAME_BRIGHT = 5.0


def _flame_fade(duration):
    """Ramp times are normalised over the component: fade in over the Lead In, hold through the Loop, fade out after."""
    u_in, u_out = LEAD_IN / duration, (LEAD_IN + PERIOD) / duration
    return u_in, u_out


def exort_flame_layer():
    if FLAME_STYLE == "produceflame":
        return layer("flame", life=0.5, rate=0, max_count=1, space=1, persistent=True,
                     clone=(PRODUCE_FLAME, "ProduceFlame_01"),
                     ov={"bb1e9c04": lambda d: [[(0, 16777215), (_flame_fade(d)[0], -1), (_flame_fade(d)[1], -1),
                                                 (1, 16777215)]],                                   # colour/alpha over effect
                         "1dc673ff": lambda d: [[(0, 1.0), (_flame_fade(d)[0], FLAME_BRIGHT),
                                                 (_flame_fade(d)[1], FLAME_BRIGHT), (1, 1.0)]],     # brightness over effect
                         "9984af4f": [[(0, FLAME_SCALE), (1, FLAME_SCALE)]],                        # scale over effect: constant
                         "b7f89b82": [[(0, FLAME_WIDTH), (1, FLAME_WIDTH)], [(0, 1.0), (1, 1.0)], [(0, 1.0), (1, 1.0)]]})
    return layer("flames", scale=(0.16, 0.24), life=(2.25, 3.6), rate=7, max_count=20,
                 clone=(MYRMIDON_FIRE, "Fire_Burst_02"),
                 ov={"068cf735": [[(0, 0.05), (1, 0.05)]], "16f5adbb": [[(0, 0.03), (1, 0.03)]],   # cone radius
                     "24fffa5e": [[(0, 0.05), (1, 0.05)]],                                         # cone height
                     "79ab5e9c": [[(0, 0.12), (1, 0.12)], [(0, 0.25), (1, 0.25)]]})                # slow rise


ELEMENTS = {
    # Quas: white-blue ice (was vanilla Chromatic Orb Cold azure 43,90,253 - read as violet in-game)
    "quas": dict(
        ids=("bf28d6be-17a7-48da-98e4-45eee203c5ab", "154b1367-62e6-4a20-a6a1-acfb8a52340e",
             "990fa50e-1dc9-440e-a8f4-282e2c8e9d12"),        # EffectResource, MEI, EffectInfo
        column=-1, bob_phase=0,      # left shoulder
        layers=[
            # Icy cyan-white (user 2026-09-30: still read as violet, too close to Wex). Keep green ~= blue and red low:
            # blue-heavy tints with some red bloom to lavender. The Sundog flake texture is used at low opacity like
            # vanilla (Cold Chromatic Orb uses it at alpha 32/255) so it can't tint the orb.
            layer("mist", "dust", argb(255, 185, 240, 250), 1.2, 0.34, 1.3, 26, 40, alpha=[(0, 0.6), (1, 0)],
                  spin=(0.05, 0.15), space=2),
            layer("aura", "glow", argb(255, 90, 215, 245), 1.3, 0.38, 0.25, 40, 16, alpha=[(0, 0.8), (1, 0)]),
            layer("crystal", "flakes", argb(255, 170, 245, 255), 1.5, 0.30, 0.45, 10, 8,
                  alpha=[(0, 0), (0.3, 0.35), (1, 0)], spin=(0.15, 0.35)),
            layer("core", "glow", argb(255, 225, 255, 255), 3.0, 0.13, 0.12, 60, 10, alpha=[(0, 1), (1, 0.6)]),
            layer("snow", "glow", argb(255, 230, 255, 255), 3.0, 0.035, 1.2, 14, 20, alpha=[(0, 1), (1, 0)],
                  velocity=("0,-1,0", 25, 0.15, 0.35), space=2),
        ]),
    # Wex: violet storm (mod palette); crackling arcs = vanilla Lightning Chromatic Orb's 4x2 lightning flipbook
    "wex": dict(
        ids=("c246d51e-6826-4734-b9be-34c809d4d921", "38f10632-9a54-4afa-8ad4-00c34705780d",
             "f8454585-165e-4fc4-8bdd-7e292347b3a9"),
        column=0, bob_phase=120,     # centre
        layers=[
            layer("trail", "glow", argb(255, 120, 70, 255), 1.6, 0.16, 0.55, 30, 24, alpha=[(0, 0.45), (1, 0)], space=2),
            layer("aura", "glow", argb(255, 110, 50, 240), 1.8, 0.36, 0.25, 40, 16, alpha=[(0, 0.8), (1, 0)]),
            layer("arcs", color=argb(255, 185, 140, 255), bright=12.0, scale=(0.22, 0.32), life=(0.08, 0.16),
                  rate=14, max_count=6, spin=(0, 0), clone=(LIGHTNING_ORB, "04x02_Lightning_01")),
            layer("core", "glow", argb(255, 235, 220, 255), 4.0, 0.13, 0.12, 60, 10, alpha=[(0, 1), (1, 0.6)]),
            layer("sparks", "glow", argb(255, 200, 170, 255), 5.0, 0.03, (0.2, 0.4), 22, 20,
                  alpha=[(0, 1), (1, 0)], velocity=("0,1,0", 180, 0.4, 0.9), space=2),
        ]),
    # Exort: amber fire; flames = vanilla Myrmidon fire's Fire_Burst_02 flipbook (colour from its own gradient)
    "exort": dict(
        ids=("2a79b1e4-4842-47ff-84f9-7cbd63d2d7d3", "fdae7102-6cae-47d3-9e96-9e5c0f113a8d",
             "153c6bfa-d291-4c8f-be86-9336b8192f48"),
        column=1, bob_phase=240,     # right shoulder
        layers=[
            layer("smoke", "dust", argb(255, 150, 70, 30), 1.0, 0.30, 1.2, 20, 30, alpha=[(0, 0.35), (1, 0)],
                  spin=(0.05, 0.15), velocity=("0,1,0", 20, 0.1, 0.25), space=2),
            layer("aura", "glow", argb(255, 255, 110, 20), 2.0, 0.38, 0.25, 40, 16, alpha=[(0, 0.8), (1, 0)]),
            exort_flame_layer(),
            layer("core", "glow", argb(255, 255, 225, 150), 4.0, 0.13, 0.12, 60, 10, alpha=[(0, 1), (1, 0.6)]),
            # embers modelled on vanilla Forge Fire / Flame Blade: released into the world (space 2) so they drift up
            # instead of being dragged along the orbit, hot-to-cool colour over life, fade in/out, slightly stretched
            layer("embers", "glow",
                  [(0, argb(255, 255, 225, 130)), (0.3, argb(255, 255, 150, 40)), (0.7, argb(255, 225, 70, 15)),
                   (1, argb(255, 110, 25, 10))],
                  [(0, 1.5), (0.15, 4.0), (1, 2.0)], (0.03, 0.05), (1.4, 2.2), 14, 40,
                  alpha=[(0, 0), (0.12, 1), (0.7, 0.8), (1, 0)], velocity=("0,1,0", 15, 0.12, 0.25),
                  space=2, stretch=(0.6, 1.6, 1)),
        ]),
}

# Timing (seconds) shared by all elements; same period keeps relative spacing constant.
SIZE = 1.8          # multiplies every layer's particle scale (in-game v1 read as a small dot)
BRIGHT = 1.6        # multiplies every layer's brightness
# Layout: element COLUMNS behind the back (user 2026-09-30). Quas over the left shoulder, Wex centre, Exort right;
# the i-th orb of an element stacks upward in its column. Offsets are relative to Dummy_BodyFX (~1 m above the feet).
# Dummy_BodyFX local axes, confirmed in-game 2026-09-30 from two screenshots: +Y up, X runs LEFT/RIGHT (+X = the
# character's left, so right = -X), Z runs FORWARD/BACK (forward = -Z, so behind = +Z).
#  - build with behind = -Z  -> orbs appeared IN FRONT of the chest (so -Z is forward)
#  - build with behind = +X  -> all three orbs on the character's LEFT, spread front-to-back along Z (so +X is left)
FORWARD_AXIS, FORWARD_SIGN = "z", -1.0   # local axis + sign that points where the character faces
RIGHT_AXIS, RIGHT_SIGN = "x", -1.0       # local axis + sign that points to the character's right
BEHIND = 0.50       # metres behind the body (was 0.30; user asked to nudge back)
COLUMN_X = 0.40     # sideways distance of the shoulder columns from the centre line
BASE_Y = 0.65       # first orb: just above shoulder height, beside the head
STACK_Y = 0.26      # vertical spacing when 2-3 orbs of one element stack
BOB = 0.035         # calm hover bob amplitude (metres) between darts
PERIOD = 4.0        # Loop phase length: calm hover + DARTS darts, then back home
BOB_PERIOD = 2.0    # one calm bob cycle (divides PERIOD, so the bob wraps seamlessly)
LEAD_IN = 0.5       # Loop phase = [LEAD_IN, LEAD_IN + PERIOD]; angle is continuous across the wrap
STEP_DEG = 10       # (unused since the jitter rework)
SNITCH_STEP = 0.04  # seconds between path keyframes (small = smooth darts)
DARTS = 3           # darts per loop (the last one returns home)
DART_TIME = 0.28    # how long a dart takes (s) - quick and snappy
DART_XZ = 0.20      # sideways / front-back dart reach (metres)
DART_Y = 0.16       # vertical dart reach (metres)

P = dict(  # ParticleSystem property ids (see ComponentDefinition.xcd / ModuleDefinition.xmd)
    name="ef1d7d1e-02b6-4548-80d9-5ef2fbcda237", time="035b5248-d0ca-44b7-853f-3acb84110e67",
    max_count="21176254-19ca-43e0-a890-b20fd264cca3", emit_rate="b16512bc-8157-4c11-bfde-732ec940b841",
    emit_stutter="7da7d536-8b67-49b7-b3fe-97e9843eb902", init_count="20d22bbd-2e85-41e1-bc13-00b2a72cdf9b",
    coord_space="b13c2ffd-c94f-4d56-947e-07077287ec52", offset="726ea55f-d0f9-4176-9a22-c5539199a83a",
    lifespan="352fac77-0097-47ec-908c-7c0d334fc161", infinite="b3d95d98-4a86-4b94-84c5-fd58a083e65f",
    color="93b34a52-eef2-4f88-80f6-19e3126188ca", brightness="7b01f163-d329-4cd0-97f0-31115055b9c8",
    uscale="02e6012f-51af-4f4c-8897-2b8421952fa1", alpha="d1892ce7-07f3-4d9c-9acb-6692b897a71b",
    kf_offset="a14d2803-fec4-4015-9e37-eb67e1c2f1d8", init_vel="79ab5e9c-2d87-496c-83bd-1b6c78cbd095",
    vel_axis="917df2bc-bbb3-4205-8d28-2450ea069f00", vel_angle="48938cdf-26e0-489f-b123-db5cffbc75bf",
    rot_angle="8ac28820-26ab-4bbe-bded-41597208ba05", rot_rate="7b539b7a-acad-48fb-b469-4edb97e395af",
    material="f01fec2b-558c-48b2-b8bc-0644cdb9fcca",
    model_pos="47a42cb9-3508-427e-8a09-8d8cc74771b7", model_mesh="15864e49",
)
M = dict(  # module ids
    required="286df729-035e-4bb8-a210-c836ddbbbacc", position="e2afc256-8cf0-4fb7-94ab-88cfb02cc1f4",
    lifetime="65eb458e-ef51-4fbd-bd7f-bedacd59a02f", color="b369fad0-cc26-42f3-bdc2-0b8f120c6081",
    scale="6737872c-53c1-424d-a16d-61a87a84d8e7", alpha="6b638fb9-009a-4391-b313-900f8ad0cac4",
    kf_position="7a790ae7-3b1c-463e-bb1f-5cc14980b78c", init_rot="640cb9e3-bcce-4067-a699-7f92fa927931",
    init_rot_rate="7a5401d4-8169-4140-aee9-4b8bb7a6364e", init_vel="cb4f2a13-f7bf-4568-88ec-0211637c05cf",
)
PHASE_DEFS = ("fc34bad5-e4a8-4855-bdd1-ece88d327719", "2d6a16c1-4632-4f7f-8097-4717dc65d7bd",
              "fc8e9f77-827a-433f-a58d-ad1007605399")  # Lead In, Loop, Lead Out
NS = uuid.UUID("7b281658-5329-4a63-aa56-6faec8f383c8")  # subclass UUID; stable namespace for generated ids
STATUS_BEGIN = "// >>> ORBFX BEGIN (generated)"
STATUS_END = "// <<< ORBFX END"
_XML_CACHE = {}


def xml(path):
    if path not in _XML_CACHE:
        _XML_CACHE[path] = ET.parse(path).getroot()
    return _XML_CACHE[path]


def prop(comp, pid):
    for p in comp.find("properties").iter("property"):
        if p.get("id").startswith(pid):
            return p
    raise KeyError(pid)


def get_value(comp, pid):
    return prop(comp, pid).find("data/datum").get("value")


def set_value(comp, pid, value):
    prop(comp, pid).find("data/datum").set("value", str(value))


def set_ramp(comp, pid, channels):
    """channels: list of [(time, value), ...] in the property's channel order (X,Y,Z / Min,Max / single)."""
    chans = list(prop(comp, pid).iter("rampchannel"))
    assert len(chans) >= len(channels), (pid, len(chans))
    for ch, keys in zip(chans, channels):
        if ch.get("type") not in ("Linear", "Spline"):
            ch.set("type", "Linear")       # e.g. FreeTangentSpline keys carry tangent handles we don't write
        kf = ch.find("keyframes")
        for k in list(kf):
            kf.remove(k)
        for t, v in keys:
            ET.SubElement(kf, "keyframe", time=f"{t:.6g}", value=f"{v:.6g}" if isinstance(v, float) else str(v))


def const(v):
    return [(0, v), (1, v)]


def pair(v):
    return v if isinstance(v, tuple) else (v, v)


def material_guid(comp):
    return get_value(comp, P["material"]).rsplit("<", 1)[1].rstrip(">")


def orbit_keys(el, duration, phase_deg):
    """Fixed spot in the element's column (slot el['slot']) with a gentle bob; the Loop phase is one bob cycle."""
    pos = {"x": 0.0, "z": 0.0}
    pos[RIGHT_AXIS] += (el["slot"] - 2) * COLUMN_X * RIGHT_SIGN      # slot 1 left, 2 centre, 3 right
    pos[FORWARD_AXIS] += -BEHIND * FORWARD_SIGN
    y0 = BASE_Y
    xs, ys, zs = [], [], []
    # Golden-Snitch motion (user 2026-10-01): the orb hovers calmly with a small bob, then darts to a nearby spot in a
    # quick overshooting burst, hovers there bobbing, darts again, and finally darts back home so the Loop wraps seamlessly.
    # Dart targets/timings are seeded per orb (phase_deg is unique per element/slot) so the three orbs dart out of step.
    rng = random.Random(int(phase_deg * 10) + 7919)
    targets = [(0.0, 0.0, 0.0)] + [
        (rng.uniform(-DART_XZ, DART_XZ), rng.uniform(-DART_Y, DART_Y), rng.uniform(-DART_XZ, DART_XZ)) for _ in range(DARTS - 1)
    ] + [(0.0, 0.0, 0.0)]
    # dart k starts at loop time start_k and takes DART_TIME; spread evenly with a random wobble, last one ends before the wrap
    slot_len = PERIOD / DARTS
    starts = [slot_len * (k + 1) - DART_TIME - 0.25 + rng.uniform(-0.2, 0.2) for k in range(DARTS)]
    starts[-1] = PERIOD - DART_TIME - 0.05

    def ease(u):  # ease-out with a small overshoot (a snitch snaps to its target and settles)
        u = min(max(u, 0.0), 1.0)
        c1 = 2.2
        return 1 + (c1 + 1) * (u - 1) ** 3 + c1 * (u - 1) ** 2

    def offset(tl):  # tl = time inside the Loop phase (may be <0 or >PERIOD during lead in/out)
        cur = 0
        for k in range(DARTS):
            if tl >= starts[k]:
                cur = k + 1
        if cur == 0:
            return targets[0]
        k = cur - 1
        f = ease((tl - starts[k]) / DART_TIME)
        a, bb = targets[k], targets[k + 1]
        return tuple(a[m] + (bb[m] - a[m]) * f for m in range(3))

    n = int(round(duration / SNITCH_STEP))
    for i in range(n + 1):
        t = duration * i / n
        tl = t - LEAD_IN
        ox, oy, oz = offset(tl)
        theta = 2 * math.pi * tl / BOB_PERIOD + math.radians(phase_deg)
        u = t / duration                           # ramp time is normalized over the component [0, duration]
        xs.append((u, round(pos["x"] + ox, 4)))
        ys.append((u, round(y0 + oy + BOB * math.sin(theta), 4)))
        zs.append((u, round(pos["z"] + oz, 4)))
    return [xs, ys, zs]


def find_component(path, material_substring):
    for c in xml(path).iter("component"):
        if c.get("class") == "ParticleSystem" and material_substring in (get_value(c, P["material"]) or ""):
            return c
    raise KeyError((path, material_substring))


def make_emitter(glow_base, tag, el, L, duration):
    cloned = L["clone"] is not None
    c = copy.deepcopy(find_component(*L["clone"]) if cloned else glow_base)
    c.set("start", "0")
    c.set("end", f"{duration:g}")
    c.set("instancename", str(uuid.uuid5(NS, f"{tag}_orb_{L['name']}")))
    set_value(c, P["name"], f"{tag}_orb_{L['name']}")
    set_value(c, P["time"], f"0,{duration:g}")
    if L["mat"]:
        set_value(c, P["material"], MAT[L["mat"]])
    set_value(c, P["max_count"], L["max_count"])
    set_ramp(c, P["emit_rate"], [const(L["rate"])])
    set_ramp(c, P["emit_stutter"], [const(0)])
    set_value(c, P["init_count"], "1,1")
    set_value(c, P["coord_space"], L["space"])
    set_value(c, P["offset"], "0,0,0")
    set_value(c, P["infinite"], 1 if L["persistent"] else 0)
    set_value(c, "40a5b37b", 0)             # Show Emitter off (editor-only wireframe of the spawn shape)
    if not L["persistent"]:
        lo, hi = pair(L["life"])
        set_ramp(c, P["lifespan"], [const(lo), const(hi)])
    set_ramp(c, P["kf_offset"], orbit_keys(el, duration, el["phase"]))
    mods = [m.get("id").lower() for m in c.find("modules") if m.get("muted") != "True"] if cloned else \
        [M["required"], M["position"], M["lifetime"]]
    want = [M["lifetime"], M["kf_position"]]
    if L["color"] is not None:
        set_ramp(c, P["color"], [L["color"] if isinstance(L["color"], list) else const(L["color"])])
        bright = L["bright"] if isinstance(L["bright"], list) else const(L["bright"])
        set_ramp(c, P["brightness"], [[(t, v * BRIGHT) for t, v in bright]])
        want.append(M["color"])
    if L["scale"] is not None:
        s_lo, s_hi = (v * SIZE for v in pair(L["scale"]))
        if L["stretch"] is not None:
            set_ramp(c, "3ab58b27", [const(float(v)) for v in L["stretch"]])      # Axis Scale X,Y,Z
        set_ramp(c, P["uscale"], [const(s_lo), const(s_hi if s_hi != s_lo else 0)])
        want.append(M["scale"])
    if L["alpha"] is not None:
        set_ramp(c, P["alpha"], [L["alpha"]])
        want.append(M["alpha"])
    if L["spin"] is not None:                  # random start angle + random spin (rotations/second)
        set_ramp(c, P["rot_angle"], [const(0), const(360)])
        set_ramp(c, P["rot_rate"], [const(L["spin"][0]), const(L["spin"][1])])
        want += [M["init_rot"], M["init_rot_rate"]]
    if L["velocity"] is not None:
        axis, cone, v_lo, v_hi = L["velocity"]
        set_value(c, P["vel_axis"], axis)
        set_ramp(c, P["vel_angle"], [const(cone), const(0)])
        set_ramp(c, P["init_vel"], [const(v_lo), const(v_hi)])
        want.append(M["init_vel"])
    elif not cloned:
        set_ramp(c, P["init_vel"], [const(0), const(0)])
    for pid, v in L["ov"].items():
        v = v(duration) if callable(v) else v
        set_ramp(c, pid, v) if isinstance(v, list) else set_value(c, pid, v)
    mods += [m for m in want if m not in mods]
    ml = c.find("modules")
    for m in list(ml):
        ml.remove(m)
    for i, mid in enumerate(mods):
        ET.SubElement(ml, "module", id=mid, muted="False", index=str(i))
    return c


def preview_models(element, duration):
    """Proxy human + floor from the vanilla cold orb effect, re-timed and dropped 1 m (BodyFX convention)."""
    out = []
    for c in xml(COLD_ORB).iter("component"):
        if c.get("class") != "Model":
            continue
        mesh = get_value(c, P["model_mesh"]) or ""
        if "Proxy_HUM_M_Fullbody" in mesh or "Floor_01_Sand" in mesh:
            m = copy.deepcopy(c)
            m.set("start", "0")
            m.set("end", f"{duration:g}")
            m.set("instancename", str(uuid.uuid5(NS, f"{element}_preview_{mesh.split()[0]}")))
            set_value(m, P["time"], f"0,{duration:g}")
            set_value(m, P["model_pos"], "0,-1,0")
            out.append(m)
    assert len(out) == 2, "preview models not found"
    return out


def write_bank(v, duration, deps):
    res_id, name = v["ids"][0], v["name"]
    dep_xml = "".join(f"""
								<node id="DependentResource">
									<attribute id="Object" type="FixedString" value="{d}" />
								</node>""" for d in deps)
    text = f"""<?xml version="1.0" encoding="utf-8"?>
<!-- GENERATED by tools/vfxcompile/build_orb.py - do not edit by hand -->
<save>
	<version major="4" minor="0" revision="7" build="200" lslib_meta="v1,bswap_guids,lsf_keys_adjacency" />
	<region id="EffectBank">
		<node id="EffectBank">
			<children>
				<node id="Resource">
					<attribute id="ID" type="FixedString" value="{res_id}" />
					<attribute id="Name" type="LSString" value="{name}" />
					<attribute id="SourceFile" type="LSString" value="Public/{MOD}/Assets/Effects/Effects_Banks/Invoker/{name}.lsfx" />
					<attribute id="EffectName" type="FixedString" value="{name}" />
					<attribute id="BoundsMin" type="fvec3" value="-1.5 -1.5 -1.5" />
					<attribute id="BoundsMax" type="fvec3" value="1.5 1.5 1.5" />
					<attribute id="CullingDistance" type="float" value="0" />
					<attribute id="Duration" type="float" value="{duration:g}" />
					<attribute id="Looping" type="bool" value="True" />
					<attribute id="InterruptionMode" type="uint32" value="2" />
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
    with open(os.path.join(OUT_DIR, f"bank_{name}.lsx"), "w", encoding="utf-8") as f:
        f.write(text)


def write_mei(v):
    res_id, mei_id, info_id = v["ids"]
    status = v["status"]
    text = f"""<?xml version="1.0" encoding="utf-8"?>
<!-- GENERATED by tools/vfxcompile/build_orb.py - do not edit by hand -->
<save>
	<version major="4" minor="0" revision="7" build="200" lslib_meta="v1,bswap_guids,lsf_keys_adjacency" />
	<region id="MultiEffectInfos">
		<node id="MultiEffectInfos">
			<attribute id="Name" type="LSString" value="{status}_StatusEffect" />
			<attribute id="UUID" type="guid" value="{mei_id}" />
			<children>
				<node id="EffectInfo">
					<attribute id="BindSourceTo" type="FixedString" value="SourceEntity" />
					<attribute id="BindTargetTo" type="FixedString" value="TargetEntity" />
					<attribute id="DetachSource" type="bool" value="False" />
					<attribute id="DetachTarget" type="bool" value="False" />
					<attribute id="EffectResourceGuid" type="guid" value="{res_id}" />
					<attribute id="KeepRotation" type="bool" value="False" />
					<attribute id="KeepScale" type="bool" value="True" />
					<attribute id="MainHand" type="bool" value="False" />
					<attribute id="MaxDistance" type="float" value="0" />
					<attribute id="MinDistance" type="float" value="0" />
					<attribute id="OffHand" type="bool" value="False" />
					<attribute id="Pivot" type="FixedString" value="Target" />
					<attribute id="UUID" type="guid" value="{info_id}" />
					<attribute id="UseDistance" type="bool" value="False" />
					<attribute id="UseOrientDirection" type="bool" value="False" />
					<attribute id="UseScaleOverride" type="bool" value="False" />
					<children>
						<node id="TargetBone">
							<attribute id="Value" type="LSString" value="Dummy_BodyFX" />
						</node>
						<node id="TargetSkeletonSlot">
							<attribute id="Value" type="LSString" value="" />
						</node>
					</children>
				</node>
			</children>
		</node>
	</region>
</save>
"""
    with open(os.path.join(OUT_DIR, f"mei_{status}.lsx"), "w", encoding="utf-8") as f:
        f.write(text)


def variants(element):
    """Dota-style slots (user 2026-09-30): the k-th orb CAST (k = held-orb count after the cast, from the ORB_1/2/3 chain)
    goes in slot k of a row behind the shoulders, whatever its element. One effect + visual status per (element, slot):
    INVOKER_ORBFX_<E>_S<k>. The orb spell applies exactly one; Dispel Orbs clears all 9."""
    el = ELEMENTS[element]
    for k in (1, 2, 3):
        ids = el["ids"] if k == 1 else tuple(
            str(uuid.uuid5(NS, f"{element}_slot{k}_{part}")) for part in ("resource", "mei", "effectinfo"))
        yield dict(element=element, n=3, i=k, ids=ids,
                   name=f"VFX_Invoker_Orb_{element.capitalize()}_Slot{k}",
                   status=f"INVOKER_ORBFX_{element.upper()}_S{k}",
                   slot=k, phase=el["bob_phase"] + (k - 1) * 110.0)


def build(v):
    element = v["element"]
    el = dict(ELEMENTS[element], phase=v["phase"], slot=v["slot"])
    name = v["name"]
    tag = f"{element}_{v['n']}_{v['i']}"
    longest = max(pair(L["life"])[1] for L in el["layers"])
    lead_out = round(longest + 0.2, 2)          # let the longest-lived particles die out
    duration = LEAD_IN + PERIOD + lead_out

    root = copy.deepcopy(xml(BASE))
    glow_base = [c for c in root.iter("component") if c.get("class") == "ParticleSystem"][1]
    bounds = copy.deepcopy(next(c for c in root.iter("component") if c.get("class") == "BoundingSphere"))
    assert "Glow_Circle_02" in get_value(glow_base, P["material"])

    phases = root.find("phases")
    for child in list(phases):
        phases.remove(child)
    for defid, dur, count in zip(PHASE_DEFS, (LEAD_IN, PERIOD, lead_out), (1, -1, 1)):
        obj = ET.SubElement(phases, "object", {"class": "", "classid": "00000000-0000-0000-0000-000000000000",
                                               "assembly": ""})
        ET.SubElement(obj, "data", id=str(uuid.uuid5(NS, f"{tag}_phase_{defid}")), duration=f"{dur:g}",
                      playcount=str(count), definitionid=defid)

    comps = [make_emitter(glow_base, tag, el, L, duration) for L in el["layers"]]
    bounds.set("start", "0")
    bounds.set("end", f"{duration:g}")
    bounds.set("instancename", str(uuid.uuid5(NS, f"{tag}_bounds")))
    set_value(bounds, P["time"], f"0,{duration:g}")

    tgs = root.find("trackgroups")
    for tg in list(tgs):
        tgs.remove(tg)
    prev = ET.SubElement(tgs, "trackgroup", name="Preview only (muted)")
    ET.SubElement(ET.SubElement(prev, "ids"), "id", value="1")
    for m in preview_models(tag, duration):
        ET.SubElement(prev, "track", name="Track", muted="True", locked="False", mutestateoverride="Unmuted").append(m)
    tg = ET.SubElement(tgs, "trackgroup", name=f"Invoker {element} orb slot {v['slot']}")
    ET.SubElement(ET.SubElement(tg, "ids"), "id", value="2")
    for comp in [bounds] + comps:
        ET.SubElement(tg, "track", name="Track", muted="False", locked="False", mutestateoverride="None").append(comp)

    out = os.path.join(OUT_DIR, name + ".lsefx")
    ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=True)
    deps = sorted({material_guid(c) for c in comps})
    write_bank(v, duration, deps)
    write_mei(v)
    if os.path.isdir(PREVIEW_DIR):
        shutil.copy2(out, PREVIEW_DIR)
    print(f"{name}: slot {v['slot']}, duration {duration:g}s, deps {len(deps)} -> {v['status']}")


def status_block(all_variants):
    """Visual-only statuses: no mechanics, hidden from portrait/overhead/combat log; StatusEffect = the orb MEI."""
    out = [STATUS_BEGIN,
           "// Visual-only orb statuses, GENERATED by tools/vfxcompile/build_orb.py (edit the script, not this block).",
           "// INVOKER_ORBFX_<E>_<N>_<i> = orb i of N held orbs of that element. The orb spells clear and re-apply them.", ""]
    for v in all_variants:
        out += [f'new entry "{v["status"]}"', 'type "StatusData"', 'data "StatusType" "BOOST"',
                f'data "StackId" "{v["status"]}"', 'data "StackType" "Ignore"',
                f'data "StatusEffect" "{v["ids"][1]}"',
                'data "StatusPropertyFlags" "DisableOverhead;DisableCombatlog;DisablePortraitIndicator"', ""]
    out.append(STATUS_END)
    return "\n".join(out) + "\n"


def main():
    for d, pattern in ((OUT_DIR, ("VFX_Invoker_Orb_", "bank_VFX_Invoker_Orb_", "mei_INVOKER_ORB")),
                       (PREVIEW_DIR, ("VFX_Invoker_Orb_",))):
        if os.path.isdir(d):                     # drop stale outputs (names change when layouts change)
            for f in os.listdir(d):
                if f.startswith(pattern):
                    os.remove(os.path.join(d, f))
    os.makedirs(PREVIEW_DIR, exist_ok=True) if os.path.isdir(os.path.dirname(PREVIEW_DIR)) else None
    all_variants = [v for element in ELEMENTS for v in variants(element)]
    for v in all_variants:
        build(v)
    with open(os.path.join(OUT_DIR, "orbfx_statuses.txt"), "w", encoding="utf-8") as f:
        f.write(status_block(all_variants))
    print(f"{len(all_variants)} orb variants + orbfx_statuses.txt")


if __name__ == "__main__":
    main()
