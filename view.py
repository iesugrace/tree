"""
Author: Joshua Chen
Date: 2015-12-30
Location: Shenzhen
Desc: Application that makes use of the acl library
to maintain a View database.

"""
from lib import *
from acl import *
import re
import sys

class View:
    """ Represents a view entry in the view database.
    When we process the view config, only the view name
    and the related acl name is significant, othe config
    will be simply treated as 'other config' and
    remain intact.
    """
    def __init__(self, name, aclName, otherConfig):
        """ name and aclName are str, otherConfig is bytes
        """
        self.name        = name
        self.aclName     = aclName      # str
        self.otherConfig = otherConfig  # bytes

    @staticmethod
    def parseConfig(lines):
        """ extract the ACL info from the config lines which
        is a list of bytes, return the ACL name as a str,
        and the rest of the view config as a list of bytes.
        The line which contains the ACL info shall be the
        first line of the 'lines'

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
        acl_line   = lines[0]
        if not re.match(b'\s*match-clients\s', acl_line):
            raise InvalidViewConfigException
        rest_lines = lines[1:]
        aclName    = acl_line.split(b';')[-3].decode()
        return (aclName, rest_lines)


class ViewGroup:
    """ All views in the group are unique in name. The acl of one
    view can overlap the one of another view, provided the view
    of the LESS acl be placed first.
    for instance:

        view1 -- acl1 -- {192.168.0.0/16;}
        view2 -- acl2 -- {192.168.1.0/24; 10.1.0.0/16;}

        view2 MUST be placed in front of view1 in the
        database, because acl2 is LESS that acl1.

    But the relationship may be more complex when these
    three are putting together in the same view database:

        view1 -- acl1 -- {192.168.1.0/24; 10.1.0.0/16;}
        view2 -- acl2 -- {192.168.0.0/16; 172.16.1.0/24;}
        view3 -- acl3 -- {172.16.0.0/16; 10.1.1.0/24}

        The relationship is: acl1 < acl2 < acl3 < acl1. It's a loop
        here, which can not satisfy the 'LESS first' rule.
        To deal with this problem, we separate acl3 and view3.

    In the ViewGroup, all views are organized in two categories:

        1. Free views
            In this category, acl of any view doesn't have common
            part with any other view in the whole ViewGroup. One
            dictionary or set is well suited for holding all these
            kind of views of a single ViewGroup.
        2. Ordered views
            If a view's acl is LESS or GREATER than another view's,
            these two views are put in a list which is ordered,
            LESS acl first. A ViewGroup may contain multiple such
            ordered lists, order is only matter within a list, not
            between lists, so a list can be placed before or after
            another.
    """
