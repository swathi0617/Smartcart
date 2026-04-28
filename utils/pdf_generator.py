from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO


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

    title = ParagraphStyle(
        "title",
        parent=styles["Title"],
        fontSize=26,
        textColor=colors.white,
        alignment=1,
        spaceAfter=6
    )

    subtitle = ParagraphStyle(
        "subtitle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.white,
        alignment=1
    )

    section = ParagraphStyle(
        "section",
        parent=styles["Heading2"],
        fontSize=15,
        textColor=colors.HexColor("#1e3a8a"),
        spaceBefore=18,
        spaceAfter=8
    )

    normal = ParagraphStyle(
        "normal",
        parent=styles["Normal"],
        fontSize=10,
        leading=14
    )

    story = []

    header = Table([
        [Paragraph("🛒 SmartCart Invoice", title)],
        [Paragraph("Thank you for shopping with SmartCart", subtitle)]
    ], colWidths=[170 * mm])

    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#2563eb")),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#2563eb")),
    ]))

    story.append(header)
    story.append(Spacer(1, 18))

    order_id = get_value(order, "order_id")
    payment_id = get_value(order, "razorpay_payment_id")
    order_date = get_value(order, "created_at")
    amount = get_value(order, "amount")

    top_info = Table([
        ["Invoice No", f"INV-{order_id}", "Order Date", str(order_date)],
        ["Payment ID", str(payment_id), "Payment Status", "Paid"]
    ], colWidths=[35 * mm, 55 * mm, 35 * mm, 45 * mm])

    top_info.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eff6ff")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1e3a8a")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#1e3a8a")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("PADDING", (0, 0), (-1, -1), 9),
    ]))

    story.append(top_info)

    story.append(Paragraph("Customer Details", section))

    address = f"""
    {get_value(order, "address")},
    {get_value(order, "city")},
    {get_value(order, "state")} - {get_value(order, "pincode")}
    """

    customer = Table([
        ["Customer Name", str(get_value(order, "full_name"))],
        ["Phone Number", str(get_value(order, "phone"))],
        ["Delivery Address", Paragraph(address, normal)],
    ], colWidths=[45 * mm, 125 * mm])

    customer.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#dcfce7")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#166534")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("PADDING", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    story.append(customer)

    story.append(Paragraph("Order Summary", section))

    item_data = [["Product Name", "Qty", "Price", "Total"]]

    grand_total = 0

    for item in items:
        name = str(get_value(item, "product_name"))
        qty = int(get_value(item, "quantity", 0))
        price = float(get_value(item, "price", 0))
        total = qty * price
        grand_total += total

        item_data.append([
            name,
            str(qty),
            f"Rs. {price:.2f}",
            f"Rs. {total:.2f}"
        ])

    items_table = Table(item_data, colWidths=[80 * mm, 25 * mm, 32 * mm, 33 * mm])

    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("PADDING", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))

    story.append(items_table)
    story.append(Spacer(1, 18))

    final_total = float(amount) if amount else grand_total

    total_box = Table([
        ["", "", "Grand Total", f"Rs. {final_total:.2f}"]
    ], colWidths=[70 * mm, 35 * mm, 35 * mm, 30 * mm])

    total_box.setStyle(TableStyle([
        ("BACKGROUND", (2, 0), (-1, -1), colors.HexColor("#16a34a")),
        ("TEXTCOLOR", (2, 0), (-1, -1), colors.white),
        ("FONTNAME", (2, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (2, 0), (-1, -1), 14),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 10),
    ]))

    story.append(total_box)
    story.append(Spacer(1, 25))

    note = Paragraph(
        "This is a computer-generated invoice. No signature required.<br/>For support, contact SmartCart customer care.",
        ParagraphStyle(
            "note",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#64748b"),
            alignment=1,
            leading=14
        )
    )

    story.append(note)

    doc.build(story)
    buffer.seek(0)
    return buffer
