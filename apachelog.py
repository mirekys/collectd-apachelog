#!/usr/bin/env python

""" A collectd-python plugin for retrieving
    metrics from Apache access log file. """

import sys
from os import access, R_OK
from datetime import datetime
from Queue import Queue, Empty
from util import remap, LogWatch
from apache_log_parser import make_parser, LineDoesntMatchException


class ApacheLog(object):
    """ Main plugin class """

    def __init__(self, debug=False):
        """ Initialize itself with sane defaults """
        self.debug_mode = debug
        self.parser = None
        self.values = {}
        self.logwatch = None
        self.interval = 1
        self.access_log = '/var/log/ssl_access.log'
        self.plugin_name = 'http_requests'
        self.access_log_format = '%h %l %u %t \"%r\" %>s %b'
        self.line_buffer = Queue()


    def configure(self, conf):
        """ Receive and process configuration block from collectd """
        for node in conf.children:
            key = node.key.lower()
            val = node.values[0]

            if key == 'access_log':
                self.access_log = val
                if not access(self.access_log, R_OK):
                    self.err('access_log %s is not readable!' % self.access_log)
            elif key == 'access_log_format':
                self.access_log_format = val
                try:
                    self.parser = make_parser(self.access_log_format)
                except LineDoesntMatchException:
                    self.err('Couldn\'t parse access log format: %s' % (
                        self.access_log_format))
                    return
            elif key == 'name':
                self.plugin_name = val
            elif key == 'interval':
                self.interval = val
            else:
                self.warn('Unknown config key: %s.' % key)


    def init(self):
        """ Prepare itself for reading in new values """
        if not self.logwatch:
            self.logwatch = LogWatch(self.access_log, self.line_buffer)
            self.logwatch.start()

        for key, val in self.values.iteritems():
            for subkey in val.keys():
                self.values[key][subkey] = 0


    def gather_metrics(self):
        """ Gather metrics data from lines queued by self.logwatch """
        read_start = datetime.now()

        while (self.logwatch.isAlive() and
               ((datetime.now()-read_start).seconds) < self.interval):
            try:
                line = self.line_buffer.get_nowait()
            except Empty:
                break

            data = self.parser(line)
            method = data['request_method']

            self.debug(datetime.now())
            self.debug(line)

            try:
                # Aggregate data by request method
                self.values[method]['count'] += 1
            except KeyError:
                self.values[method] = {
                    k:0 for k in data.keys() if k != 'status'
                }
                self.values[method]['count'] = 1

            for key, val in data.iteritems():
                val = remap(key, val)
                try:
                    if key == 'status':
                        statkey = '%s_%sxx' %(key, val[:len(val)-2])
                        try:
                            self.values[method][statkey] += 1
                        except KeyError:
                            self.values[method][statkey] = 1
                    else:
                        self.values[method][key] += int(val)
                except TypeError:
                    self.values[method][key] = val
                except ValueError:
                    self.values[method][key] = val


    def read(self, data=None):
        """ Collectd read callback to gather metrics
            data from the access log and submit them """
        self.init()
        self.gather_metrics()

        self.debug('=========DONE READING. WRITING METRICS...==============')

        for method, data in self.values.iteritems():
            self.submit('count', method, data['count'])

            for key, val in data.iteritems():
                if 'bytes' in key:
                    self.submit('bytes', '%s-%s' % (method, key), val)
                elif 'time' in key and not 'received' in key:
                    self.submit('response_time', '%s-%s' % (method, key), val)
                elif 'num' in key or 'status' in key:
                    self.submit('count', '%s-%s' % (method, key), val)


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


    def shutdown(self):
        """ Collectd plugin shutdown callback """
        self.logwatch.killed = True
        self.logwatch.join(1)


if len(sys.argv) > 1 and sys.argv[1] == 'debug':
    print('<Debugging Mode ON>')

    class NodeMock(object):
        """ Immitates single configuration item """
        def __init__(self, key, value):
            self.key = key
            self.values = [value]

    class ConfigMock(object):
        """ Immitates class passed in by collectd """
        def __init__(self, name, intvl, acclog, acclog_fmt):
            self.children = []
            self.children.append(NodeMock('name', name))
            self.children.append(NodeMock('interval', intvl))
            self.children.append(NodeMock('access_log', acclog))
            self.children.append(NodeMock('access_log_format', acclog_fmt))


    from time import sleep
    sleep_time = 1
    cfg = ConfigMock(
        'serverX_requests', sleep_time,
        '/etc/httpd/logs/ssl_access.log',
        '%h %l %u %t \"%r\" %>s %b \"%{Referer}i\"'\
        ' \"%{User-Agent}i\" %k %I %O %D')
    alog = ApacheLog(debug=True)
    alog.configure(cfg)
    try:
        while True:
            alog.read()
            sleep(sleep_time)
    except KeyboardInterrupt:
        alog.shutdown()
else:
    import collectd
    alog = ApacheLog()
    collectd.register_config(alog.configure)
    collectd.register_read(alog.read)
    collectd.register_shutdown(alog.shutdown)
