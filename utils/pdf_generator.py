from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO
import re


def clean_html(text):
    if text is None:
        return ""

    text = str(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("₹", "Rs.")
    return text.strip()


def get_value(row, key, default=""):
    try:
        return row[key]
    except:
        return default


def generate_pdf(order, items):
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Title"],
        fontSize=24,
        textColor=colors.white,
        alignment=1,
        spaceAfter=10
    )

    section_style = ParagraphStyle(
        "SectionStyle",
        parent=styles["Heading2"],
        fontSize=15,
        textColor=colors.HexColor("#1e3a8a"),
        spaceBefore=14,
        spaceAfter=8
    )

    normal_style = ParagraphStyle(
        "NormalStyle",
        parent=styles["Normal"],
        fontSize=10,
        leading=15
    )

    story = []

    header_table = Table(
        [[Paragraph("SmartCart Invoice", title_style)]],
        colWidths=[170 * mm]
    )

    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#2563eb")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#2563eb")),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))

    story.append(header_table)
    story.append(Spacer(1, 12))

    order_id = get_value(order, "order_id")
    payment_id = get_value(order, "razorpay_payment_id")
    order_date = get_value(order, "created_at")
    amount = get_value(order, "amount")

    story.append(Paragraph("Invoice Details", section_style))

    invoice_data = [
        ["Order ID", clean_html(order_id)],
        ["Payment ID", clean_html(payment_id)],
        ["Order Date", clean_html(order_date)],
    ]

    invoice_table = Table(invoice_data, colWidths=[45 * mm, 125 * mm])
    invoice_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#dbeafe")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1e3a8a")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))

    story.append(invoice_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("Customer Details", section_style))

    address = f"""
    {get_value(order, "address")},
    {get_value(order, "city")},
    {get_value(order, "state")} - {get_value(order, "pincode")}
    """

    customer_data = [
        ["Name", clean_html(get_value(order, "full_name"))],
        ["Phone", clean_html(get_value(order, "phone"))],
        ["Address", clean_html(address)],
    ]

    customer_table = Table(customer_data, colWidths=[45 * mm, 125 * mm])
    customer_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#dcfce7")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#166534")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))

    story.append(customer_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("Order Items", section_style))

    item_data = [["Product", "Qty", "Price", "Total"]]

    grand_total = 0

    for item in items:
        product_name = clean_html(get_value(item, "product_name"))
        quantity = int(get_value(item, "quantity", 0))
        price = float(get_value(item, "price", 0))
        total = quantity * price
        grand_total += total

        item_data.append([
            product_name,
            str(quantity),
            f"Rs. {price:.2f}",
            f"Rs. {total:.2f}"
        ])

    items_table = Table(item_data, colWidths=[75 * mm, 25 * mm, 35 * mm, 35 * mm])
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
    ]))

    story.append(items_table)
    story.append(Spacer(1, 16))

    if amount:
        final_total = amount
    else:
        final_total = grand_total

    total_table = Table(
        [[f"Grand Total: Rs. {float(final_total):.2f}"]],
        colWidths=[170 * mm]
    )

    total_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#dcfce7")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#166534")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 16),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("PADDING", (0, 0), (-1, -1), 12),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#86efac")),
    ]))

    story.append(total_table)
    story.append(Spacer(1, 25))

    footer = Paragraph(
        "Thank you for shopping with SmartCart.",
        ParagraphStyle(
            "FooterStyle",
            parent=normal_style,
            alignment=1,
            textColor=colors.HexColor("#64748b"),
            fontSize=11
        )
    )

    story.append(footer)

    doc.build(story)

    buffer.seek(0)
    return buffer
