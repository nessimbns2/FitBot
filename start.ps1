# FitBot Full-Stack Starter for Windows PowerShell
# Prerequisites (once): backend\.venv with requirements_v2.txt, frontend\node_modules,
# PostgreSQL running with the fitbot_db database (see database\README.md), backend\.env filled.
Write-Host "Starting FitBot Full-Stack App..." -ForegroundColor Cyan

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
Write-Host " Starting FastAPI backend on http://127.0.0.1:8000..." -ForegroundColor Green
$backendProc = Start-Process -FilePath $Python -ArgumentList "-m uvicorn main_v2:app --port 8000 --reload" -WorkingDirectory "$RootDir\backend" -PassThru

# Start Frontend in background process
Write-Host " Starting Vite frontend on http://localhost:5173..." -ForegroundColor Green
$frontendProc = Start-Process -FilePath "npm.cmd" -ArgumentList "run dev" -WorkingDirectory "$RootDir\frontend" -PassThru

Write-Host ""
Write-Host " Both services are running!" -ForegroundColor Yellow
Write-Host "   - Frontend:  http://localhost:5173"
Write-Host "   - Backend:   http://127.0.0.1:8000"
Write-Host "   - API Docs:  http://127.0.0.1:8000/docs"
Write-Host ""
Write-Host "Press Enter or Ctrl+C in this window to stop both servers..." -ForegroundColor Gray

try {
    [Console]::ReadLine()
} finally {
    Write-Host "Stopping servers..." -ForegroundColor Yellow
    if ($backendProc -and -not $backendProc.HasExited) { Stop-Process -Id $backendProc.Id -Force }
    if ($frontendProc -and -not $frontendProc.HasExited) { Stop-Process -Id $frontendProc.Id -Force }
    Write-Host "All processes stopped." -ForegroundColor Gray
}
