#!/bin/bash
# Author: Joshua Chen
# Date: 2016-01-13
# Location: Shenzhen
# Desc: compare the query log and the test data,
#       find out the unmatch log records.

if test $# -ne 2; then
    echo "Usage: $(basename $0) query-log test-data" >&2
    exit 1
fi

if test $(wc -l < $1) -ne $(wc -l < $2); then
    echo "record number of query-log and test-data don't match" >&2
    exit 1
fi

log=$1
theoryMap=$2
actualMap=$(mktemp)

# fetch mapping from the query log
cat $log | awk -F "[(): ]" '{print $12,$16}' | sort -n > $actualMap

# join the query log with the test data
joined=$(mktemp)
join $theoryMap $actualMap > $joined

# find out the unmatch
awk '{if ($NF != $(NF-1)) print $0}' $joined

# cleanup
rm -f $actualMap $joined
