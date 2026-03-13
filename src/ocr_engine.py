"""
OCR Engine für Kassenbon-Erkennung.
Nutzt Tesseract OCR mit Bildvorverarbeitung für maximale Genauigkeit.
"""
import os
import subprocess
from PIL import Image, ImageFilter, ImageEnhance

# Standard-Installationspfade für Tesseract auf Windows
TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Tesseract-OCR", "tesseract.exe"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR", "tesseract.exe"),
]


def _find_tesseract():
    """Sucht Tesseract auf dem System."""
    # Prüfe bekannte Pfade
    for path in TESSERACT_PATHS:
        if os.path.isfile(path):
            return path
    # Prüfe ob es im PATH ist
    try:
        result = subprocess.run(
            ["tesseract", "--version"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return "tesseract"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _preprocess_image(image_path):
    """
    Verbessert das Foto eines Kassenbons für bessere OCR-Ergebnisse.
    - Konvertiert zu Graustufen
    - Erhöht Kontrast und Schärfe
    - Binarisiert das Bild (Schwarz/Weiß)
    """
    img = Image.open(image_path)

    # 1. Graustufen
    img = img.convert("L")

    # 2. Kontrast stark erhöhen (Kassenbons sind oft blass)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)

    # 3. Schärfen
    img = img.filter(ImageFilter.SHARPEN)

    # 4. Binarisierung (reines Schwarz/Weiß) für OCR
    threshold = 140
    img = img.point(lambda x: 255 if x > threshold else 0, "1")

    # Temporäres Bild speichern für Tesseract
    temp_path = image_path + "_ocr_temp.png"
    img.save(temp_path)
    return temp_path


class ReceiptOCR:
    def __init__(self):
        self.tesseract_path = _find_tesseract()

    def is_available(self):
        """Prüft ob Tesseract installiert ist."""
        return self.tesseract_path is not None

    def extract_text(self, image_path):
        """Erkennt Text aus einem Kassenbon-Foto."""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Bild nicht gefunden: {image_path}")

        if not self.is_available():
            raise RuntimeError(
                "Tesseract OCR ist nicht installiert!\n\n"
                "Bitte installieren Sie Tesseract:\n"
                "1. Gehen Sie zu: https://github.com/UB-Mannheim/tesseract/wiki\n"
                "2. Laden Sie den Windows-Installer herunter\n"
                "3. Installieren Sie es (Standardpfad beibehalten!)\n"
                "4. WICHTIG: Bei der Installation auch 'German' Sprachdaten auswählen!\n"
                "5. Starten Sie dieses Programm neu."
            )

        # Bild vorverarbeiten für bessere Erkennung
        temp_path = _preprocess_image(image_path)

        try:
            # Tesseract aufrufen mit deutscher Sprache
            result = subprocess.run(
                [
                    self.tesseract_path,
                    temp_path,           # Eingabebild
                    "stdout",            # Ausgabe auf stdout
                    "-l", "deu",         # Deutsche Sprache
                    "--psm", "6",        # Einheitlicher Textblock
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                # Fallback: ohne deutsche Sprache versuchen
                result = subprocess.run(
                    [
                        self.tesseract_path,
                        temp_path,
                        "stdout",
                        "--psm", "6",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

            return result.stdout.strip()

        finally:
            # Temporäres Bild aufräumen
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    ocr = ReceiptOCR()
    if ocr.is_available():
        print(f"Tesseract gefunden: {ocr.tesseract_path}")
    else:
        print("Tesseract nicht gefunden! Bitte installieren.")
