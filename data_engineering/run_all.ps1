# run_all.ps1 - Execute toute la tache 1 en une commande (Windows / PowerShell)
#
# Usage (depuis la racine du depot) :
#   powershell -ExecutionPolicy Bypass -File .\data_engineering\run_all.ps1 -Csv "data_engineering\data\raw\Sample - Superstore.csv"
#
# Etapes : dependances -> PostgreSQL (Docker) -> schema -> nettoyage -> ingestion -> tests -> graphiques
# Le script est relancable sans risque (ingestion idempotente).

param(
    [Parameter(Mandatory = $true)][string]$Csv,
    [string]$DateFormat = "%m/%d/%Y",
    [string]$Container = "pg",
    [switch]$SkipTests
)

$ErrorActionPreference = "Continue"

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Fail($msg) { Write-Host "ECHEC : $msg" -ForegroundColor Red; exit 1 }
function Check($what) { if ($LASTEXITCODE -ne 0) { Fail $what } }

# --- Se placer a la racine du depot ---------------------------------------
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
Write-Host "Racine du depot : $(Get-Location)"

if (-not (Test-Path $Csv)) { Fail "CSV introuvable : $Csv" }

# --- 1. Environnement Python ----------------------------------------------
Step "1/7 Environnement Python"
if (-not $env:VIRTUAL_ENV) {
    $act = ".\venv\Scripts\Activate.ps1"
    if (-not (Test-Path $act)) { Fail "venv introuvable. Lancer : py -m venv venv" }
    & $act
}
python -m pip install --quiet -r data_engineering/requirements.txt
Check "installation des dependances"
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host ".env cree depuis .env.example" }

# --- 2. PostgreSQL via Docker ---------------------------------------------
Step "2/7 PostgreSQL (Docker)"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fail "Docker introuvable. Installer Docker Desktop, le demarrer, puis ouvrir un NOUVEAU terminal PowerShell."
}
docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "Docker Desktop n'est pas demarre. Le lancer et attendre l'icone verte." }

$justCreated = $false
$existing = docker ps -a --filter "name=^$Container$" --format "{{.Names}}"
if (-not $existing) {
    Write-Host "Creation du conteneur $Container (image pgvector/pgvector:pg16)..."
    docker run -d --name $Container -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=copilot `
        -p 5432:5432 -v pgdata:/var/lib/postgresql/data pgvector/pgvector:pg16 | Out-Null
    Check "creation du conteneur (le port 5432 est-il deja utilise ?)"
    $justCreated = $true
} else {
    $running = docker ps --filter "name=^$Container$" --format "{{.Names}}"
    if (-not $running) { docker start $Container | Out-Null; Check "demarrage du conteneur" }
}

Write-Host "Attente de PostgreSQL..."
$ready = $false
for ($i = 0; $i -lt 40; $i++) {
    docker exec $Container pg_isready -U postgres -d copilot 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $ready) { Fail "PostgreSQL ne repond pas" }
if ($justCreated) { Start-Sleep -Seconds 8 }  # fin de l'initialisation du conteneur

# --- 3. Schema -------------------------------------------------------------
Step "3/7 Schema SQL"
docker cp "data_engineering\sql\schema.sql" "${Container}:/tmp/schema.sql"
Check "copie de schema.sql"
$ok = $false
for ($i = 0; $i -lt 5; $i++) {
    docker exec $Container psql -U postgres -d copilot -v ON_ERROR_STOP=1 -q -f /tmp/schema.sql
    if ($LASTEXITCODE -eq 0) { $ok = $true; break }
    Write-Host "Nouvel essai dans 3 s..."
    Start-Sleep -Seconds 3
}
if (-not $ok) { Fail "application du schema" }

# --- 4. Nettoyage ----------------------------------------------------------
Step "4/7 Nettoyage Pandas"
python -m data_engineering.scripts_etl.clean_data --input "$Csv" --date-format "$DateFormat"
Check "nettoyage"

# --- 5. Ingestion ----------------------------------------------------------
Step "5/7 Ingestion PostgreSQL"
python -m data_engineering.scripts_etl.ingest
Check "ingestion"

# --- 6. Tests --------------------------------------------------------------
if (-not $SkipTests) {
    Step "6/7 Tests pytest"
    python -m pytest data_engineering/tests -q
    Check "tests unitaires"
} else { Write-Host "Tests ignores (-SkipTests)" }

# --- 7. Analytics ----------------------------------------------------------
Step "7/7 KPIs et graphiques"
python -m data_engineering.analytics
Check "analytics"

Write-Host "`nTERMINE. Fichiers generes : trend.html, bar.html, pie.html (ignores par Git)." -ForegroundColor Green
Write-Host "Etape suivante : git add / commit / push (voir le guide)."
