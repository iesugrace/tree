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
        def __init__(self, *pargs, lineNumber=0, code=None, comment=None, **kargs):
            c.__init__(self, *pargs, **kargs)
            self.lineNumber = lineNumber
            self.code       = code
            self.comment    = comment
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
        An ACL of the following networks:

            192.168.1.0/24;
            192.168.0.0/16;

        shall produce a list of [192.168.0.0/16]
        """
        networks = self.leaves()
        uni_nets = self.uniqNets(networks)
        return uni_nets

    def directUniqNetworks(self):
        """ Return a non-redundant list of networks directly
        attached to the ACL.
        """
        networks = [x for x in self.childNodes if isinstance(x, Network)]
        uni_nets = self.uniqNets(networks)
        return uni_nets

    def uniqNets(self, networks):
        """ Remove the small networks which are covered
        by a larger one, these two networks

            192.168.1.0/24;
            192.168.0.0/16;

        shall produce a result of [192.168.0.0/16]
        """
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

    def removeRedundant(self):
        """ Remove the redundant networks in an ACL
        """
        uniqNets      = self.directUniqNetworks()
        directSubAcls = [x for x in self.childNodes if isinstance(x, Acl)]
        self.childNodes = directSubAcls + uniqNets


class AclDbFormat:
    """ Define the acceptable format of
    lines for the ACL database file.
    """
    COMMENT  = 1
    ACLSTART = 2
    ACLEND   = 3
    NETWORK  = 4
    SUBACL   = 5
    OTHER    = 6

    def match(self, line):
        """ Identify the type of the line
        """
        if re.search(b'^\s*#', line):
            self.matchData = None
            return self.COMMENT
        if b'acl' in line:
            self.matchData   = line.split(b'"')[1].decode()
            self.commentData = self.extractComment(line)
            return self.ACLSTART
        if line == b'};\n':
            self.matchData = None
            return self.ACLEND
        match = re.search(b'^\s*(ecs )?\s*(([0-9]+\.){3}[0-9]+/[0-9]+)', line)
        if match:
            self.matchData   = match.group(2).decode()
            self.commentData = self.extractComment(line)
            return self.NETWORK
        match = re.search(b'"(.*)"', line)
        if match:
            self.matchData = match.group(1).decode()
            return self.SUBACL
        return self.OTHER

    def extractComment(self, line):
        """ Extract the comment info. line is a bytes,
        return a bytes if there is any, or None.
        """
        i = line.find(b'#')
        if i > 0:
            return line[i:].rstrip(b'\n')
        else:
            return None


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

    def load(self, dbFile, ignore_syntax=True):
        """ Load data from a database, the existing data of the group
        will be abandoned. Add in this manner: for each ACL, add all
        its networks to the group, and link all its networks with it,
        then add the ACL itself to the group. Exception may raised by
        Network class or Branch.addNode method during processing.

        Sample ACL database format:
            # comment
            acl "sub_acl" {
                ecs 114.213.144.0/20;
                ecs 114.213.160.0/19;
            };
            acl "parent_acl" {
                "sub_acl";
            };
        A line starts with # is a comment, will be ignored, a line
        contains 'acl' is the start of an acl definition, a network
        definition is of form 0.0.0.0/0, sub acl's name must be
        quoted, other lines will be ignored.

        We delay the coexistent check after all the data are loaded,
        in order to preserve the relationship of acls, because the
        name of the acl will be changed when split it, thus break
        the link with its parent.
        """
        if not self.checkSyntax(dbFile) and not ignore_syntax:
            print('syntax error found in %s' % dbFile, file=sys.stderr)
            return False

        self.data = {}
        fmt       = AclDbFormat()
        lines     = open(dbFile, 'rb').readlines()
        acl       = None
        for num, line in enumerate(lines, 1):
            if fmt.match(line) == AclDbFormat.COMMENT:
                continue
            if fmt.match(line) == AclDbFormat.ACLSTART:
                if acl:
                    # remove redundant networks before adding
                    acl.removeRedundant()
                    self.addAcl(acl)
                acl_name = fmt.matchData
                cmnt     = fmt.commentData
                acl      = Acl(acl_name, lineNumber=num, comment=cmnt)
                continue
            if fmt.match(line) == AclDbFormat.NETWORK:
                net_name = fmt.matchData
                cmnt     = fmt.commentData
                net      = Network(net_name, lineNumber=num, code=net_name, comment=cmnt)
                if self.addNetwork(net):
                    acl.attachChild(net)
                continue
            if fmt.match(line) == AclDbFormat.SUBACL:
                subacl_name = fmt.matchData
                subacl      = self.getNode(subacl_name)
                if subacl:
                    acl.attachChild(subacl)
                continue
        if acl:
            # remove redundant networks before adding
            acl.removeRedundant()
            self.addAcl(acl)
        self.removeConflicts()

    def checkSyntax(self, dbFile):
        """ Check if all lines in dbFile conforms to the rules.
        Even the dbFile have no syntax error from DNS server's
        perspective, it may not fully conform to our rules.
        A network 119.120.121.0 is ok for DNS server, but we
        don't allow this, every network shall have a subnet
        suffix, like 119.120.121.0/24.
        """
        lines = open(dbFile, 'rb').readlines()
        fmt   = AclDbFormat()
        stat  = True
        for num, line in enumerate(lines, 1):
            if fmt.match(line) == AclDbFormat.OTHER:
                line = line.decode().rstrip('\n')
                print('error: %s:%s' % (num, line), file=sys.stderr)
                stat = False
        return stat

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

    def parentsOfNets(self, nets):
        """ Return a unique set of parents of networks
        """
        l = []
        for net in nets:
            l.extend(net.parents())
        return set(l)

    def addAcl(self, begin_acl, validator=None, args=None):
        """ Add the acl to the group. Duplicate name of acl
        will be ignored; for a NotCoexistsException exception,
        do a binary split to the parent acls of the networks
        which cause the problem, and try again to add the new
        set of ACLs. For optimazation, we split out the group
        of networks which creates less new Acls involves less
        operations.
        """
        acls = {begin_acl.name: begin_acl}
        while acls:
            acl_name = list(acls.keys())[0]
            acl_obj  = acls.pop(acl_name)
            try:
                if validator:
                    self.addNode(acl_obj, validator, args)
                else:
                    self.addNode(acl_obj)   # default validator
            except NodeExistsException as e:
                obj  = e.args[0]
                offended_info = '%s:%s' % (obj.lineNumber, obj_name)
                print('duplicate acl: %s, %s:%s' %
                        (offended_info, acl_obj.lineNumber, acl_name), file=sys.stderr)
            except NotCoexistsException as e:   # split and retry
                # pick the least acls/efforts nets
                less_rela, greater_rela = e.args[0]
                l_n_nets = set([x[0] for x in less_rela])   # nets of new acl in LESS group
                l_o_nets = set([x[1] for x in less_rela])   # nets of old acl in LESS group
                g_n_nets = set([x[0] for x in greater_rela])
                g_o_nets = set([x[1] for x in greater_rela])
                old_acl  = e.args[1]
                count_new = len(self.parentsOfNets(l_n_nets))   # parents of new acl
                count_old = len(self.parentsOfNets(l_o_nets))   # parents of old acl
                if count_new < count_old:
                    g = (acl_obj, l_n_nets, g_n_nets)
                else:
                    g = (old_acl, l_o_nets, g_o_nets)
                acl = g[0]
                net = g[1] if len(g[1]) < len(g[2]) else g[2]

                if acl == acl_obj: # split the new
                    new_acls = self.splitAclTree(acl, net)
                    for new_acl in new_acls:
                        acls[new_acl.name] = new_acl
                else:   # split the old
                    old_acl_name = acl.name # get name befor split
                    old_acl0, old_acl1 = self.splitAclTree(acl, net)
                    self.data.pop(old_acl_name)
                    self.data[old_acl0.name] = old_acl0
                    self.data[old_acl1.name] = old_acl1
                    acls[acl_name] = acl_obj

    def removeConflicts(self):
        """ Re-add all ACLs again to deal with the coexistent
        problem. Pass an acl validator for checking, and let
        self.addAcl do the work.
        """
        acls = [x for x in self.data.values()
                if isinstance(x, Acl) and not x.parent]
        self.data = {}
        for acl in acls:
            self.addAcl(acl, self.aclValidator, (self.data,))

    def splitAclTree(self, top_acl, nets):
        """ For every network in the 'nets', split all ACLs
        in the line from the network up to the 'top_acl'.

        Example: Split net1, net3, net5, net6 out.

        Before:                     After:

        net1──┐                     net2──C0──A0──┐
              │                                   │
        net2──C──A──┐               net4──D0──B0──┴─TOP0
                    │
        net3──┐     ├─TOP           net1──C1──A1──┬─TOP1
              │     │                             │
        net4──D──B──┤               net3──D1──B1──┤
              │     │                     │       │
        net5──┘     │               net5──┘       │
              net6──┘                       net6──┘

        """
        new_acls = {}
        res_acls = []
        for net in nets:
            node   = net
            parent = node.parent
            while True:         # split all parents up the line
                if len(parent.childNodes) == 1:
                    node   = parent
                    parent = node.parent
                    continue
                if parent.name[-2:] == '-0':
                    # when process another net in the same
                    # method call, branch1 may already be
                    # created when processed a previous net.
                    branch1_name = parent.name[:-1] + '1'
                    if branch1_name in new_acls:
                        new_acls[branch1_name].moveChild(node)
                        break
                # split
                branch1_name = parent.name + '-1'
                branch1 = Acl(branch1_name)
                branch1.moveChild(node)
                new_acls[branch1.name] = branch1 # another net may want it
                branch0_name = parent.name + '-0'
                parent.rename(branch0_name)
                branch0 = parent
                node   = branch1
                parent = branch0.parent
                if parent:
                    parent.attachChild(branch1)
                else:   # splitting hit the top, done
                    res_acls = [branch0, branch1]
                    break
        return res_acls

    def save(self, dbFile):
        """ Save the group data to a database file.
        for nested ACL, output the inner one, then
        the outer one.
        """
        def format_node(node):
            """ Format the node's data, return a bytes
            """
            text   = bytearray()
            prefix = '    '     # four spaces

            # header
            header = 'acl "%s" {' % node.name
            if node.comment:
                text.extend(header.encode() + b' ' +  node.comment + b'\n')
            else:
                text.extend(header.encode() + b'\n')

            # nested acls
            nested_acls = [x for x in node.childNodes if isinstance(x, Acl)]
            for acl in nested_acls:
                sub_text = '%s"%s";\n' % (prefix, acl.name)
                text.extend(sub_text.encode())

            # networks
            nets = [x for x in node.childNodes if isinstance(x, Network)]
            for net in nets:
                sub_text = '%s%s;' % (prefix, net.name)
                if net.comment:
                    text.extend(sub_text.encode() + b' ' +  net.comment + b'\n')
                else:
                    text.extend(sub_text.encode() + b'\n')

            # tail
            tail = '};\n'
            text.extend(tail.encode())

            return bytes(text)

        def format_acl(acl, queue):
            """ Store the acl and its nested child ACLs
            in a reverse order
            """
            text   = format_node(acl)
            queue.append(text)
            subacls = [x for x in acl.childNodes if isinstance(x, Acl)]
            for subacl in subacls:
                format_acl(subacl, queue)

        heads = [v for k, v in self.data.items() if not v.parent]
        ofile = open(dbFile, 'wb')
        for head in heads:
            queue = []
            format_acl(head, queue)
            lines = queue[::-1]
            ofile.writelines(lines)

    def aclValidator(self, new_acl, group):
        """ Check if the introduction of the
        new_acl causes a coexistent probjem.
        """
        acl_group = [x for x in group.values() if isinstance(x, Acl)]
        for old_acl in acl_group:
            stat, relations = self.coexist(new_acl, old_acl)
            if not stat:
                raise NotCoexistsException(relations, old_acl)
        return True

    def coexist(self, acl1, acl2):
        """ Check if acl1 can coexist with acl2 in the same group.
        The rule is: if acl1.net1.compare(acl2.net1) yields a GREATER
        result, then all of the networks in acl1 shall not be LESS
        than any networks in acl2. Return two relation lists.
        """
        l_rela    = []
        g_rela    = []
        networks1 = acl1.networks()
        networks2 = acl2.networks()
        for net1 in networks1:
            for net2 in networks2:
                r = net1.compare(net2)
                if r == Network.GREATER:
                    g_rela.append((net1, net2))
                elif r == Network.LESS:
                    l_rela.append((net1, net2))
        if len(l_rela) and len(g_rela):
            return (False, [l_rela, g_rela])
        else:
            return (True, None)
