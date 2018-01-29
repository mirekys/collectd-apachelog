#!/usr/bin/env python

""" A collectd-python plugin for retrieving
    metrics from Apache access log file. """

import sys
import subprocess
from os import access, R_OK
from threading import Thread
from datetime import datetime
from Queue import Queue, Empty
from apache_log_parser import make_parser, LineDoesntMatchException

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


class ApacheLog(CollectdPlugin):
    """ Main plugin class """

    def __init__(self, debug=False):
        """ Initialize itself with sane defaults """
        super(ApacheLog, self).__init__(debug)
        self.parser = None
        self.values = {}
        self.logwatch = None
        self.interval = 1
        self.access_log = '/var/log/ssl_access.log'
        self.access_log_format = '%h %l %u %t \"%r\" %>s %b'
        self.line_buffer = Queue()


    def configure(self, conf):
        """ Receive and process configuration block from collectd """
        for node in conf.children:
            key = node.key.lower()
            val = node.values[0]

            if key == 'accesslog':
                self.access_log = val
                if not access(self.access_log, R_OK):
                    self.err('AccessLog %s is not readable!' % self.access_log)
            elif key == 'accesslogformat':
                self.access_log_format = val
                try:
                    self.parser = make_parser(self.access_log_format)
                except LineDoesntMatchException:
                    self.err('Couldn\'t parse AccessLogFormat: %s' % (
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
                self.values[key][subkey] = 0 if subkey != 'time_us' else []
        self.values['response_time'] = { 'avg':[], 'min':sys.maxint, 'max':0 }


    def gather_metrics(self):
        """ Gather metrics data from lines queued by self.logwatch """
        read_start = datetime.now()

        while (self.logwatch.isAlive() and
               ((datetime.now()-read_start).seconds) < self.interval):
            try:
                line = self.line_buffer.get_nowait()
            except Empty:
                break

            request = self.parser(line)
            method = request['request_method']
            status = 'status_%sxx' % request['status'][:len(request['status'])-2]

            self.debug(datetime.now())
            self.debug(line)

            # Update request count by method and HTTP status
            try:
                self.values[method]['count'] += 1
            except KeyError:
                # Initialize values dict for method with request fields
                self.values[method] = {
                    k:0 for k in request.keys() if not k in ['time_us', 'status']
                }
                if 'time_us' in request.keys():
                    self.values[method]['time_us'] = []
                self.values[method]['count'] = 1
            try:
                self.values[method][status] += 1
            except KeyError:
                self.values[method][status] = 1

            # Read and save values from request
            for key, val in request.iteritems():
                if key == 'status':
                        continue # Status has been already processed

                val = remap(key, val)
                try:
                    if key == 'time_us':
                        self.update_response_time(method, int(val))
                    else:
                        self.values[method][key] += int(val)
                except TypeError:
                    pass
                except ValueError:
                    pass # Ignore values that cannot be converted to int


    def update_response_time(self, method, val):
        cmax = self.values['response_time']['max']
        cmin = self.values['response_time']['min']
        self.values['response_time']['max'] = val if val >= cmax else cmax
        self.values['response_time']['min'] = val if val <= cmin else cmin
        self.values['response_time']['avg'].append(val)
        self.values[method]['time_us'].append(val)


    def get_avg_response_time(self, times_list):
        avg = 0
        try:
            avg = sum(times_list)/float(len(times_list))
        except ZeroDivisionError:
            pass
        return avg


    def read(self):
        """ Collectd read callback to gather metrics
            data from the access log and submit them """
        self.init()
        self.gather_metrics()

        self.debug('=========DONE READING. WRITING METRICS...==============')

        # Submit response times
        rt = self.values['response_time']
        self.submit('response_time', 'avg', self.get_avg_response_time(rt['avg']))
        self.submit('response_time', 'min', rt['min'] if rt['min'] != sys.maxint else 0)
        self.submit('response_time', 'max', rt['max'])

        # Submit hit counts
        hits = sum([val['count'] if 'count' in val.keys() else 0 for val in self.values.values()])
        self.submit('count', 'hits', hits)

        # Submit all remaining values
        for method, data in self.values.iteritems():
            for key, val in data.iteritems():
                if 'count' in key:
                    self.submit('count', method, data['count'])
                elif 'bytes' in key:
                    self.submit('bytes', '%s-%s' % (method, key), val)
                elif 'num' in key or 'status' in key:
                    self.submit('count', '%s-%s' % (method, key), val)
                elif 'time_us' in key:
                    self.submit('response_time', '%s-avg' % method, self.get_avg_response_time(val))


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
            self.children.append(NodeMock('accesslog', acclog))
            self.children.append(NodeMock('accesslogformat', acclog_fmt))


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
