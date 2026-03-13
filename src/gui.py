"""
GUI für den Kassenbon-Scanner.
Zeigt links das Bild + OCR-Rohtext, rechts die extrahierten Daten zur Überprüfung.
"""
import customtkinter as ctk
import os
import json
from tkinter import filedialog, messagebox
from PIL import Image
from ocr_engine import ReceiptOCR
from extractor import ReceiptExtractor
from exporter import ReportExporter

# Grund-Setup für das Design
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class ReceiptScannerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Mae Thai - Kassenbon Scanner")
        self.geometry("1100x700")
        self.minsize(900, 600)

        self.ocr = ReceiptOCR()
        self.extractor = ReceiptExtractor()
        self.current_image_path = None

        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        os.makedirs(self.data_dir, exist_ok=True)

        self._build_ui()
        self._check_ocr_status()

    def _build_ui(self):
        # === LINKE SEITE: Bild + OCR Text ===
        self.left_frame = ctk.CTkFrame(self, width=500)
        self.left_frame.pack(side="left", fill="both", expand=True, padx=(20, 10), pady=20)

        # Titel
        ctk.CTkLabel(self.left_frame, text="📄 Kassenbon", font=("Arial", 20, "bold")).pack(pady=(10, 5))

        # Bild laden Button
        self.btn_load = ctk.CTkButton(
            self.left_frame, text="📁 Bild laden (JPG/PNG)",
            command=self.load_image, height=40, font=("Arial", 14)
        )
        self.btn_load.pack(pady=10, padx=20, fill="x")

        self.lbl_image_path = ctk.CTkLabel(self.left_frame, text="Kein Bild geladen", text_color="gray")
        self.lbl_image_path.pack(pady=5)

        # Bild-Vorschau
        self.image_label = ctk.CTkLabel(self.left_frame, text="")
        self.image_label.pack(pady=5)

        # OCR scannen Button
        self.btn_scan = ctk.CTkButton(
            self.left_frame, text="🔍 Text erkennen (OCR)",
            command=self.scan_image, fg_color="#2d8a4e", hover_color="#1f6b3a",
            height=40, font=("Arial", 14, "bold")
        )
        self.btn_scan.pack(pady=10, padx=20, fill="x")

        # OCR Status Label
        self.lbl_ocr_status = ctk.CTkLabel(self.left_frame, text="", text_color="orange")
        self.lbl_ocr_status.pack(pady=2)

        # OCR-Rohtext Vorschau (scrollbar)
        ctk.CTkLabel(self.left_frame, text="Erkannter Rohtext:", font=("Arial", 12), anchor="w").pack(padx=20, anchor="w")
        self.txt_raw_ocr = ctk.CTkTextbox(self.left_frame, height=150, font=("Consolas", 11))
        self.txt_raw_ocr.pack(fill="both", expand=True, padx=20, pady=(5, 10))

        # Export-Button ganz unten
        self.btn_export = ctk.CTkButton(
            self.left_frame, text="📊 Monats-Excel exportieren",
            command=self.export_excel, fg_color="#1a5fb4", hover_color="#144a8f",
            height=35, font=("Arial", 13)
        )
        self.btn_export.pack(pady=(5, 15), padx=20, fill="x")

        # === RECHTE SEITE: Extrahierte Daten ===
        self.right_frame = ctk.CTkFrame(self)
        self.right_frame.pack(side="right", fill="both", expand=True, padx=(10, 20), pady=20)

        ctk.CTkLabel(
            self.right_frame, text="✏️ Erkannte Daten (bitte prüfen)",
            font=("Arial", 18, "bold")
        ).pack(pady=(15, 10))

        self.entries = {}
        fields = [
            ("Händler", "z.B. Lidl, Kaufland, Metro"),
            ("Datum", "TT.MM.JJJJ"),
            ("Brutto", "Gesamtbetrag in €"),
            ("Netto", "Betrag ohne Steuer"),
            ("Steuer_7", "MwSt 7% (Lebensmittel)"),
            ("Steuer_19", "MwSt 19% (Sonstiges)"),
            ("Kategorie", "z.B. Lebensmittel, Getränke"),
        ]

        for field_name, placeholder in fields:
            row = ctk.CTkFrame(self.right_frame, fg_color="transparent")
            row.pack(fill="x", pady=4, padx=20)
            ctk.CTkLabel(row, text=field_name, width=100, anchor="w", font=("Arial", 13)).pack(side="left")
            entry = ctk.CTkEntry(row, width=220, placeholder_text=placeholder)
            entry.pack(side="left", padx=10)
            self.entries[field_name] = entry

        # Kategorie Default
        self.entries["Kategorie"].insert(0, "Lebensmittel")

        # Speichern-Button
        self.btn_save = ctk.CTkButton(
            self.right_frame, text="✅ Beleg bestätigen & speichern",
            command=self.save_data,
            fg_color="#b8860b", hover_color="#96700a",
            height=45, font=("Arial", 15, "bold")
        )
        self.btn_save.pack(pady=30, padx=20, fill="x")

        # Anzahl gespeicherter Belege
        self.lbl_count = ctk.CTkLabel(self.right_frame, text="", text_color="gray")
        self.lbl_count.pack(pady=5)
        self._update_count()

    def _check_ocr_status(self):
        """Zeigt an ob Tesseract verfügbar ist."""
        if self.ocr.is_available():
            self.lbl_ocr_status.configure(
                text=f"✅ Tesseract OCR bereit ({self.ocr.tesseract_path})",
                text_color="green"
            )
        else:
            self.lbl_ocr_status.configure(
                text="⚠️ Tesseract nicht installiert! Bitte installieren (siehe Konsole).",
                text_color="red"
            )

    def _update_count(self):
        """Zählt wie viele Belege bereits gespeichert sind."""
        count = len([f for f in os.listdir(self.data_dir) if f.endswith('.json')])
        self.lbl_count.configure(text=f"📋 {count} Beleg(e) gespeichert")

    def load_image(self):
        file_path = filedialog.askopenfilename(
            title="Kassenbon-Foto auswählen",
            filetypes=[("Bilder", "*.png *.jpg *.jpeg *.bmp *.tiff")]
        )
        if file_path:
            self.current_image_path = file_path
            self.lbl_image_path.configure(text=os.path.basename(file_path), text_color="white")

            # Bildvorschau laden
            try:
                img = Image.open(file_path)
                # Bild skalieren für Vorschau
                img.thumbnail((300, 200))
                ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                self.image_label.configure(image=ctk_image)
                self.image_label._image = ctk_image  # Referenz behalten
            except Exception:
                self.image_label.configure(text="[Vorschau nicht verfügbar]")

    def scan_image(self):
        if not self.current_image_path:
            messagebox.showwarning("Fehler", "Bitte zuerst ein Bild laden!")
            return

        # OCR-Rohtext löschen
        self.txt_raw_ocr.delete("0.0", "end")

        try:
            # OCR durchführen
            raw_text = self.ocr.extract_text(self.current_image_path)

            # Erkannten Text anzeigen
            self.txt_raw_ocr.insert("0.0", raw_text)

            # Daten extrahieren
            extracted_data = self.extractor.extract_data(raw_text)

            # Felder befüllen
            for key, entry in self.entries.items():
                entry.delete(0, 'end')
                if key in extracted_data:
                    entry.insert(0, str(extracted_data[key]))

        except RuntimeError as e:
            messagebox.showerror("Tesseract fehlt!", str(e))
        except Exception as e:
            messagebox.showerror("Fehler bei OCR", str(e))

    def save_data(self):
        # Sammle Daten aus Eingabefeldern
        data = {key: entry.get() for key, entry in self.entries.items()}

        if not data["Händler"] or not data["Brutto"]:
            messagebox.showwarning("Fehler", "Händler und Brutto dürfen nicht leer sein!")
            return

        # Speichere in JSON
        filename = f"beleg_{data['Datum'].replace('.', '')}_{data['Händler']}.json"
        filepath = os.path.join(self.data_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        messagebox.showinfo("Erfolg", f"Beleg gespeichert!\n({filename})")

        # Felder leeren für den nächsten Bon
        for entry in self.entries.values():
            entry.delete(0, 'end')
        self.entries["Kategorie"].insert(0, "Lebensmittel")
        self._update_count()

    def export_excel(self):
        exporter = ReportExporter()
        try:
            out_file = exporter.generate_excel_report()
            messagebox.showinfo("Export Erfolgreich", f"Excel-Tabelle erstellt:\n{out_file}")
        except Exception as e:
            messagebox.showerror("Fehler beim Export", str(e))


if __name__ == "__main__":
    app = ReceiptScannerGUI()
    app.mainloop()
