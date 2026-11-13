# run-local-atlas.ps1
# Starts backend, worker, frontend — assumes MongoDB is Atlas (no local service needed)

$root = "C:\Users\Amal Varghese\Downloads\CRM"
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"

Write-Host "Starting LeadIntel CRM (Atlas mode)..." -ForegroundColor Cyan

# Backend API
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$backend'; if (Test-Path '.\venv\Scripts\Activate.ps1') { .\venv\Scripts\Activate.ps1 }; uvicorn app.main:app --reload --port 8000"
)

# Crawl Worker
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$backend'; if (Test-Path '.\venv\Scripts\Activate.ps1') { .\venv\Scripts\Activate.ps1 }; python -m app.workers.job_processor"
)

# Frontend UI
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$frontend'; npm run dev"
)

Write-Host "All services launched. Wait ~5 seconds, then open http://localhost:5173" -ForegroundColor Green
Write-Host "Watch the worker window for real crawl progress." -ForegroundColor Green
