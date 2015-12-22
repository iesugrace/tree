"""
Author: Joshua Chen
Date: 2015-12-16
Location: Shenzhen
Desc: Application that makes use of the tree library
to maintain an ACL database.

"""
from lib import Leaf, Branch, TreeGroup
import re

class Network:
    """ Represents an IPv4 network
    """
    def __init__(self, net):
        net_pattern  = '^([0-9]+\.){3}[0-9]+/[0-9]+$'
        host_pattern = '^([0-9]+\.){3}[0-9]+$'
        if re.match(host_pattern, net):
            net = '%s/32' % net
        elif not re.match(net_pattern, net):
            raise Exception("unrecognized network: %s" % net)
        self.parseNetwork(net)

    def parseNetwork(self, net):
        """ Parse the given network, convert the 'net' to the actual network
        id thus 192.168.1.3/24 will be converted to 192.168.1.0/24, store
        the string representation of the network, and the integer form of the
        first ip and the last ip.
        """
        parts      = net.split('/')
        numbers    = parts[0].split('.')
        binNumbers = ['%08d' % int(bin(int(n))[2:]) for n in numbers]
        binNumStr  = ''.join(binNumbers)
        maskLen    = int(parts[1])
        netPartStr = binNumStr[:maskLen]
        padCount   = 32 - maskLen
        firstIpBin = netPartStr + '0' * padCount
        lastIpBin  = netPartStr + '1' * padCount
        self.firstInt = int(firstIpBin, base=2)
        self.lastInt  = int(lastIpBin, base=2)
        netIdStr = firstIpBin
        netIdEle = []
        while netIdStr:
            s, netIdStr = netIdStr[:8], netIdStr[8:]
            netIdEle.append(str(int(s, base=2)))
        self.net = '%s/%s' % ('.'.join(netIdEle), maskLen)


class Acl(Branch):
    """ Represents an ACL. An ACL contains one or more networks.
    """

class AclGroup(TreeGroup):
    """ All nodes in the group are unique in name, all networks
    in the acl are of Leaf type. A single network can overlap another
    network, like 7.7.0.0/16 overlaps 7.7.7.0/24. An acl likewise,
    can overlap another acl, provided that it meets this condition:
    if a network of the first acl covers a network of the other acl,
    then no network of the first acl shall be covered by any network
    of the second acl.

    This pair is GOOD:
        aclA {192.168.1.0/24; 10.1.0.0/16;}
        aclB {192.168.0.0/16}

    This pair is GOOD:
        aclA {192.168.1.0/24; 10.1.0.0/16;}
        aclB {192.168.0.0/16; 172.16.1.0/24}

    This pair is BAD:
        aclA {192.168.1.0/24; 10.1.0.0/16;}
        aclB {192.168.0.0/16; 10.1.1.0/24;}

    Enforcing this overlaping rule is for avoiding the interleaving
    network reference in the DNS view config. To not violating this
    rule, in the view config, one view shall reference at most one acl
    thus give a chance for this class to validate the ACLs.
    """

    def load(self, dbFile, parser):
        """ Load data from a database, the existing data of the group will
        be abandoned.
        """
        # parse the acl database

    def save(self, dbFile):
        """ Save the group data to a database file.
        """
        # write to the acl database

    def defaultValidator(self, node, group):
        """ Add network range check, ensure no-overlap for all networks.
        """
        if TreeGroup.defaultValidator(node, group):
            # check network range
            ...
        else:
            return False
