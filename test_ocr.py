"""
Testskript: Erstellt ein simuliertes Kassenbon-Bild und testet die komplette OCR-Pipeline.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from PIL import Image, ImageDraw, ImageFont
from ocr_engine import ReceiptOCR
from extractor import ReceiptExtractor

def create_test_receipt(output_path):
    """Erstellt ein simuliertes Kassenbon-Bild mit Text."""
    width, height = 400, 600
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    
    # Einfacher Font
    try:
        font = ImageFont.truetype("arial.ttf", 16)
        font_bold = ImageFont.truetype("arialbd.ttf", 20)
    except:
        font = ImageFont.load_default()
        font_bold = font

    lines = [
        ("Lidl", font_bold),
        ("Tübinger Straße 9", font),
        ("80686 München", font),
        ("", font),
        ("Nutella              3,79 A", font),
        ("Brot Dinkel Ka.      2,49 A", font),
        ("Hähn.UnterkeuleXXL   6,99 A", font),
        ("", font),
        ("zu zahlen           11,36", font),
        ("Bar                 20,00", font),
        ("Rückgeld            -8,64", font),
        ("", font),
        ("MWST%  MWST  Netto  Brutto", font),
        ("A 7%   0,74  10,62  11,36", font),
        ("Summe  0,74  10,62  11,36", font),
        ("", font),
        ("13.03.26          12:23", font),
    ]
    
    y = 30
    for text, f in lines:
        if text:
            draw.text((20, y), text, fill="black", font=f)
        y += 28

    img.save(output_path)
    print(f"Testbild erstellt: {output_path}")
    return output_path


def test_pipeline():
    """Testet OCR + Extraktion auf dem Testbild."""
    print("=" * 60)
    print("  KASSENBON-SCANNER TEST")
    print("=" * 60)

    # 1. OCR prüfen
    ocr = ReceiptOCR()
    print(f"\n[1] Tesseract verfügbar: {ocr.is_available()}")
    if ocr.tesseract_path:
        print(f"    Pfad: {ocr.tesseract_path}")
    
    if not ocr.is_available():
        print("FEHLER: Tesseract nicht installiert!")
        return

    # 2. Testbild erstellen
    test_img = os.path.join(os.path.dirname(__file__), "uploads", "test_receipt.png")
    os.makedirs(os.path.dirname(test_img), exist_ok=True)
    create_test_receipt(test_img)

    # 3. OCR durchführen
    print(f"\n[2] OCR auf Testbild...")
    raw_text = ocr.extract_text(test_img)
    print(f"    Erkannter Text ({len(raw_text)} Zeichen):")
    print("-" * 40)
    print(raw_text)
    print("-" * 40)

    # 4. Daten extrahieren
    print(f"\n[3] Daten-Extraktion...")
    ext = ReceiptExtractor()
    data = ext.extract_data(raw_text)
    
    print(f"    Händler:   {data['Händler']}")
    print(f"    Datum:     {data['Datum']}")
    print(f"    Brutto:    {data['Brutto']} €")
    print(f"    Netto:     {data['Netto']} €")
    print(f"    Steuer 7%: {data['Steuer_7']} €")
    print(f"    Steuer 19%:{data['Steuer_19']} €")
    print(f"    Kategorie: {data['Kategorie']}")

    # 5. Ergebnisse prüfen
    print(f"\n[4] Ergebnis-Check:")
    issues = []
    if "Lidl" not in data["Händler"]:
        issues.append(f"  ✗ Händler falsch: '{data['Händler']}' (erwartet: Lidl)")
    else:
        print("  ✓ Händler korrekt erkannt")
    
    if data["Brutto"] == 0.0:
        issues.append("  ✗ Brutto nicht erkannt")
    else:
        print(f"  ✓ Brutto erkannt: {data['Brutto']} €")
    
    if "26" in data["Datum"] or "2026" in data["Datum"]:
        print(f"  ✓ Datum erkannt: {data['Datum']}")
    else:
        issues.append(f"  ✗ Datum nicht korrekt: '{data['Datum']}'")

    if issues:
        print("\nProbleme gefunden:")
        for i in issues:
            print(i)
    else:
        print("\n✅ Alle Tests bestanden!")

    print("=" * 60)
    return data


if __name__ == "__main__":
    test_pipeline()
