# RSHC Asset Kit (experimental): turns the model named in part.json into an installable RSHC part pack.
#   import -> materials and part definition -> cook for Windows -> containers -> checks -> Install folder + zip
param(
    [string]$Retoc = '',
    [string]$EngineBin = '',
    [switch]$SkipImport
)
$ErrorActionPreference = 'Stop'
$kit = Split-Path -Parent $PSScriptRoot

function Stop-Kit([string]$message) {
    Write-Host ''
    Write-Host "STOPPED: $message" -ForegroundColor Red
    exit 1
}

# ---- where things are
if ($kit -match '\s') { Stop-Kit "The kit folder has a space in its path ($kit). Move it somewhere like C:\RSHCKit; Unreal's command line does not cope with spaces here." }
if ($kit.Length -gt 90) { Stop-Kit "The kit folder path is $($kit.Length) characters long ($kit). Move it to a short path like C:\RSHCKit: cooked files fail above 260 characters." }

if (-not $EngineBin) {
    $EngineBin = 'C:\Program Files\Epic Games\UE_5.6\Engine\Binaries\Win64'
    try {
        $installed = (Get-ItemProperty 'HKLM:\SOFTWARE\EpicGames\Unreal Engine\5.6' -ErrorAction Stop).InstalledDirectory
        if ($installed) { $EngineBin = Join-Path $installed 'Engine\Binaries\Win64' }
    } catch {}
}
$editor = Join-Path $EngineBin 'UnrealEditor-Cmd.exe'
$pakTool = Join-Path $EngineBin 'UnrealPak.exe'
if (-not (Test-Path -LiteralPath $editor -PathType Leaf)) { Stop-Kit "Unreal Engine 5.6 was not found at $EngineBin. Install 5.6 from the Epic launcher, or run: BUILD.cmd -EngineBin ""<your UE_5.6>\Engine\Binaries\Win64""" }
if (-not (Test-Path -LiteralPath $pakTool -PathType Leaf)) { Stop-Kit "UnrealPak.exe is missing from $EngineBin." }
if (-not $Retoc) { $Retoc = Join-Path $PSScriptRoot 'retoc\retoc.exe' }
if (-not (Test-Path -LiteralPath $Retoc -PathType Leaf)) { Stop-Kit "retoc.exe was not found at $Retoc. Read Tools\retoc\PUT-RETOC-HERE.txt." }

$configPath = Join-Path $kit 'part.json'
if (-not (Test-Path -LiteralPath $configPath)) { Stop-Kit 'part.json is missing.' }
try { $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json } catch { Stop-Kit "part.json is not valid JSON: $($_.Exception.Message)" }
$pack = [string]$config.pack
if ($pack -notmatch '^[A-Za-z][A-Za-z0-9]{2,23}$') { Stop-Kit 'part.json: "pack" must be 3 to 24 letters or digits, starting with a letter.' }

$project = Join-Path $kit 'UnrealProject\RSHCAssetKit.uproject'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$build = Join-Path $kit "Build\$stamp"
New-Item -ItemType Directory -Force -Path $build | Out-Null
$env:RSHC_KIT_BUILD = $build
$shaders = Join-Path $build 'Shaders'
$cooked = Join-Path $build 'Cooked'
$stage = Join-Path $build 'Stage'
$install = Join-Path $build 'Install'
$packDir = Join-Path $install "RSDragonwilds\Content\Paks\~mods\$pack"
$partsDir = Join-Path $install 'RSDragonwilds\Binaries\Win64\ue4ss\Mods\RSHC\Parts'
New-Item -ItemType Directory -Force -Path $packDir, $partsDir | Out-Null
$common = @('-unattended', '-nosplash', '-nosound', '-nop4', '-DDC=RSHCKitCache', "-ShaderWorkingDir=$shaders")

function Invoke-Unreal([string]$what, [string[]]$arguments, [string]$log) {
    Write-Host "== $what"
    & $editor $project @arguments @common "-abslog=$log" | Out-Null
    $code = $LASTEXITCODE
    $errorFile = Join-Path $build 'kit-error.txt'
    if (Test-Path -LiteralPath $errorFile) { Stop-Kit (Get-Content -LiteralPath $errorFile -Raw) }
    if ($code -ne 0) { Stop-Kit "$what failed (exit code $code). The reason is near the end of $log" }
}

