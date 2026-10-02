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
