.. contents::

Introduction
============

``plonetool`` command which allows you to easily create and migrate sites in ``/srv/plone``.

Support Ubuntu / Debian servers. Tested with Ubuntu 12.04 LTS.

This tool is designed for a multisite hosting where

* One server hosts multiple Plone sites in ``/srv/plone`` folder, as per guidelines
  `Linux Filesystem Hierarchy <http://www.tldp.org/LDP/Linux-Filesystem-Hierarchy/html/srv.html>`_.
  Currently the script does not allow other file system layouts to be used, but supporting them
  is easy.

* These sites share the same Python installation which is created by `collective.buildout.python <https://github.com/collective/buildout.python>`_. Currently other kind of Python set-ups are not supported.

* Some additional security barries is put in the place by setting one UNIX user
  per site

* Some basic automated site maintenance is put in the place: nighly restart cron job, automatic site database packaging, site start up when the server goes up, log rotate

The script assumes a clean server installation, so it will do everything for you
starting from installing the system packages.

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

Server layout
===============

The following assumptions are made how you manage your Plone deployments.

You can have multiple Plone sites::

    /srv/plone/site1
    /srv/plone/site2
    ...

Each site has an UNIX user with the site installation name as the username.
These users have password login disabled; use either ``sudo`` or ``ssh`` with
public key authentication to log in for site maintenance work.

Plone sites use Python interpreters compiled with ``collective.buildout.python``::

    /srv/plone/python/python-2.7/bin/python # Plone 4.x
    /srv/plone/python/python-2.4/bin/python # Plone 3.x

Teh sites are restarted once in a night by ``/etc/cron.daily/plone-restart``
in graceful manner (no service interrupts).

Usage
======

Because this script will ``sudo`` to different UNIX users assuming no password prompt the only sensible
way to run this script is as a root.

Create a Plone site
----------------------

Example::

    plonetool --create mysitename

Does

* Sets up a ``/srv/plone/python`` with all Python interpreters using `buildout.python <https://github.com/collective/buildout.python>`_

* Creates UNIX user *mysitename*

* Installs more friendly shell, `ZtaneSH <https://github.com/miohtama/ztanesh>`_, for this user

* Creates /srv/plone/mysitename

* Sets up automatic restart in /etc/cron.daily/plone-restarts

* Sets up log rotate

Does not

* Set up backup

Migrate a Plone
----------------------

Copies a site (over SSH) from a source server to this server.

- Copies site buildout, site data and custom src/

- Rebootstraps buildout on the new server

- You can specify a Python version for old Plone sites

`Read basics about SSH first <http://opensourcehacker.com/2012/10/24/ssh-key-and-passwordless-login-basics-for-developers/>`_.

Example::

    # Start on your local computer
    # Setup passwordless SSH key exchange to the old server
    ssh-copy-id user@oldserver.com

    # Now SSH into the new server
    # Make sure you have ssh'ed to the server using ForwardAgent option
    ssh -A root@newserver.com

    # Migrate the site from the old server
    plonetool --migrate newsitename oldunixuser@oldserver.example.com:/srv/plone/oldsite

    # You can retype the command to resume migration

You can also migrate Plone 3.3 site using automatically installde ``/srv/plone/python/python-2.4/bin/python``::

    plonetool --migrate --python /srv/plone/python/python-2.4/bin/python newsitename oldunixuser@oldserver.example.com:/srv/plone/oldsite

`More info about copying Plone sites <http://plone.org/documentation/kb/copying-a-plone-site>`_

Check that Plone site works
--------------------------------------------

You can use script to check whether an installation under ``/srv/plone`` works::

     plonetool --check yoursitename

It checks

* plonectl command provided

* ``bin/plonectl instance fg`` starts the site

The check cannot be performed against a running site.

Restart all the sites on the server
--------------------------------------------

This is a useful shortcut for

* Nightly Plone restarts

* Start all Plone sites on the server bootup

Simply run as root::

    plonetool --restart

It will restart

.. note ::

    This command concerns only Zope front end and database processes.
    You need to handle Apache, Nginx, Varnish and others separately.

Security notes
==================

This script plainly accepts any SSH hosts you give it without allowing
you manually to check ``known_hosts`` fingerprints. Please check all
host fingerprints before using the script.

Requirements for Plone site to co-operate
========================================================

Your Plone buildout installation must come with functionality ``plonectl`` command
provided by `plone.recipe.unifiedinstaller buildout recipe <http://pypi.python.org/pypi/plone.recipe.unifiedinstaller/>`_.

Add it to your buildout if needed::

    parts =
        ...
        unifiedinstaller


    [unifiedinstaller]
    # This recipe installs the plonectl script and a few other convenience
    # items.
    # For options see http://pypi.python.org/pypi/plone.recipe.unifiedinstaller
    recipe = plone.recipe.unifiedinstaller
    user = admin:admin  # This is not used anywhere after site creation

We also assume there exist a front end client called *instance* (bin/instance script)
which we can try to use to start and stop Plone site to see if it works.

Other
=============

The script heavily uses `Python sh package <http://amoffat.github.com/sh/>`_.

If you need more advanced Python deployment recipes check
`Salt Stack <http://docs.saltstack.org/>`_.

Development
==============

Keep your senorita.plonetool is automatically synced on the server when editing files locally::

    . venv/bin/activate
    pip install watchdog
    watchmedo shell-command --patterns="*.py" --recursive --command='rsync -av --exclude=venv --exclude=.git . yourserver:~/senorita.plonetool'

