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
    def __init__(self, name, config):
        """ data is bytes, name is str.
        """
        self.name        = name
        acl_name, rest   = self.parseData(config)
        self.acl_name    = acl_name   # str
        self.otherConfig = rest       # bytes

    def parseConfig(config):
        """ extract the ACL info from config, return
        the ACL name as a str, and the rest of the
        view config as a list of bytes.

        For this view config code in the view database:

        view "VIEW_NAME" {
            match-clients           { key key_name;ACL_NAME; };
            ...
            ... other view config lines
            ...
        };

        The 'config' will be these four lines:

            match-clients           { key key_name;ACL_NAME; };
            ...
            ... other view config lines
            ...

        """
        lines = config.rstrip('\n').split(b'\n')
        acl_line   = lines[0]
        rest_lines = lines[1:]
        acl_name   = acl_line.split(b';')[-3].decode()
        return (acl_name, rest_lines)


class ViewGroup:
    """
    """
