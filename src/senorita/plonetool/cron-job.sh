#!/bin/sh
#
# This cron job will restart Plone sites on this server nightly
#

/root/senorita.plonetool/venv/bin/plonetool --restart
