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
    When we process the view config, only the view name
    and the related acl name is significant, othe config
    will be simply treated as 'rest of the config' and
    remain intact.
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
