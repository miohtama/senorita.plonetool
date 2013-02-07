#!/bin/zsh
#
# Test all script functionality.
# Note that running this command will pollute your server, so use
# discardable VM.
#
# Run under virtualenv
#


# Where we will install a lot of Plones
# Allow run tests one by one by hand without teardown
# with copy pasting
export TESTPATH="/tmp/plonetool-test"

set -e

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
    has_user senorita1 && userdel -r -f senorita1
    has_user senorita2 && userdel -r -f senorita2
    rm /etc/init.d/migration-test > /dev/null 2>&1
    rm /etc/init.d/senorita1 > /dev/null 2>&1
    rm /etc/init.d/senorita2 > /dev/null 2>&1
    rm -rf $TESTPATH > /dev/null 2>&1
    set -e
}

teardown

# First run unit tests
python -m unittest discover senorita.plonetool

plonetool --ploneversions

plonetool --create $TESTPATH/plone1 --user senorita1

# standalone install
plonetool --install --port 54001 $TESTPATH/senorita2

# buildout fix
plonetool --fixbuildout $TESTPATH/senorita2

# zeo cluster install
plonetool --install --mode cluster --port 54002 --user senorita2 $TESTPATH/senorita3

# migrate over ssh
# For ssh-add-id see https://github.com/miohtama/ztanesh/blob/master/zsh-scripts/bin/ssh-add-id
ssh-add-id senorita2
plonetool --migrate --user senorita11 $TESTPATH/migration-test senorita2@localhost:$TESTPATH/senorita2

# check command
plonetool --check $TESTPATH/plone1

# restartall command
plonetool --restartall $TESTPATH

# stop all command
plonetool --stopall $TESTPATH

teardown

echo "F*ck yeah it works"

