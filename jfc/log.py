#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from jfc.ansi import colors

def ok(msg):
    print(colors.OKGREEN, msg, colors.ENDC, sep='')

def log(msg):
    print(colors.OKBLUE, msg, colors.ENDC, sep='')

def warn(msg):
    print(colors.WARNING, msg, colors.ENDC, sep='')

def error(msg):
    print(colors.ERROR, msg, colors.ENDC, sep='')
