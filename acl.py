"""
Author: Joshua Chen
Date: 2015-12-16
Location: Shenzhen
Desc: Application that makes use of the tree library
to maintain an ACL database.

"""
from lib import Leaf, Branch, TreeGroup

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
