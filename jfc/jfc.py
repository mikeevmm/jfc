#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Making Journal Club easier.

Usage:
    jfc
    jfc config
    jfc clean db
    jfc clean config
    jfc clean all
    jfc likes
    jfc --version
    jfc --help

Options:
    --version   Show version.
    --help      Show this screen.
"""

import docopt
import toml
import os
import appdirs
import sys
import sqlite3
import halo
import datetime
import random
import textwrap
import rich
import rich.console
import rich.prompt
import webbrowser
import jfc.version as version
import jfc.headers as headers
import jfc.defaults as defaults
import jfc.arxiv as arxiv
import jfc.log as log
from jfc.cursor import WithCursor


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
    arguments = docopt.docopt(__doc__, version=version.__version__)

    conf_dir = appdirs.user_config_dir('jfc', 'mikeevmm')
    data_dir = appdirs.user_data_dir('jfc', 'mikeevmm')
    today = datetime.datetime.today()
    console = rich.console.Console()
    
    # Create configuration directories and files if they don't exist
    if not os.path.exists(conf_dir):
        os.makedirs(conf_dir)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    conf_path = os.path.join(conf_dir, 'settings.toml')
    db_path = os.path.join(data_dir, 'articles.db')

    # Config. reset mode?
    if arguments['clean']:
        if ((arguments['config'] or arguments['all']) 
                and os.path.exists(conf_path)):
            os.rename(conf_path, os.path.join(conf_dir, 'settings.toml.old'))
        if (arguments['db'] or arguments['all']) and os.path.exists(db_path):
            os.rename(db_path, os.path.join(data_dir, 'articles.db.old'))
        exit(0)

    first_time = False
    if not os.path.exists(conf_path):
        first_time = True
        with open(conf_path, 'w') as conf_file:
            conf_file.write(defaults.SETTINGS)

    # Config. dir. output mode?
    if arguments['config']:
        print(conf_path, end='')
        exit(0)

    # Read the settings
    with open(conf_path, 'r') as conf_file:
        conf = toml.load(conf_file)
    
    # Print a header, because we're cool like that
    if conf.get('show_header', True):
        headers.print_header(console)
        print('')

    if first_time:
        log.warn('It seems like this is the first time running jfc. Please '
            'give it some time to fetch articles.')
    
    with halo.Halo(text='Warming up engines...', spinner='dots') as spinner,\
         sqlite3.connect(db_path) as db:
        # Initialize articles table if first time
        with WithCursor(db) as cursor:
            cursor.execute('''CREATE TABLE IF NOT EXISTS articles
                            (year INTEGER NOT NULL,
                             month INTEGER NOT NULL,
                             day INTEGER NOT NULL,
                             title TEXT NOT NULL,
                             abstract TEXT NOT NULL,
                             authors TEXT NOT NULL,
                             category TEXT NOT NULL,
                             link TEXT NOT NULL PRIMARY KEY,
                             read INTEGER NOT NULL,
                             liked INTEGER NOT NULL)''')
        
        # Backwards compatibility; if liked column does not exist,
        # create it. There's no great way to handle this in SQL, so
        # we just try to create the column, and ignore errors that
        # happen if the column exists
        with WithCursor(db) as cursor:
            try:
                cursor.execute(
                        'ALTER TABLE articles '
                        'ADD COLUMN liked INTEGER NOT NULL DEFAULT 0')
            except sqlite3.OperationalError as e:
                pass
    
        # Prune the database of old articles
        # Prune since when?
        conf_delta = conf.get('span', 7) + 1
        prune_since = (today - datetime.timedelta(days=conf_delta)).date()

        with WithCursor(db) as cursor:
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
        with WithCursor(db) as cursor:
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
                        'title': ' '.join(line.strip()
                            for line in entry['title'].splitlines()),
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
                    with WithCursor(db) as cursor:
                        query = cursor.execute(
                            'SELECT EXISTS(SELECT 1 FROM articles '
                            'WHERE link=?)',
                            (item['link'],))
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
                
                with WithCursor(db) as cursor:
                    cursor.executemany(
                        'INSERT INTO articles '
                        '(year, month, day, title, abstract, authors, '
                            'category, link, read, liked) '
                        'VALUES '
                        '(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        [(item['date'].year,
                          item['date'].month,
                          item['date'].day,
                          item['title'],
                          ' '.join(line.strip()
                            for line in item['abstract'].splitlines()),
                          ', '.join(item['authors']),
                          item['category'],
                          item['link'],
                          False,
                          False)
                        for item in items_to_insert])
                
                if finished:
                    db.commit()
                    spinner.succeed('Done.')
                    break
    
    with sqlite3.connect(db_path) as db:
        # Get all the articles that haven't been read yet
        # The results are returned as tuples, being that the field each element
        # of the tuple corresponds to is given by the order in which the columns
        # of the table were declared. This is less than ideal, but follows from
        # the integration with SQLite.
        with WithCursor(db) as cursor:
            query = cursor.execute('SELECT * FROM articles WHERE read = false')
        articles = [
            {field: value for field, value in zip(
                ('year', 'month', 'day', 'title', 'abstract', 'authors',
                    'category', 'link', 'read', 'liked'), element)}
            for element in query]
        random.shuffle(articles)

        # Show the articles

        try:
            for article in articles:
                # Immediately set the article as read. This will allow us to
                # skip early to the next article if the user asks to do so.
                with WithCursor(db) as cursor:
                    cursor.execute(
                            'UPDATE articles SET read=1 WHERE link=?',
                            (article['link'],))

                # Show the article
                console.rule()
                console.print('')
                for line in textwrap.wrap(
                    article['title'], width=console.width):
                    console.print(line, justify='center', soft_wrap=True)
                for line in textwrap.wrap(
                    article['authors'], width=console.width):
                    console.print(line, justify='center', style='dim')
                console.print(article['link'], justify='center', style='dim')
                console.print('')
                    
                action = rich.prompt.Prompt.ask(
                        '[bold green][N][/bold green] Next  '
                        '[bold green][A][/bold green] Show abstract ',
                        choices=['n', 'a', 'N', 'A'], default='N',
                        show_choices=False).lower()
                print('\033[F\033[F') # Overwrite the prompt

                # Skip to next article
                if action == 'n':
                    continue
                
                # Otherwise, show the abstract; do this in a separate screen
                with console.screen():
                    console.print('\n')
                    for line in textwrap.wrap(
                        article['title'], width=console.width):
                        console.print(line, justify='center', soft_wrap=True)
                    for line in textwrap.wrap(
                        article['authors'], width=console.width):
                        console.print(line, justify='center', style='dim')
                    console.print(
                        article['link'], justify='center', style='dim')
                    console.print('\n')
                    for line in textwrap.wrap(
                        article['abstract'], width=console.width):
                        console.print(line, soft_wrap=True)
                    console.print('')

                    while True:
                        # If the article is already liked, no not give the
                        # user the option to like the article again
                        prompt_str = '[bold green][N][/bold green] Next  '
                        if not article['liked']:
                            prompt_str += ('[bold green][L][/bold green] Save '
                                            'to likes ')
                        prompt_str += ('[bold green][O][/bold green] Open in '
                                        'Browser')

                        prompt_choices = ['n', 'o', 'N', 'O']
                        if not article['liked']:
                            prompt_choices += ['l', 'L']

                        action = rich.prompt.Prompt.ask(
                                prompt_str,
                                choices=prompt_choices,
                                show_choices=False, default='N').lower()
                        print('\033[F\033[F') # Overwrite the prompt

                        continue_to_next = False
                        if action == 'n':
                            # Skip to the next article
                            continue_to_next = True
                        elif action == 'l':
                            # Set this article as liked
                            with WithCursor(db) as cursor:
                                cursor.execute(
                                    'UPDATE articles SET liked=1 WHERE link=?',
                                    (article['link'],))
                            article['liked'] = True

                            # Clean the old prompt
                            print(' '*console.width, '\033[F', end='')
                            continue # Re-prompt the user
                        else:   
                            # Otherwise, open the article in the browser,
                            # and continue.
                            webbrowser.open(article['link'])
                            continue_to_next = True

                        if continue_to_next:
                            break # out of prompt loop

        except KeyboardInterrupt:
            exit(0)

    rich.print('[green]:heavy_check_mark: All caught up![/green]')
