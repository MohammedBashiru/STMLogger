import sublime
import sublime_plugin

__version__ = '1.1.0'

import contextlib
import json
import os
import platform
import re
import subprocess
import sys
import time
import threading
import traceback
import urllib
import webbrowser
from datetime import datetime
from subprocess import STDOUT, PIPE
from zipfile import ZipFile
from pprint import pprint

import sqlite3
from sqlite3 import Error

is_py2 = (sys.version_info[0] == 2)
is_py3 = (sys.version_info[0] == 3)
is_win = platform.system() == 'Windows'


if is_py2:
    def u(text):
        if text is None:
            return None
        if isinstance(text, unicode):
            return text
        try:
            return text.decode('utf-8')
        except:
            try:
                return text.decode(sys.getdefaultencoding())
            except:
                try:
                    return unicode(text)
                except:
                    try:
                        return text.decode('utf-8', 'replace')
                    except:
                        try:
                            return unicode(str(text))
                        except:
                            return unicode('')

elif is_py3:
    def u(text):
        if text is None:
            return None
        if isinstance(text, bytes):
            try:
                return text.decode('utf-8')
            except:
                try:
                    return text.decode(sys.getdefaultencoding())
                except:
                    pass
        try:
            return str(text)
        except:
            return text.decode('utf-8', 'replace')

else:
    raise Exception('Unsupported Python version: {0}.{1}.{2}'.format(
        sys.version_info[0],
        sys.version_info[1],
        sys.version_info[2],
    ))

# globals
ST_VERSION = int(sublime.version())
PLUGIN_DIR = os.path.dirname(os.path.realpath(__file__))
API_CLIENT = os.path.join(PLUGIN_DIR, 'packages', 'wakatime', 'cli.py')
SETTINGS_FILE = 'STMLogger.sublime-settings'
SETTINGS = {}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "STMLogger.sqlite3")
TODAY = datetime.now().strftime('%Y-%m-%d')
conn = ""


# Log Levels
DEBUG = 'DEBUG'
INFO = 'INFO'
WARNING = 'WARNING'
ERROR = 'ERROR'


def create_connection(db_file):
    """ create a database connection to the SQLite database
        specified by the db_file
    :param db_file: database file
    :return: Connection object or None
    """
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Error as e:
        print(e)

    return None


def set_timeout(callback, seconds):
    """Runs the callback after the given seconds delay.

    If this is Sublime Text 3, runs the callback on an alternate thread. If this
    is Sublime Text 2, runs the callback in the main thread.
    """

    milliseconds = int(seconds * 1000)
    try:
        sublime.set_timeout_async(callback, milliseconds)
    except AttributeError:
        sublime.set_timeout(callback, milliseconds)


def get_daily_logs(conn, today):
    """
    Query tasks by priority
    :param conn: the Connection object
    :param priority:
    :return:
    """
    cur = conn.cursor()
    cur.execute("SELECT * FROM daily_logs WHERE created=?", (today,))

    rows = cur.fetchall()
    # print("Today is " + today)
    # print("printing rows")
    # print(rows)
    for row in rows:
        print(row)


def get_grouped_logs(conn, today):
    cur = conn.cursor()
    cur.execute("SELECT * FROM daily_logs GROUP BY created")
    rows = cur.fetchall()
    return rows


def get_logs_by_date(conn, day):
    cur = conn.cursor()
    cur.execute("SELECT * FROM daily_logs Where created=?", (day,))
    rows = cur.fetchall()
    return rows


def get_all_logs(conn, today):
    cur = conn.cursor()
    cur.execute("SELECT * FROM daily_logs ORDER BY id ASC")
    rows = cur.fetchall()
    return rows


def add_task_to_db(task, today):

    global conn
    conn = create_connection(DB_PATH)

    cur = conn.cursor()
    cur.execute('insert into daily_logs (log, created) values (?,?)', (task, today))
    conn.commit()

    print("Task Added Successfully")
    update_status_success("Task Added Successfully")
    main()


def main():

    # create a database connection
    global conn
    conn = create_connection(DB_PATH)

    # conn.row_factory = sqlite3.Row
    with conn:
        print("1. Query daily logs:")

        get_daily_logs(conn, TODAY)

        # print("2. Query all tasks")
        # select_all_tasks(conn)


def log(lvl, message, *args, **kwargs):
    try:
        if lvl == DEBUG and not SETTINGS.get('debug'):
            return
        msg = message
        if len(args) > 0:
            msg = message.format(*args)
        elif len(kwargs) > 0:
            msg = message.format(**kwargs)
        try:
            print('STMLogger [{lvl}] {msg}'.format(lvl=lvl, msg=msg))
        except UnicodeDecodeError:
            print(u('STMLogger [{lvl}] {msg}').format(lvl=lvl, msg=u(msg)))
    except RuntimeError:
        set_timeout(lambda: log(lvl, message, *args, **kwargs), 0)


