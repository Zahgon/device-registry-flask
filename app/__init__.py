"""
This module provides the app factory method.
It adds all the routers to the app.
This module also provides a reference to the users and the start time.
"""

# --------------------------------------------------------------------------------
# Imports
# --------------------------------------------------------------------------------

import time

from config import config

from fastapi import FastAPI
from fastapi.routing import APIRoute

from .responses import JsonResponse


# --------------------------------------------------------------------------------
# Variables
# --------------------------------------------------------------------------------

START_TIME = time.time()

users = dict()


# --------------------------------------------------------------------------------
# App Factory
# --------------------------------------------------------------------------------

def create_app(config_name: str) -> FastAPI:
  app = FastAPI(title='Device Registry', default_response_class=JsonResponse)
  app.state.config = config[config_name]

  # Werkzeug redirected to a path with one slash more or one slash less, which
  # Starlette's own slash redirects do not cover: MethodRoutingMiddleware does.
  app.router.redirect_slashes = False

  from .database import db
  db.init_app(app.state.config.DATABASE_URI)
  db.create_all()

  from .errors import register_error_handlers
  register_error_handlers(app)

  # The middleware added last runs outermost, so header casing covers every response.
  from .routing import HeaderCaseMiddleware, MethodRoutingMiddleware
  app.add_middleware(MethodRoutingMiddleware)
  app.add_middleware(HeaderCaseMiddleware)

  from .status import router as status_router
  app.include_router(status_router)

  from .auth import router as auth_router, generate_password_hash
  app.include_router(auth_router)

  from .devices import router as devices_router
  app.include_router(devices_router)

  # Every route that serves GET must also serve HEAD, like Werkzeug's router did.
  for route in app.routes:
    if isinstance(route, APIRoute) and 'GET' in route.methods:
      route.methods = set(route.methods) | {'HEAD'}

  username1 = app.state.config.AUTH_USERNAME1
  password1 = generate_password_hash(app.state.config.AUTH_PASSWORD1)
  users[username1] = password1

  username2 = app.state.config.AUTH_USERNAME2
  password2 = generate_password_hash(app.state.config.AUTH_PASSWORD2)
  users[username2] = password2

  return app
