#!/usr/bin/env python

""" Module containing common helper functions and classes """

import subprocess
from threading import Thread
from datetime import datetime

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


class CollectdPlugin(object):
    """ Main plugin class """

    def __init__(self, debug=False):
        self.debug_mode = debug
        self.plugin_name = 'python'
	if not self.debug_mode:
		import collectd


    def configure(self, conf):
        """ Receive and process configuration block from collectd """
        raise NotImplementedError


    def read(self):
        """ Read plugin values and call submit """
        raise NotImplementedError


    def submit(self, type, instance, value):
        """ Send collected values to collectd """
        if self.debug_mode:
            print('[%s] %s/%s-%s=%s' % (
                str(datetime.now()), self.plugin_name, type, instance, value))
        else:
            cval = collectd.Values()
            cval.plugin = self.plugin_name
            cval.type = type
            cval.type_instance = instance
            cval.values = [value, ]
            try:
                cval.dispatch()
            except TypeError:
                pass


    def debug(self, message):
        """ Log a debug message to console """
        if self.debug_mode:
            print('%s:DBG %s' % (self.plugin_name, message))


    def warn(self, message):
        """ Log a warning message """
        fmsg = '%s:WRN %s' % (self.plugin_name, message)
        if not self.debug_mode:
            collectd.warning(fmsg)
        else:
            print(fmsg)


    def err(self, message):
        """ Log an error message """
        fmsg = '%s:ERR %s' % (self.plugin_name, message)
        if not self.debug_mode:
            collectd.error(fmsg)
        else:
            print(fmsg)


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
