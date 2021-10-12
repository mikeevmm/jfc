#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import toml
import os
import headers

SETTINGS_TOML = 'settings.toml'

def main():
    conf_dir = os.path.dirname(os.path.realpath(__file__))
    
    # Read the settings
    conf_path = os.path.join(conf_dir, SETTINGS_TOML)
    with open(conf_path, 'r') as conf_file:
        conf = toml.load(conf_file)
    
    # Print a header, because we're cool like that
    headers.print_header()
