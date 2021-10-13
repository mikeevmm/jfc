#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3

class WithCursor():
    def __init__(self, db, cursor):
        self.db = db
        self.cursor = cursor
    
    def __enter__(self):
        return self.cursor

    def __exit__(self, exc_type, exc_value, traceback):
        db.commit()
        
