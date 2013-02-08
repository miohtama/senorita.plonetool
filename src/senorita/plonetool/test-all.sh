#!/bin/zsh
#
# Test all script functionality.
# Note that running this command will pollute your server, so use
# discardable VM.
#
# Note: It is *NOT* safe to run this script on the production site with other Plones running.
#
# Run under virtualenv
#


# Where we will install a lot of Plones
# Allow run tests one by one by hand without teardown
# with copy pasting
export TESTPATH="/tmp/plonetool-test"

set -e # abort on error

set -x verbose #echo on

#
# return 0 if user exists
#
function has_user {
    getent passwd $1 > /dev/null
    return $?
}

#
# Clean up test installation from the server
#
function teardown {

    set +e
    # Make sure we have not old leftover processes reserving our ports
    pkill -f zeoserver
    pkill -f instance
    pkill -f client1
    has_user plone1 && userdel -r -f plone1
    has_user plone2 && userdel -r -f plone2
    rm /etc/init.d/migration-test > /dev/null 2>&1
    rm /etc/init.d/plone1 > /dev/null 2>&1
    rm /etc/init.d/plone2 > /dev/null 2>&1
    rm -rf $TESTPATH > /dev/null 2>&1
    set -e
}

teardown

install -d $TESTPATH

# First run unit tests
python -m unittest discover senorita.plonetool

plonetool --ploneversions

# Empty installation test
plonetool --create $TESTPATH/plone1 --user plone1
rm -rf $TESTPATH/plone1

# standalone install
plonetool --install --user plone1 --port 54001 $TESTPATH/plone1

# buildout fix
plonetool --fixbuildout $TESTPATH/plone1

# zeo cluster install
plonetool --install --mode cluster --port 54002 --user plone2 $TESTPATH/plone2

# Test migrate over SSH over a localhost loopback
# For ssh-add-id see https://github.com/miohtama/ztanesh/blob/master/zsh-scripts/bin/ssh-add-id
# Don't use SSH agent forwarding if one is set
eval `ssh-agent`
export SSH_AUTH_SOCK
ssh-enable-authorized-key plone2
plonetool --migrate --user plone1 $TESTPATH/migration-test plone2@localhost:$TESTPATH/plone2
rm -rf $TESTPATH/migration-test > /dev/null

# check command
plonetool --check $TESTPATH/plone1

plonetool --check $TESTPATH/plone2

# restartall command: start plone1, plone2
plonetool --restartall $TESTPATH

# stop all command
plonetool --stopall $TESTPATH

# Sett that double stop doesn't cause funny issues
plonetool --stopall $TESTPATH

teardown

echo "F*ck yeah it works"