# ---- 1 and 2: import, then materials and the part definition
if (-not $SkipImport) {
    Invoke-Unreal 'Importing the model (1 of 5)' @('-run=pythonscript', "-script=$PSScriptRoot\import_part.py", '-NullRHI') (Join-Path $build 'import.log')
} else {
    Write-Host '== Import skipped: using what is saved in the Unreal project, materials kept as they are'
    $env:RSHC_KIT_KEEP = '1'
}
Invoke-Unreal 'Preparing materials and the part definition (2 of 5)' @('-run=pythonscript', "-script=$PSScriptRoot\prepare_part.py", '-NullRHI') (Join-Path $build 'prepare.log')
$reportPath = Join-Path $build 'part-report.json'
if (-not (Test-Path -LiteralPath $reportPath)) { Stop-Kit "The preparation step wrote no report. See $build\prepare.log" }
$report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json

# Windows refuses paths over 260 characters, and the cook then fails with unclear messages.
$longest = "$cooked\RSHCAssetKit\Content\" + ($report.cookDir -replace '/', '\') + '\' + (Split-Path $report.meshPackage -Leaf) + '_PhysicsAsset.uasset'
if ($longest.Length -gt 245) { Stop-Kit "The cooked files would have paths of about $($longest.Length) characters; Windows allows 260. Move the kit to a shorter folder (C:\RSHCKit), or shorten the pack name or the model file name." }

