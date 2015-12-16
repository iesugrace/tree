"""
Author: Joshua Chen
Date: 2015-12-16
Location: Shenzhen
Desc: Library for tree related works

"""
import Exception

class NotBranchException(Exception): pass
class NodeExistsException(Exception): pass
class NodeNotExistsException(Exception): pass
class NodeTakenException(Exception): pass
class NotChildException(Exception): pass

class Node:
    """ A tree element
    """
    parent   = None
    isBranch = False

    def __init__(self, name):
        self.name = name

    def setParent(self, newParent):
        """ Set the provided parent as the node's parent.
        Raise an exception if the parent is not a branch.
        """
        if not isinstance(newParent, Branch):
            raise NotBranchException
        if self.parent:
            self.parent.clearChildNodes()
        newParent.attachChild(self)

Leaf = Node


class Branch(Node):
    """ A tree element, of container type, consists of other branches or leaves.
    """
    childNodes = []

    def hasLeaf(self):
        """ Return true if there is any leaf reachable from the branch down.
        """

    def hasChild(self):
        """ Return true if there is any node directly under the branch.
        """

    def attachChild(self, node):
        """ Attach the given node to the branch if the node does not belong
        to any branch. Raise exception if the node belongs to a branch already.
        """
        if node.parent is not None:
            raise NodeTakenException
        self.childNodes.append(node)
        node.parent = self

    def detachChild(self, node):
        """ detach the given node from the branch.  Raise an exception
        if node doesn't exist, or it doesn't belong to the branch.
        """

    def clearChildNodes(self):
        """ Clear all child nodes.
        """
        for child in self.childNodes:
            child.parent = None
            self.childNodes.remove(child)

    def leaves(self):
        """ Return a list of all leaves under the branch or its sub-trees.
        """

    def contains(self, leaf):
        """ Return True if the leaf can be reached from the branch.
        """


class TreeGroup:
    """ Manager class that managing multiple trees.
    """

    def __init__(self):
        self.data = {}

    def addNode(self, node, validator=None, vpargs=(), vkargs={}):
        """ Add a node to the group, the validator takes the first argument
        as the node to be added, and any number of positional arguments
        and keyword arguments. The validator shall raise an exception if it
        fails to validate.
        """
        if not validator:
            validator = self.defaultValidator
            vpargs    = (self.data,)
            vkargs    = {}
        if validator(node, *vpargs, **vkargs):
            self.data[node] = None

    def defaultValidator(self, node, group):
        if node not in group:
            return True
        else:
            raise NodeExistsException

    def deleteNode(self, node):
        """ Delete the provided node from the group, raise an exception
        if the node is not found in the group.
        """

    def moveNode(self, node, parent):
        """ Move the provided node and put it under the new parent, raise
        and exception if either the node or parent does not exist, or the
        parent is not a branch.
        """

    def load(self, dbFile, parser):
        """ Load data from a database, the existing data of the group will
        be abandoned. Implemented by sub-class.
        """
        raise "sub class shall implement the load method"

    def save(self, dbFile):
        """ save the group data to a database file
        """
        raise "sub class shall implement the save method"
