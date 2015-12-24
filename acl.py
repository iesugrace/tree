"""
Author: Joshua Chen
Date: 2015-12-16
Location: Shenzhen
Desc: Application that makes use of the tree library
to maintain an ACL database.

"""
from lib import *
import re

class Network(Leaf):
    """ Represents an IPv4 network
    """
    LESS        = -1
    EQUAL       = 0
    GREATER     = 1
    NOCOMMON    = 2

    def __init__(self, name):
        Leaf.__init__(self, name)
        net_pattern  = '^([0-9]+\.){3}[0-9]+/[0-9]+$'
        host_pattern = '^([0-9]+\.){3}[0-9]+$'
        if re.match(host_pattern, name):
            name = '%s/32' % name
        elif not re.match(net_pattern, name):
            raise InvalidNetworkException("unrecognized network: %s" % name)
        self.parseNetwork()

    def parseNetwork(self):
        """ Parse the given network, convert the 'net' to the actual network
        id thus 192.168.1.3/24 will be converted to 192.168.1.0/24, store
        the string representation of the network, and the integer form of the
        first ip and the last ip.
        """
        net        = self.name
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
        self.name = '%s/%s' % ('.'.join(netIdEle), maskLen)

    def compare(self, net):
        """ Compare self with the given network, return
        Network.LESS if self is covered by the net
        Network.GREATER if self covers the net
        Network.EQUAL if the two are the same
        Network.NOCOMMON if the two has no common portion
        """
        if self.firstInt == net.firstInt and self.lastInt == net.lastInt:
            return Network.EQUAL
        if self.firstInt >= net.firstInt and self.lastInt <= net.lastInt:
            return Network.LESS
        if self.firstInt <= net.firstInt and self.lastInt >= net.lastInt:
            return Network.GREATER
        return Network.NOCOMMON


class Acl(Branch):
    """ Represents an ACL. An ACL contains one or more networks.
    """
    def networks(self):
        """ Return a non-redundant list of networks of the ACL.
        """
        networks = self.leaves()
        nonredundant_nets = []
        reduced_networks = networks[:]
        for net1 in networks:
            # net1 may be removed from the reduced_networks in
            # the previous iteration, shall not process it again
            if net1 not in reduced_networks: continue

            reduced_networks.pop(0)
            inner_networks = reduced_networks[:]
            for net2 in inner_networks:
                r = net1.compare(net2)
                if r == Network.LESS:       # keep the greater
                    net1 = net2
                if r != Network.NOCOMMON:   # remove the processed
                    reduced_networks.remove(net2)
            nonredundant_nets.append(net1)
        return nonredundant_nets


class AclGroup(TreeGroup):
    """ All nodes in the group are unique in name. A single network
    can overlap another network inside an Acl, like 7.7.0.0/16 overlaps
    7.7.7.0/24, but this kind of overlap will be reduced by the Acl
    class's networks method. An acl likewise, can overlap another acl
    inside an Acl group, provided that it meets this condition:
    If acl1.net1.compare(acl2.net1) yields a GREATER result, then all of
    the networks in acl1 shall not be LESS than any networks in acl2.
    for instance:

        These two can coexist:
            aclA {192.168.1.0/24; 10.1.0.0/16;}
            aclB {192.168.0.0/16}

        These two can coexist:
            aclA {192.168.1.0/24; 10.1.0.0/16;}
            aclB {192.168.0.0/16; 172.16.1.0/24}

        These two can NOT coexist:
            aclA {192.168.1.0/24; 10.1.0.0/16;}
            aclB {192.168.0.0/16; 10.1.1.0/24;}

    Enforcing this overlaping rule is for avoiding the interleaving
    network reference in the DNS view config. To not violate this rule,
    in the view config, one view shall reference at most one acl thus
    give a chance for this class to validate the ACLs.
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

    def aclValidator(self, new_acl, group):
        """ Check if the introduction of the node cause a violation of
        the AclGroup's Acl rule
        """
        TreeGroup.defaultValidator(node, group) # ensure uniqe
        for old_acl in group.values():
            if not self.coexist(new_acl, old_acl):
                raise NotCoexistsException('%s with %s' % (new_acl.name, old_acl.name))
        return True

    def coexist(self, acl1, acl2):
        """ Check if acl1 can coexist with acl2 in the same group.
        The rule is: if acl1.net1.compare(acl2.net1) yields a GREATER
        result, then all of the networks in acl1 shall not be LESS
        than any networks in acl2.
        """
        bad_relation = None
        networks1    = acl1.networks()
        networks2    = acl2.networks()
        for net1 in networks1:
            for net2 in networks2:
                r = net1.compare(net2)
                if r == bad_relation:
                    return False
                if r == Network.GREATER:
                    bad_relation = Network.LESS
                elif r == Network.LESS:
                    bad_relation = Network.GREATER
        return True
