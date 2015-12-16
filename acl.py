"""
Author: Joshua Chen
Date: 2015-12-16
Location: Shenzhen
Desc: Application that makes use of the tree library
to maintain an ACL database.

"""
from lib import Leaf, Branch, TreeGroup

class AclGroup(TreeGroup):
    """ All nodes in the group are unique in name, all networks
    are of Leaf type, no network shall overlap another.
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
