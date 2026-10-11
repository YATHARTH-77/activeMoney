import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Ensure output directory exists
OUT_DIR = "tests/fixtures/raw_pdfs"
os.makedirs(OUT_DIR, exist_ok=True)


def create_alpha_wealth_standard():
    """Format 1: Clean, standard PMS format with all typical columns."""
    doc = SimpleDocTemplate(f"{OUT_DIR}/alpha_wealth.pdf", pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("<b>AlphaWealth Portfolio Management Services</b>", styles['Title']))
    elements.append(Paragraph("Client: CLIENT-A01 | Period: Oct 2026", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Summary
    elements.append(Paragraph("<b>Account Summary</b>", styles['Heading2']))
    summary_text = "Opening Value: 1000000.00 | Closing Value: 1050000.00 | Cash: 50000.00"
    elements.append(Paragraph(summary_text, styles['Normal']))
    elements.append(Spacer(1, 20))

    # Holdings Table
    elements.append(Paragraph("<b>Current Holdings</b>", styles['Heading2']))
    data = [
        ["Security Name", "ISIN", "Quantity", "Cost", "Market Value", "Weight (%)"],
        ["Reliance Ind", "INE002A01018", "200", "2500.00", "510000.00", "48.57"],
        ["HDFC Bank", "INE040A01034", "300", "1500.00", "490000.00", "46.67"]
    ]
    t = Table(data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey), 
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), 
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(t)
    doc.build(elements)


def create_beta_aif_alternative():
    """Format 2: Messy headers, missing ISIN, different terminology."""
    doc = SimpleDocTemplate(f"{OUT_DIR}/beta_aif.pdf", pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("<b>Beta Alternative Investment Fund</b>", styles['Title']))
    
    context_text = "Investor ID: B-992 | For Month: October 26 | Base: INR"
    elements.append(Paragraph(context_text, styles['Normal']))
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph("<b>Portfolio Valuation</b>", styles['Heading2']))
    val_text = (
        "Start NAV: 5000000.00 | End NAV: 5200000.00 | "
        "Liquid: 200000.00 | Per Unit: 10.40"
    )
    elements.append(Paragraph(val_text, styles['Normal']))
    elements.append(Spacer(1, 20))

    # Different column names, no ISIN
    data = [
        ["Asset Description", "Units Held", "Avg Price", "Current Val", "% of Total"],
        ["Tech Startup Fund", "500000", "10.00", "5000000.00", "96.15"]
    ]
    t = Table(data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue), 
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), 
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    elements.append(t)
    doc.build(elements)


def create_gamma_multipage():
    """Format 3: Table that breaks across multiple pages."""
    doc = SimpleDocTemplate(f"{OUT_DIR}/gamma_multipage.pdf", pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("<b>Gamma Capital Partners</b>", styles['Title']))
    elements.append(Paragraph("Client: GC-777", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph("Opening: 100.00 | Closing: 150.00 | Cash: 0.00", styles['Normal']))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("<b>Transaction Ledger</b>", styles['Heading2']))
    data1 = [
        ["Date", "Txn Type", "Asset", "Qty", "Amount"],
        ["2026-10-01", "buy", "TCS", "10", "40000.00"]
    ]
    t1 = Table(data1)
    t1.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 1, colors.black)]))
    elements.append(t1)
    
    # FORCE PAGE BREAK
    elements.append(PageBreak())
    
    # CONTINUATION ON PAGE 2
    elements.append(Paragraph("<b>Transaction Ledger (Continued)</b>", styles['Heading2']))
    data2 = [
        ["Date", "Txn Type", "Asset", "Qty", "Amount"],
        ["2026-10-05", "dividend", "TCS", "", "150.00"],
        ["2026-10-10", "fee", "Mgmt", "", "-50.00"]
    ]
    t2 = Table(data2)
    t2.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 1, colors.black)]))
    elements.append(t2)

    doc.build(elements)


if __name__ == "__main__":
    create_alpha_wealth_standard()
    create_beta_aif_alternative()
    create_gamma_multipage()
    print(f"Successfully generated 3 synthetic PDFs in {OUT_DIR}")