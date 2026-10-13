import os

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def generate_stress_test_statement():
    out_dir = "tests/fixtures/raw_pdfs"
    os.makedirs(out_dir, exist_ok=True)
    pdf_path = os.path.join(out_dir, "titan_stress_test.pdf")

    c = canvas.Canvas(pdf_path, pagesize=letter)

    # ================= PAGE 1: DENSE CONTEXT, DISTRACTIONS & RUNNING FOOTER =================
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "TITAN WEALTH ENTERPRISES - CONSOLIDATED STATEMENT")

    c.setFont("Helvetica", 8)
    c.drawString(50, 730, "Client ID: TITAN-8821-X | Period: Oct 2026 | Base Currency: INR")
    c.drawString(
        50,
        715,
        "Dear Investor, enclosed is your multi-page institutional portfolio statement across equity, debt, and gold strategies.",
    )

    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, 685, "ACCOUNT SUMMARY (BASE INR)")
    c.setFont("Helvetica", 10)
    c.drawString(50, 665, "Opening Value: 50000000.00")
    c.drawString(240, 665, "Cash Balance: 1500000.00")
    c.drawString(430, 665, "Closing Value: 56500000.00")

    # DISTRACTION SECTION
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, 630, "ADVISORY FEE SCHEDULE (NON-HOLDINGS)")
    c.setFont("Helvetica", 9)
    c.drawString(50, 615, "Fixed Management Fee: 1.50% p.a. | Hurdle Rate: 10.00%")

    # REAL HOLDINGS TABLE - PAGE 1 START
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 570, "PORTFOLIO HOLDINGS")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, 550, "Security Name")
    c.drawString(200, 550, "ISIN")
    c.drawString(320, 550, "Qty")
    c.drawString(420, 550, "Market Value")

    c.setFont("Helvetica", 10)
    y = 530
    for i in range(1, 5):
        c.drawString(50, y, f"Titan Equity Fund {i}")
        c.drawString(200, y, f"INE000T0100{i}")
        c.drawString(320, y, "1000")
        c.drawString(420, y, "5000000.00")  # 4 * 5M = 20M on Page 1
        y -= 20

    # TRAP: Running Footer on Page 1 (Would kill a naive parser!)
    c.setFont("Helvetica-Oblique", 7)
    c.drawString(50, 50, "Disclaimer: Values are subject to market risk. Page 1 of 4 - Continued on next page")
    c.showPage()

    # ================= PAGE 2: CONTINUATION & RUNNING FOOTER =================
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 750, "PORTFOLIO HOLDINGS (CONTINUED PAGE 2)")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, 730, "Security Name")
    c.drawString(200, 730, "ISIN")
    c.drawString(320, 730, "Qty")
    c.drawString(420, 730, "Market Value")

    c.setFont("Helvetica", 10)
    y = 710
    for i in range(5, 10):
        c.drawString(50, y, f"Titan Debt Fund {i}")
        c.drawString(200, y, f"INE000T0200{i}")
        c.drawString(320, y, "2000")
        c.drawString(420, y, "6000000.00")  # 5 * 6M = 30M on Page 2
        y -= 20

    # TRAP: Running Footer on Page 2
    c.setFont("Helvetica-Oblique", 7)
    c.drawString(50, 50, "Disclaimer: Past performance is not indicative of future returns. Page 2 of 4")
    c.showPage()

    # ================= PAGE 3: FINAL HOLDING + TRANSACTION LEDGER =================
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 750, "PORTFOLIO HOLDINGS (CONTINUED PAGE 3)")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, 730, "Security Name")
    c.drawString(200, 730, "ISIN")
    c.drawString(320, 730, "Qty")
    c.drawString(420, 730, "Market Value")

    c.setFont("Helvetica", 10)
    c.drawString(50, 710, "Titan Gold ETF 10")
    c.drawString(200, 710, "INE000T03010")
    c.drawString(320, 710, "5000")
    c.drawString(420, 710, "5000000.00")  # 1 * 5M = 5M on Page 3. Total Holdings = 55M!

    # NEW SECTION ON PAGE 3: Transaction Ledger (Should trigger TERMINATED for Holdings)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 640, "TRANSACTION LEDGER")
    c.setFont("Helvetica", 10)
    c.drawString(50, 620, "2026-10-12 buy Titan Gold ETF 5000 5000000.00")

    c.setFont("Helvetica-Oblique", 7)
    c.drawString(50, 50, "Disclaimer: Institutional Client Copy. Page 3 of 4")
    c.showPage()

    # ================= PAGE 4: LEGAL DISCLOSURES =================
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(50, 750, "End of Statement. All 10 holdings across 3 pages must sum to 55,000,000.00 INR.")
    c.drawString(50, 50, "Page 4 of 4")
    c.save()

    print(f"✅ Titan 4-Page Multi-Page Stress Test PDF generated at: {pdf_path}")


if __name__ == "__main__":
    generate_stress_test_statement()