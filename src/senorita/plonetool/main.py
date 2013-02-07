#!/usr/bin/python
# -*- coding: utf-8 -*-
"""

    Senorita Plonetool, at your service.

    From Brazil with love <3

"""

import os
import sys
import pwd
import tempfile
import time
import json

import plac
import requests

# Commands avail on all UNIXes
# http://amoffat.github.com/sh/
from sh import sudo, install, echo, uname, python, which
from sh import cd, chown, Command

from .utils import read_template
from .fixbuildout import mod_buildout

# Debian packages we need to install to run out Plone hocus pocus
# http://plone.org/documentation/manual/installing-plone/installing-on-linux-unix-bsd/debian-libraries
# https://github.com/miohtama/ztanesh/
PACKAGES = [
"acl",
"curl",
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

# Cron job file contents for nightly Plone site rsetarts
CRON_TEMPLATE = read_template("cron-job.sh")

#: Generated shell script template to use visudo
#: to add options to /etc/sudoers
ADD_LINE_VISUDO = read_template("add_line_visudo.sh")

# buildout.cfg override for buildout.python recipe
# Only install Pythons necessary for runnign Plone 3.x, Plone 4.x
PYTHON_BUILDOUT = read_template("python-buildout.cfg")

# Debian init.d compatible script
DEBIAN_BOOT_TEMPLATE = read_template("lsb-init.template.sh")

# How fast Plone site bin/instance must come up before
# we assume it's defunct
MAX_PLONE_STARTUP_TIME = 300


# plac subcommands http://plac.googlecode.com/hg/doc/plac.html#implementing-subcommands
commands = 'create', 'migrate', 'versions', 'restart', 'check', 'find'

#: Target installation UNIX user
_user = None

#: Target installation folder
_folder = None

#: Target site name
_site_name = None


def generate_password():
    """
    Generates a random password for UNIX user.
    """
    from sh import pwgen
    return pwgen("32", "1")  # 32 characters long pw


def check_known_environment():
    """
    See that we run on a supported box.
    """
    n = uname("-a").lower()
    if not ("debian" in n or "ubuntu" in n):
        sys.exit("This script has been tested only with Ubuntu/Debian environments")


def guess_plone_site_name_and_user(folder):
    """
    Determine Plone site UNIX user and name from the installation folder.
    """

    site_name = os.path.basename(folder)
    user = site_name
    return site_name, user


def setup_context(folder, user):
    """
    Determine used site name, folder and user from command line input.

    setup_context() applies only command line commands operating against a single Plone site.
    For multisite commands, determine user for each site using ``guess_plone_site_name_and_user()``.
    """

    _site_name, _user = guess_plone_site_name_and_user(folder)

    if user:

        # Override UNIX user
        _user = user

    _folder = os.path.abspath(folder)

    return _site_name, _folder, _user


def get_unix_user_home(username):
    """
    Where is home folder for a UNIX user
    """
    return "/home/%s" % username


def check_supported_version(version):
    """
    Check if Plone installation for the given version is supported for the version.
    """

    if version.startswith("3"):
        sys.exit("Sorry, no Plone 3 installs through this script")


_unbuffered_stdout = os.fdopen(sys.stdout.fileno(), "wb", 0)


def process_unbuffered_output(char, stdin):
    """
    Echo rsync progress in ANSI compatible manner.

    Helper method for sh.
    """
    _unbuffered_stdout.write(char)


def has_line(path, line):
    """
    Check if a certain file has a given line.
    """
    from sh import grep

    # Check if we have the option already in /etc/sudoers
    # http://man.cx/grep#heading14 -> 1 == no lines
    grep_status = grep(line, path, _ok_code=[0, 1]).exit_code

    return grep_status == 0


def remove_lines(path, old_lines):
    """
    Remove a line in a file.

    Note: Operation is not FS atomic safe.
    """
    f = open(path, "rt")
    lines = f.read().split("\n")
    f.close()
    for old_line in old_lines:
        if old_line in lines:
            lines.remove(old_line)
    f = open(path, "wt")
    f.write("\n".join(lines))
    f.close()


def add_sudoers_option(line):
    """
    Adds a option to /etc/sudoers file in safe manner.

    Generate a bash script which will be invoke itself as visudo EDITOR.

    http://stackoverflow.com/a/3706774/315168
    """

    from sh import chmod, rm

    with sudo:

        if not has_line("/etc/sudoers", line):

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

    Make sure we are not asked for a password when doing SSH connection to remote.to

    :param target: SSH spec. May include diretory.
    """
    from sh import ssh

    # http://amoffat.github.com/sh/tutorials/2-interacting_with_processes.html

    def callback(char, stdin):
        """
        Handle SSH input
        """

        _unbuffered_stdout.write(char.encode())

        # Ugh http://stackoverflow.com/a/4852073/315168
        callback.aggregated += char

        if "(yes/no)? " in callback.aggregated:
            stdin.put("yes\n")
            return True

        # Clear line
        if char == "\n":
            callback.aggregated = ""

    callback.aggregated = ""

    parts = target.split(":")
    host = parts[0]

    print "Doing SSH handshake and no password login verification to %s. If the process hangs here check you have working SSH_AGENT connection (e. g. not stale one from screen)." % host

    # Run a dummy ssh command, so we see we get public key auth working
    # If the server prompts for known_hosts update auto-yes it
    p = ssh("-o", "PreferredAuthentications=publickey", host, "touch ~/plonetool.handshake",
        _out=callback,
        _err=callback,
        _out_bufsize=0,
        _tty_in=True)
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


def create_python_env(folder):
    """
    Compile a Python environment with various Python versions to run Plone.

    Create Python's under /srv/plone/python

    Use https://github.com/collective/buildout.python
    """
    from sh import git

    python_target = os.path.join(folder, "python")

    print "Setting up various Python versions at %s" % python_target

    with sudo:

        if not os.path.exists(python_target):
            cd(folder)
            git("clone", "git://github.com/collective/buildout.python.git", "python")

        if not os.path.exists(os.path.join(python_target, "python-2.7", "bin", "python")):
            cd(python_target)
            echo(PYTHON_BUILDOUT, _out="%s/buildout.cfg" % python_target)
            python("bootstrap.py")
            run = Command("%s/bin/buildout" % python_target)
            run()

        pip = Command("%s/python-2.7/bin/pip" % python_target)

        # Avoid buildout bootstrap global python write bug using Distribute 0.6.27
        pip("install", "--upgrade", "Distribute")

        # Plone 4.x sites heavily rely on lxml
        # Create a shared lxml installation. System deps should have been installed before.
        # for plone 3.x do this by hand
        # collective.buildout.python does not do lxml, which is crucial
        pip("install", "lxml")


def create_base(folder):
    """
    Create multisite Plone hosting infrastructure on a server..

    Host sites at /srv/plone or chosen cache_folder

    Each folder has a file called buildout.cfg which is the production buildout file
    for this site. This might not be a real file, but a symlink to a version controlled
    file under /srv/plone/xxx/src/yoursitecustomization.policy/production.cfg.

    Log rotate is performed using a global UNIX log rotate script:
    http://opensourcehacker.com/2012/08/30/autodiscovering-log-files-for-logrotate/

    :param folder: Base installation folder for all the sites e.g. /srv/plone
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
        if not os.path.exists(folder):
            print "Creating installation base %s" % folder
            install(folder, "-d")

        # Create nightly restart cron job
        if os.path.exists("/etc/cron.d"):
            print "(Re)setting all sites nightly restart cron job"
            echo(CRON_TEMPLATE, _out=CRON_JOB)

    create_python_env(folder)


def has_user(user):
    """
    http://stackoverflow.com/questions/2540460/how-can-i-tell-if-a-given-login-exists-in-my-linux-box-using-python
    """
    try:
        pwd.getpwnam(user)
        return True
    except KeyError:
        return False


def create_plone_unix_user(name):
    """ Create a UNIX user for the site.

    Each site has its own UNIX user for security. Only this user has
    read-write access to site files. In the case of a site gets compromised,
    the damage should be limited within that site. To do tasks for a site
    either sudo in as a site user or give the users SSH keys.
    """
    from sh import adduser

    if not has_user(name):
        print "Creating UNIX user: %s" % name
        adduser("--disabled-password", "--gecos", '""', "--shell", "/bin/zsh", name)
        print "Password is disabled. Use sudo to play around as %s." % name

    return name


def give_user_ztanesh(unix_user):
    """
    Make sure our UNIX user runs ZtaneSH shell it is more productive to work with Plone sites.

    https://github.com/miohtama/ztanesh
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
    Reset UNIX file permissions on a Plone installation folder.

    We set files readable only by the owner.
    """
    from sh import chmod

    print "Re(setting) file permissions on %s" % folder
    # Disable read access for other UNIX users
    chown("-R", "%s:%s" % (username, username), folder)
    chmod("-R", "o-rwx", folder)


def create_site_initd_script(name, folder, username):
    """
    Install /etc/init.d boot script for a Plone site.

    We do this Ubuntu style, not sure if works 100% on Debian.

    http://wiki.debian.org/LSBInitScripts

    http://developer.plone.org/hosting/restarts.html#lsbinitscripts-starting-with-debian-6-0
    """

    from sh import chmod

    updaterc = Command("/usr/sbin/update-rc.d")

    script_body = DEBIAN_BOOT_TEMPLATE % dict(user=username, folder=folder, name=name)

    initd_script = "/etc/init.d/%s" % name

    print "Creating start/stop script %s" % initd_script
    with sudo:
        echo(script_body, _out=initd_script)
        chmod("u+x", initd_script)
        updaterc(name, "defaults")


def create_site_base(name, folder, username):
    """
    Create an empty Plone site installation and corresponding UNIX user.

    Each sites has its own subfolder /srv/plone/xxx.
    """
    check_known_environment()

    base_folder = os.path.dirname(folder)

    create_base(base_folder)

    create_plone_unix_user(username)

    # Enable friendly
    give_user_ztanesh(username)

    with sudo:
        print "Creating a Plone site %s folder %s for UNIX user %s" % (name, folder, username)
        install("-d", folder)
        reset_permissions(username, folder)

    create_site_initd_script(name, folder, username)

    print "Site base (re)created: %s" % folder


def copy_site_files(source, target):
    """
    Rsync all non-regeneratable Plone files.

    We also *must* not copy some files as they would mess up
    running the buildout on the new target.

    http://plone.org/documentation/kb/copying-a-plone-site
    """

    # Make sure we can SSH into to the box without interaction
    ssh_handshake(source)

    print "Syncing site files from old site %s" % source
    from sh import rsync
    # XXX: --progress here is too verbose, rsync having multiple file transfer indicator?
    rsync("-a", "--compress-level=9", "--inplace",
        "--exclude", "*.lock",  # Data.fs.lock, instance.lock
        "--exclude", "*.pid",
        "--exclude", "*.log",  # A lot of text data we probably don't need on the new server
        "--exclude", "eggs",
        "--exclude", "downloads",  # Redownload
        "--exclude", "parts",  # Buildout always regenerates this folder
        "--exclude", "bin",  # old bin/ scripts may not regenereate, point to Py interpreter on the old server
        "--exclude", ".installed.cfg",  # Otherwise does not regenerate zeoserver
        "--exclude", ".mr.developer.cfg",
        "--exclude", "*.old",     # Data.fs.old
        "%s/*" % source, target,
        _out=_unbuffered_stdout,
        _err=_unbuffered_stdout,
        _out_bufsize=0).wait()

    # Rercreate regeneratable folders
    install("-d", "%s/eggs" % target)
    install("-d", "%s/parts" % target)
    install("-d", "%s/downloads" % target)
    install("-d", "%s/bin" % target)


def rebootstrap_site(name, folder, python, mr_developer=False):
    """
    (Re)run bootstrap.py & buildout.

    This will make Plone buildout.cfg setup pull are Python
    code needed to run the site from pypi.python.org and
    various other sources. This includes site addon code.

    Sudo first before doing this.

    :param mr_developer: Do Mr. Developer activation of src/ packages
    """

    from sh import bash

    def build_it_out(_ok_code=[0]):
        """ Little helper """
        # We really want to capture all output here since buildout is a bitch
        exit_code = bash("-c", "cd %s && bin/buildout" % folder,
            _out_bufsize=0,
            _out=_unbuffered_stdout,
            _err=_unbuffered_stdout,
            _ok_code=_ok_code
            ).wait().exit_code
        return exit_code

    # We cannot pass current working folder (cd) through sudo
    # we do a trick here by running the command through bash
    bash("-c", "cd %s && %s bootstrap.py" % (folder, python))

    print "Running buildout on %s, Mr. Developer support is %s" % (folder, "activated" if mr_developer else "deactivated")

    _ok_code = [0]

    # Mr. Developer based buildouts will bonk with exit code 1 on first run
    if mr_developer:
        _ok_code.append(1)

    exit_code = build_it_out(_ok_code)

    # This is generated by first buildout run,
    # before bo fails on unknown pkg
    develop = os.path.join(folder, "bin", "develop")

    if mr_developer and (exit_code == 1) and os.path.exists(develop):
        # Buildout return 1 when it encounters non-activated pkg
        # which is in src/
        bash("-c", "cd %s && bin/develop activate ''" % folder,
            _out_bufsize=0,
            _out=_unbuffered_stdout,
            _err=_unbuffered_stdout,
            ).wait()

        # Here we go again
        build_it_out()


def fix_bootstrap_py(folder):
    """
    Update boostrap.py to make sure its the latest version.

    This fixes some buildout bootstrapping failures on old sites.

    http://pypi.python.org/pypi/buildout.bootstrap/
    """
    from sh import curl

    bootstrap_py = os.path.join(folder, "boostrap.py")

    print "Updatong %s/bootstrap.py" % folder

    url = "http://svn.zope.org/repos/main/zc.buildout/trunk/bootstrap/bootstrap.py"

    curl("-L", "-o", bootstrap_py, url)


def migrate_site(name, folder, unix_user, source, python):
    """
    Migrate a Plone site from another server.

    :param name: New site installation id

    :param source: SSH source path

    :param python: Python interpreter used for the new installation
    """
    require_ssh_agent()

    allow_ssh_agent_thru_sudo()

    create_site_base(name)

    allow_non_root_user_to_share_ssh_agent_forwarding(unix_user)

    with sudo(H=True, i=True, u=unix_user, _with=True):
        copy_site_files(source, folder)

        # Reinstall bootstrap which might have been worn out by time
        fix_bootstrap_py(folder)

        # Apply automatic buildout fixes
        fix_buildout(os.path.join(folder, "buildout.cfg"))

        rebootstrap_site(name, folder, python, mr_developer=True)

    # Make sure all file permissions are sane after migration
    reset_permissions(unix_user, folder)

    check_startup(name)

    print "Migrated site %s and it appears to be working" % name


def check_startup(name, folder, unix_user):
    """
    Check that the site is ok for this script and related sysdmin tasks.

    :param name: Plone installation name
    """
    if not os.path.exists(folder):
        sys.exit("Folder does not exist: %s" % folder)

    if not has_user(unix_user):
        sys.exit("No UNIX user on the server: %s" % unix_user)

    # Detect a running Plone site by a ZODB database lock file
    for lock_file in ["instance.lock", "client1.lock"]:
        lock = os.path.join(folder, "var", lock_file)
        if os.path.exists(lock):
            sys.exit("Site at %s must be cleanly stopped for the sanity check. Please delete lock file %s if this is not correct." % (folder, lock))

    if not os.path.exists(os.path.join(folder, "bin", "plonectl")):
        sys.exit("plonectl command missing for %s" % folder)

    def zope_ready_checker(line, stdin, process):
        """
        We detect a succeful Plone launch from stdout debug logs.
        """
        #_unbuffered_stdout.write(line)
        #_unbuffered_stdout.write("\n")
        if "zope ready" in line.lower():
            zope_ready_checker.success = True
            process.terminate()
            return True

    zope_ready_checker.success = False

    # Do Zope standalone check
    with sudo(H=True, i=True, u=unix_user, _with=True):

        plonectl = Command("%s/bin/plonectl" % folder)

        # Do ZEO check
        if os.path.exists(os.path.join(folder, "bin", "client1")):

            print "Testing Plone site cluster mode startup at %s, max timeout %d seconds" % (folder, MAX_PLONE_STARTUP_TIME)
            # See that Plone starts
            plonectl("start", "zeoserver")
            plonectl("fg", "client1",
                _out=zope_ready_checker,
                _err=zope_ready_checker,
                _timeout=MAX_PLONE_STARTUP_TIME,
                _ok_code=[0, 143],  # Allow terminate signal
                ).wait()
            plonectl("stop", "zeoserver")

        else:

            print "Testing Plone site standlone mode at %s, max timeout %d seconds" % (folder, MAX_PLONE_STARTUP_TIME)
            # See that Plone starts
            plonectl("fg", "instance",
                _out=zope_ready_checker,
                _err=zope_ready_checker,
                _timeout=MAX_PLONE_STARTUP_TIME,
                _ok_code=[0, 143],  # Allow terminate signal
                ).wait()

    if zope_ready_checker.success:
        # got the text
        print "Site starts ok %s" % folder
    else:
        # We did not get ok signal
        sys.exit("Could not start %s - please run on foreground by hand" % folder)


def find_plone_sites(root="/srv/plone"):
    """
    Return all Plone installations under a certain folder.

    We will also detect whether the site installation is

    - Single Zope process instance

    - ZEO front end cluster (multiple front end processes)

    :return: List of (path, installation type, installation name) tuples
    """

    # XXX: Do not recurse this time, assume /srv/plone layout

    result = []

    for folder in os.listdir(root):
        path = os.path.join(root, folder)

        # buildout generated bin/client1 launcher script
        if os.path.exists(os.path.join(path, "bin", "client1")):
            result.append((path, "zeo", folder,))

        # buildout generated bin/instance launcher script
        if os.path.exists(os.path.join(path, "bin", "instance")):
            result.append((path, "zope", folder,))

    if not result:
        sys.exit("No Plone sites found at %s" % root)

    return result


def buildout_check(name):
    """
    Checks that buildout.cfg file works and builds a working Plone site.
    """
    # TODO


def get_plone_processes(folder, zeo_type):
    """

    """
    # List of processes we need to start/stop
    processes = []

    if zeo_type == "zeo":
        # Get all binaries we need to restart
        for x in range(1, 12):
            bin_name = os.path.join(folder, "bin", "client%d" % x)
            if os.path.exists(bin_name):
                processes.append(bin_name)
        processes.append(os.path.join(folder, "bin", "zeoserver"))
    else:
        processes.append(os.path.join(folder, "bin", "instance"))

    return processes


def restart_all():
    """
    Restart all sites installed on the server.

    If sites are in ZEO front end clusters try to do soft restarts so that there is at least one client up all the time.
    """

    for folder, zeo_type, name in find_plone_sites("/srv/plone"):
        processes = get_plone_processes(folder, zeo_type)

    # Restart processes one by one
    # so that there should be always
    for p in processes:
        print "Restarting process %s" % p
        cmd = Command(p)
        cmd("stop")
        if not p.endswith("zeoserver"):
            # Don't mess with database server too long
            time.sleep(20)
        cmd("start")


def stop_all():
    """
    Stop all sites installed on the server.
    """

    for folder, zeo_type, name in find_plone_sites("/srv/plone"):
        processes = get_plone_processes(folder, zeo_type)

    for p in processes:
        print "Restarting process %s" % p
        cmd = Command(p)
        cmd("stop")


def get_plone_versions():
    """
    Use Github API to get released Plone unified installer version tags.
    """

    # Plone unified installer base
    repo = "https://api.github.com/repos/plone/Installers-UnifiedInstaller/tags"

    # Let's do it with requets lib
    r = requests.get(repo)
    if not r.ok:
        sys.exit("Failed to load Plone version info from %s" % repo)

    data = json.loads(r.content)

    versions = []
    for tag in data:
        # {u'commit': {u'url': u'https://api.github.com/repos/plone/Installers-UnifiedInstaller/commits/91ebd0b0ca07642cbb51adb16901d6212ad7f349', u'sha': u'91ebd0b0ca07642cbb51adb16901d6212ad7f349'}, u'tarball_url': u'https://api.github.com/repos/plone/Installers-UnifiedInstaller/tarball/4.1.4', u'name': u'4.1.4', u'zipball_url': u'https://api.github.com/repos/plone/Installers-UnifiedInstaller/zipball/4.1.4'}
        versions.append(tag["name"])

    versions.sort()
    versions.reverse()

    return versions


def print_plone_versions():
    """
    Print available Plone installers from Github
    """
    versions = get_plone_versions()
    project_url = "https://github.com/plone/Installers-UnifiedInstaller"
    print "Currently available Plone versions at %s" % project_url
    for v in versions:
        print "   %s" % v


def install_plone(name, folder, unix_user, python, version, mode):
    """
    Installs a new Plone site using best practices.
    """

    from sh import git, bash, install, touch, rm

    if os.path.exists(folder) and not os.path.exists(os.path.join(folder, "buildout.cfg")):
        sys.exit("%s exists, but seems to lack buildout.cfg. Please remove first." % folder)

    # Create buildout structure using create_instance.py
    if not os.path.exists(os.path.join(folder, "buildout.cfg")):

        # Resolve the latest version
        if version == "latest":
            version = get_plone_versions()[0]

        # Checkout installer files from the Github
        temp_folder = tempfile.mkdtemp()
        installer_folder = os.path.join(temp_folder, "plone-unified-installer-%s" % version)
        plone_home = os.path.join(temp_folder, "plone-fake-home")

        print "Getting Plone installer"
        if not os.path.exists(installer_folder):
            git("clone", "git://github.com/plone/Installers-UnifiedInstaller.git", installer_folder)

        print "Checking out Plone installer version from Git %s" % version
        bash("-c", "cd %(installer_folder)s && git checkout %(version)s" % locals())

        # The following is needed to satisfy create_instance.py Distribute egg look-up
        # It assumes distribute and zc.buildout eggs in a predefined location.
        # We spoof these eggs as they are not going to be used in real.
        cache_folder = os.path.join(plone_home, "buildout-cache", "eggs")
        install("-d", cache_folder)
        touch(os.path.join(cache_folder, "zc.buildout-dummy.egg"))
        touch(os.path.join(cache_folder, "distribute-dummy.egg"))

        python = Command(python)
        # Run installer
        python( \
            os.path.join(installer_folder, "helper_scripts", "create_instance.py"),
            "--uidir", installer_folder,
            "--plone_home", plone_home,
            "--instance_home", folder,
            "--daemon_user", unix_user,
            "--buildout_user", unix_user,
            "--run_buildout", "0",
            "--itype", mode,
            '--install_lxml', "no",
            _out=_unbuffered_stdout,
            _err=_unbuffered_stdout
            ).wait()

        # Delete our Github installer checkout and messy files
        rm("-rf", temp_folder)

    # Integrate with LSB
    create_site_base(name, folder, unix_user)

    # Restrict FS access over what unified installer did for us
    reset_permissions(unix_user, folder)

    # Run buildout... we should be able to resume from errors
    with sudo(H=True, i=True, u=unix_user, _with=True):

        fix_buildout(folder)

        # We mod the buildout to disable shared cache,
        # as we don't want to share ../buildout-cache/egs with other UNIX users
        # on this server
        rebootstrap_site(name, folder, python)

    # Check we got it up an running Plone installation
    check_startup(name)


def fix_buildout(folder):
    """ Fix a buildout file in-place.

    Guess related buildout files based on the path.

    :param fpath: Path to the buildout.cfg
    """
    path = folder
    buildout_cfg_path = os.path.join(path, "buildout.cfg")
    base_cfg_path = os.path.join(path, "base.cfg")
    mod_buildout(buildout_cfg_path, base_cfg_path)


@plac.annotations( \
    create=("Create an empty Plone site installation under under /srv/plone with matching UNIX user", "flag", "c"),
    install=("Install a Plone site installation under under /srv/plone", "flag", "i"),
    ploneversions=("List available Plone versions", "flag", "pv"),
    migrate=("Migrate a Plone site from an existing server", "flag", "m"),
    check=("Check that Plone site configuration under /srv/plone has necessary parts", "flag", "s"),
    restartall=("Restart all Plone sites installed on the server in a specific folder. Default folder /srv/plone", "flag", "ra"),
    stopall=("Stop all Plone sites installed on the server in a specific folder. Default folder /srv/plone", "flag", "sa"),
    fixbuildout=("Upgrade buildout file in-place in a folder for the contemporary best practices", "flag", "fb"),
    python=("Which Python interpreter is used for a migrated site", "option", "p", None, None, "/srv/plone/python/python-2.7/bin/python"),
    mode=("Installation mode: 'standalone' or 'cluster'", "option", "im", None, None, "clusten"),
    version=("Which Plone version to install. Defaults the latest stable", "option", "v", None, None),
    user=("UNIX user which we use for create, migration and install. Defaults to installation folder name", "option", "u", None, None),
    folder=("Path to target folder", "positional", None, None, None, "ploneinstallationname"),
    source=("SSH source for the site migration", "positional", None, None, None, "user@server.com/~folder"),
    )
def main(create, install, ploneversions, migrate, check, restartall, stopall, fixbuildout,
    python="/srv/plone/python/python-2.7/bin/python",
    version="latest",
    mode="standalone",
    user=None,
    folder="/srv/plone/mysite",
    source=None):
    """
    A sysadmin utility to deploy and maintain multihosting Plone environment.

    More info: https://github.com/miohtama/senorita.plonetool

    """

    # XXX: Implement proper plac subcommands here so we do not need this if...else logic structure
    if create:
        name, folder, user = setup_context(folder, user)
        create_site_base(name, folder, user)
    elif install:
        # XXX: get rid of setup_context() and pass explicit parameters
        name, folder, user = setup_context(folder, user)
        install_plone(name, folder, user, python, version, mode)
    elif migrate:
        # XXX: get rid of setup_context() and pass explicit parameters
        name, folder, user = setup_context(folder, user)
        migrate_site(name, folder, user, source, python)
    elif check:
        name, folder, user = setup_context(folder, user)
        check_startup(folder)
    elif ploneversions:
        print_plone_versions()
    elif restartall:
        if not folder:
            folder = "/srv/plone"
        restart_all(folder)
    elif stopall:
        if not folder:
            folder = "/srv/plone"
        stop_all(folder)
    elif fixbuildout:
        fix_buildout(folder)
    else:
        sys.exit("Please give an action or -h for help")


def entry_point():
    """
    Application starting point which parses command line.

    Can be used from other modules too.
    """
    exit_code = plac.call(main)
    sys.exit(exit_code)

if __name__ == "__main__":
    entry_point()
