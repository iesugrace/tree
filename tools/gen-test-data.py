#!/usr/bin/env python3
"""
Author: Joshua Chen
Date: 2016-01-12
Location: Shenzhen
Desc: Create a file containing mapping
      of IP and view for view testing.
"""

import sys, os

progPath = os.path.realpath(__file__)
baseDir  = os.path.dirname(progPath)
libDir   = os.path.dirname(baseDir)
sys.path.insert(0, libDir)

from acl import *
from view import *

def generate(args):
    """ Check if all views can be ordered, check the acl if required
    """
    paths = args[:2]
    assert len(paths) == 2, "wrong arguments"

    viewPath, aclPath = paths
    ag = AclGroup()
    ag.load(aclPath, remove_conflict=False)
    vg = ViewGroup()
    vg.load(viewPath, resolveParts=False)
    acls   = ag.data
    views  = [x for x in vg.data if x.name != 'ANY']

    # collect the starting and ending IP
    # numbers of all networks in the group
    ipNums = []
    for view in views:
        acl      = acls[view.aclName]
        networks = acl.networks()
        for net in networks:
            ipNums.append(net.firstInt)
            ipNums.append(net.lastInt)

    allNets = [x for x in ag.data.values() if isinstance(x, Network)]
    seq = 0
    for ipNum in ipNums:
        coverNets = [x for x in allNets if x.firstInt <= ipNum <= x.lastInt]
        k = lambda net: int(net.name.split('/')[-1])
        coverNets.sort(key=k, reverse=True) # sort with netmask length
        net = coverNets[0]                  # get the longest netmask one
        topAcl = net.topParent()
        aclName = topAcl.name
        view = [x for x in vg.data if x.aclName == aclName][0]
        out(seq, numToIp(ipNum), view.name)
        seq += 1

def numToIp(number):
    """ Convert the number to an IPv4 address string
    """
    s      = bin(number)[2:]
    p4, s  = s[-8:], s[:-8]
    p3, s  = s[-8:], s[:-8]
    p2, p1 = s[-8:], s[:-8]
    return '%s.%s.%s.%s/32' % (
                int(p1, base=2),
                int(p2, base=2),
                int(p3, base=2),
                int(p4, base=2))

def out(seq, ip, viewName):
    suffix = 'abc.com'
    domain = '%s.%s' % (seq, suffix)
    text   = '%s %s %s' % (domain, ip, viewName)
    print(text)


def help():
    bname = os.path.basename(sys.argv[0])
    text = 'Usage: %s <view-file> <acl-file>' % bname
    print(text)


if __name__ == '__main__':
    args = sys.argv[1:]
    try:
        generate(args)
    except AssertionError as e:
        print(e, file=sys.stderr)
        help()
        exit(1)
    except Exception as e:
        text = str(e).split('] ')[-1]
        if not text:
            text = '-- no error message --'
        print(text, file=sys.stderr)
        help()
        exit(1)
    except KeyboardInterrupt:
        exit(1)
