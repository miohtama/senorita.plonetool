.. contents::

Introduction
============

``senorita.plonetool`` Python package providing you *plonetool* command which allows you to easily create, maintain, diagnose and migrate Plone sites. The script is the culmination of headache and alcohol abuse since 2004.

*plonetool* is designed for a multisite hosting situations where
a small enterprise is hosting several Plone sites from different clients running on the same server.
The tool is applicable outside its orignal use case as it generally adheres the best practices
of Linux and Plone world.

* The required packages and other global server setup is automatically
  done you by *plonetool*. You can start with a fresh server installation.

* The server hosts multiple Plone sites in ``/srv/plone`` folder, as per guidelines
  `Linux Filesystem Hierarchy <http://www.tldp.org/LDP/Linux-Filesystem-Hierarchy/html/srv.html>`_.

* The Plone sites share a Python installation which is created by `collective.buildout.python <https://github.com/collective/buildout.python>`_ recipe (Python 2.7, Python 2.4).

* For additional security, every Plone site installation is only accessible by its own UNIX user account with password disabled.

* The script can create fresh Plone site installations or migrate (copy) one from the existing server over SSH.

* Some basic automated site maintenance is put in the place: nighly restart cron job, automatic site database packaging, site start up when the server goes up, log rotate

*plonetool* support Ubuntu / Debian servers and it's tested with Ubuntu 12.04 LTS.
For other Linux distributions please run `unified installer by hand <http://plone.org/download>`_.

Installing plonetool
=====================

There exist only  *master* version of the tool and more or lessing rolling releases.
We suggest install the tool under ``/root`` with virtualenv for easy update.

To get started with *plonetool* on a clean server do the following::

    sudo -i # root me babe!
    apt-get install curl
    git clone git://github.com/miohtama/senorita.plonetool.git
    cd senorita.plonetool
    curl -L -o virtualenv.py https://raw.github.com/pypa/virtualenv/master/virtualenv.py
    python virtualenv.py venv
    . venv/bin/activate
    python setup.py develop

Now you have command *plonetool* in PATH from ``venv/bin/plonetool``.
You can directly invoke this command as ``/root/senorita.plonetool/venv/bin/plonetool``.


Server layout, maintenance and automated tasks
============================================================

Folder layout
----------------------

The following assumptions are made how you manage your Plone deployments.

You can have multiple Plone sites as described by LSB services run on the server::

    /srv/plone/site1
    /srv/plone/site1/buildout.cfg
    /srv/plone/site1/var
    /srv/plone/site1/src
    /srv/plone/site1/eggs
    ...
    /srv/plone/site2
    ...
    /srv/plone/python  # Shared Python interpreters installation

UNIX users
----------------------

Each site has an UNIX user with the site installation name as the username (e.g. ``site1``).
These users have password login disabled; use either ``sudo`` or ``ssh`` with
`public key authentication <http://opensourcehacker.com/2012/10/24/ssh-key-and-passwordless-login-basics-for-developers/>`_ to log in for the site maintenance work.

Setting up SSH keys
----------------------

The suggestion is to add your passphrase protected public SSH key to the Plone UNIX user for login::

    sudo -i
    # Make sure site1 user has ssh configuration folder
    install -d /home/site1/.ssh
    # Copy-paste your public SSH key line from your local ~/.ssh/id_rsa.pub file
    echo "Long line goes here XXX" >> /home/site1/authorized_keys
    chown -R site1:site1 /home/site1/  # Make site1 owner of the file
    chmod -R o-rwx /home/site1/.ssh  # Restrict SSH key permissions

Now you should be log in as the ``site1`` user and do the sysadmin tasks::

    ssh site1@yourserver
    cd /srv/plone/site1
    bin/buildout
    # ... etc ...

Python interpreters
----------------------

Plone sites use Python interpreters compiled with ``collective.buildout.python``::

    /srv/plone/python/python-2.7/bin/python # Plone 4.x
    /srv/plone/python/python-2.4/bin/python # Plone 3.x

LSB init scripts
----------------------

The sites have an init.d script created as::

    /etc/init.d/site1
    /etc/init.d/site2
    ...

Nightly restarts
----------------------

