#!/bin/zsh
#
# Test all script functionality.
# Note that running this command will pollute your server, so use
# discardable VM.
#
# Run under virtualenv
#


# Where we will install a lot of Plones
TESTPATH="/tmp/plonetool-test"

set -e

#
# return 0 if user exists
#
function has_user {
    getent passwd $1
    return $?
}

function teardown {
    has_user senorita1 && userdel -r -f senorita1
    has_user senorita2 && userdel -r -f senorita2

    # Tear down
    set +e
    rm /etc/init.d/migration-test > /dev/null 2>&1
    rm /etc/init.d/senorita1 > /dev/null 2>&1
    rm /etc/init.d/senorita2 > /dev/null 2>&1
    rm -rf $TESTPATH > /dev/null 2>&1
    set -e
}

teardown

plonetool --ploneversions

plonetool --create $TESTPATH/plone1 --user senorita1

# standalone install
plonetool --install $TESTPATH/senorita2

# buildout fix
plonetool --fixbuildout $TESTPATH/senorita2

# zeo cluster install
plonetool --install --mode cluster --user senorita2 $TESTPATH/senorita3

# migrate over ssh
plonetool --migrate --user senorita11 $TESTPATH/migration-test senorita2@localhost:$TESTPATH/senorita2

# check command
plonetool --check tmp/plonetool-test/plone1

# restartall command
plonetool --restartall $TESTPATH

# stop all command
plonetool --stopall $TESTPATH

teardown()

echo "F*ck yeah it works"

