from xhtml2pdf import pisa
from io import BytesIO


def generate_pdf(template_html):
    """
    HTML content ni premium colorful styled PDF ga convert chestundi
    """

    styled_html = f"""
    <html>
    <head>
    <meta charset="UTF-8">

    <style>
        body {{
            font-family: Helvetica, Arial, sans-serif;
            font-size: 13px;
            color: #0F172A;
            background: #F8FAFC;
            padding: 20px;
        }}

        .wrapper {{
            background: #FFFFFF;
            border: 2px solid #E2E8F0;
            border-radius: 12px;
            padding: 25px;
        }}

        .header {{
            background: #2563EB;
            color: #FFFFFF;
            text-align: center;
            padding: 18px;
            font-size: 28px;
            font-weight: bold;
            border-radius: 8px;
            margin-bottom: 22px;
        }}

        .info-box {{
            background: #EFF6FF;
            border-left: 6px solid #2563EB;
            padding: 12px;
            margin-bottom: 12px;
            border-radius: 6px;
            color: #1E3A8A;
        }}

        .section-title {{
            background: #7C3AED;
            color: #FFFFFF;
            padding: 10px;
            font-size: 16px;
            font-weight: bold;
            margin-top: 18px;
            margin-bottom: 10px;
            border-radius: 6px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}

        th {{
            background: #0F172A;
            color: #FFFFFF;
            padding: 10px;
            text-align: left;
            border: 1px solid #0F172A;
        }}

        td {{
            padding: 10px;
            border: 1px solid #E2E8F0;
            color: #1E293B;
        }}

        tr:nth-child(even) {{
            background: #F8FAFC;
        }}

        tr:nth-child(odd) {{
            background: #FFFFFF;
        }}

        .price {{
            color: #10B981;
            font-weight: bold;
        }}

        .old-price {{
            color: #94A3B8;
            text-decoration: line-through;
        }}

        .save {{
            color: #2563EB;
            font-weight: bold;
        }}

        .success-box {{
            background: #DCFCE7;
            color: #166534;
            border-left: 6px solid #10B981;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 12px;
            font-weight: bold;
        }}

        .warning-box {{
            background: #FEF3C7;
            color: #78350F;
            border-left: 6px solid #F59E0B;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 12px;
        }}

        .total-box {{
            margin-top: 20px;
            background: #DCFCE7;
            color: #166534;
            padding: 14px;
            text-align: right;
            font-size: 18px;
            font-weight: bold;
            border-radius: 6px;
            border: 1px solid #10B981;
        }}

        .amount-box {{
            background: #FFF7ED;
            color: #C2410C;
            border-left: 6px solid #F97316;
            padding: 12px;
            border-radius: 6px;
            margin-top: 12px;
            font-weight: bold;
        }}

        .footer {{
            margin-top: 25px;
            text-align: center;
            color: #64748B;
            font-size: 12px;
            border-top: 1px solid #E2E8F0;
            padding-top: 12px;
        }}
    </style>
    </head>

    <body>
        <div class="wrapper">
            {template_html}
        </div>
    </body>
    </html>
    """

    pdf_file = BytesIO()

    pisa_status = pisa.CreatePDF(
        src=styled_html,
        dest=pdf_file,
        encoding='UTF-8'
    )

    if pisa_status.err:
        return None

    pdf_file.seek(0)
    return pdf_file