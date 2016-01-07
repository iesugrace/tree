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
        aclName    = acl_line.split(b';')[-3].decode().strip()
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

    def __init__(self, acls=[]):
        """
        self.data holds all unprocessed views.
        self.outData holds all ready-for-output views.
        self.outData['free'] holds all views that have
            no LESS or GREATER relationship with others.
        self.outData['ordered'] holds multiple lists,
            each list is a group of views which must be
            ordered. The key of this dictionary is the
            viewName of an arbitrary view in the list,
            the characters of the key does not matter,
            the uniqueness does.
        self.acls is the acl data the views will use.
        """
        self.data               = []
        self.outData            = {}
        self.outData['free']    = set()
        self.outData['ordered'] = {}
        self.acls               = acls

    def attachAclDb(self, acls):
        """ The acls is a dictionary, key is the
        acl name, value is the acl object.
        """
        self.acls = acls

    def load(self, dbFile, ignore_syntax=True):
        """ Load data from a database, the existing data of the group
        will be abandoned.
        """
        self.data = {}
        viewBlocks = self.preproc(dbFile)
        for block in viewBlocks:
            lines = block.split(b'\n')
            view_name = lines[0].split(b'"')[1].decode()
            n = self.locateLine(lines, b'^};')
            if n is None:
                raise InvalidViewConfigException
            lines = lines[1:n]
            parsed = View.parseConfig(lines)
            aclName = parsed[0]
            otherConfig = parsed[1]
            view = View(view_name, aclName, otherConfig)
            self.addView(view)

    def addView(self, begin_view, validator=None, args=None):
        """ Add the view to the group. Duplicate name of view
        will be ignored.
        """
        views = {begin_view.name: begin_view}
        while views:
            view_name = list(views.keys())[0]
            view_obj  = views.pop(view_name)
            try:
                if validator:
                    self.__addView(view_obj, validator, args)
                else:
                    self.__addView(view_obj)   # default validator
            except ViewExistsException as e:
                obj  = e.args[0]
                print('duplicate view: %s' % obj_name, file=sys.stderr)
            except NotCoexistsException as e:   # split and retry
                pass

    def __addView(self, obj, validator=None, vpargs=(), vkargs={}):
        if not validator:
            validator = self.defaultValidator
            vpargs    = (self.data,)
            vkargs    = {}
        validator(obj, *vpargs, **vkargs)  # may raise an exception
        self.data[obj.name] = obj
        return True

    def defaultValidator(self, view, group):
        """ Default validator of the ViewGroup
        Ensure unique view name in the group.
        """
        if view.name not in group:
            return True
        else:
            raise ViewExistsException(group[view.name])

    def locateLine(self, lines, pattern):
        """ Return the index number of the matching line
        None will be returned if none match.
        """
        n = None
        for idx, line in enumerate(lines):
            if re.search(pattern, line):
                n = idx
                break
        return n

    def preproc(self, dbFile):
        """ Process the dbFile, return a list of bytes,
        each bytes contains all config data of a view,
        without the leading 'view' keyword.
        """
        lines = open(dbFile, 'rb').read()
        lines = lines.split(b'\n')

        # remove all comment and empty lines above the first view
        # and remove the leading keyword 'view' of the first view
        n = self.locateLine(lines, b'^view\s')
        if n is None:
            raise InvalidViewConfigException
        lines[n] = re.sub(b'^view\s', b'', lines[n])
        lines   = lines[n:]
        rawData = b'\n'.join(lines)
        blocks  = re.split(b'\nview\s', rawData)
        return blocks

    def writeOneView(self, view, ofile):
        """ Format a code text for the view,
        and write it to the ofile.
        """
        linePrefix  = '    '
        viewName    = view.name
        aclName     = view.aclName
        otherConfig = view.otherConfig
        header      = 'view "%s" {\n' % viewName
        keyName     = aclName.lower()
        aclLine     = '%smatch-clients { key %s; %s; };\n' % (
                        linePrefix,
                        keyName,
                        aclName)
        tailer      = '};\n'
        ba          = bytearray()
        ba.extend(header.encode())
        ba.extend(aclLine.encode())
        ba.extend(b'\n'.join(otherConfig))  # a list of bytes objects
        ba.extend(b'\n')
        ba.extend(tailer.encode())
        ba.extend(b'\n')
        ofile.write(bytes(ba))

    def save(self, dbFile):
        """ Save the group data to a database file.
        Views with LESS acl shall be put in front of
        the one which is GREATER.
        """
        ofile = open(dbFile, 'wb')
        for viewList in self.outData['ordered'].values():
            for view in viewList:
                self.writeOneView(view, ofile)
        for view in self.outData['free']:
            self.writeOneView(view, ofile)

        ofile.seek(-1, 1)   # back one character for
        ofile.truncate()    # removing the last empty line
