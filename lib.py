"""
Author: Joshua Chen
Date: 2015-12-16
Location: Shenzhen
Desc: Library for tree related works

"""
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

    def __repr__(self):
        return self.name

    def setParent(self, newParent):
        """ Set the provided parent as the node's parent.
        Raise an exception if the parent is not a branch.
        """
        if newParent.__class__ is not Branch:
            raise NotBranchException
        if self.parent:
            self.parent.clearChildNodes()
        newParent.attachChild(self)

Leaf = Node


class Branch(Node):
    """ A tree element, of container type, consists of other branches or leaves.
    """
    childNodes = []

    def walkTree(self, branch, collector):
        """ Walk the tree from the branch 'branch' down,
        process the nodes, return the result object
        """
        for child in branch.selfNodes:
            collector.process(child)
            if collector.done:
                break
            if child.__class__ is Branch:
                res = self.walkTree(child, collector)
                if collector.done:
                    break
        return collector

    def hasLeaf(self):
        """ Return true if there is any leaf reachable from the branch down.
        """
        class c(Collector):
            def __init__(self):
                self.result = False
            def process(self, node):
                if node.__class__ is Leaf:
                    self.result = True
                    self.done   = True

        return self.walkTree(self, c()).result

    def hasChild(self):
        """ Return true if there is any node directly under the branch.
        """
        return len(self.childNodes) > 0

    def attachChild(self, node):
        """ Attach the given node to the branch if the node does not belong
        to any branch. Raise exception if the node belongs to a branch already.
        """
        if node.parent is not None:
            raise NodeTakenException
        self.childNodes.append(node)
        node.parent = self

    def detachChild(self, node, sure=False):
        """ detach the given node from the branch. Raise an exception
        if node doesn't belong to the branch.
        """
        if not sure and node not in self.childNodes:
            raise NotChildException
        node.parent = None
        self.childNodes.remove(node)

    def clearChildNodes(self):
        """ Clear all child nodes.
        """
        for child in self.childNodes:
            self.detachChild(child, sure=True)

    def leaves(self):
        """ Return a list of all leaves under the branch or its sub-trees.
        """
        class c(Collector):
            def __init__(self):
                self.result = []
            def process(self, node):
                if node.__class__ is Leaf:
                    self.result.append(node)

        return self.walkTree(self, c()).result

    def covers(self, node):
        """ Return True if the node is reachable from the branch.
        In here, 'covered' means reachable, sub-classes may extend
        it to mean more.
        """
        class c(Collector):
            def __init__(self):
                self.result = False
            def process(self, inNode):
                if inNode is node:
                    self.result = True
                    self.done   = True

        return self.walkTree(self, c()).result


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
        """ Default validator, ensure all nodes in the group are unique.
        """
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
        """ Save the group data to a database file. Implemented by sub-class.
        """
        raise "sub class shall implement the save method"



class Collector:
    """ Record and return information
    """
    done   = False
    def process(self, obj):
        raise "sub class shall implement the process method"
