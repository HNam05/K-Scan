"""
Mae Thai - Kassenbon Scanner (Web-Version)
Flask-basierter lokaler Server für den Browser.
"""
import sys
import os
import json
import uuid
from datetime import datetime

# Projektverzeichnis
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(PROJECT_DIR, "src")
sys.path.insert(0, SRC_DIR)

from flask import Flask, render_template, request, jsonify, send_file
from ocr_engine import ReceiptOCR
from extractor import ReceiptExtractor
from exporter import ReportExporter

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # Max 16MB Upload

# Verzeichnisse
UPLOAD_DIR = os.path.join(PROJECT_DIR, "uploads")
DATA_DIR = os.path.join(PROJECT_DIR, "data")
BELEGE_DIR = os.path.join(PROJECT_DIR, "belege")

for d in [UPLOAD_DIR, DATA_DIR, BELEGE_DIR]:
    os.makedirs(d, exist_ok=True)

# OCR und Extraktor initialisieren
ocr = ReceiptOCR()
extractor = ReceiptExtractor()


@app.route("/")
def index():
    """Hauptseite."""
    receipt_count = len([f for f in os.listdir(DATA_DIR) if f.endswith(".json")])
    ocr_status = ocr.is_available()
    return render_template("index.html", receipt_count=receipt_count, ocr_available=ocr_status)


@app.route("/api/scan", methods=["POST"])
def scan_receipt():
    """Nimmt ein Bild entgegen, führt OCR aus und gibt die extrahierten Daten zurück."""
    if "image" not in request.files:
        return jsonify({"error": "Kein Bild hochgeladen"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "Kein Bild ausgewählt"}), 400

    # Datei speichern
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
        return jsonify({"error": "Nur Bilder (JPG, PNG) erlaubt"}), 400

    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    file.save(filepath)

    try:
        # OCR durchführen
        raw_text = ocr.extract_text(filepath)

        # Daten extrahieren
        data = extractor.extract_data(raw_text)

        return jsonify({
            "success": True,
            "raw_text": raw_text,
            "data": data,
            "image_file": filename,
        })

    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"OCR Fehler: {str(e)}"}), 500


@app.route("/api/save", methods=["POST"])
def save_receipt():
    """Speichert die (ggf. korrigierten) Belegdaten als JSON."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Keine Daten erhalten"}), 400

    # Validierung
    if not data.get("Händler") or not data.get("Brutto"):
        return jsonify({"error": "Händler und Brutto sind Pflichtfelder"}), 400

    # Dateiname generieren
    datum_clean = data.get("Datum", "unknown").replace(".", "")
    haendler_clean = data.get("Händler", "unknown").replace(" ", "_")[:20]
    filename = f"beleg_{datum_clean}_{haendler_clean}_{uuid.uuid4().hex[:6]}.json"
    filepath = os.path.join(DATA_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    receipt_count = len([f for f in os.listdir(DATA_DIR) if f.endswith(".json")])

    return jsonify({
        "success": True,
        "filename": filename,
        "receipt_count": receipt_count,
    })


@app.route("/api/export", methods=["POST"])
def export_excel():
    """Generiert die Excel-Monatsabrechnung."""
    try:
        exp = ReportExporter()
        output_file = exp.generate_excel_report()
        return jsonify({
            "success": True,
            "file": os.path.basename(output_file),
            "path": output_file,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/receipts", methods=["GET"])
def list_receipts():
    """Listet alle gespeicherten Belege."""
    receipts = []
    for filename in sorted(os.listdir(DATA_DIR)):
        if filename.endswith(".json"):
            filepath = os.path.join(DATA_DIR, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["_filename"] = filename
                receipts.append(data)
    return jsonify(receipts)


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    """Liefert ein hochgeladenes Bild aus."""
    return send_file(os.path.join(UPLOAD_DIR, filename))


@app.route("/download/<filename>")
def download_file(filename):
    """Download der Excel-Datei."""
    return send_file(os.path.join(BELEGE_DIR, filename), as_attachment=True)


if __name__ == "__main__":
    print("=" * 50)
    print("  Mae Thai - Kassenbon Scanner")
    print("  Öffnen Sie: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)
