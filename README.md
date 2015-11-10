# collectd-apachelog
[Collectd](http://www.collectd.org/) plugin for obtaining request metrics from [Apache's](https://httpd.apache.org/) access log. Based on the [apache-log-parser](https://github.com/rory/apache-log-parser) library and the [collectd-python](https://collectd.org/documentation/manpages/collectd-python.5.shtml).

# Installation & Configuration

* Install the [apache-log-parser](https://github.com/rory/apache-log-parser) package
* Clone this repo: ```git clone https://github.com/mirekys/collectd-apachelog.git```
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
                Access_log "/etc/httpd/log/ssl_access.log"
                # Whichever format does your Apache server use for the Access_log
                Access_log_format "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\" %k %I %O %D" 
        </Module>
</Plugin>
```

# Output

Output of the plugin is dependent mainly on the *Access_log_format* that you specify. It is used by the *apache-log-parser* which then returns specific keys & values depending on format.

Values are then aggregated by HTTP method and further into *bytes*, *count* and *response time* field types. The value paths provided by the plugin are built dynamically as it reads the different requests from the Access_log (there is no predetermined set of value paths).

Output example:
```
[2015-11-10 11:09:45.232481] serverX_requests/count-GET=4
[2015-11-10 11:09:45.232532] serverX_requests/count-GET-num_keepalives=3
[2015-11-10 11:09:45.232632] serverX_requests/bytes-GET-bytes_tx=16017
[2015-11-10 11:09:45.232878] serverX_requests/bytes-GET-bytes_rx=3679
[2015-11-10 11:09:45.232732] serverX_requests/bytes-GET-response_bytes_clf=12614
[2015-11-10 11:09:45.232681] serverX_requests/response_time-GET-time_us=457318
[2015-11-10 11:09:45.232832] serverX_requests/count-GET-status_2xx=4
[2015-11-10 11:09:45.232924] serverX_requests/count-GET-status_3xx=0
```
