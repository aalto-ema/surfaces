# Use an isolated destination and launch the installed executable outside the checkout.
$ErrorActionPreference = 'Stop'
$installer = @(Get-ChildItem 'dist\installer\*-setup.exe')
if ($installer.Count -ne 1) { throw "Expected one installer, found $($installer.Count)." }
$root = Join-Path $env:RUNNER_TEMP 'Surfaces installer smoke test'
$destination = Join-Path $root 'Installed app'
New-Item -ItemType Directory -Path $root -Force | Out-Null
$report = Join-Path $root 'smoke.txt'
$silent = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART'

function Invoke-CheckedProcess($executable, $arguments, $timeoutSeconds) {
    $process = Start-Process -FilePath $executable -ArgumentList $arguments `
        -WorkingDirectory $root -PassThru
    if (-not $process.WaitForExit($timeoutSeconds * 1000)) {
        $process.Kill()
        throw "$executable timed out."
    }
    if ($process.ExitCode -ne 0) {
        if (Test-Path -LiteralPath $report) { Get-Content -LiteralPath $report }
        throw "$executable returned $($process.ExitCode)."
    }
}

Invoke-CheckedProcess $installer[0].FullName `
    "$silent /SP- /DIR=`"$destination`" /LOG=`"$root\setup.log`"" 180
$app = Join-Path $destination 'Surfaces.exe'
if (-not (Test-Path -LiteralPath (Join-Path $destination 'THIRD-PARTY-NOTICES.txt'))) {
    throw 'The installer omitted third-party notices.'
}
Invoke-CheckedProcess $app "--installer-smoke-test `"$report`"" 120
if ((Get-Content -LiteralPath $report -Raw).Trim() -ne 'OK') { throw 'Missing smoke-test result.' }

$uninstaller = @(Get-ChildItem -LiteralPath $destination -Filter 'unins*.exe')
if ($uninstaller.Count -ne 1) { throw 'Could not identify the uninstaller.' }
Invoke-CheckedProcess $uninstaller[0].FullName "$silent /LOG=`"$root\uninstall.log`"" 180
# Inno Setup can finish cleanup in a separate process after the initial exe exits.
for ($i = 0; $i -lt 20 -and (Test-Path -LiteralPath $app); $i++) { Start-Sleep -Seconds 1 }
if (Test-Path -LiteralPath $app) { throw 'Uninstall did not remove Surfaces.exe.' }
