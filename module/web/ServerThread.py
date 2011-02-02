#!/usr/bin/env python
from __future__ import with_statement
from os.path import exists
import threading
import logging
import sqlite3

core = None
log = logging.getLogger("log")

class WebServer(threading.Thread):
    def __init__(self, pycore):
        global core
        threading.Thread.__init__(self)
        self.core = pycore
        core = pycore
        self.running = True
        self.server = pycore.config['webinterface']['server']
        self.https = pycore.config['webinterface']['https']
        self.cert = pycore.config["ssl"]["cert"]
        self.key = pycore.config["ssl"]["key"]
        self.host = pycore.config['webinterface']['host']
        self.port = pycore.config['webinterface']['port']

        self.setDaemon(True)

    def run(self):
        import webinterface
        global webinterface

        self.checkDB()

        if self.https:
            if not exists(self.cert) or not exists(self.key):
                log.warning(_("SSL certificates not found."))
                self.https = False

        if self.server in ("lighttpd", "nginx"):
            log.warning(_("Sorry, we dropped support for starting %s directly within pyLoad") % self.server)
            log.warning(_("You can use the threaded server which offers good performance and ssl,"))
            log.warning(_("of course you can still use your existing %s with pyLoads fastcgi server") % self.server)
            log.warning(_("sample configs are located in the module/web/servers directory"))
            self.server = "builtin"

        if self.server == "fastcgi":
            try:
                import flup
            except:
                log.warning(_("Can't use %(server)s, python-flup is not installed!") % {
                    "server": self.server})
                self.server = "builtin"

        if self.server == "fastcgi":
            self.start_fcgi()
        elif self.server == "threaded":
            self.start_threaded()
        else:
            self.start_builtin()


    def checkDB(self):
        conn = sqlite3.connect('web.db')
        c = conn.cursor()
        c.execute("SELECT * from users LIMIT 1")
        empty = True
        if c.fetchone():
            empty = False

        c.close()
        conn.close()

        if not empty:
            return True

        if exists("pyload.db"):
            log.info(_("Converting old database to new web.db"))
            conn = sqlite3.connect('pyload.db')
            c = conn.cursor()
            c.execute("SELECT username, password, email from auth_user WHERE is_superuser")
            users = []
            for r in c:
                pw = r[1].split("$")
                users.append((r[0], pw[1] + pw[2], r[2]))

            c.close()
            conn.close()

            conn = sqlite3.connect('web.db')
            c = conn.cursor()
            c.executemany("INSERT INTO users(name, password, email) VALUES (?,?,?)", users)
            conn.commit()
            c.close()
            conn.close()
            return True

        else:
            log.warning(_("Database for Webinterface does not exitst, it will not be available."))
            log.warning(_("Please run: python pyLoadCore.py -s"))
            log.warning(_("Go through the setup and create a database and add an user to gain access."))
            return False


    def start_builtin(self):

        if self.https:
            log.warning(_("The simple builtin server offers no SSL, please consider using threaded instead"))

        self.core.log.info(_("Starting builtin webserver: %(host)s:%(port)d") % {"host": self.host, "port": self.port})
        webinterface.run_simple(host=self.host, port=self.port)

    def start_threaded(self):
        if self.https:
            self.core.log.info(_("Starting threaded SSL webserver: %(host)s:%(port)d") % {"host": self.host, "port": self.port})
        else:
            self.cert = ""
            self.key = ""
            self.core.log.info(_("Starting threaded webserver: %(host)s:%(port)d") % {"host": self.host, "port": self.port})

        webinterface.run_threaded(host=self.host, port=self.port, cert=self.cert, key=self.key)

    def start_fcgi(self):

        self.core.log.info(_("Starting fastcgi server: %(host)s:%(port)d") % {"host": self.host, "port": self.port})
        webinterface.run_fcgi(host=self.host, port=self.port)

    def quit(self):
        self.running = False