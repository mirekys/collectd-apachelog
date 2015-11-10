#!/usr/bin/env python

import sys
import datetime
from util import tac, remap
from os import access, R_OK
from apache_log_parser import make_parser


class ApacheLog(object):

    def __init__(self, debug=False):
        """ Initialize itself with sane defaults """
        self.parser            = None
        self.interval          = 1
        self.plugin_name       = 'http_requests'
        self.access_log        = '/var/log/ssl_access.log'
        self.access_log_format = '%h %l %u %t \"%r\" %>s %b'
        self.DEBUG             = debug
        self.values            = {}
        self.lastline          = ''
        
    def configure(self, c):
        """ Receive and process configuration block from collectd """
        for node in c.children:
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
                except:
                    self.err('Couldn\'t parse access log format: %s' % (
                        self.access_log_format))
                    return
            elif key == 'name':
                self.plugin_name = val
            elif key == 'interval':
                self.interval = val
            else:
                self.warn('Unknown config key: %s.' % key)


    def read(self, data=None):
        """ Read and aggregate request data from access log and submit them """
        for k,v in self.values.iteritems():
            for sk in v.keys():
                self.values[k][sk] = 0

        last=True # Last line in the access_log?
        for line in tac(self.access_log):
            data   = self.parser(line)
            method = data['request_method']
            date   = data['time_received_datetimeobj']
           
            if last:
                self.lastline = line

            self.debug(datetime.datetime.now())

            time_diff = (datetime.datetime.now() - date).seconds
            if time_diff > (self.interval):
                break
            elif line == self.lastline:
                if last:
                    last=False
                else:
                    break

            self.debug(line)
            try:
                # Aggregate data by request method
                self.values[method]['count'] += 1
            except KeyError:
                self.values[method] = {k:0 for k in data.keys() if k != 'status'}
                self.values[method]['count'] = 1
           
            for k,v in data.iteritems():
                v = remap(k,v)
                try:
                    if k == 'status':
                        try:
                            self.values[method]['%s_%sxx' %(k,v[:len(v)-2])] += 1
                        except KeyError:
                            self.values[method]['%s_%sxx' %(k,v[:len(v)-2])] = 1
                    else:
                        self.values[method][k] += int(v)
                except TypeError:
                    self.values[method][k] = v
                except ValueError:
                    self.values[method][k] = v

        for method, data in self.values.iteritems():
            self.submit('count', method, data['count'])

            for key,val in data.iteritems():
                if 'bytes' in key:
                    self.submit('bytes', '%s-%s' % (method, key), val)
                elif 'time' in key and not 'received' in key:
                    self.submit('response_time', '%s-%s' % (method,key), val)
                elif 'num' in key or 'status' in key:
                    self.submit('count', '%s-%s' % (method, key), val)


    def submit(self, type, instance, value):
        """ Sends collected values to collectd """
        if self.DEBUG:
            print('[%s] %s/%s-%s=%s' % (str(datetime.datetime.now()),  self.plugin_name, type, instance, value))
        else:
            v = collectd.Values()
            v.plugin = self.plugin_name
            v.type = type
            v.type_instance = instance
            v.values = [value, ]
            try:
                v.dispatch()
            except TypeError:
                pass


    def debug(self, message):
        if self.DEBUG:
            print('%s:DBG %s' % (self.plugin_name, message))
            

    def warn(self, message):
        fmsg = '%s:WRN %s' % (self.plugin_name, message)
        if not self.DEBUG:
            collectd.warning(fmsg)
        else:
            print(fmsg)


    def err(self, message):
        fmsg = '%s:ERR %s' % (self.plugin_name, message)
        if not self.DEBUG:
            collectd.error(fmsg)
        else:
            print(fmsg)


if len(sys.argv) > 1:
    if sys.argv[1] == 'debug':
        print('<Debugging Mode ON>')


        class NodeMock(object):
            """ Immitates single configuration item """
            def __init__(self,key,value):
                self.key = key
                self.values = [value]

        class ConfigMock(object):
            """ Immitates class passed in by collectd """
            def __init__(self, name, interval, acclog, acclog_fmt):
                self.children = []
                self.children.append(NodeMock('name',name))
                self.children.append(NodeMock('interval',interval))
                self.children.append(NodeMock('access_log',acclog))
                self.children.append(NodeMock('access_log_format',acclog_fmt))


        from time import sleep
        interval = 1 
        c = ConfigMock('serverX_requests', interval, '/etc/httpd/logs/ssl_access.log',
            '%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\" %k %I %O %D')
        r = ApacheLog(debug=True)
        r.configure(c)
        while True:
            r.read()
            sleep(interval)
else:
    import collectd
    r = ApacheLog()
    collectd.register_config(r.configure)
    collectd.register_read(r.read);
