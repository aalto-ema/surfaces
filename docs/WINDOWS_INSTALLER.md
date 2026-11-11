# Windows installer

Surfaces provides an x64 setup executable built by the
[Windows installer workflow](https://github.com/aalto-ema/surfaces/actions/workflows/windows-installer.yml).
It bundles Python and the required libraries. Setup installs for the current
account without requiring administrator privileges by default.

1. Sign in to GitHub, select a successful workflow run for the version you want,
   and download the **Surfaces-Windows-x64** artifact.
2. Extract the ZIP and run `Surfaces-<version>-windows-x64-setup.exe`.
   The default location is `%LOCALAPPDATA%\Programs\Surfaces`.
3. Open **Surfaces** from Start. To remove it, select Surfaces in **Settings →
   Apps → Installed apps**. Save projects outside the installation directory.

The executable is unsigned, so Windows may display an unknown-publisher warning.
To check that the downloaded executable matches the build, run this in PowerShell
and compare the hash with the first field in the included `.sha256` file:

```powershell
Get-FileHash .\Surfaces-0.1.0-windows-x64-setup.exe -Algorithm SHA256
```

The checksum checks file integrity; it is not a code signature. Artifacts are
retained for 30 days. GitHub sign-in is required for artifact downloads. The
workflow does not publish a GitHub Release.

## Build and verify

The workflow builds on Windows Server 2025 x64 after relevant changes or via
**Run workflow**. It freezes the app with PyInstaller and compiles the setup
executable with Inno Setup 6. Before upload it installs into an isolated test
directory, starts the packaged Qt window, renders the default slab, tests ASE
imports and particle generation, exports a transparent PNG, and uninstalls.

To rebuild locally, install x64 Python 3.13, PowerShell 7, and Inno Setup 6, then
run the following from a clean checkout:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install . "PyInstaller==6.22.3"
./packaging/windows/build.ps1
```

The executable and checksum are in `dist\installer`. The bundle includes
`THIRD-PARTY-NOTICES.txt` and license files. The frozen app includes ASE readers
for CIF, XYZ, extended XYZ, trajectory, and VASP files; other dynamically
loaded ASE readers may require running from source.