All sites on the server are set up to be `restarted once in a night <http://developer.plone.org/hosting/restarts.html#nightly-restart>`_ by ``/etc/cron.daily/plone-restart``script.
If you use clustered install this happens in graceful manner, without affecting the site users (too much).

Log rotate
----------------------

The site `log rotation is handled internally by the buildout <http://developer.plone.org/reference_manuals/active/deployment/logs.html>`_.

Database package
----------------------

TODO: Pack the site database automatically.

Usage
======

Because this script will ``sudo`` to different UNIX users assuming no password prompt the only sensible
way to run this script is as a root.

You can execute Plone tool directly from its installation location::

    /root/senorita.plonetool/venv/bin/plonetool

List Plone versions
-------------------------------------

This command gets available Plone versions from `Github installer repo <https://github.com/plone/Installers-UnifiedInstaller>`_.

Example::

    plonetool --ploneversions

Use this command to get available Plone versios for running install (as below).

Install a Plone site
-------------------------------------

This command downloads, installs and set-ups Plone site for multisite hosting on the server.
Plone versions are available on Github using `Plone unified installer <https://github.com/plone/Installers-UnifiedInstaller/>´_.

The site is integrated with the server maintenance structure
as described in *Create an empty Plone installation*..

To install the latest Plone version as *yoursitename*::

    plonetool --install yoursitename #

Or::

    plonetool --version 4.2 --install yoursitename

The command *should be* able to resume errors, especially if running buildout fails
due to network errors. After the installation *plonetool* checks that your site is
fully functional (starts up properly).

Please note that by default all Plone sites use port (range) starting at 8080.
Currently ``plonetools install`` does not change this.
You must manually edit buildout.cfg to allocate free TCP/IP ports on the server,
so that all sites have unique ports.

Differences to Unified installer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The major difference between running Unified Installer by hand and using *plonetool* are

* *plonetool* forces you to follow Linux Standard Base server layout. Init and restart scripts support multiple sites on the same server.

* ``UNIX user`` for Plone site maintenance is configured for you automatically

* Sites on the server share the Python interpreter (``/srv/plone/python``)

* *plonetool* sets file system permissions in more restrictive manner

* *plonetool* supports Plone 3.x installations

In both the cases, buildout skeleton is setup by the same `create_instance.py script <https://github.com/plone/Installers-UnifiedInstaller/blob/master/helper_scripts/create_instance.py>`_.

Create an empty Plone installation
-------------------------------------

This command creates an empty server structure where you can drop in your Plone site.

Example::

    plonetool --create mysitename

Does

* Sets up a ``/srv/plone/python`` with all Python interpreters using `buildout.python <https://github.com/collective/buildout.python>`_

* Creates UNIX user *mysitename*

* Installs more friendly shell, `ZtaneSH <https://github.com/miohtama/ztanesh>`_, for this user

* Creates /srv/plone/mysitename

* Creates Ubuntu/Debian LBS start/stop script in ``/etc/init.d``

* Sets up automatic restart in /etc/cron.daily/plone-restarts

* Sets up log rotate

Does not do

* Set up site backups

Migrate a Plone site over SSH
------------------------------

Copies a site (over SSH) from a source server to this server.

- Copies site buildout, site data and custom ``src/``

- Rebootstraps buildout on the new server

- Buildout and site startup check after the migration

`Read basics about SSH public key handshaking first <http://opensourcehacker.com/2012/10/24/ssh-key-and-passwordless-login-basics-for-developers/>`_. All migration happens over SSH, password free.

Example::

    # Start the process on your local computer
    # Setup passwordless SSH key exchange to the old server
    ssh-copy-id user@oldserver.com

    # Now SSH into the new server
    # Make sure you have ssh'ed to the server using ForwardAgent option
    ssh -A root@newserver.com

    # Migrate the site from the old server
    plonetool --migrate newsitename oldunixuser@oldserver.example.com:/srv/plone/oldsite

    # You can retype the command above to resume the migration

You can also migrate Plone 3.3 site using automatically install``/srv/plone/python/python-2.4/bin/python``::

    plonetool --migrate --python /srv/plone/python/python-2.4/bin/python newsitename oldunixuser@oldserver.example.com:/srv/plone/oldsite