def update_status_bar(status):
    """Updates the status bar."""

    try:
        if SETTINGS.get('status_bar_message'):
            msg = datetime.now().strftime(SETTINGS.get('status_bar_message_fmt'))
            print(msg)
            if '{status}' in msg:
                msg = msg.format(status=status)

            active_window = sublime.active_window()
            if active_window:
                for view in active_window.views():
                    view.set_status('stmlogger', msg)
    except RuntimeError:
        set_timeout(lambda: update_status_bar(status), 0)


def update_status_success(msg):
    try:
        if SETTINGS.get('status_bar_message'):
            active_window = sublime.active_window()
        if active_window:
            for view in active_window.views():
                view.set_status('Task Manager : ', msg)

    except RuntimeError:
        set_timeout(lambda: update_status_bar(msg), 0)


def prompt_enter_task():
    default_text = ''
    global TODAY
    window = sublime.active_window()
    if window:
        def got_text(text):
            if text:
                print("We got text from user " + text)
                print("This day is " + TODAY)
                add_task_to_db(text, TODAY)
        window.show_input_panel('Task Manager Enter your task:', default_text, got_text, None, None)
        return True
    else:
        log(ERROR, 'Could not prompt for api key because no window found.')
        return False


def plugin_loaded():
    global SETTINGS
    SETTINGS = sublime.load_settings(SETTINGS_FILE)

    log(INFO, 'Initializing STMLogger Plugin v%s' % __version__)
    update_status_bar('Initializing')

    # after_loaded()
    main()


def after_loaded():
    if not prompt_enter_task():
        set_timeout(after_loaded, 0.5)


def open_file():
    window = sublime.active_window()
    if window:
        window.new_file()


class OpenWebPageCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        webbrowser.open_new_tab("http://66.205.176.237/stm/")


class AddTaskCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        prompt_enter_task()


class SpliterTestCommand(sublime_plugin.TextCommand):
    def run(self, Regex):
        sublime.run_command("new_window")
        window = sublime.active_window()
        window.set_layout({
            "cols": [0, 0.5, 1],
            "rows": [0.0, 0.33, 0.66, 1.0],
            "cells": [[0, 0, 1, 3], [1, 0, 2, 1], [1, 1, 2, 2], [1, 2, 2, 3]]
        })
        # For each of the new groups call putHello (self.window.num_groups() = 4)
        for numGroup in range(window.num_groups()):
            # If the group is empty (has no views) then we create a new file (view) and insert the text hello
            if len(window.views_in_group(numGroup)) == 0:
                window.focus_group(numGroup)  # Focus in group
                createdView = window.new_file()  # New view in group
                createdView.set_name("Daily Task Logs " + str(numGroup))
                # createdView.run_command("insert", {"characters": "Hello"})  # Insert in created view


class ShowTaskListCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        global conn
        conn = create_connection(DB_PATH)

        if self.view.name() == "Daily Task Logs":
            self.view.set_read_only(False)
            self.view.erase(edit, sublime.Region(0, self.view.size()))
            self.view.insert(edit, 0, "------------- DAILY TASK LOGS --------------- \n\n")
            grouped_task = get_grouped_logs(conn, TODAY)
            # print(grouped_task)

            for group in grouped_task:
                tasks = get_logs_by_date(conn, group[2])
                group_date = "[%s]\n" % str(group[2])
                cursor = self.view.sel()[0].begin()
                self.view.insert(edit, cursor, group_date)

                i = 0;
                for task in tasks:
                    i = i + 1
                    cursor = self.view.sel()[0].begin()
                    content = "		" + str(i) + ": " + task[1] + "\n"
                    self.view.insert(edit, cursor, content)
            self.view.set_read_only(True)

        else:
            window = sublime.active_window()
            if window:
                new_tab = window.new_file()
                if new_tab:
                    view = window.active_view()
                    cursor = view.sel()[0].begin()
                    view.set_read_only(False)
                    new_tab.set_name("Daily Task Logs")
                    new_tab.insert(edit, cursor, "------------- DAILY TASK LOGS --------------- \n\n")

                    grouped_task = get_grouped_logs(conn, TODAY)
                    print(grouped_task)

                    for group in grouped_task:
                        tasks = get_logs_by_date(conn, group[2])
                        group_date = "[%s]\n" % str(group[2])
                        cursor = view.sel()[0].begin()
                        view.insert(edit, cursor, group_date)

                        i = 0;
                        for task in tasks:
                            i = i + 1
                            cursor = view.sel()[0].begin()
                            content = "		" + str(i) + ": " + task[1] + "\n"
                            view.insert(edit, cursor, content)
                    view.set_read_only(True)


# need to call plugin_loaded because only ST3 will auto-call it
if ST_VERSION < 3000:
    plugin_loaded()