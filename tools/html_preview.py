"""HTML preview generator for live rendering."""
import html as html_module


def wrap_html_document(html_code: str) -> str:
    html_code = html_code.strip()
    if not html_code:
        html_code = "<div style='padding:24px;color:#94a3b8;font-family:sans-serif'>Preview is empty.</div>"

    if "<html" not in html_code.lower():
        html_code = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Live Preview</title>
  <style>
    body {{ margin: 0; padding: 16px; font-family: Inter, Arial, sans-serif; background: #0b1020; color: #e5e7eb; }}
    * {{ box-sizing: border-box; }}
  </style>
</head>
<body>
{html_code}
</body>
</html>"""
    return html_code


def preview_html(html_code: str) -> str:
    document = wrap_html_document(html_code)
    escaped = html_module.escape(document, quote=True)
    return (
        "<iframe "
        "style='width:100%;height:760px;border:1px solid #27324a;border-radius:14px;background:#0b1020' "
        "sandbox='allow-scripts allow-same-origin allow-modals allow-forms allow-downloads' "
        f'srcdoc="{escaped}"></iframe>'
    )
