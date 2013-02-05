#!/bin/sh
### BEGIN INIT INFO
# Provides:          %(name)s
# Required-Start:    $remote_fs $syslog
# Required-Stop:     $remote_fs $syslog
# Should-Start:      my plone site
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Start Plone %(name)s
# Description:       Start Plone instance at %(folder)s
#
#
#
#
### END INIT INFO

PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

[ -f %(folder)s/bin/plonectl ] || exit 0

DAEMON=%(folder)s/bin/plonectl
NAME="%(name)s"
DESC="Plone site at %(folder)s"

. /lib/lsb/init-functions

case "$1" in
    start)
        log_daemon_msg "Starting $DESC" "$NAME"
        if start-stop-daemon --quiet --oknodo --chuid %(user)s:%(user)s \
                             --exec ${DAEMON} --start start
        then
            log_end_msg 0
        else
            log_end_msg 1
        fi
        ;;

    stop)
        log_daemon_msg "Stopping $DESC" "$NAME"
        if start-stop-daemon --quiet --oknodo --chuid %(user)s:%(user)s \
                             --exec ${DAEMON} --start stop
        then
            log_end_msg 0
        else
            log_end_msg 1
        fi
        ;;

    restart)
        log_daemon_msg "Restarting $DESC" "$NAME"
        if start-stop-daemon --quiet --oknodo --chuid %(user)s:%(user)s \
                             --exec ${DAEMON} --start restart
        then
            log_end_msg 0
        else
            log_end_msg 1
        fi
        ;;

    status)
        start-stop-daemon --chuid %(user)s:%(user)s \
                            --exec ${DAEMON} --start status
        ;;

    force-reload)
        echo "Plone doesn't support force-reload, use restart instead."
        ;;

    *)
        echo "Usage: /etc/init.d/%(name)s {start|stop|status|restart}"
        exit 1
        ;;
esac

exit 0