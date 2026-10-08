-- Arcane Invoker's Gauntlets — grant to the host character's inventory once, on first load.
-- (Camp chest isn't treasure-table-addressable; the player can stash the gauntlets there afterward.)

local GAUNTLETS = "e6b53f1a-7082-4441-b0bf-7acded17a960"  -- INVOKER_ARCANE_GAUNTLETS RootTemplate

-- Persistent flag so the grant happens only once (LevelGameplayStarted fires on every region load).
Ext.Vars.RegisterModVariable(ModuleUUID, "GauntletsGranted", {
    Server = true,
    Persistent = true,
})

Ext.Osiris.RegisterListener("LevelGameplayStarted", 2, "after", function(level, isEditorMode)
    local host = Osi.GetHostCharacter()
    if host == nil then return end

    local vars = Ext.Vars.GetModVariables(ModuleUUID)
    if vars.GauntletsGranted then return end

    Osi.TemplateAddTo(GAUNTLETS, host, 1, 0)
    vars.GauntletsGranted = true
end)

-- ---------------------------------------------------------------------------------------------
-- SUN STRIKE: Dota-style damage split (Script Extender only).
--
-- Without Script Extender the data-only INVOKER_SUNSTRIKE runs: full damage in the inner 2 m, a smaller
-- burn on enemies out to 4 m. With Script Extender this file swaps the Invoke container's entry to
-- INVOKER_SUNSTRIKE_SE, which deals no damage itself. It only marks each creature it hits with
--     INVOKER_SUNSTRIKE_SPLIT_FULL        (cast with a level 3 slot)
--     INVOKER_SUNSTRIKE_SPLIT_FULL_<n>    (cast with a level n slot; each level above 3 adds 1d10)
-- Sun Strike has no saving throw (like Dota), so every creature marked takes its share. The marks from one
-- strike land in the same instant. We collect them, count N creatures hit, roll the damage ONCE and give
-- every creature roll / N.
--
-- Set ENABLE_SUNSTRIKE_SPLIT = false (here AND in BootstrapClient.lua) to go back to the data-only version.
-- Set DEBUG = false once it is verified in game to silence the console lines.
-- ---------------------------------------------------------------------------------------------
local ENABLE_SUNSTRIKE_SPLIT = true
local DEBUG = false

local BASE_SPELL = "INVOKER_SUNSTRIKE"
local SE_SPELL = "INVOKER_SUNSTRIKE_SE"
local CONTAINER = "INVOKER_INVOKE"
local MARK = "INVOKER_SUNSTRIKE_SPLIT_FULL"      -- cast with the base slot; INVOKER_SUNSTRIKE_SPLIT_FULL_<n> = cast with a level n slot
local BASE_SLOT = 3     -- Sun Strike's own slot level; every slot level above it adds one die (+1d10, like vanilla upcasting)
local DIE = 10          -- d10, like Levelmaps/LevelMapValues.lsx "InvokerSunStrike"
local SETTLE_TICKS = 3  -- ticks to wait after the last mark so every creature of the strike is counted

local function dbg(...)
    if DEBUG then Ext.Utils.Print("[Invoker]", ...) end
end

-- Mirrors the "InvokerSunStrike" level map (4d10 at levels 1-2 up to 12d10 at level 11-12 and 16d10 at level 19-20; above 20 uses the last value).
-- Keep in sync with source/Public/<mod>/Levelmaps/LevelMapValues.lsx.
local DICE_BY_LEVEL = { 4, 4, 6, 6, 8, 8, 9, 9, 10, 10, 12, 12, 13, 13, 14, 14, 15, 15, 16, 16 }
local function diceCount(level)
    level = math.max(1, math.min(#DICE_BY_LEVEL, math.floor(tonumber(level) or 1)))
    return DICE_BY_LEVEL[level]
end

local function rollTotal(level, extraDice)
    local total = 0
    for _ = 1, diceCount(level) + (extraDice or 0) do
        total = total + math.random(1, DIE)
    end
    return total
end

-- Swap the Sun Strike entry in the Invoke container. Idempotent, so it is safe to run on StatsLoaded and again on SessionLoaded.
local function swapContainerEntry(sync)
    local container = Ext.Stats.Get(CONTAINER)
    if container == nil or Ext.Stats.Get(SE_SPELL) == nil then
        dbg("swap skipped: stat missing", CONTAINER, SE_SPELL)
        return
    end
    local list = container.ContainerSpells
    if type(list) ~= "string" then
        dbg("swap skipped: ContainerSpells is", type(list))
        return
    end
    local out, changed = {}, false
    for token in list:gmatch("[^;]+") do
        if token == SE_SPELL then return end   -- already swapped
        if token == BASE_SPELL then
            token = SE_SPELL
            changed = true
        end
        out[#out + 1] = token
    end
    if not changed then return end
    container.ContainerSpells = table.concat(out, ";")
    if sync then pcall(function() container:Sync() end) end
    dbg("Invoke container now uses", SE_SPELL)
end

if ENABLE_SUNSTRIKE_SPLIT then
    pcall(function() math.randomseed(Ext.Utils.MonotonicTime()) end)   -- Lua 5.3 starts from a fixed seed otherwise

    local function subscribe(name, fn)
        local ok, err = pcall(function() Ext.Events[name]:Subscribe(fn) end)
        if not ok then Ext.Utils.PrintError("[Invoker] could not subscribe to " .. name .. ": " .. tostring(err)) end
    end

    local pending = {}     -- [causee] = { slot = slot level of the cast, victims = { { guid = ..., mark = status name }, ... } }
    local ticksLeft = 0

    local function isBlank(guid)
        return guid == nil or guid == "" or tostring(guid):find("^NULL_") ~= nil
    end

    -- Slot level a marker stands for: INVOKER_SUNSTRIKE_SPLIT_FULL = the base slot, INVOKER_SUNSTRIKE_SPLIT_FULL_<n> = a level n slot.
    local function slotOf(status)
        status = tostring(status)
        if status == MARK then return BASE_SLOT end
        local n = status:match("^" .. MARK .. "_(%d+)$")
        return n and tonumber(n) or nil
    end

    local function resolveStrike(causee, strike)
        local victims = strike.victims
        local n = #victims
        local extra = math.max(0, strike.slot - BASE_SLOT)
        local okLevel, level = pcall(Osi.GetLevel, causee)
        local total = rollTotal(okLevel and level or 1, extra)
        local share = math.max(1, math.floor(total / n))
        dbg(string.format("Sun Strike (slot %d): %d hit, rolled %d (+%d dice), %d each", strike.slot, n, total, extra, share))
        for _, victim in ipairs(victims) do
            pcall(Osi.RemoveStatus, victim.guid, victim.mark)
            local ok, err = pcall(Osi.ApplyDamage, victim.guid, share, "Fire", isBlank(causee) and victim.guid or causee)
            if not ok then Ext.Utils.PrintError("[Invoker] Sun Strike damage failed: " .. tostring(err)) end
        end
    end

    Ext.Osiris.RegisterListener("StatusApplied", 4, "after", function(object, status, causee, storyActionID)
        if tostring(status):sub(1, #MARK) ~= MARK then return end   -- cheap test first: this runs for every status in the game
        local slot = slotOf(status)
        if slot == nil then return end
        local key = isBlank(causee) and "unknown" or causee
        local strike = pending[key]
        if strike == nil then
            strike = { slot = slot, victims = {} }
            pending[key] = strike
        end
        strike.victims[#strike.victims + 1] = { guid = object, mark = status }
        ticksLeft = SETTLE_TICKS
    end)

    subscribe("Tick", function()
        if ticksLeft <= 0 then return end
        ticksLeft = ticksLeft - 1
        if ticksLeft > 0 then return end
        local batch = pending
        pending = {}
        for causee, strike in pairs(batch) do
            resolveStrike(causee == "unknown" and nil or causee, strike)
        end
    end)

    subscribe("StatsLoaded", function() swapContainerEntry(false) end)
    subscribe("SessionLoaded", function() swapContainerEntry(true) end)
    dbg("BootstrapServer.lua loaded: Sun Strike split enabled")
end
