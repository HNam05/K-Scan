"""Test OCR auf allen 3 echten Kassenbon-Fotos."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from ocr_engine import ReceiptOCR
from extractor import ReceiptExtractor

ocr = ReceiptOCR()
ext = ReceiptExtractor()

upload_dir = os.path.join(os.path.dirname(__file__), "uploads")

for fname in ["1.jpeg", "2.jpeg", "3.jpeg"]:
    fpath = os.path.join(upload_dir, fname)
    if not os.path.exists(fpath):
        print(f"SKIP: {fname} nicht gefunden")
        continue

    print("=" * 60)
    print(f"  BILD: {fname}")
    print("=" * 60)

    raw = ocr.extract_text(fpath)
    print("--- OCR Rohtext ---")
    print(raw)
    print("--- Extraktion ---")
    data = ext.extract_data(raw)
    for k, v in data.items():
        print(f"  {k}: {v}")
    print()
