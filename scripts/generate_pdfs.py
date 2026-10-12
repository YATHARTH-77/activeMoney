import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

def generate_stress_test_statement():
    out_dir = "tests/fixtures/raw_pdfs"
    os.makedirs(out_dir, exist_ok=True)
    pdf_path = os.path.join(out_dir, "titan_stress_test.pdf")
    
    c = canvas.Canvas(pdf_path, pagesize=letter)
    
    # ================= PAGE 1: DENSE CONTEXT & DISTRACTIONS =================
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, 750, "TITAN WEALTH ENTERPRISES - CONSOLIDATED STATEMENT")
    
    c.setFont("Helvetica", 8)
    text = "Dear Client, enclosed is your highly detailed, multi-page consolidated statement for the period ending October 2026. " * 5
    c.drawString(50, 720, text[:130])
    c.drawString(50, 710, text[130:260])
    
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, 680, "ACCOUNT SUMMARY (BASE INR)")
    c.setFont("Helvetica", 10)
    c.drawString(50, 660, "Opening Value: 50000000.00")
    c.drawString(250, 660, "Cash Balance: 1500000.00")
    c.drawString(450, 660, "Closing Value: 56500000.00")
    
    # DISTRACTION TABLE (AI might mistakenly parse this)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, 620, "FEE SCHEDULE (IGNORE THIS TABLE)")
    c.setFont("Helvetica", 9)
    c.drawString(50, 600, "Management Fee: 2.0% | Performance Fee: 20.0%")
    
    # REAL HOLDINGS TABLE - START
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 550, "PORTFOLIO HOLDINGS")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, 530, "Security Name")
    c.drawString(200, 530, "ISIN")
    c.drawString(320, 530, "Qty")
    c.drawString(400, 530, "Market Value")
    
    c.setFont("Helvetica", 10)
    y = 510
    for i in range(1, 5):
        c.drawString(50, y, f"Titan Equity Fund {i}")
        c.drawString(200, y, f"INE000T0100{i}")
        c.drawString(320, y, "1000")
        c.drawString(400, y, "5000000.00")  # 4 * 5M = 20M on this page
        y -= 20
        
    c.showPage()
    
    # ================= PAGE 2: PURE HOLDINGS TABLE =================
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 750, "PORTFOLIO HOLDINGS (CONTINUED PAGE 2)")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, 730, "Security Name")
    c.drawString(200, 730, "ISIN")
    c.drawString(320, 730, "Qty")
    c.drawString(400, 730, "Market Value")
    
    c.setFont("Helvetica", 10)
    y = 710
    for i in range(5, 10):
        c.drawString(50, y, f"Titan Debt Fund {i}")
        c.drawString(200, y, f"INE000T0200{i}")
        c.drawString(320, y, "2000")
        c.drawString(400, y, "6000000.00") # 5 * 6M = 30M on this page
        y -= 20
        
    c.showPage()
    
    # ================= PAGE 3: FINAL HOLDING & TRANSACTIONS =================
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 750, "PORTFOLIO HOLDINGS (CONTINUED PAGE 3)")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, 730, "Security Name")
    c.drawString(200, 730, "ISIN")
    c.drawString(320, 730, "Qty")
    c.drawString(400, 730, "Market Value")
    
    c.setFont("Helvetica", 10)
    c.drawString(50, 710, "Titan Gold ETF 10")
    c.drawString(200, 710, "INE000T03010")
    c.drawString(320, 710, "5000")
    c.drawString(400, 710, "5000000.00") # 1 * 5M = 5M. Total = 20M + 30M + 5M = 55M.
    
    c.showPage()
    
    # ================= PAGE 4: FOOTER =================
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(50, 750, "End of Statement. This document was automatically generated for stress testing.")
    c.save()
    
    print(f"✅ Titan Stress Test 4-Page PDF generated at: {pdf_path}")

if __name__ == "__main__":
    generate_stress_test_statement()