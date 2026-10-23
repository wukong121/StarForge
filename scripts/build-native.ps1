[CmdletBinding()]
param(
    [string]$WorkDir = (Join-Path $PSScriptRoot "../build/native")
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
Set-StrictMode -Version Latest

function Invoke-Checked {
    param([string]$Program, [string[]]$ArgumentList)
    & $Program @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "$Program failed with exit code $LASTEXITCODE"
    }
}

$repository = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$work = [IO.Path]::GetFullPath($WorkDir)
if ((Test-Path $work) -and @(Get-ChildItem -Force $work).Count -ne 0) {
    throw "Build directory must be empty: $work"
}
New-Item -ItemType Directory -Force $work | Out-Null
$artifact = Join-Path $work "artifact"
$dependencyOutput = Join-Path $work "bwapi-build"
New-Item -ItemType Directory $artifact, $dependencyOutput | Out-Null

$archiveUrl = "https://github.com/bwapi/bwapi/releases/download/v4.4.0/BWAPI.7z"
$expectedHash = "e6d1abeff2a9b31886d9ade15c5c783a32f7e973f1f0e7137911f3d083fa72e2"
$bwapiRevision = "7687da8abc4726f8366401f11ab648d421385793"
$archive = Join-Path $work "BWAPI.7z"
Invoke-WebRequest -Uri $archiveUrl -OutFile $archive
if ((Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedHash) {
    throw "BWAPI archive SHA256 does not match the pinned release bytes."
}
$sevenZip = (Get-Command 7z.exe -ErrorAction Stop).Source
Invoke-Checked $sevenZip @("x", $archive, "-o$(Join-Path $work 'sdk')", "-y")
$sdk = Join-Path $work "sdk/Release_Binary"
$vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio/Installer/vswhere.exe"
$installation = (Invoke-Checked $vswhere @(
    "-latest", "-version", "[17.0,18.0)", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
    "-property", "installationPath"
)).Trim()
if (-not $installation) {
    throw "Visual Studio with MSVC x86/x64 tools was not found."
}
$msbuild = Join-Path $installation "MSBuild/Current/Bin/MSBuild.exe"
$toolsVersion = (Get-Content (Join-Path $installation "VC/Auxiliary/Build/Microsoft.VCToolsVersion.default.txt")).Trim()
$dumpbin = Join-Path $installation "VC/Tools/MSVC/$toolsVersion/bin/Hostx64/x86/dumpbin.exe"
$outDir = $dependencyOutput + [IO.Path]::DirectorySeparatorChar
Invoke-Checked $msbuild @(
    (Join-Path $sdk "ExampleAIModule/ExampleAIModule.vcxproj"),
    "/m:2", "/p:Configuration=Release", "/p:Platform=Win32", "/p:PlatformToolset=v143",
    "/p:WindowsTargetPlatformVersion=10.0", "/p:OutDir=$outDir"
)
$library = Join-Path $dependencyOutput "BWAPILIB.lib"
if (-not (Test-Path $library)) {
    throw "The matching SDK did not produce BWAPILIB.lib."
}
$cmakeBuild = Join-Path $work "starforge"
Invoke-Checked "cmake" @(
    "-S", (Join-Path $repository "native"), "-B", $cmakeBuild,
    "-G", "Visual Studio 17 2022", "-A", "Win32",
    "-DBWAPI_ROOT=$sdk", "-DBWAPI_LIBRARY=$library"
)
Invoke-Checked "cmake" @("--build", $cmakeBuild, "--config", "Release", "--parallel", "2")
Copy-Item (Join-Path $cmakeBuild "Release/StarForge.dll") $artifact
Copy-Item (Join-Path $cmakeBuild "Release/StarForgeProbe.exe") $artifact
Copy-Item (Join-Path $dependencyOutput "ExampleAIModule.dll") $artifact

$probe = Join-Path $artifact "StarForgeProbe.exe"
$expectedProbeOutput = "STARFORGE_MODULE_LOAD_OK pointer_bits=32 real_game_validated=false"
$files = [ordered]@{}
foreach ($name in @("StarForge.dll", "ExampleAIModule.dll")) {
    $dll = Join-Path $artifact $name
    $headers = Invoke-Checked $dumpbin @("/headers", $dll)
    $exports = Invoke-Checked $dumpbin @("/exports", $dll)
    $imports = Invoke-Checked $dumpbin @("/dependents", $dll)
    $headers | Set-Content (Join-Path $artifact "$name.headers.txt")
    $exports | Set-Content (Join-Path $artifact "$name.exports.txt")
    $imports | Set-Content (Join-Path $artifact "$name.imports.txt")
    if (-not ($headers -match "14C machine \(x86\)") -or -not ($headers -match "10B magic # \(PE32\)")) {
        throw "$name is not PE32/i386."
    }
    foreach ($entry in @("gameInit", "newAIModule")) {
        if (-not ($exports -match "^\s+\d+\s+[0-9A-F]+\s+[0-9A-F]+\s+$entry(?:\s|$)")) {
            throw "$name does not export the exact entry point $entry."
        }
    }
    $probeOutput = (Invoke-Checked $probe @($dll)).Trim()
    if ($probeOutput -ne $expectedProbeOutput) {
        throw "Unexpected module probe output for ${name}: $probeOutput"
    }
    $files[$name] = [ordered]@{
        sha256 = (Get-FileHash $dll -Algorithm SHA256).Hash.ToLowerInvariant()
        pe = "PE32/i386"
        exports = @("gameInit", "newAIModule")
        dependencies = @($imports | ForEach-Object { $_.Trim() } | Where-Object { $_ -match "^[A-Za-z0-9_.-]+\.dll$" })
        module_lifetime_probe = $probeOutput
        real_game_validated = $false
    }
}
$files["StarForgeProbe.exe"] = @{
    sha256 = (Get-FileHash $probe -Algorithm SHA256).Hash.ToLowerInvariant()
}
& $probe
if ($LASTEXITCODE -ne 1) {
    throw "Probe did not reject a missing module argument."
}
& $probe (Join-Path $artifact "missing.dll")
if ($LASTEXITCODE -ne 2) {
    throw "Probe did not reject a missing DLL."
}
& $probe (Join-Path $env:WINDIR "SysWOW64/version.dll")
if ($LASTEXITCODE -ne 3) {
    throw "Probe did not reject a DLL without BWAPI entry points."
}

$relink = Join-Path $artifact "relink-source"
New-Item -ItemType Directory (Join-Path $relink "sdk/BWAPILIB"), (Join-Path $relink "sdk/ExampleAIModule"), (Join-Path $relink "StarForge/scripts") | Out-Null
Copy-Item -Recurse (Join-Path $sdk "include") (Join-Path $relink "sdk")
Copy-Item -Recurse (Join-Path $sdk "BWAPILIB/Source") (Join-Path $relink "sdk/BWAPILIB")
Copy-Item (Join-Path $sdk "BWAPILIB/UnitCommand.cpp"), (Join-Path $sdk "BWAPILIB/BWAPILIB.vcxproj") (Join-Path $relink "sdk/BWAPILIB")
Copy-Item -Recurse (Join-Path $sdk "ExampleAIModule/Source") (Join-Path $relink "sdk/ExampleAIModule")
Copy-Item (Join-Path $sdk "ExampleAIModule/ExampleAIModule.vcxproj") (Join-Path $relink "sdk/ExampleAIModule")
Copy-Item -Recurse (Join-Path $repository "native") (Join-Path $relink "StarForge")
Copy-Item $PSCommandPath (Join-Path $relink "StarForge/scripts")
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/bwapi/bwapi/$bwapiRevision/LICENSE" -OutFile (Join-Path $artifact "BWAPI-LGPL-3.0.txt")
Invoke-WebRequest -Uri "https://www.gnu.org/licenses/gpl-3.0.txt" -OutFile (Join-Path $artifact "GPL-3.0.txt")
@"
These modules use BWAPILIB 4.4.0 under LGPL-3.0. Its license, GPL-3.0,
library source, example source, and corresponding StarForge application source
are included. Modification of the library and reverse engineering for debugging
such modifications are not restricted by this artifact.
To relink, build sdk/BWAPILIB/BWAPILIB.vcxproj in Release/Win32 with MSVC,
then configure StarForge/native with BWAPI_ROOT pointing to sdk and BWAPI_LIBRARY
pointing to the resulting BWAPILIB.lib. No game files are included.
"@ | Set-Content (Join-Path $artifact "NOTICE.txt")
$revision = (Invoke-Checked "git" @("-C", $repository, "rev-parse", "HEAD")).Trim()
[ordered]@{
    schema_version = 1
    source_revision = $revision
    configuration = "Release"
    architecture = "Win32"
    msvc_tools_version = $toolsVersion
    bwapi = @{
        version = "4.4.0"
        source_revision = $bwapiRevision
        archive_url = $archiveUrl
        archive_sha256 = $expectedHash
    }
    files = $files
    real_game_validated = $false
} | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $artifact "manifest.json")
Write-Host "Native artifacts: $artifact"
