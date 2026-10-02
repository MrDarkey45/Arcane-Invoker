# Repack the Invoker mod from source/ into InvokerAbilities.pak
# Edit the mod files under .\source\ (Mods\... and Public\...), then run this to rebuild the .pak.
# The item RootTemplate is edited as .\roottemplate_src\merged.lsx (human-readable) and auto-converted
# to source\...\RootTemplates\merged.lsf here (the game only loads .lsf RootTemplates from a pak).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$lib  = "D:\Game Mods\Baldur's Gate 3\BG3 Mod Manager\_Lib"
$src  = Join-Path $root "source"
$out  = Join-Path $root "InvokerAbilities.pak"
$tool = Join-Path $root "tools\pakbuild\bin\Release\net8.0\pakbuild.dll"
$mod  = "InvokerAbilities_39a130d8-8e3d-6d6c-5a20-ae216d580752"
$master = Join-Path $root "roottemplate_src\merged.lsx"
$lsf    = Join-Path $src ("Public\" + $mod + "\RootTemplates\merged.lsf")

if (-not (Test-Path $tool)) { throw "packer not found: $tool" }

if (Test-Path $master) {
    Write-Host "Converting RootTemplate lsx -> lsf ..."
    dotnet $tool $lib convert $master $lsf
}

# Custom VFX (vfx_src\, see toolsfxcompileuild_orb.py): effect sources compile to .lsfx, and the bank / MultiEffectInfo
# masters convert to .lsf. Regenerate an orb source first with: python tools\vfxcompile\build_orb.py <element> <out>
$vfxSrc = Join-Path $root "vfx_src"
if (Test-Path $vfxSrc) {
    $pub = Join-Path $src ("Public\" + $mod)
    $fxDir   = Join-Path $pub "Assets\Effects\Effects_Banks\Invoker"
    $bankDir = Join-Path $pub "Content\Assets\Effects\Effects\[PAK]_Invoker"
    $meiDir  = Join-Path $pub "MultiEffectInfos"
    # These three folders hold only generated output: clear them so renamed/removed effects don't linger in the pak.
    foreach ($d in $fxDir, $bankDir, $meiDir) {
        New-Item -ItemType Directory -Force $d | Out-Null
        Get-ChildItem -LiteralPath $d -File | Remove-Item -Force
    }
    # Splice the generated visual-only orb statuses (build_orb.py -> orbfx_statuses.txt) into Status_BOOST.txt.
    $block = Join-Path $vfxSrc "orbfx_statuses.txt"
    if (Test-Path $block) {
        $boost = Join-Path $pub "Stats\Generated\Data\Status_BOOST.txt"
        $text = [IO.File]::ReadAllText($boost)
        $text = [regex]::Replace($text, '(?s)(\r?\n)*// >>> ORBFX BEGIN.*?// <<< ORBFX END\r?\n?', '')
        $gen = ([IO.File]::ReadAllText($block) -replace '\r?\n', "`r`n")
        [IO.File]::WriteAllText($boost, $text.TrimEnd() + "`r`n`r`n" + $gen, (New-Object Text.UTF8Encoding $false))
    }
    Get-ChildItem $vfxSrc -Filter "VFX_*.lsefx" | ForEach-Object {
        Write-Host "Compiling effect $($_.Name) ..."
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "tools\vfxcompile\compile-effect.ps1") `
            $_.FullName (Join-Path $fxDir ($_.BaseName + ".lsfx"))
        if ($LASTEXITCODE -ne 0) { throw "effect compile failed: $($_.Name)" }
    }
    Get-ChildItem $vfxSrc -Filter "bank_*.lsx" | ForEach-Object {
        dotnet $tool $lib convert $_.FullName (Join-Path -Path $bankDir -ChildPath ($_.BaseName.Substring(5) + ".lsf"))
    }
    Get-ChildItem $vfxSrc -Filter "mei_*.lsx" | ForEach-Object {
        # MEI files are named by their UUID, like vanilla.
        $uuid = [regex]::Match((Get-Content $_.FullName -Raw), 'id="UUID" type="guid" value="([0-9a-f-]+)"').Groups[1].Value
        dotnet $tool $lib convert $_.FullName (Join-Path $meiDir ($uuid + ".lsf"))
    }
}

Write-Host "Packing '$src' -> '$out' ..."
dotnet $tool $lib pack $src $out

# Install into the game's Mods folder so the game actually loads the new build.
$modsDir = Join-Path $env:LOCALAPPDATA "Larian Studios\Baldur's Gate 3\Mods"
if (Get-Process -Name "bg3","bg3_dx11","Glasses" -ErrorAction SilentlyContinue) {
    # Glasses.exe = the BG3 Toolkit, which also keeps the installed pak open.
    Write-Warning "BG3 or the Toolkit is running - close it, then copy '$out' into '$modsDir' yourself (or rerun this)."
} else {
    Copy-Item $out (Join-Path $modsDir "InvokerAbilities.pak") -Force
    Write-Host "Installed to $modsDir. Launch the game to test."
}
