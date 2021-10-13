#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rich

def ok(msg):
    rich.print(f'[green]{msg}[/green]')

def log(msg):
    rich.print(f'[blue]{msg}[/blue]')

def warn(msg):
    rich.print(f'[yellow]{msg}[/yellow]')

def error(msg):
    rich.print(f'[red]{msg}[/red]')
