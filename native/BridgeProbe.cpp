#include <BWAPI.h>
#include <Windows.h>
#include <iostream>

static_assert(sizeof(void*) == 4, "The module probe must be built for Win32.");

int wmain(int argc, wchar_t** argv) {
    if (argc != 2) {
        std::cerr << "Usage: StarForgeProbe.exe <BWAPI module DLL>\n";
        return 1;
    }
    HMODULE library = LoadLibraryW(argv[1]);
    if (!library) {
        std::cerr << "LoadLibrary failed: " << GetLastError() << '\n';
        return 2;
    }
    using Initialize = void(__cdecl*)(BWAPI::Game*);
    using Create = BWAPI::AIModule*(__cdecl*)();
    auto initialize = reinterpret_cast<Initialize>(GetProcAddress(library, "gameInit"));
    auto create = reinterpret_cast<Create>(GetProcAddress(library, "newAIModule"));
    if (!initialize || !create) {
        std::cerr << "Module is missing gameInit or newAIModule\n";
        FreeLibrary(library);
        return 3;
    }
    // Exercise module lifetime without calling any in-game callbacks.
    initialize(nullptr);
    auto module = create();
    if (!module) {
        std::cerr << "newAIModule returned null\n";
        FreeLibrary(library);
        return 4;
    }
    delete module;
    if (!FreeLibrary(library)) {
        std::cerr << "FreeLibrary failed: " << GetLastError() << '\n';
        return 5;
    }
    std::cout << "STARFORGE_MODULE_LOAD_OK pointer_bits=32 real_game_validated=false\n";
    return 0;
}
