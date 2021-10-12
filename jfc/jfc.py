#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import toml
import os
import appdirs
import sys
import sqlite3
import halo
import time
import datetime
import random
import curses
import jfc.headers as headers
import jfc.defaults as defaults
import jfc.arxiv as arxiv
import jfc.log as log
import jfc.ansi as ansi


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

    # Config. reset mode?
    if len(sys.argv) > 1 and sys.argv[1].lower() == 'clean':
        if os.path.exists(conf_path):
            os.rename(conf_path, os.path.join(conf_dir, 'settings.toml.old'))
        if os.path.exists(db_path):
            os.rename(db_path, os.path.join(data_dir, 'articles.db.old'))
        exit(0)

    first_time = False
    if not os.path.exists(conf_path):
        first_time = True
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
    if conf.get('show_header', True):
        headers.print_header()
        print('')

    if first_time:
        log.warn('It seems like this is the first time running jfc. Please '
            'give it some time to fetch articles.')
    
    with halo.Halo(text='Warming up engines...', spinner='dots') as spinner,\
         sqlite3.connect(db_path) as db:
        # Load the database
        cursor = db.cursor()

        # Initialize articles table if first time
        cursor.execute('''CREATE TABLE IF NOT EXISTS articles
                        (year INTEGER NOT NULL,
                         month INTEGER NOT NULL,
                         day INTEGER NOT NULL,
                         title TEXT NOT NULL,
                         abstract TEXT NOT NULL,
                         authors TEXT NOT NULL,
                         category TEXT NOT NULL,
                         link TEXT NOT NULL PRIMARY KEY,
                         read BOOLEAN)''')
    
        # Prune the database of old articles
        # Prune since when?
        conf_delta = conf.get('span', 7)
        prune_since = (today - datetime.timedelta(days=conf_delta)).date()

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
            if last_published is None or date > last_published:
                last_published = date
        
        # (articles are published on yesterday's midnight; this is parsed as
        #   yesterday)
        if (last_published is not None and
            last_published == today_date - datetime.timedelta(days=1)):
            # No need to poll the API again
            pass
        else:
            # Poll the ArXiv API
            # We're very explicit here to make sure we don't send garbage into
            #  the ArXiv query.
            categories = [cat for cat in CATEGORY_KEYS
                            if conf.get('categories', {}).get(cat, False)]
            
            page_size = 200
            for i, results_page in enumerate(arxiv.query(
                                        categories, page_size=page_size)):
                spinner.text = (random.choice([
                    'Perusing ArXiv...',
                    'Eyeing articles...',
                    'Contacting Reviewer #2...',
                    'Checking out the math...',
                    'Contacting the corresponding author...',
                    'Commenting publication...',
                    'Skipping to the conclusions...',
                    'Recompiling LaTeX...',
                    'Calling the arXiv API... (no, really)',
                    'Wow, this is taking a while?',
                    'Reading the abstract only...'])
                    + ' (' + str(i*page_size) + ')')

                if results_page['bozo'] == True:
                    spinner.fail(
                        'Something went wrong on the ArXiv end of things. '
                        'Please try again later.')
                    exit(1)

                items_to_insert = []

                finished = False
                for entry in results_page['entries']:
                    item = {
                        'link': entry['link'],
                        'date': datetime.datetime(
                            *entry['published_parsed'][:6]).date(),
                        'title': entry['title'],
                        'abstract': entry['summary'],
                        'authors': [
                            author['name'] for author in entry['authors']],
                        'category': entry['arxiv_primary_category']['term']
                    }

                    # Results are sorted by update date from newest to oldest,
                    # so if we're looking at dates older than the pruning date
                    # we can abort.
                    if item['date'] < prune_since:
                        # However, if this is an item that has appeared because
                        # its update date is recent, we continue scanning the
                        # list.
                        update_date = datetime.datetime(
                            *entry['updated_parsed'][:6]).date()
                        if update_date >= prune_since:
                            continue

                        finished = True
                        break
                    
                    # Likewise, if the link is found in the database, then we've
                    # already seen this and everything older.
                    query = cursor.execute(
                        'SELECT EXISTS(SELECT 1 FROM articles WHERE link=:link)',
                        {'link': item['link']})
                    seen = False
                    for value in query:
                        if value != (0,):
                            seen = True
                    if seen:
                        finished = True
                        break 
                    
                    # Otherwise, push this item into the database
                    # We can batch-execute queries/inserts into the SQL database,
                    # so we postpone this to the end of the loop.
                    items_to_insert.append(item)
                
                cursor.executemany(
                    'INSERT INTO articles '
                    '(year, month, day, title, abstract, authors, category, '
                        'link, read) '
                    'VALUES '
                    '(?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    [(item['date'].year,
                      item['date'].month,
                      item['date'].day,
                      item['title'],
                      item['abstract'],
                      ', '.join(item['authors']),
                      item['category'],
                      item['link'],
                      False)
                    for item in items_to_insert])
                
                if finished:
                    spinner.succeed('Done.')
                    break
    
    with sqlite3.connect(db_path) as db:
        cursor = db.cursor()

        # Get all the articles that haven't been read yet
        # The results are returned as tuples, being that the field each element
        # of the tuple corresponds to is given by the order in which the columns
        # of the table were declared. This is less than ideal, but follows from
        # the integration with SQLite.
        query = cursor.execute('SELECT * FROM articles WHERE read = false')
        articles = [
            {field: value for field, value in zip(
                ('year', 'month', 'day', 'title', 'abstract', 'authors',
                    'category', 'link', 'read'), element)}
            for element in query]
        random.shuffle(articles)

         # Initialize curses
         stdscr=curses.initscr()
         curses.noecho()
         curses.cbreak()
         stdscr.keypad(1)

