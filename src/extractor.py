"""
Daten-Extraktion aus erkanntem Kassenbon-Text.
Findet Datum, Händler, Beträge und Steuersätze per RegEx.
"""
import re
from datetime import datetime


# Bekannte Supermarkt-Ketten (erweiterbar)
KNOWN_MERCHANTS = [
    "Lidl", "Kaufland", "V-Markt", "V-MARKT",
    "Metro", "Rewe", "Aldi", "Edeka", "Penny",
    "Netto", "Norma", "Rossmann", "dm",
    "Müller", "Asia", "Globus", "Real",
]


class ReceiptExtractor:
    """Extrahiert strukturierte Daten aus OCR-Rohtext."""

    def __init__(self):
        # Datum: DD.MM.YY oder DD.MM.YYYY
        self.date_patterns = [
            re.compile(r'(\d{2}\.\d{2}\.\d{4})'),
            re.compile(r'(\d{2}\.\d{2}\.\d{2})(?!\d)'),
        ]
        # Eurobeträge z.B. "11,36" oder "58.14"
        self.amount_pattern = re.compile(r'(\d+[.,]\d{2})')

        # Steuer-Zeilen: "A 7%" oder "B 19%" oder "MwSt 7%"
        self.tax_line_7 = re.compile(
            r'(?:A\s*)?7\s*[%,.]?\s*\D*?(\d+[.,]\d{2})\s+(\d+[.,]\d{2})\s+(\d+[.,]\d{2})',
            re.IGNORECASE
        )
        self.tax_line_19 = re.compile(
            r'(?:B\s*)?19\s*[%,.]?\s*\D*?(\d+[.,]\d{2})\s+(\d+[.,]\d{2})\s+(\d+[.,]\d{2})',
            re.IGNORECASE
        )

        # Gesamtsumme-Schlüsselwörter
        self.sum_keywords = re.compile(
            r'(?:summe|zu\s*zahlen|zu\s*bezahlen|gesamt|total|betrag)\s*:?\s*(\d+[.,]\d{2})',
            re.IGNORECASE
        )

    def _parse_amount(self, text: str) -> float:
        """Wandelt '11,36' oder '11.36' in float um."""
        return float(text.replace(',', '.'))

    def _find_merchant(self, text: str) -> str:
        """Sucht nach bekannten Händlernamen im Text."""
        text_upper = text.upper()
        for merchant in KNOWN_MERCHANTS:
            if merchant.upper() in text_upper:
                return merchant
        # Fallback: Erste nicht-leere Zeile als Händler
        for line in text.split('\n'):
            line = line.strip()
            if len(line) > 2 and not line.startswith('*'):
                return line[:40]
        return "Unbekannt"

    def _find_date(self, text: str) -> str:
        """Sucht nach dem Belegdatum."""
        for pattern in self.date_patterns:
            matches = pattern.findall(text)
            if matches:
                # Nimm das letzte gefundene Datum (oft am Bonende)
                date_str = matches[-1]
                # Kurzes Jahr (26) in volles Jahr (2026) umwandeln
                if len(date_str) == 8:  # DD.MM.YY
                    parts = date_str.split('.')
                    year = int(parts[2])
                    if year < 100:
                        year += 2000
                    return f"{parts[0]}.{parts[1]}.{year}"
                return date_str
        return datetime.now().strftime("%d.%m.%Y")

    def _find_total(self, text: str) -> float:
        """Findet den Gesamtbetrag."""
        # Zuerst nach Schlüsselwörtern suchen
        match = self.sum_keywords.search(text)
        if match:
            return self._parse_amount(match.group(1))

        # Fallback: Alle Beträge sammeln, größten nehmen
        amounts = []
        for m in self.amount_pattern.finditer(text):
            try:
                val = self._parse_amount(m.group(1))
                if val > 0:
                    amounts.append(val)
            except ValueError:
                pass
        return max(amounts) if amounts else 0.0

    def _find_taxes(self, text: str, brutto: float):
        """Findet Steuerbeträge (7% und 19%) aus den MwSt-Zeilen."""
        steuer_7 = 0.0
        steuer_19 = 0.0
        netto = 0.0

        # Suche nach der 7%-Steuerzeile
        match_7 = self.tax_line_7.search(text)
        if match_7:
            # Normalerweise: MwSt-Betrag, Netto, Brutto
            steuer_7 = self._parse_amount(match_7.group(1))

        # Suche nach der 19%-Steuerzeile
        match_19 = self.tax_line_19.search(text)
        if match_19:
            steuer_19 = self._parse_amount(match_19.group(1))

        # Netto berechnen
        netto = brutto - steuer_7 - steuer_19

        # Falls keine Steuerzeilen gefunden: Standard 7% (Lebensmittel)
        if steuer_7 == 0.0 and steuer_19 == 0.0 and brutto > 0:
            steuer_7 = round(brutto - (brutto / 1.07), 2)
            netto = round(brutto / 1.07, 2)

        return round(netto, 2), round(steuer_7, 2), round(steuer_19, 2)

    def extract_data(self, text: str) -> dict:
        """
        Hauptfunktion: Extrahiert alle relevanten Daten aus dem OCR-Text.
        Gibt ein Dictionary zurück, bereit für JSON-Speicherung.
        """
        haendler = self._find_merchant(text)
        datum = self._find_date(text)
        brutto = self._find_total(text)
        netto, steuer_7, steuer_19 = self._find_taxes(text, brutto)

        return {
            "Händler": haendler,
            "Datum": datum,
            "Brutto": brutto,
            "Netto": netto,
            "Steuer_7": steuer_7,
            "Steuer_19": steuer_19,
            "Kategorie": "Lebensmittel",
        }


if __name__ == "__main__":
    # Testfall: Simulierter OCR-Output eines Lidl-Bons
    test_text = """
    Lidl
    Tübinger Straße 9
    80686 München
    Nutella 3,79 A
    Brot Dinkel Ka. 2,49 A
    Hähn.UnterkeuleXXL 6,99 A
    zu zahlen 11,36
    MWST% MWST + Netto = Brutto
    A 7% 0,74 10,62 11,36
    Summe 0,74 10,62 11,36
    13.03.26 12:23
    """
    extractor = ReceiptExtractor()
    result = extractor.extract_data(test_text)
    for key, val in result.items():
        print(f"  {key}: {val}")
