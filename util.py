#!/usr/bin/env python

""" Module containing common helper functions and classes """

import subprocess
from threading import Thread

# Dictionary of functions to be mapped to each key's value
FLDMAP = {
    'response_bytes_clf': (lambda x: str(x).replace('-', '0'))
}

def remap(key, value):
    """ Returns value transformed by accorging mapping table entry """
    try:
        return FLDMAP[key](value)
    except KeyError:
        return value


class LogWatch(Thread):
    """ Thread watching a log file for appended lines """
    def __init__(self, logfile, line_queue):
        Thread.__init__(self)
        self.killed = False
        self.logfile = logfile
        self.line_queue = line_queue


    def run(self):
        """ Main thread entrypoint """
        self.tail()


    def tail(self):
        """ Watch for, and enqueue lines appended to a file """
        tail = subprocess.Popen(
            ["tail", "-f", self.logfile], stdout=subprocess.PIPE)
        while not self.killed:
            line = tail.stdout.readline()
            self.line_queue.put(line)
            if not line:
                break
