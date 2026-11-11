# Run with 64-bit Python 3.13, the installed project, PyInstaller and Inno Setup 6.
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

Push-Location (Join-Path $PSScriptRoot '..\..')
try {
    $version = python -c "from importlib.metadata import version; print(version('surfaces-app'))"
    if ($version -notmatch '^\d+\.\d+\.\d+(?:[a-z]+\d+)?$') {
        throw "Unsupported installer version: $version"
    }

    $iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
    if (-not $iscc) {
        $iscc = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
    }
    if (-not (Test-Path -LiteralPath $iscc)) {
        throw 'Inno Setup 6 was not found.'
    }

    python -m PyInstaller --noconfirm --clean --onedir --windowed --noupx --noarchive `
        --name Surfaces --icon NONE --specpath build --workpath build\pyinstaller `
        --collect-data ase --collect-submodules skimage.measure `
        --hidden-import ase.io.cif --hidden-import ase.io.extxyz --hidden-import ase.io.xyz `
        --hidden-import ase.io.trajectory --hidden-import ase.io.vasp `
        packaging\windows\launch.py

    python packaging\windows\notices.py dist\Surfaces
    & $iscc "/DAppVersion=$version" packaging\windows\Surfaces.iss

    $filename = "Surfaces-$version-windows-x64-setup.exe"
    $installer = Join-Path 'dist\installer' $filename
    $digest = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
    "$digest  $filename" | Set-Content -LiteralPath "$installer.sha256" -Encoding ascii
}
finally {
    Pop-Location
}
