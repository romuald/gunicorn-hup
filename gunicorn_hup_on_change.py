#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Send gunicorn a HUP when .py files are changed
"""
import os
import os.path
import sys
import re
import signal
import logging

from threading import Timer
from optparse import OptionParser

try:
    import pyinotify as pyi
except ImportError:
    print >>sys.stderr, """Pyinotify package not found.
    You can try apt-get install python-pyinotify
    or maybe pip install pyinotify
    """
    raise

class GenericEventHandler(pyi.ProcessEvent):
    """Handles events on specific dirs, then call call the callback method

    @ivar manager: The manager to use for watching new directories

    @ivar wmask: pyinotify mask to use for watching new directories
    @type wmask: int

    @ivar wpatterns: patterns that trigger action
    @type wpatterns: list of regexp
    """
    manager = None
    wmask = 0
    wpatterns = [ re.compile( '^[^.].*\.py$' ) ]

    def __init__(self, watchdirs, manager=None, callback=None):
        if not manager:
            manager = pyi.WatchManager()

        if callback and callable(callback):
            self.callback = callback

        self.manager = manager
        self.wmask = pyi.IN_CREATE | pyi.IN_MODIFY | pyi.IN_MOVED_TO

        for dirname in watchdirs:
            logger.debug("watch: %s" % dirname)
            self.manager.add_watch(dirname, self.wmask, rec=True)

    def loop(self):
        """Main loop - B{blocks}
        """
        notifier = pyi.Notifier(self.manager, self)
        notifier.loop()

    def callback(self, event):
        """Default callback does nothing
        """
        raise NotImplementedError("Override this")

    def changed(self, event):
        """Something changed, trigger callback if matching pattern
        or add dir to watchlist
        """
        # Add new directories to watch
        if event.dir and event.mask & pyi.IN_CREATE:
            logger.debug("watch: %s" % event.pathname)
            self.manager.add_watch(event.pathname, self.wmask)
            return

        # Return if none of our pattern matches
        for r in self.wpatterns:
            if r.match(event.name):
                break
        else:
            # else clause called if no break was reached
            return

        logger.debug("change: %s %s" % ( event.pathname, event.mask ))

        self.callback(event)

    process_IN_CREATE = changed
    process_IN_MODIFY = changed
    process_IN_MOVED_TO = changed

class GunicornHUP(GenericEventHandler):
    appname = None
    pidfile = None
    known_pid = None
    wait_time = 500
    timer = None

    def callback(self, event):
        if self.known_pid is not None:
            try:
                os.kill(self.known_pid, 0)
            except OSError, e:
                if e.errno != 3:
                    raise
                self.known_pid = None

        if self.known_pid is None:
            if self.pidfile:
                self.known_pid = int(open(self.pidfile).read())
                logger.info("found master process %d (%s)" % (
                    self.known_pid, self.pidfile) )
                return

            #gunicorn: master [website]
            mre = re.compile(r'^gunicorn:\s+master\s+\[(.*)\]')
            pids = [ int(pid) for pid in os.listdir('/proc') if pid.isdigit() ]
            for pid in pids:
                path = os.path.join('/proc', str(pid), 'cmdline')
                try:
                    # process might be gone between ls and open
                    data = open(path).read()
                except:
                    continue

                found = mre.search(data)
                if not found:
                    continue

                appname = found.group(1)
                if self.appname is None or appname == self.appname:
                    self.known_pid = pid
                    logger.info("found master process %d (%s)" % (
                        self.known_pid, appname) )
                    break
            else:
                msg = "Could not find gunicorn master process"
                if self.appname:
                    msg += " for %s" % self.appname
                logger.error(msg)

                return

        def kill(pid):
            logger.info("HUP: %d" % pid)
            os.kill(pid, signal.SIGHUP)

        if self.timer:
            self.timer.cancel()

        self.timer = Timer(self.wait_time / 1000.0, kill, [ self.known_pid ])
        self.timer.start()

if __name__ == '__main__':
    usage = "usage: %prog [-q|-v] [-w wait] [-p pidfile] [-a app_module] [watch_dirs]"

    parser = OptionParser(usage)
    parser.add_option("-a", dest="appmodule", help="application module")
    parser.add_option("-p", dest="pidfile", help="pidfile containing master pid")
    parser.add_option("-w", dest="wait", type="int", default=500, help="wait"
        " interval milliseconds before sending HUP [default: %default]")
    parser.add_option("-v", dest="verbose", action="store_true", default=False,
        help="be more verbose")
    parser.add_option("-q", dest="quiet", action="store_true", default=False,
        help="quiet")

    (options, args) = parser.parse_args()


    watchdirs = args or filter(os.path.isdir, sys.path)

    # Setup logging "alamano" since pyinotify already sets up some of its soup
    if options.quiet and options.verbose:
        parser.error("quiet and verbose options are both set")
    elif options.quiet:
        loglevel = "ERROR"
    elif options.verbose:
        loglevel = "DEBUG"
    else:
        loglevel = "INFO"

    logging.setLoggerClass(logging.Logger)
    logger = logging.getLogger("zulu")
    loghandler = logging.StreamHandler()
    loghandler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))

    logger.addHandler(loghandler)
    logger.setLevel(logging.getLevelName(loglevel))

    handler = GunicornHUP(watchdirs)
    handler.appname = options.appmodule
    handler.pidfile = options.pidfile
    handler.wait_time = max(20, options.wait)

    parser.destroy()

    handler.loop()
