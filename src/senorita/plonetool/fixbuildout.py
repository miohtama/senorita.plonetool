"""

    Utilities to modify Plone's buildout.cfg INI file in place.

    We can upgrade automatically old buildout.cfgs to reflect the contemporary best practices.

    Because buildout configs can be layered via extends, we need to pass several configs
    files to be mutated. Sites may have only buildout.cfg, or buildout.cfg + base.cfg (unified installer model).

    We need to implement some magic and heurestics to guess how people have build their
    buildout.cfgs in the past and we cannot be succesful every time.

"""

import os
import stat

# Structure reserving INI parser
# http://code.google.com/p/iniparse/
import iniparse

from collections import OrderedDict

# Which bo section name is used to generate client1, client2, ect
POSSIBLE_CLIENT_TEMPLATE_SECTIONS = "client_base", "client1", "head", "instance"


# http://opensourcehacker.com/2012/07/11/working-around-buildout-server-down-problems/
ALLOW_HOSTS = """github.com
    *.python.org
    *.plone.org
    launchpad.net
#    *.zope.org
"""


def guess_client_base(*cfgs):
    """ Guess what's the master "ZEO client" template in buildout configuratio.

    :return: (buildout iniparser instance, name)
    """

    for buildout in cfgs:
        for sect in POSSIBLE_CLIENT_TEMPLATE_SECTIONS:
            if buildout.has_section(sect):
                return (buildout, sect)

    return None, None


def add_plonectl(*cfgs):
    """
    Add missing plonectl command.

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
    """

    # Read parts of all layered configs
    parts = []

    # XXX: Detect by recipe, not by part name
    part_name = "unifiedinstaller"

    for buildout in cfgs:

        if buildout.has_section(part_name):
            # += added section, iniparser can't understand, etc
            return

        if buildout.has_section("buildout"):
            if buildout.has_option("buildout", "parts"):
                parts += buildout.get('buildout', 'parts').split('\n')

    # We have it already
    if part_name in parts:
        return

    print "Adding plonectl command to buildout"

    # Write out new unifiedinstaller
    buildout = cfgs[0]
    if buildout.has_option("buildout", "parts"):
        # looks like we fail here if the
        # buildout syntax uses extends and parts +=
        parts = buildout.get('buildout', 'parts').split('\n')
        parts += part_name

    buildout.add_section(part_name)
    buildout.set(part_name, "recipe", "plone.recipe.unifiedinstaller")
    buildout.set(part_name, "user", "admin:admin")


def add_logrotate(*cfgs):
    """

    This prevents your server disk space eventually fulling with logs.


    # Comment the next four lines out if you don't need
    # automatic log rotation for event and access logs.
    event-log-max-size = 5 MB
    event-log-old-files = 5
    access-log-max-size = 20 MB
    access-log-old-files = 5
    """
    buildout, section = guess_client_base(*cfgs)

    if not buildout:
        return

    if buildout.has_option(section, "event-log-max-size"):
        return

    print "Adding logrotate to buildout section %s" % section
    buildout.set(section, "event-log-max-size", "5 MB")
    buildout.set(section, "event-log-old-files", "5")
    buildout.set(section, "access-log-max-size", "20 MB")
    buildout.set(section, "access-log-old-files", "5")


def remove_buildout_cache(*cfgs):
    """
    Remove shard buildout cache folder.

    This adds additional layer of security. Different UNIX users cannot modify other sites' Python code.
    """

    remove_keys = ["eggs-directory", "download-cache", "extends-cache"]

    for buildout in cfgs:
        for key in remove_keys:
            if buildout.has_option("buildout", key):
                print "Removing buildout option %s" % key
                buildout.remove_option("buildout", key)


def fix_env_vars(*cfgs):
    """
    TODO

    Need to add

    zope_i18n_compile_mo_files true
    PYTHON_EGG_CACHE ${buildout:directory}/var/.python-eggs
    PYTHONHASHSEED random
    """


def strip_clients_line(*cfgs):
    """ Uuurhgs.

    https://github.com/plone/plone.recipe.unifiedinstaller/issues/1
    """
    for buildout in cfgs:
        if buildout.has_section("unifiedinstaler"):
            if buildout.has_option("unifiedinstaler", "clients"):
                buildout.remove_option("unifiedinstaler", "clients")


def set_allow_hosts(*cfgs):
    """
    Set allowed download hosts.

    http://opensourcehacker.com/2012/07/11/working-around-buildout-server-down-problems/
    """
    buildout = cfgs[0]
    buildout.set("buildout", "allow-hosts", ALLOW_HOSTS)


def knife_it(*buildouts):
    """
    Our buildout modification tasklist.
    """
    add_plonectl(*buildouts)
    add_logrotate(*buildouts)
    #add_random_hash(*buildouts)
    remove_buildout_cache(*buildouts)
    strip_clients_line(*buildouts)
    set_allow_hosts(*buildouts)


def write_buildout(path, buildout):
    """
    Write out a parsed buildout.cfg INI.
    """
    # Stringify content
    buildout = str(buildout.data)

    # Replace the file
    fd = file(path, 'w')
    fd.write(buildout)
    fd.close()
    # XXX: Not sure about this, but was in orignal code
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def mod_buildout(*paths):
    """ Modify buildout file(s).

    We read in several .cfg files which should be layered by buildouts extend = mechanism.

    All new stuff gets appended to file 1.

    We automatically skip missing files (E.g. if base.cfg is not provided)

    Example::

        mod_buildout("buildout.cfg", "base.cfg")

    :param path: Path to buildout.cfg
    """

    cfgs = OrderedDict()

    # See https://github.com/plone/Installers-UnifiedInstaller/blob/master/helper_scripts/create_instance.py#L126
    for path in paths:
        if not os.path.exists(path):
            continue

        buildout = iniparse.RawConfigParser()
        buildout.read(path)
        cfgs[path] = buildout

    knife_it(*cfgs.values())

    for path, buildout in cfgs.items():
        write_buildout(path, buildout)


def set_buildout_port(path, mode, port):
    """
    Set HTTP port in a buildout.

    In the case of cluster install, set port range start.

    :param path: Path to a buildout.cfg

    :param mode: "standalone" or "cluster"
    """
    buildout = iniparse.RawConfigParser()
    buildout.read(path)

    port = int(port)

    if mode == "standalone":
        print "Updating buildout.cfg port to %s" % port
        buildout.set("instance", "http-address", port)
    else:
        zeo_address = "127.0.0.1:%d" % port
        print "Updating buildout.cfg port range to %s" % port
        buildout.set("zeoserver",  "zeo-address", zeo_address)
        port += 1
        for part in ["client1", "client2", "client3", "client4"]:
            if buildout.has_section(part):
                buildout.set(part, "http-address", port)
                buildout.set(part, "zeo-address", zeo_address)

    write_buildout(path, buildout)
