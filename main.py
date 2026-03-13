"""
Mae Thai - Kassenbon Scanner
Startpunkt der Anwendung.
"""
import sys
import os

# Projektverzeichnis bestimmen
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(PROJECT_DIR, "src")

# src-Ordner zum Python-Suchpfad hinzufügen
sys.path.insert(0, SRC_DIR)

# Umgebungsvariable setzen, damit alle Module den Projektordner kennen
os.environ["KSCAN_PROJECT_DIR"] = PROJECT_DIR

from gui import ReceiptScannerGUI


def main():
    print("Starte Mae Thai Beleg-Scanner...")
    print(f"Projektordner: {PROJECT_DIR}")
    app = ReceiptScannerGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