You cannot run migrate command in screen, as because if your SSH agent connection dies
remote file copying over SSH hangs.

`More info about copying Plone sites <http://plone.org/documentation/kb/copying-a-plone-site>`_

Check that Plone site works
--------------------------------------------

You can use script to check whether an installation under ``/srv/plone`` works::

     plonetool --check yoursitename

It checks

* plonectl command provided

* ``bin/plonectl instance fg`` starts the site

The check cannot be performed against a running site.

Restart all Plone sites on the server
--------------------------------------------

This is a useful shortcut for

* Nightly Plone restarts

* Start all Plone sites on the server bootup

Simply run as root::

    plonetool --restart

It will restart all Plone sites found in /srv/plone.

.. note ::

    This command concerns only Zope front end and database processes.
    You need to handle Apache, Nginx, Varnish and others separately.

Fix buildout
--------------------------------------------

Automatically modify buildout.cfg and base.cfg in place
to reflect modern Plone best pratices, effectively upgrading
and fixing old buildouts to be run with ``plonetool``.

Usage::

    plonetool --fixbuildout buildout.cfg  # Automatically disovers base.cfg

Automatizes

* Log rotation enable

* Add missing plonectl command

* Strip out shared egg cache

Security notes
==================

When migrating sites, *plonetool* plainly accepts any SSH hosts you give it without allowing
you manually to check ``known_hosts`` fingerprints. Please check all
host fingerprints before using the script.

The script supports shared Python eggs folder under ``/srv/plone/buildout-cache``
but security wise this is bad idea. Instead, only on local development machines I recommend adding a
`buildout global configuration file <http://plone.org/documentation/manual/developer-manual/managing-projects-with-buildout/creating-a-buildout-defaults-file>`_  ~/.buildout/default.cfg::

    # OSX example
    [buildout]
    eggs-directory = /Users/moo/code/buildout-cache/eggs
    download-cache = /Users/moo/code/buildout-cache/downloads
    extends-cache = /Users/moo/code/buildout-cache/extends


Requirements for Plone configurations to co-operate with plonetool
===================================================================

Your Plone buildout installation must come with functionality ``plonectl`` command
provided by `plone.recipe.unifiedinstaller buildout recipe <http://pypi.python.org/pypi/plone.recipe.unifiedinstaller/>`_.

Add it to your buildout if needed::

    parts =
        ...
        unifiedinstaller


    [unifiedinstaller]
    # This recipe installationls the plonectl script and a few other convenience
    # items.
    # For options see http://pypi.python.org/pypi/plone.recipe.unifiedinstaller
    recipe = plone.recipe.unifiedinstaller
    user = admin:admin  # This is not used anywhere after site creation

More complex example with two ZEO front end clients::

    [unifiedinstaller]
    # This recipe installs the plonectl script and a few other convenience
    # items.
    # For options see http://pypi.python.org/pypi/plone.recipe.unifiedinstaller
    recipe = plone.recipe.unifiedinstaller
    user = admin:admin  # This is not used anywhere after site creation
    zeoserver = zeoserver
    clients = client1 client2

Currently the script does not allow other file system layouts besides /srv/plone, but supporting them is easy to add.

Currently only ``/srv/plone/python`` Python set-ups are supported.

Other
=============

The script heavily uses `Python sh package <http://amoffat.github.com/sh/>`_.

If you need more advanced Python deployment recipes check
`Salt Stack <http://docs.saltstack.org/>`_.

Development
==============

To ``senorita.plonetool`` is automatically synced on the server when editing files locally::

    . venv/bin/activate
    pip install watchdog
    watchmedo shell-command --patterns="*.py" --recursive --command='rsync -av --exclude=venv --exclude=.git . yourserver:~/senorita.plonetool'

Lightweight unit tests provider::

    . venv/bin/activate
    python -m unittest discover senorita.plonetool

Author
=======

`Mikko Ohtamaa <http://opensourcehacker.com>`_ (`Twitter <http://twitter.com/moo9000>`_, `Facebook <https://www.facebook.com/pages/Open-Source-Hacker/181710458567630>`_)
