# Win32 bridge build and loading checks

## Scope and compatibility

The bridge targets original SC1 1.16.1 with BWAPI 4.4.0. It must remain a
PE32/i386 DLL built with an MSVC-compatible C++ ABI and the Release DLL runtime.
Linux GCC/MinGW is not a substitute for this check.

The official [BWAPI 4.4.0 release](https://github.com/bwapi/bwapi/releases/tag/v4.4.0)
does **not** ship prebuilt `.lib` files or `ExampleAIModule.dll`. Its archive
contains `Release_Binary/include`, the `BWAPILIB` static-library project and the
example project. The previous assumption of `lib/BWAPI.lib` was incorrect.
The library to build and link is **BWAPILIB.lib**, not an arbitrary import library.

Pinned inputs:

- Archive: the official release's `BWAPI.7z`.
- Observed/pinned archive SHA256:
  `e6d1abeff2a9b31886d9ade15c5c783a32f7e973f1f0e7137911f3d083fa72e2`.
  This pins the downloaded bytes; the release API did not provide a publisher
  digest, so this is not a separate publisher-signature verification.
- Corresponding release source revision:
  `7687da8abc4726f8366401f11ab648d421385793`.

## Reproducible Windows build

Use Windows with Visual Studio 2022's MSVC x86/x64 C++ tools, Windows 10 SDK,
CMake, 7-Zip on PATH and PowerShell. From the repository root:

```powershell
./scripts/build-native.ps1
```

The build directory must be empty. To preserve a previous build:

```powershell
./scripts/build-native.ps1 -WorkDir build/native-next
```

The script downloads and checks the pinned SDK, builds its official example and
BWAPILIB project, then configures/builds StarForge with the matching library.
It retargets the old `v141_xp` project to installed `v143`/Windows 10 tools without
editing SDK source. The actual MSVC tool version is recorded in the manifest.
This necessary retargeting is not proof that a real BWAPI game loads the module.

Manual CMake configuration after building the SDK library:

```powershell
cmake -S native -B build/native-manual -A Win32 `
  "-DBWAPI_ROOT=$env:BWAPI_ROOT" "-DBWAPI_LIBRARY=$env:BWAPI_LIBRARY"
cmake --build build/native-manual --config Release
```

`BWAPI_ROOT` is the extracted SDK directory containing `include/`.
`BWAPI_LIBRARY` is the absolute path to the matching **Release/Win32**
`BWAPILIB.lib` built with compatible MSVC tools. Do not mix versions or Debug
runtime objects. CMake retains the Windows/MSVC/32-bit guards.

## Artifact and verification

The independent `native/wine-route1` branch has a Windows-2022 build workflow.
It also supports manual dispatch and native-file pull requests.
[The build at `287aee0` passed](https://github.com/wukong121/StarForge/actions/runs/39926874158)
with MSVC tools 14.44.35207, including both positive module probes and all three
negative probe cases. The downloaded artifact's archive digest and file hashes
were checked again on the H100 host.
It does not merge the branch or upload any game assets. Artifacts expire after
seven days and contain:

- `StarForge.dll`, the upstream `ExampleAIModule.dll`, `StarForgeProbe.exe`.
- PE headers, exact exported entry points and imported dependency reports.
- A manifest with source revision, compiler version, SDK hash and DLL hashes.
- Library/example/application source and LGPL/GPL notices for relinking with
  a modified BWAPILIB. SDK/runtime binaries and games are not committed to Git.

Both DLLs must be PE32/i386 and export exact `gameInit` and `newAIModule` names.
The script runs the probe for each DLL and tests missing arguments, a missing
DLL, and a DLL without BWAPI entry points.

The probe only loads the module, resolves exports, calls `gameInit(nullptr)`,
creates and destroys an AIModule, and unloads the DLL. It intentionally calls
**no game callbacks**. Its success marker includes `real_game_validated=false`.
It can be run on Windows or through a separately verified Wine prefix:

```text
StarForgeProbe.exe <absolute-path-to-module.dll>
```

PE inspection and the loader probe check different things. Neither demonstrates
actual BWAPI injection, Game-interface ABI behavior, fog-of-war correctness,
game commands, terminal classification, or replay validity.

Both DLLs subsequently passed the same probe under Wine 9.0 on the H100 host,
including argument/file/export rejection cases. This used Wine's builtin CRT,
not an installed native VC redistributable. Logs and manifest copies are in
`runs/route1-20261023T083536Z/`; `real_game_validated` remains false.

## Real-game gate

After a legally obtained **1.16.1** installation is available:

1. Check game version and required MPQ/runtime files; keep assets outside Git.
2. Use a new isolated Wine prefix and install the required, verified CRT if needed.
3. First load the official example through a verified BWAPI launcher/injector.
4. Confirm actual commands and a saved replay.
5. Start the existing StarForge policy service, load StarForge as Terran, and
   complete a real match with terminal JSONL, bridge log and replay.

No automatic game-launch command is asserted here. Current Blizzard free-download
links resolve to a modern Battle.net installer, not a standalone 1.16.1 game.
Do not substitute that launcher, a Wine GUI probe or module-load success for this
gate. No unknown game repack or unofficial download is used.
