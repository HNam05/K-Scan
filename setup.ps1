# ============================================================
# Mae Thai - Kassenbon Scanner: Automatisches Setup-Skript
# ============================================================
# Dieses Skript installiert alle benoetigten Programme und
# Bibliotheken fuer den Kassenbon-Scanner.
#
# AUSFUEHRUNG (als Administrator empfohlen):
#   Right-click -> "Mit PowerShell ausfuehren"
#   oder: powershell -ExecutionPolicy Bypass -File setup.ps1
# ============================================================

$ErrorActionPreference = "Stop"

# Farben fuer die Konsole
function Write-Step  { param($msg) Write-Host "`n[SCHRITT] $msg" -ForegroundColor Cyan }
function Write-Ok    { param($msg) Write-Host "[  OK  ] $msg" -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "[ WARN ] $msg" -ForegroundColor Yellow }
function Write-Fail  { param($msg) Write-Host "[FEHLER] $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "=========================================" -ForegroundColor Magenta
Write-Host " Mae Thai - Kassenbon Scanner Setup"      -ForegroundColor Magenta
Write-Host "=========================================" -ForegroundColor Magenta
Write-Host ""

# ----------------------------------------------------------
# 1. Python pruefen
# ----------------------------------------------------------
Write-Step "Python Installation pruefen..."
try {
    $pyVersion = python --version 2>&1
    Write-Ok "Python gefunden: $pyVersion"
} catch {
    Write-Fail "Python ist nicht installiert!"
    Write-Host "  Bitte installieren Sie Python von https://www.python.org/downloads/"
    Write-Host "  Achten Sie darauf, 'Add Python to PATH' anzukreuzen!"
    Read-Host "Druecken Sie Enter zum Beenden"
    exit 1
}

# ----------------------------------------------------------
# 2. Tesseract OCR pruefen und installieren
# ----------------------------------------------------------
Write-Step "Tesseract OCR pruefen..."

$tesseractPath = "C:\Program Files\Tesseract-OCR\tesseract.exe"
$tesseractInstalled = Test-Path $tesseractPath

if ($tesseractInstalled) {
    $tessVersion = & $tesseractPath --version 2>&1 | Select-Object -First 1
    Write-Ok "Tesseract bereits installiert: $tessVersion"
} else {
    Write-Warn "Tesseract OCR ist nicht installiert. Starte Download..."

    $installerUrl = "https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe"
    $installerPath = "$env:TEMP\tesseract-setup.exe"

    try {
        Write-Host "  Lade herunter von GitHub (~48 MB)..."
        curl.exe -L -o $installerPath $installerUrl --progress-bar
        
        if (-not (Test-Path $installerPath) -or (Get-Item $installerPath).Length -lt 1000000) {
            throw "Download fehlgeschlagen oder Datei zu klein."
        }

        Write-Host "  Installiere Tesseract (Silent-Modus)..."
        Start-Process -FilePath $installerPath -ArgumentList "/S" -Wait
        
        if (Test-Path $tesseractPath) {
            Write-Ok "Tesseract erfolgreich installiert!"
        } else {
            throw "Installation abgeschlossen, aber tesseract.exe nicht gefunden."
        }
    } catch {
        Write-Fail "Automatische Installation fehlgeschlagen: $_"
        Write-Host ""
        Write-Host "  Bitte installieren Sie Tesseract manuell:" -ForegroundColor Yellow
        Write-Host "  1. Oeffnen Sie: https://github.com/UB-Mannheim/tesseract/releases"
        Write-Host "  2. Laden Sie 'tesseract-ocr-w64-setup-*.exe' herunter"
        Write-Host "  3. Fuehren Sie den Installer aus (Standardpfad beibehalten!)"
        Write-Host "  4. Fuehren Sie dieses Setup-Skript danach erneut aus."
        Read-Host "Druecken Sie Enter zum Beenden"
        exit 1
    }
}

# ----------------------------------------------------------
# 3. Deutsche Sprachdaten fuer Tesseract
# ----------------------------------------------------------
Write-Step "Deutsche Sprachdaten (deu.traineddata) pruefen..."

$tessDataDir = "C:\Program Files\Tesseract-OCR\tessdata"
$deuData = Join-Path $tessDataDir "deu.traineddata"

if (Test-Path $deuData) {
    Write-Ok "Deutsche Sprachdaten bereits vorhanden."
} else {
    Write-Warn "Deutsche Sprachdaten fehlen. Lade herunter..."

    $deuUrl = "https://github.com/tesseract-ocr/tessdata/raw/main/deu.traineddata"
    $tempDeu = "$env:TEMP\deu.traineddata"

    try {
        curl.exe -L -o $tempDeu $deuUrl --progress-bar

        if (-not (Test-Path $tempDeu) -or (Get-Item $tempDeu).Length -lt 1000000) {
            throw "Download der Sprachdaten fehlgeschlagen."
        }

        # Kopieren mit Admin-Rechten falls noetig
        try {
            Copy-Item $tempDeu $deuData -Force
        } catch {
            Write-Host "  Benoetige Admin-Rechte zum Kopieren..."
            Start-Process powershell -Verb RunAs -ArgumentList "-Command", "Copy-Item '$tempDeu' '$deuData' -Force" -Wait
        }

        if (Test-Path $deuData) {
            Write-Ok "Deutsche Sprachdaten installiert!"
        } else {
            throw "Kopieren fehlgeschlagen."
        }
    } catch {
        Write-Fail "Sprachdaten konnten nicht installiert werden: $_"
        Write-Host "  Bitte manuell herunterladen von:"
        Write-Host "  https://github.com/tesseract-ocr/tessdata/raw/main/deu.traineddata"
        Write-Host "  und nach '$tessDataDir' kopieren."
    }
}

# ----------------------------------------------------------
# 4. Python-Pakete installieren
# ----------------------------------------------------------
Write-Step "Python-Pakete installieren..."

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$requirementsFile = Join-Path $scriptDir "requirements.txt"

if (Test-Path $requirementsFile) {
    try {
        python -m pip install --upgrade pip 2>&1 | Out-Null
        python -m pip install -r $requirementsFile 2>&1
        Write-Ok "Alle Python-Pakete installiert!"
    } catch {
        Write-Fail "Fehler beim Installieren der Python-Pakete: $_"
        exit 1
    }
} else {
    Write-Fail "requirements.txt nicht gefunden in: $scriptDir"
    exit 1
}

# ----------------------------------------------------------
# 5. Ordnerstruktur erstellen
# ----------------------------------------------------------
Write-Step "Ordnerstruktur pruefen..."

$dirs = @("data", "belege", "src")
foreach ($dir in $dirs) {
    $fullPath = Join-Path $scriptDir $dir
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
        Write-Host "  Erstellt: $dir/"
    }
}
Write-Ok "Ordnerstruktur bereit."

# ----------------------------------------------------------
# 6. Verifizierung
# ----------------------------------------------------------
Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host " Setup abgeschlossen!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host ""
Write-Host " Starten Sie den Scanner mit:" -ForegroundColor White
Write-Host "   python main.py" -ForegroundColor Yellow
Write-Host ""
Write-Host " Projektordner: $scriptDir" -ForegroundColor Gray
Write-Host ""

# Kurze Zusammenfassung
Write-Host " Installierte Komponenten:" -ForegroundColor White
Write-Host "   - Python:    $(python --version 2>&1)" -ForegroundColor Gray

if (Test-Path $tesseractPath) {
    $tv = & $tesseractPath --version 2>&1 | Select-Object -First 1
    Write-Host "   - Tesseract: $tv" -ForegroundColor Gray
}

$langs = & $tesseractPath --list-langs 2>&1
if ($langs -match "deu") {
    Write-Host "   - Sprachen:  Deutsch + Englisch" -ForegroundColor Gray
} else {
    Write-Host "   - Sprachen:  Englisch (Deutsch fehlt!)" -ForegroundColor Yellow
}

Write-Host ""
Read-Host "Druecken Sie Enter zum Beenden"
