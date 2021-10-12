#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import toml
import os
import appdirs
import sys
import sqlite3
import halo
import datetime
import jfc.headers as headers
import jfc.defaults as defaults
import jfc.arxiv as arxiv


CATEGORY_KEYS = [
    'cs',
    'econ',
    'eess',
    'math',
    'astro-ph',
    'cond-mat',
    'gr-qc',
    'hep-ex',
    'hep-lat',
    'hep-ph',
    'hep-th',
    'math-ph',
    'nlin',
    'nucl-ex',
    'nucl-th',
    'physics',
    'quant-ph',
    'q-bio',
    'q-fin',
    'stat',
]


def main():
    conf_dir = appdirs.user_config_dir('jfc', 'mikeevmm')
    data_dir = appdirs.user_data_dir('jfc', 'mikeevmm')
    today = datetime.datetime.today()
    
    # Create configuration directories and files if they don't exist
    if not os.path.exists(conf_dir):
        os.makedirs(conf_dir)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    conf_path = os.path.join(conf_dir, 'settings.toml')
    db_path = os.path.join(data_dir, 'articles.db')

    if not os.path.exists(conf_path):
        with open(conf_path, 'w') as conf_file:
            conf_file.write(defaults.SETTINGS)

    # Config. dir. output mode?
    if len(sys.argv) > 1 and sys.argv[1].lower() == 'config':
        print(conf_path, end='')
        exit(0)

    # Read the settings
    with open(conf_path, 'r') as conf_file:
        conf = toml.load(conf_file)
    
    # Print a header, because we're cool like that
    if conf['show_header']:
        headers.print_header()
        print('')
    
    with halo.Halo(text='Warming up engines', spinner='dots'):
        # Load the database
        db = sqlite3.connect(db_path)
        cursor = db.cursor()

        # Initialize articles table if first time
        cursor.execute('''CREATE TABLE IF NOT EXISTS articles
                        (id INTEGER NOT NULL PRIMARY KEY,
                         year INTEGER NOT NULL,
                         month INTEGER NOT NULL,
                         day INTEGER NOT NULL,
                         title TEXT NOT NULL,
                         abstract TEXT NOT NULL,
                         link TEXT NOT NULL UNIQUE)''')
    
        # Prune the database of old articles
        # Prune since when?
        conf_delta = conf['span']
        prune_since = today - datetime.timedelta(days=conf_delta)

        cursor.execute('DELETE FROM articles WHERE YEAR<:year OR '
                        '(YEAR=:year AND MONTH<:month) OR '
                        '(YEAR=:year AND MONTH=:month AND DAY<:day)',
                    {'day':prune_since.day,
                     'month':prune_since.month,
                     'year':prune_since.year})
        
        # Find out if we need to poll the ArXiv database again
        # (or if we have already done so today)
        last_published = None
        today_date = today.date()
        query = cursor.execute('SELECT day, month, year FROM articles')
        for (day, month, year) in query:
            date = datetime.date(day=day, month=month, year=year)
            if last_published is None or date > today_date:
                last_published = date
        
        # last_published == None is also covered
        if last_published == today_date:
            # No need to poll the API again
            pass
        else:
            # Poll the ArXiv API
            # We're very explicit here to make sure we don't send garbage into
            #  the ArXiv query.
            categories = [cat for cat in CATEGORY_KEYS
                            if conf['categories'].get(cat, False)]

            for results_page in arxiv.query(categories):
                pass
                break # TODO
