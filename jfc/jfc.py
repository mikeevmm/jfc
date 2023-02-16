#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Making Journal Club easier.

Usage:
    jfc
    jfc config
    jfc clean db
    jfc clean config
    jfc clean all
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
import itertools
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

MONTHS = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Ago',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
]


def main():
    arguments = docopt.docopt(__doc__, version=version.__version__)

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
    if arguments['clean']:
        if ((arguments['config'] or arguments['all']) 
                and os.path.exists(conf_path)):
            os.rename(conf_path, os.path.join(conf_dir, 'settings.toml.old'))
        if (arguments['db'] or arguments['all']) and os.path.exists(db_path):
            db_backup_path = os.path.join(data_dir, 'articles.db.old')
            if os.path.exists(db_backup_path):
                os.remove(db_backup_path)
            os.rename(db_path, db_backup_path)
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

    # Set up the output
    term_props = conf.get('terminal', {})
    term_width = lambda: min(console.width,
                             term_props.get('width', console.width))

    console = rich.console.Console(highlight=conf.get('highlight', False))
    
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
                             crosslist INTEGER,
                             link TEXT NOT NULL PRIMARY KEY,
                             read INTEGER NOT NULL)''')
        
        # BACKWARDS COMPATIBILITY: As of the introduction of the `crosslists`
        # options, these may require knowing whether a publication is a
        # crosslist. As part of backwards compatibility, we assume that any
        # article already in the database is NOT a crosslist.
        with WithCursor(db) as cursor:
            # Check if the column exists
            try:
                cursor.execute('ALTER TABLE articles '
                               'ADD COLUMN crosslist INTEGER')
                # The column did not exist.
                # The column will be added with null values. This is intended,
                # and will signal that we don't know whether the existing
                # publications are crosslists or not.
            except sqlite3.OperationalError:
                # The column already existed.
                pass
        
        # Prune the database of old articles
        # Prune since when?
        conf_delta = conf.get('span', 7)
        prune_since = (today - datetime.timedelta(days=conf_delta)).date()

        with WithCursor(db) as cursor:
            cursor.execute('DELETE FROM articles WHERE YEAR<:year OR '
                            '(YEAR=:year AND MONTH<:month) OR '
                            '(YEAR=:year AND MONTH=:month AND DAY<:day)',
                        {'day':prune_since.day,
                         'month':prune_since.month,
                         'year':prune_since.year})

        # Also prune publications from categories that are no longer selected
        categories = [cat for cat in CATEGORY_KEYS
                        if conf.get('categories', {}).get(cat, False)]

        query = ('DELETE FROM articles WHERE ' +
                ' AND '.join(f'category != "{category}"'
                             for category in categories))
        with WithCursor(db) as cursor:
            cursor.execute(query)
        
        # Find out if we need to poll the ArXiv database again
        # (or if we have already done so today)
        last_published = None
        today_date = today.date()
        with WithCursor(db) as cursor:
            query = cursor.execute('SELECT day, month, year, category '
                                   'FROM articles')
        for (day, month, year, category) in query:
            date = datetime.date(day=day, month=month, year=year)
            if last_published is None or date > last_published:
                last_published = date

        # (articles are published on yesterday's midnight; this is parsed as
        #   yesterday)
        db_up_to_date = (last_published is not None and
            last_published == today_date - datetime.timedelta(days=1))
        
        if db_up_to_date:
            # No need to poll the API again
            pass
        else:
            # Poll the ArXiv API
            # We're very explicit where possible to make sure we don't send 
            #  garbage into the ArXiv query.

            page_size = 200
            arxiv_poll_phrases = [
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
                'Reading the abstract only...',
                'Proposing collaboration...',
                'Envying results...',
                'Searching for the published version...']

            # Connection errors are caught, because even if ArXiv is down, the
            # cached items are still usable.
            try:
                query = arxiv.query(categories, page_size=page_size)
            except ConnectionError as e:
                # ArXiv is likely down. Report to the user, but keep going.
                spinner.fail(
                    'Something went wrong on the ArXiv end of things. '
                    '(ArXiv is likely down.) '
                    'Please try again later.')
                if os.environ.get('JFC_DEBUG'):
                    print('Guru meditation:')
                    print(e)
                query = []

            for i, results_page in enumerate(query):
                spinner.text = (random.choice(arxiv_poll_phrases) 
                                + ' (' + str(i*page_size) + ' seen...)')

                if results_page['bozo'] == True:
                    spinner.fail(
                        'Something went wrong on the ArXiv end of things. '
                        '(We got a bad response from the ArXiv API.) '
                        'Please try again later.')
                    if os.environ.get('JFC_DEBUG'):
                        print('Guru meditation:')
                        print(results_page)
                    break

                if len(results_page['entries']) == 0:
                    spinner.fail('Something went wrong. '
                                  '(ArXiv returned no results for the query.) '
                                  'Please try again later.')
                    if os.environ.get('JFC_DEBUG'):
                        print('Guru meditation:')
                        print(results_page)
                    break

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
                            'WHERE link=?)', (item['link'],))
                    seen = False
                    for value in query:
                        if value != (0,):
                            seen = True
                    if seen:
                        finished = True
                        break 
                    
                    # Otherwise, push this item into the database
                    # We can batch-execute queries/inserts into the SQL database
                    # so we postpone this to the end of the loop.
                    items_to_insert.append(item)
                
                # Note that crossposts are left as NULL. This is on purpose and
                # addressed later.
                with WithCursor(db) as cursor:
                    cursor.executemany(
                        'INSERT INTO articles '
                        '(year, month, day, title, abstract, authors, '
                            'category, link, read) '
                        'VALUES '
                        '(?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        [(item['date'].year,
                          item['date'].month,
                          item['date'].day,
                          item['title'],
                          ' '.join(line.strip()
                            for line in item['abstract'].splitlines()),
                          ', '.join(item['authors']),
                          item['category'],
                          item['link'],
                          False)
                        for item in items_to_insert])
                
                if finished:
                    spinner.succeed('Done.')
                    break

            # Categorize publications as cross-listings or not.
            # Even if a given publication was downloaded from category A as a 
            # cross-listing of category B, if we are also subscribed to category
            # B the publication would've been downloaded anyway.
            # Therefore, the only criterion for whether a publication is a
            # cross-listing is whether it belongs to any category to which we
            # are not subscribed.
            # UPDATE (1.5.2): Always just update the cross-listing status of
            #  everything at start-up. It's fast, requires only four queries,
            #  and deals with edge cases such as the configuration having been
            #  changed since the value was set.
            with WithCursor(db) as cursor:
                db.execute('UPDATE articles SET crosslist = 0 '
                           'WHERE category IN '
                           '(' + ', '.join(f'"{x}"' for x in categories) + ')')
                db.execute('UPDATE articles SET crosslist = 1 '
                           'WHERE category NOT IN '
                           '(' + ', '.join(f'"{x}"' for x in categories) + ')')
    
    with sqlite3.connect(db_path) as db:
        # Get all the articles that haven't been read yet
        # The results are returned as tuples, being that the field each element
        # of the tuple corresponds to is given by the order in which the columns
        # of the table were declared. This is less than ideal, but follows from
        # the integration with SQLite.
        crosslist_conf = conf.get('crosslists', {})
        crosslists_include = crosslist_conf.get('include', True)
        crosslists_highlight = crosslist_conf.get('highlight', False)

        fields = ('year', 'month', 'day', 'title', 'abstract', 'authors',
                    'category', 'crosslist', 'link', 'read')

        with WithCursor(db) as cursor:
            query = f'SELECT {", ".join(fields)} FROM articles WHERE read = 0'
            if not crosslists_include:
                query += ' AND crosslist != 1'
            query = cursor.execute(query)

        articles = [
            {field: value for field, value in zip(fields, element)}
            for element in query]

        # As of 1.4.0, shuffling is optional and controlled by preferences.
        if conf.get('shuffle', True):
            random.shuffle(articles)

        # As of 1.7.0, the date of the publication can optionally be shown
        show_date = conf.get('show_date', True)

        # Show the articles

        try:
            # The prompt at title level is different depending on user options
            title_level_choices = ['n', 'a', 'N', 'A']
            title_level_prompt = '[bold green][N][/bold green] Next  '
            if conf.get('browser_from_title', False):
                title_level_choices += ['o', 'O']
                title_level_prompt += (
                        '[bold green][O][/bold green] Open in browser  ')
            title_level_prompt += '[bold green][A][/bold green] Show abstract '

            for article in articles:
                # Immediately set the article as read. This will allow us to
                # skip early to the next article if the user asks to do so.
                with WithCursor(db) as cursor:
                    cursor.execute(
                            'UPDATE articles SET read=1 WHERE link=?',
                            (article['link'],))


                # Show the article
                console.rule()
                if show_date:
                    # Move up one line up and one cell right
                    cursor_move = '\033[F\033[C'
                    date = (f' {article["year"]}-' +
                           f'{MONTHS[article["month"] - 1]}-' +
                           f'{article["day"]} ')
                    console.print(cursor_move + date, style='dim')
                console.print('')
                for line in textwrap.wrap(
                    article['title'], width=term_width()):
                    console.print(line, justify='center')
                for line in textwrap.wrap(
                    article['authors'], width=term_width()):
                    console.print(line, justify='center', style='dim')
                console.print(article['link'], justify='center', style='dim')
                if crosslists_highlight and article['crosslist']:
                    for line in textwrap.wrap(
                        f'({article["category"]} cross-listing)',
                        width=term_width()):
                            console.print(line, justify='center', style='bold')
                console.print('')
                    
                action = rich.prompt.Prompt.ask(
                        title_level_prompt,
                        choices=title_level_choices, default='N',
                        show_choices=False).lower()
                print('\033[F\033[F') # Overwrite the prompt

                # Skip to next article
                if action == 'n':
                    continue

                # Open in browser and continue
                # (The abstract will be in the ArXiv page)
                if action == 'o':
                    webbrowser.open(article['link'])
                    continue
                
                # Otherwise, show the abstract; do this in a separate screen
                with console.screen():
                    console.print('\n')
                    for line in textwrap.wrap(
                        article['title'], width=term_width()):
                        console.print(line, justify='center', soft_wrap=True)
                    for line in textwrap.wrap(
                        article['authors'], width=term_width()):
                        console.print(line, justify='center', style='dim')
                    console.print(
                        article['link'], justify='center', style='dim')
                    if crosslists_highlight and article['crosslist']:
                        for line in textwrap.wrap(
                            f'({article["category"]} cross-listing)',
                            width=term_width()):
                                console.print(
                                    line, justify='center', style='bold')
                    console.print('\n')
                    left_padding = (
                        max(console.width - term_width(), 0)//2 - 1)
                    for line in textwrap.wrap(
                        article['abstract'], width=term_width()):
                            console.print(' ' * left_padding, line)
                    console.print('')

                    action = rich.prompt.Prompt.ask(
                            '[bold green][N][/bold green] Next  '
                            '[bold green][O][/bold green] Open in Browser',
                            choices=['n', 'o', 'N', 'O'],
                            show_choices=False, default='N').lower()
                    print('\033[F\033[F') # Overwrite the prompt

                    if action == 'n':
                        # Skip to the next article
                        continue

                    # Otherwise, open the article in the browser,
                    # and continue.
                    webbrowser.open(article['link'])

        except KeyboardInterrupt or EOFError:
            exit(0)

    rich.print('[green]:heavy_check_mark: All caught up![/green]')

