param([Parameter(Mandatory = $true)][string]$ManifestPath)
$ErrorActionPreference = 'Stop'
$update = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$source = [IO.Path]::GetFullPath([string]$update.source)
$target = [IO.Path]::GetFullPath([string]$update.target)
$suffix = [guid]::NewGuid().ToString('N')
$staged = "$target.next-$suffix"
$backup = "$target.previous-$suffix.exe"
$replaced = $false

function Write-UpdateLog([string]$Message) {
    Add-Content -LiteralPath $update.log -Value ("{0:o} {1}" -f [DateTime]::Now, $Message) -Encoding UTF8
}

try {
    if ($source -eq $target) { throw 'The downloaded file must differ from the installed executable.' }
    Write-UpdateLog 'Waiting for the running application to exit.'
    $running = Get-Process -Id ([int]$update.source_pid) -ErrorAction SilentlyContinue
    if ($running -and -not $running.WaitForExit(120000)) {
        throw 'The running application did not exit within two minutes.'
    }

    # Never remove any _MEI directory. Other apps or the old bootloader may use it.
    Copy-Item -LiteralPath $source -Destination $staged
    $stream = [IO.File]::OpenRead($staged)
    $hasher = [Security.Cryptography.SHA256]::Create()
    try {
        $actual = [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '')
    } finally {
        $stream.Dispose()
        $hasher.Dispose()
    }
    if ($actual -ne $update.sha256) { throw 'The downloaded executable changed before installation.' }

    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            # Replace on the same volume, retaining the previous executable.
            [IO.File]::Replace($staged, $target, $backup)
            $replaced = $true
            break
        } catch {
            if ($attempt -eq 59) { throw }
            Start-Sleep -Milliseconds 500
        }
    }

    foreach ($entry in @(Get-ChildItem Env:)) {
        if ($entry.Name -like '_PYI_*' -or $entry.Name -like '_MEIPASS*') {
            [Environment]::SetEnvironmentVariable($entry.Name, $null, 'Process')
        }
    }
    $env:PYTHONHOME = $null
    $env:PYTHONPATH = $null
    $env:PYINSTALLER_RESET_ENVIRONMENT = '1'
    Write-UpdateLog "Starting updated application. Previous version: $backup"
    # Reopening the GUI is the action the user requested when accepting restart.
    Start-Process -FilePath $target -WorkingDirectory ([IO.Path]::GetDirectoryName($target)) | Out-Null
    Write-UpdateLog 'Update installed and application launched.'
    Remove-Item -LiteralPath $source -Force -ErrorAction SilentlyContinue
} catch {
    $failure = $_
    if ($replaced -and (Test-Path -LiteralPath $backup)) {
        try {
            [IO.File]::Replace($backup, $target, $null)
            Write-UpdateLog 'Restored the previous executable after the launch failed.'
        } catch {
            Write-UpdateLog "The previous executable is available at: $backup"
        }
    }
    Write-UpdateLog "Update failed: $failure"
    exit 1
} finally {
    if (Test-Path -LiteralPath $staged) {
        Remove-Item -LiteralPath $staged -Force -ErrorAction SilentlyContinue
    }
}
