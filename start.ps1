# FitBot Full-Stack Starter for Windows PowerShell
# Prerequisites (once): backend\.venv with requirements_v2.txt, frontend\node_modules,
# PostgreSQL running with the fitbot_db database (see database\README.md), backend\.env filled.
Write-Host "Starting FitBot Full-Stack App..." -ForegroundColor Cyan

function Test-LocalPort([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try { return $client.ConnectAsync('127.0.0.1', $Port).Wait(500) }
    catch { return $false }
    finally { $client.Dispose() }
}

function Stop-StartedService([System.Diagnostics.Process]$ServiceProcess) {
    $ServiceProcess.Refresh()
    if ($ServiceProcess.HasExited) { return }
    # Uvicorn --reload and Python venv launchers create child processes.
    # Follow only descendants of a process started by this script.
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $($ServiceProcess.Id)" -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        $childProcess = Get-Process -Id $child.ProcessId -ErrorAction SilentlyContinue
        if ($childProcess) { Stop-StartedService $childProcess }
    }
    Stop-Process -Id $ServiceProcess.Id -Force -ErrorAction SilentlyContinue
}

$reuseBackend = $false
$reuseFrontend = $false
if (Test-LocalPort 8000) {
    try {
        $spec = Invoke-RestMethod 'http://127.0.0.1:8000/openapi.json' -TimeoutSec 3
        $ready = Invoke-RestMethod 'http://127.0.0.1:8000/api/health/ready' -TimeoutSec 3
        $reuseBackend = $spec.info.title -eq 'Fitness Coach API' -and $ready.database -eq 'ok'
    } catch { }
    if (-not $reuseBackend) { throw 'Port 8000 is occupied by another service or an unready API. Check the existing server first.' }
}
if (Test-LocalPort 5173) {
    try {
        $page = Invoke-WebRequest 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 3
        $reuseFrontend = $page.Content -match '<title>FitBot\s*\|'
    } catch { }
    if (-not $reuseFrontend) { throw 'Port 5173 is occupied by another application. Check the existing server first.' }
}

$RootDir = $PSScriptRoot
$Python = Join-Path $RootDir "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Host "backend\.venv not found - using the system python" -ForegroundColor Yellow
    $Python = "python"
}

# Database migrations (idempotent) - the API also runs them at startup
Write-Host " Applying database migrations (alembic upgrade head)..." -ForegroundColor Green
# (run from backend\ so that backend\.env is picked up)
Push-Location "$RootDir\backend"
& $Python -m alembic upgrade head
$migrationExit = $LASTEXITCODE
Pop-Location
if ($migrationExit -ne 0) {
    Write-Host "Migrations failed: is PostgreSQL running and DATABASE_URL correct in backend\.env?" -ForegroundColor Red
    exit 1
}

# Start Backend in background process
try {
Write-Host " Starting FastAPI backend on http://127.0.0.1:8000..." -ForegroundColor Green
$backendProc = $null
if ($reuseBackend) {
    Write-Host ' Backend already running on port 8000; reusing it.' -ForegroundColor Cyan
} else {
    $backendProc = Start-Process -FilePath $Python -ArgumentList "-m uvicorn main_v2:app --host 127.0.0.1 --port 8000 --reload" -WorkingDirectory "$RootDir\backend" -WindowStyle Hidden -PassThru
}

# Start Frontend in background process
Write-Host " Starting Vite frontend on http://localhost:5173..." -ForegroundColor Green
$frontendProc = $null
if ($reuseFrontend) {
    Write-Host ' Frontend already running on port 5173; reusing it.' -ForegroundColor Cyan
} else {
    $frontendProc = Start-Process -FilePath "npm.cmd" -ArgumentList "run dev -- --strictPort" -WorkingDirectory "$RootDir\frontend" -WindowStyle Hidden -PassThru
}

Write-Host ""
foreach ($service in @(@{Port=8000; Process=$backendProc}, @{Port=5173; Process=$frontendProc})) {
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    while (-not (Test-LocalPort $service.Port)) {
        if ($service.Process) {
            $service.Process.Refresh()
            if ($service.Process.HasExited) { throw "The service on port $($service.Port) failed to start." }
        }
        if ($timer.Elapsed.TotalSeconds -gt 45) { throw "The service on port $($service.Port) did not start within 45 seconds." }
        Start-Sleep -Milliseconds 500
    }
}

Write-Host " Both service ports are available." -ForegroundColor Yellow
Write-Host "   - Frontend:  http://localhost:5173"
Write-Host "   - Backend:   http://127.0.0.1:8000"
Write-Host "   - API Docs:  http://127.0.0.1:8000/docs"
Write-Host ""
if ($reuseBackend -and $reuseFrontend) {
    Write-Host 'FitBot was already running. No duplicate server was started.' -ForegroundColor Green
    return
}
Write-Host "Press Enter or Ctrl+C in this window to stop services started here..." -ForegroundColor Gray

    [Console]::ReadLine()
} finally {
    Write-Host "Stopping servers..." -ForegroundColor Yellow
    if ($backendProc) { Stop-StartedService $backendProc }
    if ($frontendProc) { Stop-StartedService $frontendProc }
    Write-Host "Services started here have stopped; reused services remain running." -ForegroundColor Gray
}
