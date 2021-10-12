#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import toml
import os
import appdirs
import sys
import jfc.headers as headers
import jfc.defaults as defaults

SETTINGS_TOML = 'settings.toml'

def main():
    conf_dir = appdirs.user_config_dir('jfc', 'mikeevmm')
    
    if not os.path.exists(conf_dir):
        os.makedirs(conf_dir)
    
    conf_path = os.path.join(conf_dir, SETTINGS_TOML)

    if not os.path.exists(conf_path):
        with open(conf_path, 'w') as conf_file:
            conf_file.write(defaults.SETTINGS)

    if len(sys.argv) > 1 and sys.argv[1].lower() == 'config':
        print(conf_path, end='')
        exit(0)

    # Read the settings
    with open(conf_path, 'r') as conf_file:
        conf = toml.load(conf_file)
    
    # Print a header, because we're cool like that
    headers.print_header()
