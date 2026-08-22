"""
This module provides the response classes this app puts on the wire.

Both classes exist because the bytes matter to clients. JSON is written with
sorted keys, escaped non-ASCII and a closing newline. A redirect carries the
courtesy HTML page that names its target, so a browser that does not follow the
redirect still shows the link.
"""

# --------------------------------------------------------------------------------
# Imports
# --------------------------------------------------------------------------------

import json

from html import escape
from typing import Any

from starlette.responses import JSONResponse, Response


# --------------------------------------------------------------------------------
# Responses
# --------------------------------------------------------------------------------

class JsonResponse(JSONResponse):
  """A JSON response with sorted keys, escaped non-ASCII and a trailing newline."""

  def render(self, content: Any) -> bytes:
    body = json.dumps(content, ensure_ascii=True, sort_keys=True, separators=(',', ':'))
    return f'{body}\n'.encode('utf-8')


class RedirectResponse(Response):
  """A redirect that also carries the HTML page naming its target."""

  def __init__(self, location: str, status_code: int = 302) -> None:
    link = escape(location)
    super().__init__(
      content=(
        '<!doctype html>\n'
        '<html lang=en>\n'
        '<title>Redirecting...</title>\n'
        '<h1>Redirecting...</h1>\n'
        '<p>You should be redirected automatically to the target URL: '
        f'<a href="{link}">{link}</a>. If not, click the link.\n'),
      status_code=status_code,
      media_type='text/html',
      headers={'Location': location})