# ---- 3: cook
$cookDir = Join-Path $kit ('UnrealProject\Content\' + ($report.cookDir -replace '/', '\'))
Write-Host '== Cooking for Windows (3 of 5). The first build compiles the engine shaders and can take 30 to 60 minutes; later builds take a few.'
$cookLog = Join-Path $build 'cook.log'
& $editor $project '-run=Cook' '-TargetPlatform=Windows' '-CookSkipRequests' '-SkipEditorContent' '-NoZenStore' '-noiostore' "-OutputDir=$cooked" "-CookDir=$cookDir" @common "-abslog=$cookLog" | Out-Null
if ($LASTEXITCODE -ne 0) { Stop-Kit "The cook failed. Search $cookLog for 'Error:'." }
$cookedPack = Join-Path $cooked "RSHCAssetKit\Content\Mods\$pack"
if (-not (Test-Path -LiteralPath $cookedPack)) { Stop-Kit "The cook produced nothing under Content\Mods\$pack. See $cookLog" }
if (Get-ChildItem -LiteralPath (Join-Path $cooked 'RSHCAssetKit\Content') -Filter 'ShaderArchive-*.ushaderbytecode' -ErrorAction SilentlyContinue) {
    Stop-Kit 'The cook wrote a shared shader archive. UnrealProject\Config\DefaultGame.ini must keep bShareMaterialShaderCode=False.'
}

# ---- 4: containers
Write-Host '== Packing (4 of 5)'
$stagedPack = Join-Path $stage "RSDragonwilds\Content\Mods\$pack"
New-Item -ItemType Directory -Force -Path (Split-Path $stagedPack -Parent) | Out-Null
Copy-Item -LiteralPath $cookedPack -Destination $stagedPack -Recurse
$utoc = Join-Path $packDir "${pack}_P.utoc"
& $Retoc to-zen --version UE5_6 $stage $utoc
if ($LASTEXITCODE -ne 0) { Stop-Kit 'retoc could not write the container.' }
& $Retoc verify $utoc
if ($LASTEXITCODE -ne 0) { Stop-Kit 'retoc could not read back the container it wrote.' }
# The pack's own asset list goes to a private place. It must never be written to the game's own AssetRegistry.bin.
$registry = Join-Path $cooked 'RSHCAssetKit\AssetRegistry.bin'
$response = Join-Path $build 'registry-response.txt'
Set-Content -LiteralPath $response -Encoding ascii -Value ('"' + $registry + '" "../../../RSDragonwilds/Mods/' + $pack + '/AssetRegistry.bin"')
$pak = Join-Path $packDir "${pack}_P.pak"
& $pakTool $pak "-Create=$response" -compress | Out-Null
if ($LASTEXITCODE -ne 0) { Stop-Kit 'UnrealPak could not write the .pak.' }
& $pakTool $pak -Test | Out-Null
if ($LASTEXITCODE -ne 0) { Stop-Kit 'The .pak failed its integrity test.' }
Copy-Item -LiteralPath (Join-Path $build $report.manifest) -Destination $partsDir

# ---- 5: checks on what was actually cooked
Write-Host '== Checking (5 of 5)'
$problems = @()
$meshName = Split-Path ($report.meshPackage) -Leaf
$meshFiles = Get-ChildItem -LiteralPath $stagedPack -Recurse -File | Where-Object { $_.BaseName -eq $meshName }
if (-not ($meshFiles | Where-Object Extension -eq '.uexp')) { $problems += "The cooked mesh $meshName is missing." }
$latin = [System.Text.Encoding]::GetEncoding(28591)
$meshText = ($meshFiles | ForEach-Object { $latin.GetString([System.IO.File]::ReadAllBytes($_.FullName)) }) -join ''
foreach ($morph in $report.morphs) { if (-not $meshText.Contains($morph)) { $problems += "Morph '$morph' is not in the cooked mesh." } }
foreach ($slot in $report.slots) { if ($slot.section -and -not $meshText.Contains($slot.name)) { $problems += "Material slot '$($slot.name)' is not in the cooked mesh." } }
if ($meshText.Contains('/Interchange/') -or $meshText.Contains('/Engine/EngineMaterials/')) { $problems += 'The cooked mesh still points at an importer or engine material, which the game does not have.' }
foreach ($slot in $report.slots) {
    $materialName = ($slot.material -split '\.')[-1]
    $materialFiles = Get-ChildItem -LiteralPath $stagedPack -Recurse -File | Where-Object { $_.BaseName -eq $materialName }
    if (-not $materialFiles) { $problems += "Material $materialName (slot $($slot.name)) was not cooked into the pack."; continue }
    if ($slot.source -eq 'tint') {
        $materialText = ($materialFiles | ForEach-Object { $latin.GetString([System.IO.File]::ReadAllBytes($_.FullName)) }) -join ''
        if (-not $materialText.Contains('RSHCColor')) { $problems += "Material $materialName has no RSHCColor parameter after cooking; the in-game colour would do nothing." }
    }
}
$cookText = Get-Content -LiteralPath $cookLog -Raw
if ($cookText -match 'Failed to compile Material') { $problems += "A material failed to compile for one of the shader formats (search cook.log for 'Failed to compile Material'); it would show as a grey checkerboard." }
$long = Get-ChildItem -LiteralPath $stagedPack -Recurse -File | Where-Object { $_.FullName.Length -gt 250 }
if ($long) { $problems += 'Some cooked paths are close to the 260 character limit; use a shorter kit folder, pack name or model name.' }
foreach ($ext in 'pak', 'utoc', 'ucas') { if (-not (Test-Path -LiteralPath (Join-Path $packDir "${pack}_P.$ext"))) { $problems += "${pack}_P.$ext was not written." } }
if ($problems.Count) { Stop-Kit ("The pack was built but did not pass the checks:`n - " + ($problems -join "`n - ")) }

$readme = @"
$($config.label) ($($report.id)) - RSHC part pack

Needs RSHC (RuneScape: Dragonwilds) installed. Close the game, then copy the RSDragonwilds folder from this zip
over the RSDragonwilds folder of your game install (merge, nothing is replaced). Start the game and open the RSHC
editor: the part is under "$(if ($config.slotLabel) { $config.slotLabel } else { $config.slot })".

In co-op every player needs this pack to see the part.

To remove it, delete:
  RSDragonwilds\Content\Paks\~mods\$pack
  RSDragonwilds\Binaries\Win64\ue4ss\Mods\RSHC\Parts\$($report.manifest)
"@
Set-Content -LiteralPath (Join-Path $install 'READ ME.txt') -Value $readme -Encoding utf8
$zip = Join-Path $build "$pack.zip"
Compress-Archive -Path (Join-Path $install '*') -DestinationPath $zip -Force

Write-Host ''
Write-Host "DONE: $($report.id)" -ForegroundColor Green
Write-Host "  sliders from morphs : $(if ($report.morphs) { $report.morphs -join ', ' } else { 'none' })"
Write-Host "  colour sections     : $(if ($report.sections) { ($report.sections | ForEach-Object { $_.id + ' (' + $_.source + ')' }) -join ', ' } else { 'none' })"
Write-Host "  to test             : close the game, copy $install\RSDragonwilds over your game's RSDragonwilds folder"
Write-Host "  to share            : $zip"
