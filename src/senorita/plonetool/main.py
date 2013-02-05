#!/usr/bin/python
# -*- coding: utf-8 -*-
"""

    Senorita Plonetool, at your service.

    From Brazil with love.

"""

import os
import sys
import pwd
import tempfile

import plac

# Commands avail on all UNIXes
# http://amoffat.github.com/sh/
from sh import sudo, install, echo, uname, python, which
from sh import cd, chown, Command

# Debian packages we need to install to run out Plone hocus pocus
# http://plone.org/documentation/manual/installing-plone/installing-on-linux-unix-bsd/debian-libraries
# https://github.com/miohtama/ztanesh/
PACKAGES = [
"acl",
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
"pwgen"
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

#: Generated shell script template to use visudo
#: to add options to /etc/sudoers
ADD_LINE_VISUDO = """#!/bin/bash

set -e

if [ ! -z "$1" ]; then
        echo "" >> $1
        echo "{line}" >> $1
else
        export EDITOR=$0
        visudo
fi
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


def generate_password():
    """
    Generates a random password for UNIX user.
    """
    from sh import pwgen
    return pwgen("32", "1")  # 32 characters long pw


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


def add_sudoers_option(line):
    """
    Adds a option to /etc/sudoers file in safe manner.

    Generate a bash script which will be invoke itself as visudo EDITOR.

    http://stackoverflow.com/a/3706774/315168
    """

    from sh import grep, chmod, rm

    with sudo:

        # Check if we have the option already in /etc/sudoers
        # http://man.cx/grep#heading14 -> 1 == no lines
        grep_status = grep('%s' % line, "/etc/sudoers", _ok_code=[0, 1]).exit_code

        if grep_status == 1:

            print "Updating /etc/sudoers to enable %s" % line

            tmp = tempfile.NamedTemporaryFile(mode="wt", delete=False)
            # Generate visudo EDITOR which adds the line
            # https://www.ibm.com/developerworks/mydeveloperworks/blogs/brian/entry/edit_sudoers_file_from_a_script4?lang=en
            script = ADD_LINE_VISUDO.format(line=line)
            tmp.write(script)
            tmp.close()
            chmod("u+x", tmp.name)
            Command(tmp.name)()
            rm(tmp.name)


def require_ssh_agent():
    """
    Make sure that we use SSH keys from the SSH agent.
    """
    if not "SSH_AUTH_SOCK" in os.environ:
        sys.exit("We can only do this if you are using SSH agent properly with ForwardAgent option: http://opensourcehacker.com/2012/10/24/ssh-key-and-passwordless-login-basics-for-developers/")


def ssh_handshake(target):
    """
    Make sure we get a remote host added in ~/.ssh/known_hosts in sane manner.

    Make sure we are not asked for a password when doing SSH.
    """
    from sh import ssh

    # http://amoffat.github.com/sh/tutorials/2-interacting_with_processes.html

    stdout = os.fdopen(sys.stdout.fileno(), "wb", 0)

    def callback(char, stdin):
        """
        Handle SSH input
        """
        stdout.write(char.encode())

        # Ugh http://stackoverflow.com/a/4852073/315168
        callback.aggregated += char

        if "(yes/no)? " in callback.aggregated:
            print "Done"
            stdin.put("yes\n")
            return True

        # Clear line
        if char == "\n":
            callback.aggregated = ""

    callback.aggregated = ""

    parts = target.split(":")
    host = parts[0]
    p = ssh("-o", "PreferredAuthentications=publickey", host, "touch ~/plonetool.handshake", _out=callback, _out_bufsize=0, _tty_in=True)
    p.wait()


def allow_ssh_agent_thru_sudo():
    """
    Make it possible to use SSH agent forwarding with sudo on the server.
    """
    # http://serverfault.com/a/118932/74975
    add_sudoers_option("Defaults    env_keep+=SSH_AUTH_SOCK")


def allow_non_root_user_to_share_ssh_agent_forwarding(username):
    """
    When you need to pass SSH agent to non-root user over sudo.
    """

    if not "SSH_AUTH_SOCK" in os.environ:
        raise RuntimeError("SSH agent forwarding must be enabled")

    # http://serverfault.com/a/442099/74975
    from sh import setfacl
    setfacl("-m", "u:%s:rw" % username, os.environ["SSH_AUTH_SOCK"])
    setfacl("-m", "u:%s:x" % username, os.path.dirname(os.environ["SSH_AUTH_SOCK"]))


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
        adduser("--disabled-password", "--gecos", '""', "--shell", "/bin/zsh", name)
        print "Password is disabled. Use sudo to play around as %s." % name

    return name


def give_user_ztanesh(unix_user):
    """
    Make sure our UNIX user runs ZtaneSH shell it is more productive to work with Plone sites.
    """
    from sh import git
    from sh import chsh

    home = get_unix_user_home(unix_user)

    # Install ZtaneSH
    if not os.path.exists("%s/tools" % home):

        print "Installing ZtaneSH for user %s" % unix_user

        with sudo(i=True, u=unix_user, _with=True):
            cd(home)
            git("clone", "git://github.com/miohtama/ztanesh.git", "tools")
            setup = "%s/tools/zsh-scripts/setup.zsh" % home
            run = Command(setup)
            run()

    # Set user default shell
    with sudo:
        chsh("-s", "/bin/zsh", unix_user)


def reset_permissions(username, folder):
    """
    Reset UNIX file permissions on a Plone folder.
    """
    from sh import chmod

    print "Re(setting) file permissions on %s" % folder
    # Disable read access for other UNIX users
    chown("-R", "%s:%s" % (username, username), folder)
    chmod("-R", "o-rwx", folder)


def create_site_base(site_name):
    """
    Each sites has its own subfolder /srv/plone/xxx and
    """
    check_known_environment()

    create_base()

    username = create_plone_unix_user(site_name)

    # Enable friendly
    give_user_ztanesh(username)

    folder = get_site_folder(site_name)

    with sudo:
        print "Creating a Plone site %s folder %s" % (site_name, folder)
        install("-d", folder)
        reset_permissions(username, folder)

    print "Site base (re)created: %s" % folder


def copy_site_files(source, target):
    """
    Rsync all non-regeneratable Plone files

    http://plone.org/documentation/kb/copying-a-plone-site
    """

    # Make sure we can SSH into to the box without interaction
    ssh_handshake(source)

    stdout = os.fdopen(sys.stdout.fileno(), "wb", 0)

    def process_output(char, stdin):
        """
        Echo rsync progress in ANSI compatible manner.
        """
        stdout.write(char)

    print "Copying site files from: %s" % source
    from sh import rsync
    # XXX: --progress here is too verbose, rsync having multiple file transfer indicator?
    rsync("-a", "--compress-level=9", "--inplace", "--exclude", "*.log", "--exclude", "eggs", "--exclude", "downloads", "--exclude", "parts", "%s/*" % source, target, _out=process_output, _err=process_output, _out_bufsize=0).wait()

    # Rercreate regeneratable folders
    install("-d", "%s/eggs" % target)
    install("-d", "%s/parts" % target)
    install("-d", "%s/downloads" % target)


def rebootstrap_site(name, folder, python):
    """
    Re-run buildout
    """
    cd(folder)
    python = Command(python)
    python("bootstrap.py")
    Command("%s/bin/buildout")()


def migrate_site(name, source, python):
    """
    Migrate a Plone site from another server.
    """

    require_ssh_agent()

    allow_ssh_agent_thru_sudo()

    create_site_base(name)

    folder = get_site_folder(name)
    unix_user = get_unix_user(name)

    allow_non_root_user_to_share_ssh_agent_forwarding(unix_user)

    with sudo(H=True, i=True, u=unix_user, _with=True):
        folder = get_site_folder(name)
        copy_site_files(source, folder)
        rebootstrap_site(name, folder, python)

    # Make sure all file permissions are sane after migration
    reset_permissions(unix_user, folder)


@plac.annotations( \
    create=("Create an empty Plone site installation under under /srv/plone with matching UNIX user", "flag", "c"),
    migrate=("Migrate a Plone site from an existing server", "flag", "m"),
    python=("Which Python interpreter is used for a migrated site", "option", "p", None, None, "/srv/plone/python/python-2.7/bin/python"),
    name=("Installation name", "positional", None, None, None, "yourplonesite"),
    source=("SSH source for the site", "positional", None, None, None, "user@server.com/~folder"),
    )
def main(create, migrate, python, name, source=None):
    """
    A sysadmin utility to set-up multihosting Plone environment, create Plone sites and migrate existing ones.

    More info: https://github.com/miohtama/senorita.plonetool
    """

    if create:
        create_site_base(name)
    elif migrate:
        migrate_site(name, source, python)
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


