.. contents::

Introduction
============

``plonetool`` command which allows you to easily create and migrate sites in ``/srv/plone``.

Support Ubuntu / Debian servers.

This tool is designed for a multisite hosting where

* One server hosts multiple Plone sites

* These sites share the same Python installation which is created by the script

* Some additional security barries is put in the place by setting one UNIX user
  per site

* Some basic automated site maintenance is put in the place: nighly restart cron job, automatic site database packaging, site start up when the server goes up, log rotate

Installation
==============

Example::

    apt-get install curl
    git clone git://github.com/miohtama/senorita.plonetool.git
    cd senorita.plonetool
    curl -L -o virtualenv.py https://raw.github.com/pypa/virtualenv/master/virtualenv.py
    python virtualenv.py venv
    . venv/bin/activate
    python setup.py develop

Now you have command ``plonetool`` in PATH from ``venv/bin/plonetool``.


Usage
======

Create a Plone site
----------------------

Example::

    plonetool --create mysitename

Does

* Sets up a ``/srv/plone/python`` with all Python interpreters using `buildout.python <https://github.com/collective/buildout.python>`_

* Creates UNIX user *mysitename*

* Installs ZtaneSH for this user

* Creates /srv/plone/mysitename

* Sets up automatic restart in /etc/cron.daily/plone-restarts

* Sets up log rotate

Does not

* Set up backup

Migrate a Plone
----------------------

Copies a site (over SSH) from a source server to this server.



Requirements for Plone site to co-operate
========================================================

Your Plone buildout installation must come with functionality ``plonectl`` command.

Development
==============

Keep your script automatically synced on the server when editing files locally::

    . venv/bin/activate
    pip install watchdog
    watchmedo shell-command --recursive --command='rsync -av --exclude=venv --exclude=.git . yourserver:~/senorita.plonetool'

