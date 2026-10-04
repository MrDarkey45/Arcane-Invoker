-- Arcane Invoker: client side of the Sun Strike damage split (see BootstrapServer.lua for the full explanation).
-- The Invoke container's child list is read by the UI on the client, so the swap INVOKER_SUNSTRIKE -> INVOKER_SUNSTRIKE_SE
-- has to be made here as well as on the server. Without Script Extender neither file runs and the data-only version is used.
--
-- Keep ENABLE_SUNSTRIKE_SPLIT in step with BootstrapServer.lua.

local ENABLE_SUNSTRIKE_SPLIT = true
local DEBUG = false

local BASE_SPELL = "INVOKER_SUNSTRIKE"
local SE_SPELL = "INVOKER_SUNSTRIKE_SE"
local CONTAINER = "INVOKER_INVOKE"

local function dbg(...)
    if DEBUG then Ext.Utils.Print("[Invoker client]", ...) end
end

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
    local function subscribe(name, fn)
        local ok, err = pcall(function() Ext.Events[name]:Subscribe(fn) end)
        if not ok then Ext.Utils.PrintError("[Invoker] could not subscribe to " .. name .. ": " .. tostring(err)) end
    end
    subscribe("StatsLoaded", function() swapContainerEntry(false) end)
    subscribe("SessionLoaded", function() swapContainerEntry(true) end)
    dbg("BootstrapClient.lua loaded: Sun Strike split enabled")
end
