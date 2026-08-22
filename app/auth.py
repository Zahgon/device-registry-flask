"""
This module provides a router and dependencies for authentication support.
Most resources (but not all) in this app require authentication.

Authentication may be handled two ways:
1. Basic HTTP authentication (username/password)
2. Token authentication (Bearer)

The username and password come from 'users', which gets values from the config.
In a *real* app, the database should store users and passwords.

Call the "/authenticate/" resource to get an authentication token.
Tokens expire after 1 hour (unless otherwise configured).
"""

# --------------------------------------------------------------------------------
# Imports
# --------------------------------------------------------------------------------

import base64
import hashlib
import hmac
import jwt
import os

from typing import Optional, Tuple

from fastapi import APIRouter, Depends, Request

from . import users
from .errors import UnauthenticatedError


# --------------------------------------------------------------------------------
# Router
# --------------------------------------------------------------------------------

router = APIRouter()


# --------------------------------------------------------------------------------
# Variables
# --------------------------------------------------------------------------------

# The one scheme that names a token. Every other scheme names basic credentials.
TOKEN_SCHEME = 'Bearer'


# --------------------------------------------------------------------------------
# Password Hashing Functions
# --------------------------------------------------------------------------------

HASH_METHOD = 'sha256'
HASH_ITERATIONS = 260000


def generate_password_hash(password: str) -> str:
  """Hashes a password with a random salt using PBKDF2."""

  salt = os.urandom(16)
  digest = hashlib.pbkdf2_hmac(HASH_METHOD, password.encode('utf-8'), salt, HASH_ITERATIONS)
  return f'pbkdf2:{HASH_METHOD}:{HASH_ITERATIONS}${salt.hex()}${digest.hex()}'


def check_password_hash(password_hash: str, password: str) -> bool:
  """Verifies that 'password' matches the given PBKDF2 hash."""

  try:
    method, salt_hex, digest_hex = password_hash.split('$')
    iterations = int(method.split(':')[2])
    salt = bytes.fromhex(salt_hex)
  except (AttributeError, IndexError, ValueError):
    return False

  digest = hashlib.pbkdf2_hmac(HASH_METHOD, password.encode('utf-8'), salt, iterations)
  return hmac.compare_digest(digest.hex(), digest_hex)


# --------------------------------------------------------------------------------
# Authentication Token Functions
# --------------------------------------------------------------------------------

def serialize_token(username: str, secret_key: str) -> str:
  token = jwt.encode({"username": username}, secret_key, algorithm="HS256")
  return token


def deserialize_token(token: str, secret_key: str) -> Optional[str]:
  try:
    data = jwt.decode(token, secret_key, algorithms=["HS256"])
  except:
    return None
  if 'username' in data:
    return data['username']
  return None


# --------------------------------------------------------------------------------
# Authentication Verification Functions
# --------------------------------------------------------------------------------

def verify_password(username: str, password: str) -> Optional[str]:
  if username in users:
      if check_password_hash(users.get(username), password):
          return username
  return None


def verify_token(token: str, secret_key: str) -> Optional[str]:
  if username := deserialize_token(token, secret_key):
    return username
  return None


# --------------------------------------------------------------------------------
# Authorization Header Parsing
# --------------------------------------------------------------------------------

def read_basic_credentials(header: str) -> Optional[Tuple[str, str]]:
  """Reads the "username:password" pair out of an Authorization header value.

  Only the credentials are read: whichever scheme names them is accepted, and
  the base64 decoder skips over any character that cannot be part of a payload.
  """

  try:
    scheme, credentials = header.encode('utf-8').split(b' ', 1)
    username, password = base64.b64decode(credentials).split(b':', 1)
  except ValueError:
    return None

  try:
    return username.decode('utf-8'), password.decode('utf-8')
  except UnicodeDecodeError:
    return username.decode('latin-1'), password.decode('latin-1')


def read_token(header: str) -> Optional[str]:
  """Reads the token out of an Authorization header value that names one."""

  parts = header.split(None, 1)
  return parts[1] if len(parts) == 2 and parts[0] == TOKEN_SCHEME else None


# --------------------------------------------------------------------------------
# Dependencies
# --------------------------------------------------------------------------------

def authenticate_request(request: Request, allow_token: bool) -> str:
  """Resolves the current user from the Authorization header."""

  username: Optional[str] = None
  header = request.headers.get('Authorization')
  token = read_token(header) if header and allow_token else None

  if token is not None:
    username = verify_token(token, request.app.state.config.SECRET_KEY)
  elif header:
    credentials = read_basic_credentials(header)
    username = verify_password(*credentials) if credentials else None

  if not username:
    raise UnauthenticatedError()

  return username


async def basic_auth(request: Request) -> str:
  """Requires basic HTTP authentication."""
  return authenticate_request(request, allow_token=False)


async def multi_auth(request: Request) -> str:
  """Requires either basic HTTP authentication or token authentication."""
  return authenticate_request(request, allow_token=True)


# --------------------------------------------------------------------------------
# Resources
# --------------------------------------------------------------------------------

@router.get('/authenticate/')
async def authenticate(request: Request, username: str = Depends(basic_auth)):
  """
  Uses HTTP basic authentication to generate an authentication token.
  Any resource that requires authentication can use either basic auth or this token.
  """

  token = serialize_token(username, request.app.state.config.SECRET_KEY)
  return {'token': token}
