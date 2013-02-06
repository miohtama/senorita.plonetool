"""

    Some random unit tests.

"""

import os
import unittest
import StringIO

import iniparse

from senorita.plonetool.fixbuildout import knife_it


class TestModBuildout(unittest.TestCase):
    """
    Check that our buildout modder works.
    """

    def parse_old_stuff(self):
        src1 = os.path.join(os.path.dirname(__file__), "testdata", "oldbuildout.cfg")
        src2 = os.path.join(os.path.dirname(__file__), "testdata", "base.cfg")

        buildout1 = iniparse.RawConfigParser()
        buildout1.read(src1)

        buildout2 = iniparse.RawConfigParser()
        buildout2.read(src2)

        knife_it(buildout1, buildout2)

        # Check we modded bo1 correctly
        buf = StringIO.StringIO()
        buildout1.write(buf)
        text = buf.getvalue()

        buf = StringIO.StringIO()
        buildout2.write(buf)
        text2 = buf.getvalue()

        return text, text2

    def test_add_plonectrl(self):
        text, text2 = self.parse_old_stuff()
        self.assertTrue("unifiedinstaller" in text)

    def test_no_eggs_cache(self):
        text, text2 = self.parse_old_stuff()
        self.assertFalse("eggs-directory" in text2)

    def test_log_rotate(self):
        text, text2 = self.parse_old_stuff()
        self.assertTrue("event-log-max-size" in text)

