# FitBot Full-Stack Starter for Windows PowerShell
Write-Host "🏋️  Starting FitBot Full-Stack App..." -ForegroundColor Cyan

$RootDir = $PSScriptRoot

# Start Backend in background process
Write-Host " Starting FastAPI backend on http://127.0.0.1:8000..." -ForegroundColor Green
$backendProc = Start-Process -FilePath "python" -ArgumentList "-m uvicorn main_v2:app --port 8000 --reload" -WorkingDirectory "$RootDir\backend" -PassThru


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
