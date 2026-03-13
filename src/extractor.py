"""
Daten-Extraktion aus erkanntem Kassenbon-Text.
Findet Datum, Haendler, Betraege und Steuersaetze per RegEx.
Optimiert fuer echte OCR-Ausgabe von Tesseract (mit typischen OCR-Fehlern).
"""
import re
from datetime import datetime


# Bekannte Supermarkt-Ketten + OCR-Tippfehler-Varianten
KNOWN_MERCHANTS = [
    "Lidl", "Lid)", "Lid]", "LiDL",  # OCR-Fehler: ) statt l
    "Kaufland", "Kaufen", "Kauf land",
    "V-Markt", "V-MARKT", "V Markt", "VMarkt", "V-Mart", "V Mart",
    "Metro", "Rewe", "Aldi", "Edeka", "Penny",
    "Netto", "Norma", "Rossmann", "dm",
    "Mueller", "Müller", "Asia", "Globus", "Real",
]

# Mapping OCR-Tippfehler -> korrekter Name
MERCHANT_CORRECTIONS = {
    "Lid)": "Lidl", "Lid]": "Lidl", "LiDL": "Lidl",
    "Kaufen": "Kaufland", "Kauf land": "Kaufland",
    "V-Mart": "V-Markt", "V Mart": "V-Markt", "VMarkt": "V-Markt",
}


