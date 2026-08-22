"""
This module provides a router for device resources.
The resources cover basic CRUD operations.
"""

# --------------------------------------------------------------------------------
# Imports
# --------------------------------------------------------------------------------

import json

from typing import Any, Dict, NamedTuple, Optional, Tuple

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from .auth import multi_auth
from .database import get_session
from .errors import NotFoundError, UserUnauthorizedError, ValidationError
from .models import Device


# --------------------------------------------------------------------------------
# Router
# --------------------------------------------------------------------------------

router = APIRouter()


# --------------------------------------------------------------------------------
# Functions
# --------------------------------------------------------------------------------

def query_device(session: Session, id: int, username: str) -> Device:
  device = session.query(Device).filter_by(id=id).first()

  if not device:
    raise NotFoundError()
  elif device.owner != username:
    raise UserUnauthorizedError()

  return device


def save_device(session: Session, device: Device) -> Dict[str, Any]:
  session.add(device)
  session.commit()
  return device.to_json()


class RequestBody(NamedTuple):
  content_type: str
  content: bytes


async def read_request_body(request: Request) -> RequestBody:
  """Reads the body without parsing it, so a route may run other checks first."""

  content_type = request.headers.get('content-type', '').split(';')[0].strip().lower()
  return RequestBody(content_type, await request.body())


def parse_json_body(body: RequestBody) -> Any:
  """Parses the JSON request body, like Flask's 'request.json' property did."""

  if body.content_type != 'application/json' and not body.content_type.endswith('+json'):
    raise ValidationError('request body is missing all fields')

  if not body.content:
    raise ValidationError('request body is missing all fields')

  try:
    return json.loads(body.content)
  except ValueError:
    raise ValidationError('request body is missing all fields')


async def get_json_from_request(request: Request) -> Any:
  return parse_json_body(await read_request_body(request))


def first_query_values(request: Request) -> Dict[str, str]:
  """Gets the first value of every query parameter, repeated ones included."""

  values: Dict[str, str] = dict()

  for name, value in request.query_params.multi_items():
    values.setdefault(name, value)

  return values


def read_byte_range(header: Optional[str], length: int) -> Optional[Tuple[int, int]]:
  """Reads the single byte range 'header' asks for, as a half-open span.

  Returns None when the client asked for no range, or for one this body cannot
  satisfy, in which case the whole body is sent.
  """

  if not header or not header.startswith('bytes='):
    return None

  first, separator, last = header[len('bytes='):].strip().partition('-')
  if not separator or not (first + last).isdigit():
    return None

  if first:
    start = int(first)
    stop = min(int(last) + 1, length) if last else length
  else:
    start, stop = max(length - int(last), 0), length

  return (start, stop) if start < stop else None


def download(request: Request, content: bytes, filename: str) -> Response:
  """Serves 'content' as a named plain-text download, honoring a byte range."""

  headers = {
    'Content-Disposition': f'attachment; filename="{filename}"',
    'Cache-Control': 'no-cache',
  }

  span = read_byte_range(request.headers.get('range'), len(content))
  if span is None:
    return Response(content=content, media_type='text/plain', headers=headers)

  start, stop = span
  headers['Accept-Ranges'] = 'bytes'
  headers['Content-Range'] = f'bytes {start}-{stop - 1}/{len(content)}'

  return Response(
    content=content[start:stop],
    status_code=206,
    media_type='text/plain',
    headers=headers)


# --------------------------------------------------------------------------------
# Resources
# --------------------------------------------------------------------------------

@router.get('/devices/')
def devices_get(
  request: Request,
  username: str = Depends(multi_auth),
  session: Session = Depends(get_session)):
  """
  Gets a list of all devices owned by the user.
  Requires authentication.
  """

  filter_args = dict()
  filter_args['owner'] = username
  query_values = first_query_values(request)

  for field in ['id', 'name', 'location', 'type', 'model', 'serial_number']:
    if value := query_values.get(field):
      filter_args[field] = value

  ds = session.query(Device).filter_by(**filter_args)
  device_dict = {'devices': [device.to_json() for device in ds]}
  return device_dict


@router.post('/devices/')
def devices_post(
  username: str = Depends(multi_auth),
  session: Session = Depends(get_session),
  data: Any = Depends(get_json_from_request)):
  """
  Adds a new device owned by the user.
  Requires authentication.
  """

  device = Device.from_json(data, username)
  return save_device(session, device)


@router.get('/devices/{id:int}')
def device_id_get(
  id: int,
  username: str = Depends(multi_auth),
  session: Session = Depends(get_session)):
  """
  Gets a device owned by the user.
  Requires authentication.
  """

  device = query_device(session, id, username)
  return device.to_json()


@router.put('/devices/{id:int}')
def device_id_put(
  id: int,
  username: str = Depends(multi_auth),
  session: Session = Depends(get_session),
  body: RequestBody = Depends(read_request_body)):
  """
  Replaces a device owned by the user.
  Requires authentication.
  """

  device = query_device(session, id, username)
  device.update_from_json(parse_json_body(body))
  return save_device(session, device)


@router.patch('/devices/{id:int}')
def device_id_patch(
  id: int,
  username: str = Depends(multi_auth),
  session: Session = Depends(get_session),
  body: RequestBody = Depends(read_request_body)):
  """
  Updates a device owned by the user.
  Requires authentication.
  """

  device = query_device(session, id, username)
  device.patch_from_json(parse_json_body(body))
  return save_device(session, device)


@router.delete('/devices/{id:int}')
def device_id_delete(
  id: int,
  username: str = Depends(multi_auth),
  session: Session = Depends(get_session)):
  """
  Deletes a device owned by the user.
  Requires authentication.
  """

  device = query_device(session, id, username)
  session.delete(device)
  session.commit()
  return dict()


@router.get('/devices/{id:int}/report')
def devices_id_report_get(
  request: Request,
  id: int,
  username: str = Depends(multi_auth),
  session: Session = Depends(get_session)):
  """
  Prints a text-based report for a device owned by the user.
  Requires authentication.
  """

  device = query_device(session, id, username)

  lines = [
    f'ID: {device.id}',
    f'Name: {device.name}',
    f'Location: {device.location}',
    f'Type: {device.type}',
    f'Model: {device.model}',
    f'Serial Number: {device.serial_number}',
    f'Owner: {device.owner}',
  ]
  report = ''.join(f'{line}\n' for line in lines).encode('ascii')

  return download(request, report, f'{device.name}.txt')
