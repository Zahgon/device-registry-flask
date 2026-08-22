"""
This module provides middleware for HTTP method and trailing-slash handling.

Werkzeug (Flask's routing layer) automatically answered OPTIONS requests,
returned "405 Method Not Allowed" responses that advertise the valid methods,
and redirected a request whose path only matched once a slash was added or a
run of slashes was collapsed. Starlette's router does none of those things, so
this middleware restores that routing behavior.
"""

# --------------------------------------------------------------------------------
# Imports
# --------------------------------------------------------------------------------

import re

from typing import Dict, List, Optional, Set, Tuple

from starlette.datastructures import URL
from starlette.responses import Response
from starlette.routing import Route
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .errors import method_not_allowed
from .responses import RedirectResponse


# --------------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------------

# Header names whose conventional capitalization is not simply title case.
HEADER_CASE_OVERRIDES: Dict[bytes, bytes] = {
  b'www-authenticate': b'WWW-Authenticate',
  b'etag': b'ETag',
  b'te': b'TE',
}


# --------------------------------------------------------------------------------
# Path Functions
# --------------------------------------------------------------------------------

def merge_slashes(path: str) -> str:
  """Collapses each run of slashes in 'path' into one."""
  return re.sub('/{2,}?', '/', path)


def declared_methods(app, path: str) -> Set[str]:
  """Gets the set of HTTP methods declared by the routes that match 'path'."""

  methods: Set[str] = set()

  for route in app.routes:
    if isinstance(route, Route) and route.methods and route.path_regex.match(path):
      methods |= set(route.methods)

  return methods


def valid_methods(declared: Set[str]) -> List[str]:
  """Gets the sorted list of methods a client may call, including OPTIONS."""
  return sorted(declared | {'OPTIONS'})


def resolve(app, path: str, method: str) -> Tuple[Optional[str], Set[str]]:
  """Resolves a request path the way Werkzeug's router did.

  Werkzeug matched the path as it arrived and, when nothing matched, again with
  its repeated slashes collapsed. Either attempt could also find a match one
  trailing slash further on. A path that only matched after a correction was
  answered with a redirect to the corrected path.

  Returns the path to redirect to, or None to stay on this one, together with
  the methods the matched routes declare.
  """

  for candidate in dict.fromkeys([path, merge_slashes(path)]):
    declared = declared_methods(app, candidate)
    if declared:
      return (None if candidate == path else candidate), declared

    declared = declared_methods(app, f'{candidate}/')
    if declared and method in valid_methods(declared):
      return f'{candidate}/', declared

  return None, set()


# --------------------------------------------------------------------------------
# Header Functions
# --------------------------------------------------------------------------------

def capitalize_header_name(name: bytes) -> bytes:
  """Capitalizes a header name the way Werkzeug wrote it onto the wire."""

  lowered = name.lower()

  if lowered in HEADER_CASE_OVERRIDES:
    return HEADER_CASE_OVERRIDES[lowered]

  return b'-'.join(word[:1].upper() + word[1:] for word in lowered.split(b'-'))


# --------------------------------------------------------------------------------
# Middleware
# --------------------------------------------------------------------------------

class HeaderCaseMiddleware:
  """Rewrites outgoing header names to Werkzeug's capitalization.

  Starlette lowercases every header name it emits, while Werkzeug capitalized
  them. Clients treat header names case-insensitively, but some tools compare
  the names as they arrive, so this restores the original casing.
  """

  def __init__(self, app: ASGIApp) -> None:
    self.app = app

  async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
    if scope['type'] != 'http':
      await self.app(scope, receive, send)
      return

    async def send_capitalized(message: Message) -> None:
      if message['type'] == 'http.response.start':
        message['headers'] = [
          (capitalize_header_name(name), value) for name, value in message['headers']]
      await send(message)

    await self.app(scope, receive, send_capitalized)


class MethodRoutingMiddleware:
  """Answers OPTIONS requests, 405 errors, and the router's redirects."""

  def __init__(self, app: ASGIApp) -> None:
    self.app = app

  async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
    if scope['type'] == 'http':
      # Werkzeug matched a path with its leading slashes collapsed into one.
      scope = dict(scope, path='/' + scope['path'].lstrip('/'))
      response = self.intercept(scope)
      if response is not None:
        await response(scope, receive, send)
        return

    await self.app(scope, receive, send)

  def intercept(self, scope: Scope) -> Optional[Response]:
    """Builds a response for this request, or None to let the router handle it."""

    app = scope['app']
    method = scope['method']
    target, declared = resolve(app, scope['path'], method)

    if target is not None:
      return RedirectResponse(str(URL(scope=scope).replace(path=target)), status_code=308)

    if not declared:
      return None

    valid = valid_methods(declared)

    if method == 'OPTIONS':
      return Response(status_code=200, media_type='text/html', headers={'Allow': ', '.join(valid)})

    if method not in declared:
      return method_not_allowed(valid)

    return None
