"""
OCR Engine fuer Kassenbon-Erkennung.
Nutzt Tesseract OCR mit intelligenter Bildvorverarbeitung:
1. EXIF-Rotation und Skalierung
2. Graustufen + Kontrast + Binarisierung
3. Mehrere PSM-Modi ausprobieren, besten Output waehlen
"""
import os
import subprocess
from PIL import Image, ImageFilter, ImageEnhance, ImageOps

# Standard-Installationspfade fuer Tesseract auf Windows
TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Tesseract-OCR", "tesseract.exe"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR", "tesseract.exe"),
]


def _find_tesseract():
    """Sucht Tesseract auf dem System."""
    for path in TESSERACT_PATHS:
        if os.path.isfile(path):
            return path
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
    Bildvorverarbeitung fuer Handy-Fotos von Kassenbons.
    Erzeugt DREI verschiedene vorverarbeitete Versionen:
    - Version A: Graustufen + leichter Kontrast (fuer gute Fotos)
    - Version B: Starker Kontrast + Binarisierung (fuer verrauschte Fotos)
    - Version C: Sehr hoher Threshold (fuer Fotos mit Muster-Hintergrund)
    """
    img = Image.open(image_path)
    img = ImageOps.exif_transpose(img)

    # Skalieren
    max_width = 1800
    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    gray = img.convert("L")

    versions = []

    # Version A: Leicht verbessert (fuer saubere Fotos)
    v_a = ImageEnhance.Contrast(gray).enhance(1.5)
    v_a = v_a.filter(ImageFilter.SHARPEN)
    path_a = image_path + "_ocr_a.png"
    v_a.save(path_a, "PNG")
    versions.append(path_a)

    # Version B: Stark + Binarisierung (fuer mittlere Qualitaet)
    v_b = ImageEnhance.Contrast(gray).enhance(2.5)
    v_b = ImageEnhance.Brightness(v_b).enhance(1.3)
    v_b = v_b.filter(ImageFilter.SHARPEN)
    v_b = v_b.point(lambda x: 0 if x < 140 else 255, "1")
    path_b = image_path + "_ocr_b.png"
    v_b.save(path_b, "PNG")
    versions.append(path_b)

    # Version C: Sehr hoher Threshold (Tischdecke/Muster entfernen)
    v_c = ImageEnhance.Contrast(gray).enhance(3.0)
    v_c = ImageEnhance.Brightness(v_c).enhance(1.5)
    v_c = v_c.filter(ImageFilter.SHARPEN)
    v_c = v_c.point(lambda x: 0 if x < 180 else 255, "1")
    path_c = image_path + "_ocr_c.png"
    v_c.save(path_c, "PNG")
    versions.append(path_c)

    return versions


def _score_text(text):
    """
    Bewertet OCR-Output: Je mehr echte Woerter und Zahlen, desto besser.
    Straft Rauschen (einzelne Buchstaben, Sonderzeichen) ab.
    """
    if not text:
        return 0

    score = 0
    lines = text.strip().split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Anteil alphanumerischer Zeichen
        alnum = sum(1 for c in line if c.isalnum() or c in '.,€%')
        total = len(line)

        if total == 0:
            continue

        ratio = alnum / total

        if ratio > 0.5:
            score += len(line) * ratio  # Gute Zeile
        else:
            score -= 5  # Rausch-Zeile bestrafen

        # Bonus fuer erkannte Schluesselwoerter
        line_lower = line.lower()
        keywords = ['summe', 'kartenzahlung', 'brutto', 'netto', 'steuer',
                     'mwst', 'zahlen', 'bar', 'datum', 'eur',
                     'lidl', 'kaufland', 'markt', 'rewe', 'aldi', 'edeka']
        for kw in keywords:
            if kw in line_lower:
                score += 20

        # Bonus fuer erkannte Geldbetraege (X,XX oder X.XX)
        import re
        amounts = re.findall(r'\d+[.,]\d{2}', line)
        score += len(amounts) * 10

    return score


class ReceiptOCR:
    def __init__(self):
        self.tesseract_path = _find_tesseract()

    def is_available(self):
        """Prueft ob Tesseract installiert ist."""
        return self.tesseract_path is not None

    def extract_text(self, image_path):
        """Erkennt Text aus einem Kassenbon-Foto. Probiert mehrere Strategien."""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Bild nicht gefunden: {image_path}")

        if not self.is_available():
            raise RuntimeError(
                "Tesseract OCR ist nicht installiert!\n\n"
                "Bitte fuehren Sie setup.bat aus oder installieren Sie Tesseract manuell:\n"
                "https://github.com/UB-Mannheim/tesseract/releases"
            )

        # Drei vorverarbeitete Versionen erstellen
        temp_paths = _preprocess_image(image_path)

        try:
            best_text = ""
            best_score = -1

            # Fuer jede Version: Verschiedene PSM-Modi probieren
            for temp_path in temp_paths:
                for psm in ["4", "6"]:
                    text = self._run_tesseract(temp_path, lang="deu", psm=psm)
                    if text:
                        score = _score_text(text)
                        if score > best_score:
                            best_score = score
                            best_text = text

            return best_text.strip()

        finally:
            for p in temp_paths:
                if os.path.exists(p):
                    os.remove(p)

    def _run_tesseract(self, image_path, lang="deu", psm="4"):
        """Fuehrt Tesseract als Subprocess aus, encoding-sicher."""
        cmd = [
            self.tesseract_path,
            image_path,
            "stdout",
            "--psm", psm,
        ]
        if lang:
            cmd.extend(["-l", lang])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30,
            )

            if result.returncode != 0:
                return None

            text = result.stdout.decode("utf-8", errors="replace")
            return text

        except (subprocess.TimeoutExpired, Exception):
            return None


if __name__ == "__main__":
    ocr = ReceiptOCR()
    if ocr.is_available():
        print(f"Tesseract gefunden: {ocr.tesseract_path}")
    else:
        print("Tesseract nicht gefunden!")
