"""
Daten-Extraktion aus erkanntem Kassenbon-Text.
Findet Datum, Haendler, Betraege und Steuersaetze per RegEx.
Optimiert fuer echte OCR-Ausgabe von Tesseract (mit typischen OCR-Fehlern).
"""
import re
from datetime import datetime


# Bekannte Supermarkt-Ketten + OCR-Tippfehler-Varianten
KNOWN_MERCHANTS = [
    "Lidl", "Lid)", "Lid]", "LiDL",
    "Kaufland", "Kaufen", "Kauf land",
    "V-Markt", "V-MARKT", "V Markt", "VMarkt",
    "Metro", "Rewe", "Aldi", "Edeka", "Penny",
    "Netto", "Norma", "Rossmann", "dm",
    "Hamberger", "Fresh-GO", "Fresh GO", "Ngocha", "Asia Markt",
    "Mueller", "Müller", "Asia", "Globus", "Real",
]

# Mapping OCR-Tippfehler -> korrekter Name
MERCHANT_CORRECTIONS = {
    "Lid)": "Lidl", "Lid]": "Lidl", "LiDL": "Lidl",
    "Kaufen": "Kaufland", "Kauf land": "Kaufland",
    "V-Mart": "V-Markt", "V Mart": "V-Markt", "VMarkt": "V-Markt",
    "Fresh GO": "Fresh-GO Asia", "Fresh-GO": "Fresh-GO Asia",
    "Ngocha": "Ngocha Asia Markt",
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
        # "Summe", "Sume", "Sar", "Gesamtbetrag", "zu zahlen", etc.
        self.sum_keywords = re.compile(
            r'(?:'
            r'zu\s*bezahlen|zu\s*zahlen|zuzahlen'
            r'|zahlbetrag\s*brutto'                  # Fresh-GO
            r'|s[ua][mr](?:me)?'
            r'|gesantbetrag|gesamtbetrag|ges\.?betrag'
            r'|total|betrag'
            r'|summe'                                # Ngocha etc.
            r'|zwischensumme'
            r'|endbetrag|endsumme'
            r')'
            r'\s*[:\-—=*]?\s*(\d+[.,]\d{2})',
            re.IGNORECASE
        )

        # "Kartenzahlung" / "EC-Cash" gefolgt von Betrag (zuverlaessiger Indikator)
        self.card_payment = re.compile(
            r'(?:Kartenzahlung|EC-Cash|Geg\.\s*EC-Cash|girocard)\s*[:\-—=]?\s*(\d+[.,]\d{2})',
            re.IGNORECASE
        )

        # Barzahlung ausschließen (wenn "Bar" oder "Gegeben" davor steht)
        self.payment_keywords = re.compile(
            r'(?:Bar|Gegeben|Geg\.)\s*[:\-—=]?\s*(\d+[.,]\d{2})',
            re.IGNORECASE
        )

        # "EUR" gefolgt von Betrag (z.B. "EUR 58,14")
        self.eur_amount = re.compile(
            r'EUR\s+(\d+[.,]\d{2})',
            re.IGNORECASE
        )

        # Steuer-Zeilen Typ 1 (Kaufland/Lidl/Rewe):
        # "A 19,00% 9,42 7,92 1,50"
        # "B 7,0% 5,61 0,33 6,00"
        # "Gesantbetrag 6,65 0,59 7,24"
        self.tax_table_line = re.compile(
            r'(?:[AB]=?|Gesantbetrag|Gesamtbetrag)\s*(\d*[.,]?\d*\s*%?)?\s+(\d+[.,]\d{2})\s+(\d+[.,]\d{2})\s+(\d+[.,]\d{2})',
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
        # Hamberger Steuertabelle:
        # "7,0 % 63,13 4,42 67,55"
        # "19,0 % 85,41 16,23 101,64"
        self.hamberger_tax = re.compile(
            r'(\d+[.,]\d+)\s*%\s+(\d+[.,]\w+)\s+(\d+[.,]\w+)\s+(\d+[.,]\w+)',
            re.IGNORECASE
        )

        # Fresh-GO Netto/MwSt/Brutto
        self.freshgo_netto = re.compile(r'Summe\s*Netto\s*\.?\s*[:\-—=]?\s*(\d+[.,]\d{2,})', re.IGNORECASE)
        self.freshgo_mwst = re.compile(r'Summe\s*MwSt\s*\.?\s*[:\-—=]?\s*(\d+[.,]\d{2,})', re.IGNORECASE)
        self.freshgo_brutto = re.compile(r'Zahlbetrag\s*Brutto\s*[:\-—=]?\s*[„"\'\s]*(\d+)', re.IGNORECASE)

    def _parse_amount(self, text):
        """Wandelt '11,36' oder '11.36' in float um."""
        return float(text.replace(',', '.'))

    def _find_merchant(self, text):
        """Sucht nach bekannten Haendlernamen im Text."""
        lines = text.split('\n')
        # Die ersten 15 Zeilen sind meist entscheidend fuer den Haendler
        header_text = "\n".join(lines[:15]).upper()
        text_upper = text.upper()

        if "MAE THAI" in text_upper:
            # Wenn Mae Thai im Text steht, ist es oft der Empfänger (Eigenes Restaurant)
            header_text = header_text.replace("MAE THAI", "---")
            text_upper = text_upper.replace("MAE THAI", "---")

        if "FRESH-GO" in text_upper or "FRESH GO" in text_upper:
            return "Fresh-GO Asia"
        if "NGOCHA" in text_upper or "NGOC HA" in text_upper:
            return "Ngocha Asia Markt"
        if "HAMBERGER" in text_upper:
            return "Hamberger"
        
        # Spezielle Prüfung: "Summe Netto" ausschließen
        if "SUMME NETTO" in header_text:
            header_text = header_text.replace("SUMME NETTO", "---")
        if "SUMME NETTO" in text_upper:
            text_upper = text_upper.replace("SUMME NETTO", "---")

        if "V-MARKT" in header_text:
            return "V-Markt"
        if "REWE" in header_text:
            return "REWE"
        if "LIDL" in header_text or "LID)" in header_text:
            return "Lidl"
        if "KAUFLAND" in header_text:
            return "Kaufland"
        
        for merchant in KNOWN_MERCHANTS:
            if merchant.upper() in header_text:
                if merchant.upper() == "NETTO" and ("SUMME" in header_text or "STEUER" in header_text):
                    continue # Überspringe "Summe Netto" oder Steuertabellen-Header
                return MERCHANT_CORRECTIONS.get(merchant, merchant)
        
        # Fallback auf gesamten Text
        for merchant in KNOWN_MERCHANTS:
            if merchant.upper() in text_upper:
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
                date_str = date_str.replace(',', '.')
                parts = date_str.split('.')
                try:
                    day = int(parts[0])
                    # FIX: Manchmal erkennt OCR '44' statt '14'
                    if day > 31:
                        day = int(str(day)[1:]) if len(str(day)) > 1 else day
                    
                    month = int(parts[1])
                    if month > 12:
                        month = int(str(month)[1:]) if len(str(month)) > 1 else month
                    
                    year = int(parts[2])
                    if year < 100:
                        year += 2000
                    # Weitere Plausibilitäts-Checks
                    if day == 0: day = 1
                    if month == 0: month = 1
                    if year > 2100: year = 2026
                    return f"{day:02d}.{month:02d}.{year}"
                except (ValueError, IndexError):
                    return date_str
        return datetime.now().strftime("%d.%m.%Y")

    def _find_total(self, text):
        """
        Findet den Gesamtbetrag - mehrstufiger Ansatz:
        1. Explizite "Summe" / "Gesamtbetrag" (sehr zuverlaessig)
        2. "ZU BEZAHLEN" (hohe Prioritaet)
        3. Kartenzahlung (EC-Cash/Girocard)
        4. Barzahlung (als Fallback, aber niedriger als Summe)
        """
        # Wir sammeln alle moeglichen Betraege mit Gewichten
        candidates = []

        # Fresh-GO Spezialcheck (Zahlbetrag Brutto ohne Komma)
        fg_match = self.freshgo_brutto.search(text)
        if fg_match:
            val_str = fg_match.group(1)
            # Wenn der Betrag sehr groß ist (> 1000) und Fresh-GO im Text steht, 
            # ist es wahrscheinlich Cent ohne Komma (z.B. 21982 -> 219.82)
            if len(val_str) >= 4 and ("FRESH-GO" in text.upper() or "FRESH GO" in text.upper()):
                val = float(val_str) / 100.0
                candidates.append((val, 180))

        for line in text.split('\n'):
            line_upper = line.upper()
            
            # Suche nach Beträgen in der Zeile
            match = self.amount_pattern.search(line)
            if not match:
                continue
                
            try:
                val = self._parse_amount(match.group(1))
            except ValueError:
                continue

            if val <= 0.1:
                continue

            # Gewichtung der Zeile
            weight = 0
            
            if "ZAHLBETRAG BRUTTO" in line_upper:
                weight = 170
            elif "ZU BEZAHLEN" in line_upper or "ZU ZAHLEN" in line_upper:
                weight = 150
            elif "GESAMT BRUTTO" in line_upper or "GESAMTSUMME" in line_upper:
                weight = 160
            elif "SUMME" in line_upper and "NETTO" not in line_upper:
                weight = 100
            elif "GESAMTBETRAG" in line_upper or "GES.BETRAG" in line_upper:
                weight = 110
            elif "TOTAL" in line_upper:
                weight = 80
            elif "KARTENZAHLUNG" in line_upper or "EC-CASH" in line_upper or "GIROCARD" in line_upper:
                weight = 95
            elif "EUR" in line_upper:
                weight = 70
            elif "BAR" in line_upper or "GEGEBEN" in line_upper:
                weight = 40
            
            # STRAFE: Wenn "NETTO" in der Zeile steht, ist es wahrscheinlich kein Brutto-Endbetrag
            if "NETTO" in line_upper or "MWST" in line_upper:
                weight -= 100

            if weight > 0:
                candidates.append((val, weight))

        # Zusätzliche Prüfung durch RegEx (historisch)
        for match in self.sum_keywords.finditer(text):
            try:
                val = self._parse_amount(match.group(1))
                if val > 0.1:
                    label = match.group(0).lower()
                    if "netto" not in label and "mwst" not in label:
                        candidates.append((val, 100))
            except ValueError:
                pass

        # 6. Speziell REWE: Betrag in der letzten Zeile der Steuer-Tabelle
        tax_matches = list(self.tax_table_line.finditer(text))
        if tax_matches:
            # Letzter Eintrag in der Tabelle ist oft die Gesamtsumme
            last_match = tax_matches[-1]
            try:
                val = self._parse_amount(last_match.group(4))
                candidates.append((val, 110)) # Sehr verlässlich bei REWE/Lidl
            except ValueError:
                pass # Fallback, wenn die Gruppe nicht passt

        if not candidates:
            # Fallback: Groesster Betrag im Text
            all_amounts = [self._parse_amount(m) for m in self.amount_pattern.findall(text)]
            valid_amounts = [v for v in all_amounts if 0.1 < v < 5000]
            if valid_amounts:
                return max(valid_amounts)
            return 0.0

        # Wähle den Kandidaten mit dem höchsten Gewicht
        candidates.sort(key=lambda x: x[1], reverse=True)
        # Wenn mehrere Kandidaten das gleiche Gewicht haben, nimm den größten
        best_weight = candidates[0][1]
        best_vals = [c[0] for c in candidates if c[1] == best_weight]
        return max(best_vals)

    def _find_taxes(self, text, brutto):
        """Findet Steuerbetraege (7% und 19%) aus den MwSt-Zeilen."""
        steuer_7 = 0.0
        steuer_19 = 0.0

        # Tabellarische Auswertung (Lidl, Rewe, Kaufland)
        for match in self.tax_table_line.finditer(text):
            label = match.group(0).lower()
            tax_pct_str = match.group(1) or ""
            
            try:
                val1 = self._parse_amount(match.group(2))
                val2 = self._parse_amount(match.group(3))
                val3 = self._parse_amount(match.group(4))
                
                steuer_val = 0.0
                # Heuristik: Die Steuer ist oft der kleinste der drei Beträge,
                # oder die Differenz zwischen Brutto und Netto.
                # Oder die dritte Spalte ist direkt die Steuer.
                
                # Versuch 1: Brutto = Netto + Steuer
                if abs((val1 + val2) - val3) < 0.05: # val1=Netto, val2=Steuer, val3=Brutto
                    steuer_val = val2
                elif abs((val2 + val3) - val1) < 0.05: # val2=Netto, val3=Steuer, val1=Brutto
                    steuer_val = val3
                elif abs((val1 + val3) - val2) < 0.05: # val1=Netto, val3=Steuer, val2=Brutto
                    steuer_val = val3
                else: # Fallback: Nimm den kleinsten der drei, wenn er nicht 0 ist
                    if val1 > 0 and val2 > 0 and val3 > 0:
                        steuer_val = min(val1, val2, val3)
                    elif val1 > 0 and val2 > 0:
                        steuer_val = min(val1, val2)
                    elif val1 > 0:
                        steuer_val = val1 # Letzter Ausweg
                
                if steuer_val > 0:
                    if "19" in tax_pct_str or "a" in label:
                        steuer_19 = float(steuer_19) + steuer_val
                    elif "7" in tax_pct_str or "b" in label:
                        steuer_7 = float(steuer_7) + steuer_val
            except ValueError:
                pass # Skip if parsing fails

        # 3. Hamberger Format (Großmarkt)
        for match in self.hamberger_tax.finditer(text):
            try:
                rate = float(str(match.group(1)).replace(',', '.'))
                # Hamberger OCR ist oft abgeschnitten am Ende (z.B. 4,42 -> 4,4)
                # Wir parsen es so gut wie möglich
                mwst_str = str(match.group(3)).replace(',', '.')
                # Entferne Buchstaben wie 'E' am Ende
                mwst_str = re.sub(r'[^0-9.]', '', mwst_str)
                mwst = float(mwst_str)
                
                if 6.0 <= rate <= 8.0:
                    steuer_7 = float(steuer_7) + mwst
                elif 18.0 <= rate <= 20.0:
                    steuer_19 = float(steuer_19) + mwst
            except ValueError:
                pass

        # 4. Fresh-GO Spezialextraktion
        if "FRESH-GO" in text.upper() or "FRESH GO" in text.upper():
            # MwSt unter Summe MwSt (oft mit Zeilenumbruch)
            mwst_part = re.search(r'Summe\s*MwSt\.?[\s\n]*[:\-—=]?[\s\n]*(\d+[.,]\d{2})', text, re.IGNORECASE)
            if mwst_part:
                try:
                    steuer_7 = self._parse_amount(mwst_part.group(1))
                except ValueError: pass
            
            # Netto unter Summe Netto
            netto_part = re.search(r'Summe\s*Netto\.?[\s\n]*[:\-—=]?[\s\n]*(\d+[.,]\d{2})', text, re.IGNORECASE)
            if netto_part:
                # Wir können Netto nutzen um Brutto zu verifizieren
                pass

        # 5. Hamberger Fallback: Suche nach Beträgen nahe "TUmsatz-Steuer"
        if "HAMBERGER" in text.upper() and steuer_7 == 0.0 and steuer_19 == 0.0:
            ts_match = re.search(r'(?:TUmsatz-Steuer|Umsatz-Steuer)[\s\n]*(\d+[.,]\d+)', text, re.IGNORECASE)
            if ts_match:
                try:
                    steuer_7 = self._parse_amount(ts_match.group(1))
                except ValueError: pass

        # Netto berechnen
        f_brutto = float(brutto)
        f_s7 = float(steuer_7)
        f_s19 = float(steuer_19)
        
        netto = 0.0
        if f_s7 > 0 or f_s19 > 0:
            netto = f_brutto - f_s7 - f_s19
        elif f_brutto > 0:
            # Fallback: Standard 7% (Lebensmittel)
            f_steuer_7 = float(f_brutto - (f_brutto / 1.07))
            steuer_7 = round(f_steuer_7, 2)
            netto = round(float(f_brutto / 1.07), 2)
        else:
            netto = 0.0

        return round(f_brutto, 2), round(netto, 2), round(f_s7, 2), round(f_s19, 2)

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
