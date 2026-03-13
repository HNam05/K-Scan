import os
import json
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

class ReportExporter:
    def __init__(self):
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        self.export_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "belege")

    def generate_excel_report(self):
        all_receipts = []
        for filename in os.listdir(self.data_dir):
            if filename.endswith('.json'):
                path = os.path.join(self.data_dir, filename)
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    all_receipts.append(data)

        if not all_receipts:
            raise ValueError("Keine gespeicherten Belege im Ordner 'data' gefunden.")

        # Neue Excel über openpyxl
        wb = Workbook()
        ws = wb.active
        ws.title = "Journal"
        
        # Kopfzeile
        headers = ["Händler", "Datum", "Brutto", "Netto", "Steuer_7", "Steuer_19", "Kategorie"]
        ws.append(headers)
        
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill("solid", fgColor="4F81BD")
        for col, _ in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col)
            cell.font = header_font
            cell.fill = header_fill

        # Daten schreiben & formatieren
        totals = {"Brutto": 0.0, "Netto": 0.0, "Steuer_7": 0.0, "Steuer_19": 0.0}
        
        for r_idx, receipt in enumerate(all_receipts, start=2):
            row_data = [
                receipt.get("Händler", ""),
                receipt.get("Datum", ""),
            ]
            
            for key in ["Brutto", "Netto", "Steuer_7", "Steuer_19"]:
                try:
                    val = float(str(receipt.get(key, "0")).replace(',', '.'))
                except ValueError:
                    val = 0.0
                row_data.append(val)
                totals[key] += val
                
            row_data.append(receipt.get("Kategorie", ""))
            ws.append(row_data)
            
            # Währungen formatieren
            for c_idx in range(3, 7):
                ws.cell(row=r_idx, column=c_idx).number_format = '#,##0.00 €'
                
        # Summenzeile
        last_row = len(all_receipts) + 2
        ws.append(["GESAMTSUMME MONAT", ""])
        ws.cell(row=last_row, column=1).font = Font(bold=True)
        
        col_idx = 3
        for key in ["Brutto", "Netto", "Steuer_7", "Steuer_19"]:
            cell = ws.cell(row=last_row, column=col_idx)
            cell.value = totals[key]
            cell.number_format = '#,##0.00 €'
            cell.font = Font(bold=True)
            col_idx += 1

        current_month = datetime.now().strftime("%Y_%m")
        output_file = os.path.join(self.export_dir, f"Mae_Thai_Abrechnung_{current_month}.xlsx")
        
        wb.save(output_file)
        return output_file

if __name__ == "__main__":
    exporter = ReportExporter()
    try:
        out = exporter.generate_excel_report()
        print(f"Excel Bericht erfolgreich erstellt: {out}")
    except Exception as e:
        print(f"Fehler: {e}")
