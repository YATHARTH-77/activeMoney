import os

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def generate_dense_statement():
    # Save it outside the normal folder so you can manually email it!
    out_dir = "tests/fixtures"
    os.makedirs(out_dir, exist_ok=True)
    pdf_path = os.path.join(out_dir, "zephyr_hostile_test.pdf")
    
    c = canvas.Canvas(pdf_path, pagesize=letter)
    
    # --- HEADER SECTION (NOISE) ---
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, 760, "ZEPHYR QUANTUM WEALTH - INSTITUTIONAL CONSOLIDATED REPORT")
    c.setFont("Helvetica", 7)
    c.drawString(40, 745, "Client: ZQ-7742-ALPHA | Statement Date: 31-Oct-2026 | Base Currency: INR (Indian Rupee) | Generated via Secure API")
    c.drawString(40, 735, "Confidentiality Notice: This document contains highly sensitive financial data. Unauthorized distribution is strictly prohibited under Act 402.")
    
    # --- SUMMARY SECTION (COMPLEX OFFSETS) ---
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, 710, "EXECUTIVE FINANCIAL SUMMARY")
    c.setFont("Helvetica", 9)
    # The AI must calculate offset_words = 6 for this to work!
    c.drawString(40, 695, "Opening Portfolio Value as of 01-Oct-26: 25000000.00") 
    
    # The AI must calculate offset_words = 4 for this!
    c.drawString(40, 680, "Total Settled Cash Balance (INR): 1500000.00")
    
    # The AI must calculate offset_words = 5 for this!
    c.drawString(40, 665, "Net Closing Value (Base INR): 26500000.00")
    
    # Distraction math that the validator doesn't care about
    c.drawString(350, 695, "Total Margin Available: 500000.00")
    c.drawString(350, 680, "Accrued Interest (Not Settled): 25000.00")
    
    # --- DENSE HOLDINGS TABLE ---
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, 630, "ZEPHYR QUANTUM HOLDINGS LEDGER") # This is the start_anchor!
    
    c.setFont("Helvetica-Bold", 8)
    # 6 columns, very tight spacing
    c.drawString(40, 615, "Security Description")
    c.drawString(200, 615, "ISIN Code")
    c.drawString(300, 615, "Quantity")
    c.drawString(360, 615, "Avg Cost")
    c.drawString(430, 615, "Market Value")
    c.drawString(510, 615, "Unrealized P/L")
    
    # Draw a line
    c.line(40, 610, 570, 610)
    
    c.setFont("Helvetica", 8)
    # Row 1 (10 Million)
    c.drawString(40, 595, "Quantum Tech ETF Class B")
    c.drawString(200, 595, "INE999Q01011")
    c.drawString(300, 595, "5000")
    c.drawString(360, 595, "1800.00")
    c.drawString(430, 595, "10000000.00")
    c.drawString(510, 595, "+1000000.00")
    
    # Row 2 (10 Million)
    c.drawString(40, 580, "Zephyr Alpha Strategy")
    c.drawString(200, 580, "INE999Q01022")
    c.drawString(300, 580, "2500")
    c.drawString(360, 580, "3500.00")
    c.drawString(430, 580, "10000000.00")
    c.drawString(510, 580, "+1250000.00")
    
    # Row 3 (5 Million)
    c.drawString(40, 565, "Liquid BeES Treasury")
    c.drawString(200, 565, "INE999Q01033")
    c.drawString(300, 565, "5000")
    c.drawString(360, 565, "1000.00")
    c.drawString(430, 565, "5000000.00")
    c.drawString(510, 565, "0.00")
    
    # Math check: 10M + 10M + 5M = 25M Holdings. + 1.5M Cash = 26.5M Closing.
    
    # --- FOOTER SECTION (MASSIVE NOISE) ---
    c.setFont("Helvetica-Oblique", 6)
    y = 520
    noise_text = "DISCLAIMER: The valuations provided in this statement are for informational purposes only. Zephyr Quantum Wealth does not guarantee the accuracy of third-party pricing feeds. " * 3
    c.drawString(40, y, noise_text[:150])
    c.drawString(40, y-10, noise_text[150:300])
    c.drawString(40, y-20, noise_text[300:450])
    c.drawString(40, y-30, "Past performance is not indicative of future results. Market values include accrued interest where applicable. Please consult your tax advisor regarding Unrealized P/L.")
    
    c.save()
    print(f"✅ Hostile 1-Page PDF generated at: {pdf_path}")

if __name__ == "__main__":
    generate_dense_statement()