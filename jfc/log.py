#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rich

def ok(msg):
    rich.print(msg, style='green')

def log(msg):
    rich.print(msg, style='blue')

def warn(msg):
    rich.print(msg, style='yellow')

def error(msg):
    rich.print(msg, style='red')
