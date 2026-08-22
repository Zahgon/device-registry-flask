"""
This module provides error handlers for this FastAPI app.
Error handlers must be overridden to provide JSON responses.
This module also provides a ValidationError exception class.
Any ValidationError exceptions yield a "400 Bad Request" response.
"""

# --------------------------------------------------------------------------------
# Imports
# --------------------------------------------------------------------------------

from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .responses import JsonResponse


# --------------------------------------------------------------------------------
# Variables
# --------------------------------------------------------------------------------

# Flask-HTTPAuth added this header to every "401 Unauthorized" response.
AUTHENTICATE_HEADERS = {'WWW-Authenticate': 'Bearer realm="Authentication Required"'}


# --------------------------------------------------------------------------------
# Exceptions
# --------------------------------------------------------------------------------

class NotFoundError(Exception):
  def __str__(self):
    return 'not found'


class UserUnauthorizedError(Exception):
  def __str__(self):
    return 'current user is not authorized to access this resource'


class UnauthenticatedError(Exception):
  def __str__(self):
    return 'Invalid credentials'


class ValidationError(ValueError):
  pass


# --------------------------------------------------------------------------------
# Response Builders
# --------------------------------------------------------------------------------

def bad_request(message: str) -> JsonResponse:
  return JsonResponse(
    status_code=400,
    content={'error': 'bad request', 'message': message})


def unauthorized(message: str) -> JsonResponse:
  return JsonResponse(
    status_code=401,
    content={'error': 'unauthorized', 'message': message},
    headers=AUTHENTICATE_HEADERS)


def forbidden(message: str) -> JsonResponse:
  return JsonResponse(
    status_code=403,
    content={'error': 'forbidden', 'message': message})


def not_found() -> JsonResponse:
  return JsonResponse(
    status_code=404,
    content={'error': 'not found'})


def method_not_allowed(valid_methods: List[str]) -> JsonResponse:
  return JsonResponse(
    status_code=405,
    content={'error': 'method not allowed', 'valid_methods': valid_methods})


def internal_server_error() -> JsonResponse:
  return JsonResponse(
    status_code=500,
    content={'error': 'internal server error'})


# --------------------------------------------------------------------------------
# Exception Handlers
# --------------------------------------------------------------------------------

async def validation_error_handler(request: Request, exc: ValidationError) -> JsonResponse:
  return bad_request(str(exc))


async def request_validation_error_handler(
  request: Request, exc: RequestValidationError) -> JsonResponse:
  return bad_request('request body is missing all fields')


async def unauthenticated_error_handler(
  request: Request, exc: UnauthenticatedError) -> JsonResponse:
  return unauthorized(str(exc))


async def user_unauthorized_error_handler(
  request: Request, exc: UserUnauthorizedError) -> JsonResponse:
  return forbidden(str(exc))


async def not_found_error_handler(request: Request, exc: NotFoundError) -> JsonResponse:
  return not_found()


async def http_exception_handler(
  request: Request, exc: StarletteHTTPException) -> JsonResponse:
  """Converts the framework's default HTTP errors into this app's JSON format."""

  if exc.status_code == 400:
    return bad_request(str(exc.detail))
  elif exc.status_code == 401:
    return unauthorized(str(exc.detail))
  elif exc.status_code == 403:
    return forbidden(str(exc.detail))
  elif exc.status_code == 404:
    return not_found()
  elif exc.status_code == 405:
    allow: Optional[str] = (exc.headers or dict()).get('Allow')
    valid_methods = sorted(allow.split(', ')) if allow else list()
    return method_not_allowed(valid_methods)
  elif exc.status_code == 500:
    return internal_server_error()

  content: Dict[str, Any] = {'error': str(exc.detail)}
  return JsonResponse(status_code=exc.status_code, content=content, headers=exc.headers)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JsonResponse:
  return internal_server_error()


# --------------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------------

def register_error_handlers(app: FastAPI) -> None:
  """Registers every error handler on the app."""

  app.add_exception_handler(ValidationError, validation_error_handler)
  app.add_exception_handler(RequestValidationError, request_validation_error_handler)
  app.add_exception_handler(UnauthenticatedError, unauthenticated_error_handler)
  app.add_exception_handler(UserUnauthorizedError, user_unauthorized_error_handler)
  app.add_exception_handler(NotFoundError, not_found_error_handler)
  app.add_exception_handler(StarletteHTTPException, http_exception_handler)
  app.add_exception_handler(Exception, unhandled_exception_handler)
