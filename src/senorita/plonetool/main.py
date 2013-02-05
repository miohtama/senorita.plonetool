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


def get_site_folder(site_name):
    """
    Where our Plone installation will be.
    """
    return "/srv/plone/%s" % site_name


def get_unix_user(site_name):
    """
    Which UNIX user will control the file-system permissions.
    """
    return site_name


def get_unix_user_home(username):
    """
    Where is home folder for a UNIX user
    """
    return "/home/%s" % username


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

    Make sure we are not asked for a password when doing SSH.
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
            print "Done"
            stdin.put("yes\n")
            return True

        # Clear line
        if char == "\n":
            callback.aggregated = ""

    callback.aggregated = ""

    parts = target.split(":")
    host = parts[0]
    # Run a dummy ssh command, so we see we get public key auth working
    # If the server prompts for known_hosts update auto-yes it
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

        # Create buildout shared cache folder if some buildouts use them
        if not os.path.exists("/srv/plone/buildout-cache/eggs"):
            install("-d", "/srv/plone/buildout-cache/eggs")
            install("-d", "/srv/plone/buildout-cache/downloads")

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


def create_site_initd_script(name):
    """
    Install /etc/init.d boot script for a Plone site.

    We do this Ubuntu style, not sure if works 100% on Debian.

    http://wiki.debian.org/LSBInitScripts

    http://developer.plone.org/hosting/restarts.html#lsbinitscripts-starting-with-debian-6-0
    """

    from sh import chmod

    updaterc = Command("/usr/sbin/update-rc.d")

    username = create_plone_unix_user(name)
    folder = get_site_folder(name)

    script_body = DEBIAN_BOOT_TEMPLATE % dict(user=username, folder=folder, name=name)

    initd_script = "/etc/init.d/%s" % name

    print "Creating start/stop script %s" % initd_script
    with sudo:
        echo(script_body, _out=initd_script)
        chmod("u+x", initd_script)
        updaterc(name, "defaults")


@plac.annotations(
    name=("Installation name under /srv/plone", "positional", None, None, None, "yourplonesite"),
    )
def create_site_base(name):
    """
    Create an empty Plone site installation and corresponding UNIX user.

    Each sites has its own subfolder /srv/plone/xxx.
    """
    check_known_environment()

    create_base()

    username = create_plone_unix_user(name)

    # Enable friendly
    give_user_ztanesh(username)

    folder = get_site_folder(name)

    with sudo:
        print "Creating a Plone site %s folder %s" % (name, folder)
        install("-d", folder)
        reset_permissions(username, folder)

    create_site_initd_script(name)

    print "Site base (re)created: %s" % folder


def copy_site_files(source, target):
    """
    Rsync all non-regeneratable Plone files

    http://plone.org/documentation/kb/copying-a-plone-site
    """

    # Make sure we can SSH into to the box without interaction
    ssh_handshake(source)

    print "Syncing site files from old site %s" % source
    from sh import rsync
    # XXX: --progress here is too verbose, rsync having multiple file transfer indicator?
    rsync("-a", "--compress-level=9", "--inplace", "--exclude", "*.lock", "--exclude", "*.log", "--exclude", "eggs", "--exclude", "downloads", "--exclude", "parts", "%s/*" % source, target,
        _out=_unbuffered_stdout,
        _err=_unbuffered_stdout,
        _out_bufsize=0).wait()

    # Rercreate regeneratable folders
    install("-d", "%s/eggs" % target)
    install("-d", "%s/parts" % target)
    install("-d", "%s/downloads" % target)


def rebootstrap_site(name, folder, python):
    """
    (Re)run buildout.

    Sudo first before doing this.
    """

    from sh import bash
    # Bootstrap + buildout is so dummy with its cwd which we cannot pass through sudo
    # we do a trick here by running the command through bash
    bash("-c", "cd %s && %s bootstrap.py" % (folder, python))
    print "Running buildout on %s" % folder

    # We really want to capture all output here since buildout is a bitch
    bash("-c", "cd %s && bin/buildout" % folder,
        _out_bufsize=0,
        _out=_unbuffered_stdout,
        _err=_unbuffered_stdout).wait()


def migrate(name, source, python):
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

    check(name)

    print "Migrated site %s and it appears to be working" % name


