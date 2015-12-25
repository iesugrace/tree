"""
Author: Joshua Chen
Date: 2015-12-16
Location: Shenzhen
Desc: Application that makes use of the tree library
to maintain an ACL database.

"""
from lib import *
import re
import sys

# decorator function
def addMoreInfo(c):
    class X(c):
        def __init__(self, *pargs, lineNumber=0, code=None, **kargs):
            c.__init__(self, *pargs, **kargs)
            self.lineNumber = lineNumber
            self.code       = code
    return X


@addMoreInfo
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


@addMoreInfo
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

    def load(self, dbFile):
        """ Load data from a database, the existing data of the group
        will be abandoned. Add in this manner: for each ACL, add all
        its networks to the group, and link all its networks with it,
        then add the ACL itself to the group. Exception may raised by
        Network class or Branch.addNode method during processing.

        Sample ACL database format:
            # comment
            acl "ACL_NAME" {
                ecs 114.213.144.0/20;
                ecs 114.213.160.0/19;
            };

        A line starts with # is a comment, will be ignored, a line
        contains 'acl' is the start of an acl definition, a network
        definition is of form 0.0.0.0/0, other lines will be ignored.
        """
        self.data = {}
        lines = open(dbFile, 'rb').readlines()
        acl = None
        for num, line in enumerate(lines, 1):
            # comment line
            if re.search(b'^\s*#', line):
                continue
            # acl line
            if b'acl' in line:
                if acl:
                    self.addAcl(acl)
                acl_name  = line.split(b'"')[1].decode()
                acl       = Acl(acl_name, lineNumber=num)
                continue
            # network line
            match = re.search(b'([0-9]+\.){3}[0-9]+/[0-9]+', line)
            if match:
                net_name = match.group(0).decode()
                net      = Network(net_name, lineNumber=num, code=net_name)
                if self.addNetwork(net):
                    acl.attachChild(net)
                continue
            # sub-acl line
            match = re.search(b'"(.*)"', line)
            if match:
                subacl_name = match.group(1).decode()
                subacl      = self.getNode(subacl_name)
                if subacl:
                    acl.attachChild(subacl)
                continue
        if acl:
            self.addAcl(acl)

    def addNetwork(self, net):
        """ Add the network to the group
        """
        try:
            self.addNode(net)   # use default validator
        except NodeExistsException as e:
            old_net  = e.args[0]
            old_info = '%s:%s' % (old_net.lineNumber, old_net.code)
            new_info = '%s:%s' % (net.lineNumber, net.code)
            msg      = 'duplicate net: %s <%s, %s>' % (net.name, old_info, new_info)
            print(msg, file=sys.stderr)
            return False
        else:
            return True

    def addAcl(self, acl):
        """ Add the acl to the group
        """
        try:
            self.addNode(acl, self.aclValidator, (self.data,))
        except NodeExistsException as e:
            obj  = e.args[0]
            offended_info = '%s:%s' % (obj.lineNumber, obj.name)
            print('duplicate acl: %s, %s:%s' %
                    (offended_info, acl.lineNumber, acl.name), file=sys.stderr)
        except NotCoexistsException as e:
            old_acl  = e.args[0]
            pairs    = e.args[1]
            new_net1 = pairs[0][0]
            new_net2 = pairs[1][0]
            old_net1 = pairs[0][1]
            old_net2 = pairs[1][1]
            old_info = '%s:%s <%s:%s, %s:%s>' % (
                        old_acl.lineNumber, old_acl.name,
                        old_net1.lineNumber, old_net1.code,
                        old_net2.lineNumber, old_net2.code,
                        )
            new_info = '%s:%s <%s:%s, %s:%s>' % (
                        acl.lineNumber, acl.name,
                        new_net1.lineNumber, new_net1.code,
                        new_net2.lineNumber, new_net2.code,
                        )
            msg =  'coexist problem: %s\n' % old_info
            msg += '                 %s' % new_info
            print(msg, file=sys.stderr)

    def save(self, dbFile):
        """ Save the group data to a database file.
        """
        # write to the acl database

    def aclValidator(self, new_acl, group):
        """ Check if the introduction of the node cause a violation of
        the AclGroup's Acl rule
        """
        TreeGroup.defaultValidator(self, new_acl, group) # ensure uniqe
        acl_group = [x for x in group.values() if isinstance(x, Acl)]
        for old_acl in acl_group:
            stat, pairs = self.coexist(new_acl, old_acl)
            if not stat:
                raise NotCoexistsException(old_acl, pairs)
        return True

    def coexist(self, acl1, acl2):
        """ Check if acl1 can coexist with acl2 in the same group.
        The rule is: if acl1.net1.compare(acl2.net1) yields a GREATER
        result, then all of the networks in acl1 shall not be LESS
        than any networks in acl2.
        """
        bad_relation = None
        rela_pairs   = []
        networks1    = acl1.networks()
        networks2    = acl2.networks()
        for net1 in networks1:
            for net2 in networks2:
                r = net1.compare(net2)
                if r == bad_relation:
                    rela_pairs.append((net1, net2))
                    return (False, rela_pairs)
                if r == Network.GREATER:
                    bad_relation = Network.LESS
                    rela_pairs.append((net1, net2))
                elif r == Network.LESS:
                    bad_relation = Network.GREATER
                    rela_pairs.append((net1, net2))
        return (True, None)
