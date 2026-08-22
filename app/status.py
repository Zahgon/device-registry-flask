"""
This module provides a router for status-related resources.
"""

# --------------------------------------------------------------------------------
# Imports
# --------------------------------------------------------------------------------

import time

from fastapi import APIRouter

from . import START_TIME
from .responses import RedirectResponse


# --------------------------------------------------------------------------------
# Router
# --------------------------------------------------------------------------------

router = APIRouter()


# --------------------------------------------------------------------------------
# Resources
# --------------------------------------------------------------------------------

@router.get('/')
async def index() -> RedirectResponse:
  """
  Redirects to '/status/'.
  """

  return RedirectResponse('/status/', status_code=302)


@router.get('/status/')
async def status_get():
  """
  Provides uptime information about the web service.
  """

  response = {
    'online': True,
    'uptime': round(time.time() - START_TIME, 3)
  }
  return response