class ReceiptExtractor:
    """Extrahiert strukturierte Daten aus OCR-Rohtext."""

    def __init__(self):
        # Datum: DD.MM.YY oder DD.MM.YYYY, auch DD.MM,YY (OCR-Fehler)
        self.date_patterns = [
            re.compile(r'(\d{2}[.,]\d{2}[.,]\d{4})'),
            re.compile(r'(\d{2}[.,]\d{2}[.,]\d{2})(?!\d)'),
        ]

        # Eurobetraege z.B. "11,36" oder "58.14"
        self.amount_pattern = re.compile(r'(\d+[.,]\d{2})')

        # Summe-Schluesselwoerter (SEHR robust gegen OCR-Fehler)
        # "Summe", "Sume", "Sar" (OCR-Fehler fuer Summe), "zu zahlen", etc.
        self.sum_keywords = re.compile(
            r'(?:'
            r'zu\s*zahlen|zuzahlen|zu\s*bezahlen'  # "zu zahlen" Varianten
            r'|s[ua][mr](?:me)?'                     # "Summe", "Sume", "Sar", "Sum"
            r'|gesamt|total|betrag'                   # andere Keywords
            r'|zwischensumme'                         # Zwischensumme
            r')'
            r'\s*[:\-—=]?\s*(\d+[.,]\d{2})',
            re.IGNORECASE
        )

        # "Kartenzahlung" gefolgt von Betrag (zuverlaesSiger als Summe)
        self.card_payment = re.compile(
            r'Kartenzahlung\s+(\d+[.,]\d{2})',
            re.IGNORECASE
        )

        # "EUR" gefolgt von Betrag (z.B. "EUR 58,14")
        self.eur_amount = re.compile(
            r'EUR\s+(\d+[.,]\d{2})',
            re.IGNORECASE
        )

        # Steuer-Zeilen im Kaufland-Format:
        # "A 19,00% 9,42 7,92 1,50"
        # "B 7,00% 48,72 45,53 3,19"
        self.kaufland_tax = re.compile(
            r'([AB])\s*(\d+)[.,]?0*\s*%?\s+(\d+[.,]\d{2})\s+(\d+[.,]\d{2})\s+(\d+[.,]\d{2})',
            re.IGNORECASE
        )

        # Steuer-Zeilen im Lidl-Format:
        # "A 7% 0,74 10,62 11,36"
        self.lidl_tax = re.compile(
            r'A\s*7\s*%?\s+(\d+[.,]\d{2})\s+(\d+[.,]\d{2})\s+(\d+[.,]\d{2})',
            re.IGNORECASE
        )

        # V-Markt MwSt-Format:
        # "B:19,00 0,83 0,16 0,99"
        self.vmarkt_tax = re.compile(
            r'([BE])\s*[;:]\s*(\d+)[.,]?0*\s+[—-]?(\d+[.,]\d{2})\s+[—-]?(\d+[.,]\d{2})\s+[—-]?(\d+[.,]\d{2})',
            re.IGNORECASE
        )

    def _parse_amount(self, text):
        """Wandelt '11,36' oder '11.36' in float um."""
        return float(text.replace(',', '.'))

    def _find_merchant(self, text):
        """Sucht nach bekannten Haendlernamen im Text."""
        text_upper = text.upper()
        for merchant in KNOWN_MERCHANTS:
            if merchant.upper() in text_upper:
                # Korrektur von OCR-Tippfehlern
                return MERCHANT_CORRECTIONS.get(merchant, merchant)
        # Fallback: Erste nicht-leere Zeile mit > 3 sinnvollen Zeichen
        for line in text.split('\n'):
            line = line.strip()
            # Filtere "Rauschen"-Zeilen: Zu viele Sonderzeichen
            alpha_chars = sum(1 for c in line if c.isalpha())
            if alpha_chars > 3 and alpha_chars > len(line) * 0.4:
                return line[:40]
        return "Unbekannt"

    def _find_date(self, text):
        """Sucht nach dem Belegdatum."""
        for pattern in self.date_patterns:
            matches = pattern.findall(text)
            if matches:
                # Nimm das letzte gefundene Datum (oft am Bonende)
                date_str = matches[-1]
                # Komma statt Punkt (OCR-Fehler)
                date_str = date_str.replace(',', '.')
                # Kurzes Jahr (26) to volles Jahr (2026)
                if len(date_str) == 8:  # DD.MM.YY
                    parts = date_str.split('.')
                    year = int(parts[2])
                    if year < 100:
                        year += 2000
                    return f"{parts[0]}.{parts[1]}.{year}"
                return date_str
        return datetime.now().strftime("%d.%m.%Y")

    def _find_total(self, text):
        """
        Findet den Gesamtbetrag - mehrstufiger Ansatz:
        1. "Kartenzahlung" Betrag (sehr zuverlaessig)
        2. "Summe/zu zahlen" Betrag
        3. Groesster wiederholt vorkommender Betrag
        """
        candidates = []

        # 1. "ZU BEZAHLEN" / "zu zahlen" (hoechste Prioritaet!)
        zu_zahlen = re.search(
            r'(?:zu\s*bezahlen|zu\s*zahlen|zuzahlen)\s*[:\-—=]?\s*(\d+[.,]\d{2})',
            text, re.IGNORECASE
        )
        if zu_zahlen:
            val = self._parse_amount(zu_zahlen.group(1))
            if val > 0:
                return val  # Direkt zurueckgeben, hoechste Prioritaet

        # 2. Kartenzahlung
        for match in self.card_payment.finditer(text):
            val = self._parse_amount(match.group(1))
            if val > 0:
                candidates.append(("Kartenzahlung", val))

        # 3. Summe-Keywords
        for match in self.sum_keywords.finditer(text):
            val = self._parse_amount(match.group(1))
            if val > 0:
                candidates.append(("Summe", val))

        # 4. EUR-Betraege
        for match in self.eur_amount.finditer(text):
            val = self._parse_amount(match.group(1))
            if val > 0:
                candidates.append(("EUR", val))

        if candidates:
            # Haeufigster Betrag unter den Kandidaten gewinnt
            from collections import Counter
            amounts = [c[1] for c in candidates]
            count = Counter(amounts)
            most_common_val, most_common_count = count.most_common(1)[0]
            if most_common_count >= 2:
                return most_common_val
            # Sonst: Kartenzahlung hat Prioritaet
            for label, val in candidates:
                if label == "Kartenzahlung":
                    return val
            return candidates[0][1]

        # 4. Fallback: Alle Betraege, groessten nehmen (aber < 10000)
        amounts = []
        for m in self.amount_pattern.finditer(text):
            try:
                val = self._parse_amount(m.group(1))
                if 0.5 < val < 10000:
                    amounts.append(val)
            except ValueError:
                pass

        if amounts:
            from collections import Counter
            count = Counter(amounts)
            # Betrag der >= 2x vorkommt
            for val, cnt in count.most_common():
                if cnt >= 2:
                    return val
            # Sonst groesster
            return max(amounts)

        return 0.0

    def _find_taxes(self, text, brutto):
        """Findet Steuerbetraege (7% und 19%) aus den MwSt-Zeilen."""
        steuer_7 = 0.0
        steuer_19 = 0.0
        netto = 0.0

        # Kaufland-Format: "A 19,00% 9,42 7,92 1,50" / "B 7,00% 48,72 45,53 3,19"
        for match in self.kaufland_tax.finditer(text):
            letter = match.group(1).upper()
            pct = int(match.group(2))
            brutto_tax = self._parse_amount(match.group(3))
            netto_tax = self._parse_amount(match.group(4))
            steuer_val = self._parse_amount(match.group(5))

            if pct == 19 or letter == "A":
                steuer_19 = steuer_val
            elif pct == 7 or letter == "B":
                steuer_7 = steuer_val

        # Lidl-Format: "A 7% 0,74 10,62 11,36"
        if steuer_7 == 0.0 and steuer_19 == 0.0:
            match = self.lidl_tax.search(text)
            if match:
                steuer_7 = self._parse_amount(match.group(1))

        # V-Markt-Format
        if steuer_7 == 0.0 and steuer_19 == 0.0:
            for match in self.vmarkt_tax.finditer(text):
                letter = match.group(1).upper()
                pct = int(match.group(2))
                if pct == 19 or letter == "B":
                    steuer_19 = self._parse_amount(match.group(5))
                elif pct == 7:
                    steuer_7 = self._parse_amount(match.group(5))

        # Netto berechnen
        if steuer_7 > 0 or steuer_19 > 0:
            netto = brutto - steuer_7 - steuer_19
        elif brutto > 0:
            # Fallback: Standard 7% (Lebensmittel)
            steuer_7 = round(brutto - (brutto / 1.07), 2)
            netto = round(brutto / 1.07, 2)

        return brutto, round(netto, 2), round(steuer_7, 2), round(steuer_19, 2)

    def extract_data(self, text):
        """
        Hauptfunktion: Extrahiert alle relevanten Daten aus dem OCR-Text.
        """
        haendler = self._find_merchant(text)
        datum = self._find_date(text)
        brutto = self._find_total(text)
        brutto, netto, steuer_7, steuer_19 = self._find_taxes(text, brutto)

        return {
            "Haendler": haendler,
            "Datum": datum,
            "Brutto": brutto,
            "Netto": netto,
            "Steuer_7": steuer_7,
            "Steuer_19": steuer_19,
            "Kategorie": "Lebensmittel",
        }


if __name__ == "__main__":
    # Test mit echtem OCR-Output von Kaufland Bon
    test_text = """
    Kaufland
    Margot-Kalinke-Strasse 4
    Pfanner Heidelbeer 0,99 A
    Argeta Tunfisch 14 1,00 14,00 B
    Summe 58,14
    Kartenzahlung 58,14
    Steuer X Brutto Netto Steuer
    A 19,00% 9,42 7,92 1,50
    B 7,00% 48,72 45,53 3,19
    Datum 13.03.26 13:24 Uhr
    """
    ext = ReceiptExtractor()
    result = ext.extract_data(test_text)
    for key, val in result.items():
        print(f"  {key}: {val}")
