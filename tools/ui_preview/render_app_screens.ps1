$ErrorActionPreference = "Stop"

$env:QT_QUICK_CONTROLS_STYLE = "Basic"
$env:QT_QUICK_BACKEND = "software"
$env:QML_DISABLE_DISK_CACHE = "1"

$qmlPath = (Get-Command qml -ErrorAction Stop).Source
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent (Split-Path -Parent $scriptDir)
$outputDir = Join-Path $repoRoot "docs\images\app-screens"

New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$scenes = @(
    @{ runner = "RenderAppHome.qml"; output = "home.png" },
    @{ runner = "RenderDeviceActions.qml"; output = "device-actions.png" },
    @{ runner = "RenderAppCamera.qml"; output = "camera.png" },
    @{ runner = "RenderAppProcessing.qml"; output = "processing.png" },
    @{ runner = "RenderAppResult.qml"; output = "result.png" },
    @{ runner = "RenderAppError.qml"; output = "error.png" },
    @{ runner = "RenderAppHistory.qml"; output = "history.png" },
    @{ runner = "RenderAppHistoryDetail.qml"; output = "history-detail.png" }
)

foreach ($scene in $scenes) {
    $runnerPath = Join-Path $scriptDir $scene.runner
    $outputPath = Join-Path $outputDir $scene.output
    Remove-Item $outputPath -ErrorAction SilentlyContinue
    & $qmlPath $runnerPath
    if ($LASTEXITCODE -ne 0) {
        throw "Preview render failed for $($scene.runner)."
    }
    if (!(Test-Path -LiteralPath $outputPath)) {
        throw "Preview image was not created for $($scene.runner)."
    }
}

Write-Host "Rendered app screenshots to $outputDir"