def check(name):
    """
    Check that the site is ok for this script and related sysdmin tasks.
    """
    folder = get_site_folder(name)

    user = get_unix_user(name)

    if not os.path.exist(folder):
        sys.exit("Folder does not exist: %s" % folder)

    if not has_user(user):
        sys.exit("No UNIX user on the server: %s" % user)

    # Detect a running Plone site by a ZODB database lock file
    if os.path.exists(os.path.join(folder, "var", "Data.fs.lock")):
        sys.exit("Site at %s must be cleanly stopped for the sanity check" % folder)

    if not os.path.exists(os.path.join(folder, "bin", "plonectl")):
        sys.exit("plonectl command missing for %s" % folder)

    def zope_ready_checker(line, stdin, process):
        """
        We detect a succeful Plone launch from stdout debug logs.
        """
        print line
        if "zope ready" in line.lower():
            process.terminate()
            return True

    unix_user = get_unix_user(name)

    with sudo(H=True, i=True, u=unix_user, _with=True):
        # See that Plone starts
        print "Testing Plone site startup at %s, max timeout %d seconds" % (folder, MAX_PLONE_STARTUP_TIME)
        plonectl = Command("%s/bin/plonectl" % folder)
        plonectl("fg", "instance", _timeout=MAX_PLONE_STARTUP_TIME).wait()


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
    Checks that a buildout work.
    """
    pass


def restart():
    """
    Restart all sites installed on the server.

    If sites are in ZEO front end clusters try to do soft restarts so that there is at least one client up all the time.
    """

    # List of processes we need to start/stop
    processes = []

    for folder, zeo_type, name in find_plone_sites("/srv/plone"):
        if zeo_type == "zeo":
            # Get all binaries we need to restart
            for x in range(1, 12):
                bin_name = os.path.join(folder, "bin", "client%d" % x)
                if os.path.exists(bin_name):
                    processes.append(bin_name)
            processes.append(os.path.join(folder, "bin", "zeoserver"))
        else:
            processes.append(os.path.join(folder, "bin", "instance"))

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


def install_plone(name, python, version, mode):
    """
    Installs a new Plone site using best practices.
    """

    from sh import git, bash, install, touch, rm

    folder = get_site_folder(name)
    unix_user = get_unix_user(name)

    # Resolve the latest version
    if version == "latest":
        version = get_plone_versions()[0]

    # We run installer as the root and will fix up permissions later

    # Checkout installer files from the Github
    temp_folder = tempfile.mkdtemp()
    installer_folder = os.path.join(temp_folder, "plone-unified-installer-%s" % version)
    plone_home = os.path.join(temp_folder, "plone-fake-home")

    # create_instance.py wants no folder, we fix up later
    if os.path.exists(folder):
        sys.exit("%s exists. Please remove first." % folder)

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
        "--run_buildout", "0",
        "--itype", mode,
        '--install_lxml', "no",
        _out=_unbuffered_stdout,
        _err=_unbuffered_stdout
        ).wait()

    # Delete our Github installer checkout and messy files
    rm("-rf", temp_folder)

    # Restrict FS access
    reset_permissions(unix_user, folder)

    create_site_base(name)

    # Run buildout
    with sudo(H=True, i=True, u=unix_user, _with=True):

        # We mod the buildout to disable shared cache,
        # as we don't want to share ../buildout-cache/egs with other UNIX users
        # on this server
        buildout_base = os.path.join(folder, "base.cfg")
        remove_lines(buildout_base, ["eggs-directory=../buildout-cache/eggs", "download-cache=../buildout-cache/downloads"])

        rebootstrap_site(name, folder, python)

    # Check we got it up an running Plone installation
    check(name)


@plac.annotations( \
    create=("Create an empty Plone site installation under under /srv/plone with matching UNIX user", "flag", "c"),
    install=("Install a Plone site installation under under /srv/plone", "flag", "i"),
    ploneversions=("List available Plone versions", "flag", "pv"),
    migrate=("Migrate a Plone site from an existing server", "flag", "m"),
    check=("Check that Plone site configuration under /srv/plone has necessary parts", "flag", "s"),
    restart=("Restart all Plone sites installed on the server", "flag", "r"),
    python=("Which Python interpreter is used for a migrated site", "option", "p", None, None, "/srv/plone/python/python-2.7/bin/python"),
    mode=("Installation mode: 'standalone' or 'cluster'", "option", "im", None, None, "clusten"),
    version=("Which Plone version to install. Defaults the latest stable", "option", "v", None, None),
    name=("Installation name under /srv/plone", "positional", None, None, None, "ploneinstallationname"),
    source=("SSH source for the site migration", "positional", None, None, None, "user@server.com/~folder"),
    )
def main(create, install, ploneversions, migrate, check, restart,
    python="/srv/plone/python/python-2.7/bin/python",
    version="latest",
    mode="cluster",
    name=None,
    source=None):
    """
    A sysadmin utility to deploy and maintain multihosting Plone environment.

    More info: https://github.com/miohtama/senorita.plonetool
    """

    # XXX: Implement proper plac subcommands here so we do not need this if...else logic structure
    if create:
        create_site_base(name)
    elif install:
        install_plone(name, python, version, mode)
    elif migrate:
        migrate(name, source, python)
    elif check:
        check(name)
    elif ploneversions:
        print_plone_versions()
    elif restart:
        restart()
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
