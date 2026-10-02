# Headless AllSpark effect compile: .lsefx (editor XML) -> normalized .lsx -> .lsfx (game binary).
# Uses the BG3 Toolkit's own AllSpark DLLs, so no Toolkit GUI is needed.
# Proven 2026-09-29: VFX_Character_Spectre_HandFX_01 compiled this way is identical (order-insensitive)
# to the .lsfx Larian ships in GustavX.pak.
# Usage: powershell -File compile-effect.ps1 <in.lsefx> <out.lsfx>
param([Parameter(Mandatory)][string]$InPath, [Parameter(Mandatory)][string]$OutPath)
$ErrorActionPreference = "Stop"
$toolkit = "E:\SteamLibrary\steamapps\common\Baldurs Gate 3 Toolkit"
$defs    = "E:\SteamLibrary\steamapps\common\Baldurs Gate 3\Data\Editor\Config\AllSpark"
$lib     = "D:\Game Mods\Baldur's Gate 3\BG3 Mod Manager\_Lib"
$pakbuild = Join-Path $PSScriptRoot "..\pakbuild\bin\Release\net8.0\pakbuild.dll"

[AppDomain]::CurrentDomain.add_AssemblyResolve({ param($s, $e)
    $p = Join-Path "E:\SteamLibrary\steamapps\common\Baldurs Gate 3 Toolkit" (($e.Name -split ',')[0] + ".dll")
    if (Test-Path $p) { [Reflection.Assembly]::LoadFrom($p) } })
Add-Type -AssemblyName System.Xml.Linq
[void][Reflection.Assembly]::LoadFrom("$toolkit\AllSpark.DataLayer.dll")
[void][Reflection.Assembly]::LoadFrom("$toolkit\AllSpark.EffectCompiler.dll")

$md  = (New-Object AllSpark.DataLayer.Module.ModuleDefinition).Load("$defs\ModuleDefinition.xmd")
$cd  = (New-Object AllSpark.DataLayer.ComponentDefinition($md)).Load("$defs\ComponentDefinition.xcd")
$eff = (New-Object AllSpark.DataLayer.Effect($cd.PropertyDefinitionContainer, $md)).Load(
          [System.Xml.Linq.XDocument]::Load($InPath).Root)
$doc = (New-Object AllSpark.EffectCompiler.Compiler).Compile($eff)

# The compiler emits <region id="X"><node id="root">; LSLib keys regions by that top node name, so two
# "root" nodes collide and Dependencies is lost. The shipped format names the top node after its region.
foreach ($region in $doc.Root.Elements("region")) {
    $region.Element("node").SetAttributeValue("id", $region.Attribute("id").Value)
}
$tmpLsx = [IO.Path]::ChangeExtension($OutPath, ".tmp.lsx")
$tmpLsf = [IO.Path]::ChangeExtension($OutPath, ".tmp.lsf")
$doc.Save($tmpLsx)
dotnet $pakbuild $lib convert $tmpLsx $tmpLsf   # pakbuild picks format by extension; .lsfx is LSF renamed
Move-Item $tmpLsf $OutPath -Force
Remove-Item $tmpLsx
Write-Host "Compiled $InPath -> $OutPath"
