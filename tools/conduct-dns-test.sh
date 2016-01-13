#!/bin/bash
# Author: Joshua Chen
# Date: 2016-01-13
# Location: Shenzhen
# Desc: run DNS query parallelly with a limited
#       number of queries at once, the purpose
#       to limit the number of parallel queries
#       is for avoiding been denied by the server.

runOneBlock() {
    srcFile=$1
    while read domain subnet view
    do
        dig @127.0.0.1 $domain +subnet=$subnet +time=3 &>/dev/null &
    done < $srcFile
    wait
}

if test $# -ne 1; then
    echo "Usage: $(basename $0) test-data" >&2
    exit 1
fi

file=$1
totalLines=$(wc -l < "$file")
startLine=1
blockSize=500

while test "$startLine" -le "$totalLines"
do
    tmpfile=$(mktemp)
    endLine=$((startLine + blockSize - 1))
    sed -n ${startLine},${endLine}p $file > $tmpfile
    echo "running for $startLine:$endLine"
    runOneBlock $tmpfile
    rm -f $tmpfile
    startLine=$((startLine + blockSize))
done
