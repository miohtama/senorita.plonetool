#!/usr/bin/python
"""

    Senorita Plonetool, at your service.

    From Brazil with love.

"""

import os
import sys
import pwd

import plac

# Commands avail on all UNIXes
# http://amoffat.github.com/sh/
from sh import sudo, install, echo, uname, python, which
from sh import cd, chown, Command

# Debian packages we need to install to run out Plone hocus pocus
# http://plone.org/documentation/manual/installing-plone/installing-on-linux-unix-bsd/debian-libraries
# https://github.com/miohtama/ztanesh/
PACKAGES = [
"supervisor",
"git-core",
"highlight",
"zsh",
"subversion",
"build-essential",
"libssl-dev",
"libxml2-dev",
"libxslt1-dev",
"libbz2-dev",
"zlib1g-dev",
"python-distribute",
"python-dev",
"libjpeg62-dev",
"libreadline-gplv2-dev",
"python-imaging",
"wv",
"poppler-utils",
]

# Which Cron script does nightly restarts
CRON_JOB = "/etc/cron.daily/restart-plones"


CRON_TEMPLATE = """#!/bin/sh
#
# This cron job will restart Plone sites on this server daily
#
/srv/plone/restart-all.sh

"""

RESTART_ALL_TEMPLATE = """#!/bin/sh
# Restart all the sites on a server


"""

# buildout.cfg override for buildout.python recipe
# Only install Pythons necessary for runnign Plone 3.x, Plone 4.x
PYTHON_BUILDOUT = """
[buildout]
extends =
    src/base.cfg
    src/readline.cfg
    src/libjpeg.cfg
    src/python24.cfg
    src/python27.cfg
    src/links.cfg

parts =
    ${buildout:base-parts}
    ${buildout:readline-parts}
    ${buildout:libjpeg-parts}
    ${buildout:python24-parts}
    ${buildout:python27-parts}
    ${buildout:links-parts}

python-buildout-root = ${buildout:directory}/src

# we want our own eggs directory and nothing shared from a
# ~/.buildout/default.cfg to prevent any errors and interference
eggs-directory = eggs

[install-links]
prefix = /opt/local
"""


def check_known_environment():
    """
    """
    n = uname("-a").lower()
    if not ("debian" in n or "ubuntu" in n):
        sys.exit("This script has been tested only with Ubuntu/Debian environments")


def get_site_folder(site_name):
    return "/srv/plone/%s" % site_name


def get_unix_user(site_name):
    """
    Which UNIX user will control the file-system permissions.
    """
    return site_name


def get_unix_user_home(username):
    """
    """
    return "/home/%s" % username


def create_python_env():
    """
    Compile a Python environment with various Python versions to run Plone.

    Create Python's under /srv/plone/python

    Use https://github.com/collective/buildout.python
    """
    from sh import git

    print "Setting up various Python versions"

    with sudo:

        if not os.path.exists("/srv/plone/python"):
            cd("/srv/plone")
            git("clone", "git://github.com/collective/buildout.python.git", "python")

        if not os.path.exists("/srv/plone/python/python-2.7/bin/python"):
            cd("/srv/plone/python")
            echo(PYTHON_BUILDOUT, _out="/srv/plone/python/buildout.cfg")
            python("bootstrap.py")
            run = Command("/srv/plone/python/bin/buildout")
            run()


def create_base():
    """
    Create multisite Plone hosting infrastructure on a server..

    Host sites at /srv/plone

    Each folder has a file called buildout.cfg which is the production buildout file
    for this site. This might not be a real file, but a symlink to a version controlled
    file under /srv/plone/xxx/src/yoursitecustomization.policy/production.cfg.

    Log rotate is performed using a global UNIX log rotate script:
    http://opensourcehacker.com/2012/08/30/autodiscovering-log-files-for-logrotate/
    """
    from sh import apt_get

    with sudo:

        # Return software we are going to need in any case
        # Assumes Ubuntu / Debian
        # More info: https://github.com/miohtama/ztanesh
        if (not which("zsh")) or (not which("git")) or (not which("gcc")):
            # Which returs zero on success
            print "Installing OS packages"
            apt_get("update")
            apt_get("install", "-y", *PACKAGES)

        # Create base folder
        if not os.path.exists("/srv/plone"):
            print "Creating /srv/plone"
            install("/srv/plone", "-d")

        # Create nightly restart cron job
        if os.path.exists("/etc/cron.d"):
            print "(Re)setting all sites nightly restart cron job"
            echo(CRON_TEMPLATE, _out=CRON_JOB)

    create_python_env()


def has_user(user):
    """
    http://stackoverflow.com/questions/2540460/how-can-i-tell-if-a-given-login-exists-in-my-linux-box-using-python
    """
    try:
        pwd.getpwnam(user)
        return True
    except KeyError:
        return False


def create_plone_unix_user(site_name):
    """ Create a UNIX user for the site.

    Each site has its own UNIX user for security. Only this user has
    read-write access to site files. In the case of a site gets compromised,
    the damage should be limited within that site. To do tasks for a site
    either sudo in as a site user or give the users SSH keys.
    """
    from sh import adduser

    name = get_unix_user(site_name)

    if not has_user(name):
        print "Creating UNIX user: %s" % name
        print "Please give a random password"
        adduser(name)

    return name


def give_user_ztanesh(unix_user):
    """
    Make sure our UNIX user runs ZtaneSH shell it is more productive to work with Plone sites.
    """
    from sh import git
    from sh import chsh

    home = get_unix_user_home()

    # Install ZtaneSH
    if not os.path.exist("/home/%s/tools/" % home):

        print "Installing ZtaneSH for user %s" % unix_user

        with sudo(i=True, u=unix_user, _with=True):
            cd(home)
            git("clone", "git://github.com/miohtama/ztanesh.git")
            run = Command("/home/%s/tools/setup.zsh" % home)
            run()

    # Set user default shell
    with sudo:
        chsh("-s", "/bin/zsh", unix_user)


def create_site_base(site_name):
    """
    Each sites has its own subfolder /srv/plone/xxx and
    """
    check_known_environment()

    create_base()

    username = create_plone_unix_user(site_name)

    folder = get_site_folder(site_name)

    with sudo:
        install("-d", "/srv/plone/%s" % folder)
        chown("-R", "%s:%s" % (username, username), folder)


def migrate_site(name, source):
    """
    """
    pass


@plac.annotations( \
    create=("Create a new Plone site installation with UNIX user under /srv/plone", "flag", "c"),
    name=("Installation name", "positional", None, None, None, "yourplonesite"),
    )
def main(create, name):
    """
    A sysadmin utility to set-up multihosting Plone environment, create Plone sites and migrate existing ones.

    More info: https://github.com/miohtama/senorita.plonetool
    """

    if create:
        create_site_base(name)
    else:
        sys.exit("Please give an action")


def entry_point():
    """
    Application starting point which parses command line.

    Can be used from other modules too.
    """
    exit_code = plac.call(main)
    sys.exit(exit_code)

if __name__ == "__main__":
    entry_point()


