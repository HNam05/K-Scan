# Mae Thai - Kassenbon Scanner 🚀

Ein intelligentes Tool zur automatischen Erfassung und Verarbeitung von Kassenbons und Rechnungen. Optimiert für Gastronomie und privaten Gebrauch.

## Features
- **Batch-Processing**: Scanne bis zu 40 Belege gleichzeitig.
- **Gastronomie-Support**: Erkennt spezielle Belege von Hamberger, Fresh-GO, Metro etc.
- **Finanzamt-Ready**: Erstellt konsolidierte Excel-Berichte mit korrekten Steuersätzen (7% & 19%).
- **Datenschutz**: Alle Daten bleiben lokal auf deinem Rechner.

## Installation
1. Stelle sicher, dass **Python** installiert ist.
2. Führe die `setup.bat` aus, um Tesseract OCR und alle Abhängigkeiten zu installieren.

## Starten der Anwendung

### 🌐 Web-Interface (Empfohlen)
Doppelklicke auf:
**`start_web.bat`**
(Dies öffnet automatisch deinen Browser auf `http://localhost:5000`)

Alternativ über die Konsole:
```bash
python app.py
```

### 🖥️ Desktop GUI (Tkinter)
Falls du lieber ein klassisches Fenster nutzt:
```bash
python main.py
```

## Datenschutz
Dieses Repository ist durch eine `.gitignore` Datei geschützt. Deine Bilder im `uploads/` Ordner sowie die generierten Daten in `data/` und `belege/` werden **nicht** auf Git/GitHub hochgeladen.
