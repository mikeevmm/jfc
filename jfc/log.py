#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from jfc.ansi import colors

def log(msg):
    print(colors.OKBLUE, msg, colors.ENDC, sep='')

def error(msg):
    print(colors.ERROR, msg, colors.ENDC, sep='')
