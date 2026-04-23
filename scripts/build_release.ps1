param(
    [string]$PythonExe = "python",
    [string]$Version = "",
    [switch]$SkipTests,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Invoke-Checked {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $FilePath $($Arguments -join ' ')"
    }
}

function Copy-PathIfExists {
    param(
        [string]$Source,
        [string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Source)) {
        return
    }

    $parent = Split-Path -Parent $Destination
    if ($parent) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }

    Copy-Item -LiteralPath $Source -Destination $Destination -Force
}

function Find-InnoSetupCompiler {
    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }

    return $null
}

if (-not $Version) {
    $Version = & $PythonExe -c "from src.version import __version__; print(__version__)"
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to resolve application version from src/version.py"
    }
    $Version = $Version.Trim()
}

$VenvPath = Join-Path $RepoRoot ".venv-release"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
$BuildPath = Join-Path $RepoRoot "build"
$PyInstallerDist = Join-Path $RepoRoot "dist\ZONES"
$ReleaseRoot = Join-Path $RepoRoot "dist\ZONES-v$Version"
$ReleaseAppRoot = Join-Path $ReleaseRoot "app\ZONES"
$ReleaseDocsRoot = Join-Path $ReleaseRoot "docs"
$ReleaseMt4Root = Join-Path $ReleaseRoot "MT4"
$ReleaseInstallerRoot = Join-Path $ReleaseRoot "installer"
$ReleaseZip = Join-Path $RepoRoot "dist\ZONES-v$Version.zip"

Write-Step "Cleaning previous build artifacts"
@($BuildPath, $PyInstallerDist, $ReleaseRoot, $ReleaseZip) | ForEach-Object {
    if (Test-Path -LiteralPath $_) {
        Remove-Item -LiteralPath $_ -Recurse -Force
    }
}

Write-Step "Creating or reusing release virtual environment"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    Invoke-Checked -FilePath $PythonExe -Arguments @("-m", "venv", $VenvPath)
}

Write-Step "Installing release dependencies"
Invoke-Checked -FilePath $VenvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel")
if (Test-Path -LiteralPath "requirements.txt") {
    Invoke-Checked -FilePath $VenvPython -Arguments @("-m", "pip", "install", "-r", "requirements.txt")
}
Invoke-Checked -FilePath $VenvPython -Arguments @("-m", "pip", "install", "-e", ".[dev,build]")

if ((Test-Path -LiteralPath "tests") -and (-not $SkipTests)) {
    Write-Step "Running automated tests"
    Invoke-Checked -FilePath $VenvPython -Arguments @("-m", "unittest", "discover", "-s", "tests")
}

Write-Step "Building Windows executable with PyInstaller"
Invoke-Checked -FilePath $VenvPython -Arguments @("-m", "PyInstaller", "--clean", "--noconfirm", "ZONES.spec")

Write-Step "Creating release folder structure"
New-Item -ItemType Directory -Force -Path $ReleaseAppRoot, $ReleaseDocsRoot, $ReleaseMt4Root, $ReleaseInstallerRoot | Out-Null
Copy-Item -Path (Join-Path $PyInstallerDist "*") -Destination $ReleaseAppRoot -Recurse -Force

Write-Step "Collecting documentation"
$docFiles = @(
    "README.md",
    "LICENSE.md",
    "docs\INSTALL.md",
    "docs\RELEASE.md",
    "docs\TROUBLESHOOTING.md",
    "docs\GITHUB_RELEASE_CHECKLIST.md",
    "docs\mt4-python-architecture.md"
)
foreach ($doc in $docFiles) {
    $source = Join-Path $RepoRoot $doc
    $destination = Join-Path $ReleaseDocsRoot ([System.IO.Path]::GetFileName($doc))
    Copy-PathIfExists -Source $source -Destination $destination
}

Write-Step "Collecting MT4 release files"
$mt4Files = @(
    @{ Source = "MQL4\Experts\ZONES.mq4"; Destination = "Experts\ZONES.mq4" },
    @{ Source = "MQL4\Experts\ZONES.ex4"; Destination = "Experts\ZONES.ex4" },
    @{ Source = "MQL4\Include\ZonesBridge.mqh"; Destination = "Include\ZonesBridge.mqh" },
    @{ Source = "MQL4\Libraries\ZonesBridge.dll"; Destination = "Libraries\ZonesBridge.dll" },
    @{ Source = "MQL4\Indicators\ZigZag.mq4"; Destination = "Indicators\ZigZag.mq4" },
    @{ Source = "MQL4\Indicators\ZigZag.ex4"; Destination = "Indicators\ZigZag.ex4" },
    @{ Source = "MQL4\Presets\setting.set"; Destination = "Presets\setting.set" },
    @{ Source = "MQL4\Images\zones_ea.ico"; Destination = "Images\zones_ea.ico" }
)
foreach ($item in $mt4Files) {
    $source = Join-Path $RepoRoot $item.Source
    $destination = Join-Path $ReleaseMt4Root $item.Destination
    Copy-PathIfExists -Source $source -Destination $destination
}

$manifest = @{
    version = $Version
    built_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss zzz")
    executable = "app\ZONES\ZONES.exe"
    docs = @(
        "docs\INSTALL.md",
        "docs\RELEASE.md",
        "docs\TROUBLESHOOTING.md",
        "docs\GITHUB_RELEASE_CHECKLIST.md"
    )
    mt4 = @(
        "MT4\Experts\ZONES.mq4",
        "MT4\Experts\ZONES.ex4",
        "MT4\Include\ZonesBridge.mqh",
        "MT4\Indicators\ZigZag.mq4",
        "MT4\Indicators\ZigZag.ex4",
        "MT4\Presets\setting.set"
    )
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -Path (Join-Path $ReleaseRoot "release-manifest.json") -Encoding UTF8

if (-not $SkipInstaller) {
    Write-Step "Building Inno Setup installer"
    $iscc = Find-InnoSetupCompiler
    if ($null -eq $iscc) {
        Write-Warning "Inno Setup 6 was not found. Skipping installer build."
    }
    else {
        Invoke-Checked -FilePath $iscc -Arguments @(
            "/DAppVersion=$Version",
            "/DReleaseRoot=$ReleaseRoot",
            (Join-Path $RepoRoot "installer\ZONES.iss")
        )
    }
}

Write-Step "Creating release zip archive"
Compress-Archive -Path $ReleaseRoot -DestinationPath $ReleaseZip -Force

Write-Host ""
Write-Host "Release complete." -ForegroundColor Green
Write-Host "Folder : $ReleaseRoot"
Write-Host "Zip    : $ReleaseZip"
if (-not $SkipInstaller) {
    Write-Host "Setup  : $ReleaseInstallerRoot"
}
