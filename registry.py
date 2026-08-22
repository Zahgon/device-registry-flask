"""
This module is the "entry point" for running this FastAPI app.
It creates the app using the "create_app" factory function.
It also creates a CLI command "init-db" for creating the app's SQLite database.

To run this app:
1. Run "uvicorn registry:app".

By default, this app uses the "default" config.
Change the target config by setting the "FLASK_CONFIG" environment variable.
"""

# --------------------------------------------------------------------------------
# Imports
# --------------------------------------------------------------------------------

import click
import os

from app import create_app
from app.database import db
from app.models import Device


# --------------------------------------------------------------------------------
# App Creation
# --------------------------------------------------------------------------------

app = create_app(os.getenv('FLASK_CONFIG') or 'default')


# --------------------------------------------------------------------------------
# CLI Commands
# --------------------------------------------------------------------------------

@click.group()
def cli():
    """Command line utilities for the device registry."""


@cli.command('init-db')
def init_db():
    """Initializes the database with devices."""

    db.drop_all()
    db.create_all()

    light = Device(
      name='Front Porch Light',
      location='Front Porch',
      type='Light Switch',
      model='GenLight 64B',
      serial_number='GL64B-99987',
      owner='pythonista')

    thermostat = Device(
      name='Main Thermostat',
      location='Living Room',
      type='Thermostat',
      model='ThermoBest 3G',
      serial_number='TB3G-12345',
      owner='pythonista')
    
    fridge = Device(
      name='Family Fridge',
      location='Kitchen',
      type='Refrigerator',
      model='El Gee Mondo21',
      serial_number='LGM-20201',
      owner='engineer')

    session = db.session()
    try:
      session.add(light)
      session.add(thermostat)
      session.add(fridge)
      session.commit()
    finally:
      session.close()
    
    click.echo('Initialized the database with fresh data.')


if __name__ == '__main__':
    cli()
