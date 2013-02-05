#!/bin/bash

set -e

if [ ! -z "$1" ]; then
        echo "" >> $1
        echo "{line}" >> $1
else
        export EDITOR=$0
        visudo
fi