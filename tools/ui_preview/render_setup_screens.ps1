$ErrorActionPreference = "Stop"

$env:QT_QUICK_CONTROLS_STYLE = "Basic"
$env:QT_QUICK_BACKEND = "software"
$env:QML_DISABLE_DISK_CACHE = "1"

$qmlCommand = Get-Command qml -ErrorAction Stop
$qmlPath = $qmlCommand.Source
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent (Split-Path -Parent $scriptDir)
$outputDir = Join-Path $repoRoot "docs\\images\\setup-wizard"

New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;

public struct RECT {
    public int Left;
    public int Top;
    public int Right;
    public int Bottom;
}

public struct POINT {
    public int X;
    public int Y;
}

public static class NativeMethods {
    [DllImport("user32.dll")]
    public static extern bool GetClientRect(IntPtr hWnd, out RECT rect);

    [DllImport("user32.dll")]
    public static extern bool ClientToScreen(IntPtr hWnd, ref POINT point);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@

$scenes = @(
    @{ runner = "RenderSetupWelcome.qml"; output = "welcome.png" },
    @{ runner = "RenderSetupWifi.qml"; output = "wifi.png" },
    @{ runner = "RenderSetupOpenAi.qml"; output = "openai.png" },
    @{ runner = "RenderSetupCamera.qml"; output = "camera.png" },
    @{ runner = "RenderSetupGpio.qml"; output = "gpio.png" },
    @{ runner = "RenderSetupFinish.qml"; output = "finish.png" }
)

foreach ($scene in $scenes) {
    $runnerPath = Join-Path $scriptDir $scene.runner
    $outputPath = Join-Path $outputDir $scene.output
    Remove-Item $outputPath -ErrorAction SilentlyContinue

    $process = Start-Process -FilePath $qmlPath -ArgumentList "`"$runnerPath`"" -PassThru
    try {
        $handle = [IntPtr]::Zero
        for ($attempt = 0; $attempt -lt 40; $attempt += 1) {
            Start-Sleep -Milliseconds 250
            $process.Refresh()
            if ($process.MainWindowHandle -ne 0) {
                $handle = [IntPtr]$process.MainWindowHandle
                break
            }
        }

        if ($handle -eq [IntPtr]::Zero) {
            throw "No window handle found for $($scene.runner)."
        }

        [void][NativeMethods]::ShowWindow($handle, 5)
        [void][NativeMethods]::SetForegroundWindow($handle)
        Start-Sleep -Milliseconds 700

        $clientRect = New-Object RECT
        [void][NativeMethods]::GetClientRect($handle, [ref]$clientRect)

        $point = New-Object POINT
        $point.X = $clientRect.Left
        $point.Y = $clientRect.Top
        [void][NativeMethods]::ClientToScreen($handle, [ref]$point)

        $width = $clientRect.Right - $clientRect.Left
        $height = $clientRect.Bottom - $clientRect.Top

        $bitmap = New-Object System.Drawing.Bitmap $width, $height
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        try {
            $graphics.CopyFromScreen($point.X, $point.Y, 0, 0, $bitmap.Size)
            $bitmap.Save($outputPath, [System.Drawing.Imaging.ImageFormat]::Png)
        } finally {
            $graphics.Dispose()
            $bitmap.Dispose()
        }
    } finally {
        if (!$process.HasExited) {
            Stop-Process -Id $process.Id -Force
        }
    }
}

Write-Host "Rendered setup screenshots to $outputDir"
