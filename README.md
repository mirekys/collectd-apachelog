# collectd-apachelog
[Collectd](http://www.collectd.org/) plugin for obtaining request metrics from [Apache's](https://httpd.apache.org/) access log. Based on the [apache-log-parser](https://github.com/rory/apache-log-parser) library and the [collectd-python](https://collectd.org/documentation/manpages/collectd-python.5.shtml).

# Installation & Configuration

* Install the [apache-log-parser](https://github.com/rory/apache-log-parser) package
* Clone this repo: ```git clone https://github.com/mirekys/collectd-apachelog.git```
* Place *apachelog.py* and *util.py* to your collectd-python ModulePath
* Update your collectd.conf
```
  <Plugin python>
        ModulePath "/../../collectd-plugins/" # Path, where will the apachelog.py reside
        LogTraces false
        Interactive false
        Import "apachelog"

        <Module apachelog>
                # Plugin instance name
                Name "serverX_requests"
                # Which time interval should be read from the Access_log at each plugin run
                Interval 1
                AccessLog "/etc/httpd/logs/ssl_access.log"
                # Whichever format does your Apache server use for the Access_log
                AccessLogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\" %k %I %O %D" 
        </Module>
</Plugin>
```

# Output

Output of the plugin is dependent mainly on the *Access_log_format* that you specify. It is used by the *apache-log-parser* which then returns specific keys & values depending on format.

Values are then aggregated by HTTP method and further into *bytes*, *count* and *response time* field types. The value paths provided by the plugin are built dynamically as it reads the different requests from the Access_log (there is no predetermined set of value paths).

Output example:
```
serverX_requests/count-GET=4
serverX_requests/count-GET-num_keepalives=3
serverX_requests/bytes-GET-bytes_tx=16017
serverX_requests/bytes-GET-bytes_rx=3679
serverX_requests/bytes-GET-response_bytes_clf=12614
serverX_requests/response_time-GET-time_us=457318
serverX_requests/count-GET-status_2xx=4
serverX_requests/count-GET-status_3xx=0
```

# Debugging

You can run this plugin in standalone debug mode, where it outputs to console
what would be otherwise sent to the collectd daemon:

``` ./apachelog.py debug ```
