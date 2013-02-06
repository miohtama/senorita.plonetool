"""

    Utilities to modify Plone's buildout.cfg INI file in place.

    We can upgrade automatically old buildout.cfgs to reflect the contemporary best practices.

    Because buildout configs can be layered via extends, we need to pass several configs
    files to be mutated. Sites may have only buildout.cfg, or buildout.cfg + base.cfg (unified installer model).

"""

import os

# Structure reserving INI parser
# http://code.google.com/p/iniparse/
import iniparser

from collections import OrderedDict


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

    for buildout in cfgs:
        parts += buildout.get('buildout', 'parts').split('\n')

    # We have it already
    if "unifiedinstaller" in parts:
        continue

    # Write out new unifiedinstaller
    buildout = cfgs[0]
    parts = buildout.get('buildout', 'parts').split('\n')
    parts += "unifiedinstaller"

    buildout.add_section("unifiedinstaller")
    buildout.set("unifiedinstaler", "recipe", "plone.recipe.unifiedinstaller")
    buildout.set("unifiedinstaler", "user", "admin:admin")


def add_logrotate(*cfgs):
    pass


def remove_buildout_cache(*cfgs):
    """
    Remove shard buildout cache folder.

    This adds additional layer of security. Different UNIX users cannot modify other sites' Python code.
    """

    remove_keys = ["eggs-directory ", "download-cache", "extends-cache"]

    for buildout in cfgs:
        for key in remove_keys:
            if buildout.has_option("buildout", key):
                buildout.remove_option("buildout", key)


def knife_it(*buildouts):
    add_plonectrl(*buildouts)


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

    knife_it(cfgs.values())

    for path, buildout in cfgs.items():
        fd = file(path, 'w')
        fd.write(buildout)
        fd.close()
        os.chmod(fn, stat.S_IRUSR | stat.S_IWUSR)




