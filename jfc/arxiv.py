#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib
import feedparser
import time

def query(categories, page_size=40):
    request_string = 'http://export.arxiv.org/api/query?'

    # Query the given categories
    request_string += '&search_query='
    for category in categories[:-1]:
        request_string += 'cat:' + urllib.parse.quote(categrory)
        request_string += '+OR+'
    request_string += 'cat:' + urllib.parse.quote(categories[-1])

    # Sort the results from newest to oldest
    request_string += '&sortBy=lastUpdatedDate&sortOrder=descending'

    # Page the results so that the user can abort when they're no longer
    # interested
    request_string += '&max_results=' + str(page_size)

    # Return pages as an iterator
    start = 0
    # It is the user's responsibility to abort the iterator when the results no
    # longer interest them. Otherwise, this iterator runs forever.
    while True:
        page_query = request_string + '&start=' + str(start)
        yield feedparser.parse(page_query)
        start += page_size

        # We honor the ArXiv documentation in the 3 second delay between requests
        time.sleep(3)

