"""Small browser form for opening a password protected short link."""

from html import escape
from urllib.parse import quote

from fastapi.responses import HTMLResponse


def password_page(short_code: str, *, invalid: bool = False) -> HTMLResponse:
    action = f"/link/{quote(short_code, safe='')}/unlock"
    icon = quote(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<rect width="64" height="64" rx="4" fill="#0b0f0e"/>'
        '<path d="M13 13h38v8L26 43h25v8H13v-8l25-22H13z" fill="#e8f0eb"/>'
        '<path d="M37 55h14v5H37z" fill="#6ef3b4"/></svg>',
        safe="",
    )
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
  <title>unlock link · zipp_</title>
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,{icon}">
  <style>
    :root {{
      color-scheme: dark;
      --color-bg: #0b0f0e;
      --color-surface: #151c19;
      --color-accent: #6ef3b4;
      --color-text: #e8f0eb;
      --color-text-muted: #889b90;
      --color-border: #25332c;
      --color-border-strong: #3b5144;
      --color-hover: #1d2923;
      --color-danger: #ff8585;
      font: 14px/1.5 ui-monospace, monospace;
      background: var(--color-bg);
      color: var(--color-text);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      min-height: 100vh;
      margin: 0;
      display: grid;
      place-items: center;
      padding: 20px;
      background: radial-gradient(circle, var(--color-border) 1px,
                  transparent 1px) 0 0 / 16px 16px, var(--color-bg);
    }}
    main {{
      width: min(100%, 440px);
      background: var(--color-surface);
      border: 1px solid var(--color-border);
      padding: 24px;
    }}
    .brand {{ color: var(--color-accent); font-size: 13px; }}
    h1 {{ margin: 24px 0 8px; font-size: 28px; }}
    p, label {{ color: var(--color-text-muted); }}
    label {{ display: block; margin: 22px 0 8px; }}
    input {{
      display: block;
      width: 100%;
      min-height: 44px;
      padding: 10px;
      background: var(--color-bg);
      color: var(--color-text);
      border: 1px solid var(--color-border-strong);
      border-radius: 0;
      font: inherit;
    }}
    button {{
      width: 100%;
      min-height: 44px;
      margin-top: 16px;
      padding: 10px;
      background: var(--color-accent);
      color: var(--color-bg);
      border: 0;
      border-radius: 0;
      font: inherit;
      font-weight: bold;
      cursor: pointer;
    }}
    button:hover {{ background: var(--color-hover); color: var(--color-accent); }}
    :focus-visible {{ outline: 2px solid var(--color-accent); outline-offset: 2px; }}
    .error {{ color: var(--color-danger); }}
  </style>
</head>
<body>
  <main>
    <div class="brand">zipp_</div>
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
                "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
                "form-action 'self' http: https:; base-uri 'none'"
            ),
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )
