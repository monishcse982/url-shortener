"""Small browser form for opening a password protected short link."""

from html import escape
from urllib.parse import quote

from fastapi.responses import HTMLResponse


def password_page(short_code: str, *, invalid: bool = False) -> HTMLResponse:
    action = f"/link/{quote(short_code, safe='')}/unlock"
    error = (
        '<p class="error" role="alert">Invalid password. Try again.</p>'
        if invalid
        else ""
    )
    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Unlock link · Shawty</title>
  <style>
    :root {{
      color-scheme: dark;
      font: 14px/1.5 monospace;
      background: #0b0b0c;
      color: #e8e6e1;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      min-height: 100vh;
      margin: 0;
      display: grid;
      place-items: center;
      padding: 20px;
    }}
    main {{
      width: min(100%, 440px);
      background: #141416;
      border: 1px solid #2a2a2e;
      padding: 24px;
    }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    p, label {{ color: #a1a1a6; }}
    label {{ display: block; margin: 22px 0 8px; }}
    input {{
      display: block;
      width: 100%;
      min-height: 44px;
      padding: 10px;
      background: #0b0b0c;
      color: #e8e6e1;
      border: 1px solid #3a3a3f;
      border-radius: 0;
      font: inherit;
    }}
    button {{
      width: 100%;
      min-height: 44px;
      margin-top: 16px;
      padding: 10px;
      background: #ff5a36;
      color: #0b0b0c;
      border: 0;
      border-radius: 0;
      font: inherit;
      font-weight: bold;
      cursor: pointer;
    }}
    :focus-visible {{ outline: 2px solid #ff5a36; outline-offset: 2px; }}
    .error {{ color: #ff6b6b; }}
  </style>
</head>
<body>
  <main>
    <h1>unlock link</h1>
    <p>Enter the password to open this link.</p>
    {error}
    <form method="post" action="{escape(action, quote=True)}">
      <label for="password">password</label>
      <input id="password" name="password" type="password"
             required autofocus autocomplete="off">
      <button type="submit">open link &gt;</button>
    </form>
  </main>
</body>
</html>"""
    return HTMLResponse(
        body,
        status_code=401 if invalid else 200,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'none'; style-src 'unsafe-inline'; "
                "form-action 'self' http: https:; base-uri 'none'"
            ),
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )
