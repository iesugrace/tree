"""
Author: Joshua Chen
Date: 2015-12-30
Location: Shenzhen
Desc: Application that makes use of the acl library
to maintain a View database.

"""
from acl import *
import re
import sys

class View:
    """ Represents a view entry in the view database.
    """
    def __init__(self, name, data):
        """ data is bytes, name is str.
        """
        self.name      = name
        acl, data      = self.parseData(data)
        self.acl       = acl    # str
        self.otherData = data   # bytes

    def parseData(data):
        """ extract the ACL info from data, return
        the ACL name as a str, and the rest of the
        view config data as a list of bytes.
        """
        lines = data.rstrip('\n').split(b'\n')
        acl_line   = lines[0]
        rest_lines = lines[1:]
        acl        = acl_line.split(b';')[-3].decode()
        return (acl, rest_lines)


class ViewGroup:
    """
    """
