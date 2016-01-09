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
            no LESS or GREATER relationship with others,
            the order of it does not matter.
        self.outData['ordered'] holds multiple lists,
            each list is a group of views which must be
            ordered. The order of the lists does not
            matter, but the order of views in each list
            does.
        self.acls is the acl data the views will use.
        """
        self.data               = []
        self.outData            = {}
        self.outData['free']    = []
        self.outData['ordered'] = []
        self.attachAclDb(acls)

    def attachAclDb(self, acls):
        """ Add the acl database for the ViewGroup to use
        The acls is a dictionary, the key is the acl name,
        and the value is the acl object. The view database
        usually make use of a preset acl named 'ANY' for
        default selection, here we ensure that acl exists.
        """
        anyName = 'ANY'
        if anyName not in acls:
            acls[anyName] = Acl(anyName)
        self.acls = acls

    def load(self, dbFile, ignore_syntax=True):
        """ Load data from a database, the existing data of the group
        will be abandoned.
        """
        self.data = []
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
        self.resolveViewsParts()

    def addView(self, view, validator=None, vpargs=(), vkargs={}):
        """ Add the view to the group. Duplicate name of view
        will be ignored.
        """
        if not validator:
            validator = self.defaultValidator
            vpargs    = (self.data,)
            vkargs    = {}
        try:
            validator(view, *vpargs, **vkargs)
        except ViewExistsException as e:
            view  = e.args[0]
            print('duplicate view: %s' % view.name, file=sys.stderr)
        else:
            self.data.append(view)
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
        for viewList in self.outData['ordered']:
            for view in viewList:
                self.writeOneView(view, ofile)
        for view in self.outData['free']:
            self.writeOneView(view, ofile)

    def resolveViewsParts(self):
        """ Find out all views whose acl is missing (been
        split), and find out all parts of that old acl,
        create a new view for each part of it.
        """
        views = [x for x in self.data if x.aclName not in self.acls]
        for view in views:
            newViews = self.resolveOneViewParts(view)
            if not newViews:
                print("%s's acl %s is missing" % (view.name, view.aclName),
                        file=sys.stderr)
            else:
                self.data.remove(view)
                self.data.extend(newViews)

    def resolveOneViewParts(self, view):
        """ A view's acl may be split into parts in a
        previous operation. This method finds out all
        new acls of the old one, and creates new views
        for each of these new acls, returns a list of
        the new views.

        If an acl been broken into parts, the name is
        changed like this:

            oldacl --> oldacl-0
                       oldacl-1 --> oldacl-1-0
                                    oldacl-1-1

        The new views have different name and aclName
        comparing to the old view, but the MySQL
        statement is identical, since these different
        views all use the same data in the database.

        This method shall not be call if the acl which
        the 'view' connects already exists in self.acls.
        """
        flag     = view.aclName + '-'
        names    = [x for x in self.acls if x.startswith(flag)]
        newViews = []
        if len(names) > 1:
            for aclName in names:
                newView = View(aclName, aclName, view.otherConfig)
                newViews.append(newView)
        return newViews

    def order(self):
        """ Sort all views in the group
        """
        views = list(self.data)
        self.enforceRules(views)
        for view in views:
            self.placeView(view)

    def placeView(self, begin_view, verbose=False):
        """ Place the view to an appropricate location,
        according to the order rule. On failure, split
        the view and its acl, and start over.
        """
        views = {begin_view.name: begin_view}
        while views:
            viewName = list(views.keys())[0]
            viewObj  = views.pop(viewName)
            if verbose:
                print("placing %s" % viewName)
            try:
                self.insertView(viewObj)
            except ViewOrderException as e:     # split and retry
                nets = e.args[0]
                oldAclName = viewObj.aclName    # get name befor split
                oldAcl0, oldAcl1 = Acl.splitTree(nets)
                self.acls.pop(oldAclName)       # remove the old name
                self.acls[oldAcl0.name] = oldAcl0
                self.acls[oldAcl1.name] = oldAcl1
                for suffix, aclName in [('-0', oldAcl0.name), ('-1', oldAcl1.name)]:
                    name        = viewName + suffix
                    newView     = View(name, aclName, viewObj.otherConfig)
                    views[name] = newView

    def insertView(self, newView):
        """ Find a good location in the self.outData, and
        insert the view into it.

        This is the core mechanism that ensures a logically
        correct view database. The rule is: IF ANY VIEW'S
        ACL OVERLAPS OTHER VIEW'S, THE VIEW OF THE LESS ACL
        SHALL BE PLACED FIRST, THEN THE GREATER ONE.

        If it's impossible to pick a location that complies
        to the order rule, raise an exception. It's possible
        that the exception raised halfway at which point
        some views may had already been moved from their
        original position, thus corrupt the view group, to
        prevent it, we make shallow copies of the groups,
        and process the copies, after all existing views had
        been processed, we update the view group with the
        processed copies.

        If a list in the orderedGroups has a view LESS or
        GREATER than the newView, the same will be deleted,
        all views in it will be moved to a new list. If a
        view in the freeViews group LESS or GREATER than
        the newView, the same will be moved to a new list.
        """
        freeViews     = list(self.outData['free'])
        orderedGroups = [list(l) for l in self.outData['ordered']]
        intactGroups  = []  # holds the view lists that have
                            # no relationship with the newView
        globalL       = []  # holds all views that LESS than the newView
        globalR       = []  # holds all views that GREATER than the newView
        newAcl        = self.acls[newView.aclName]

        # the free category
        lGroup    = []
        gGroup    = []
        for existView in freeViews:
            existAcl = self.acls[existView.aclName]
            rela     = existAcl.compare(newAcl)
            if rela == Acl.LESS:
                lGroup.append(existView)
            elif rela == Acl.GREATER:
                gGroup.append(existView)
        for v in (lGroup + gGroup):
            freeViews.remove(v)
        globalL.extend(lGroup)
        globalR.extend(gGroup)

        # the ordered category
        for viewList in orderedGroups:
            lessLen = 0
            lGroup  = []
            gGroup  = []
            for existView in viewList:
                existAcl = self.acls[existView.aclName]
                rela     = existAcl.compare(newAcl)
                if rela == Acl.LESS:
                    lessLen += 1
                elif rela == Acl.GREATER:
                    lGroup = viewList[:lessLen]
                    gGroup = viewList[lessLen:]
                else:
                    lessLen += 1
            # at this point, all views in the lGroup are
            # LESS than the newView (its acl actually), but
            # in the gGroup, only the first of it is GREATER
            # than the newView, all subsequent ones are
            # undetermined. The next step is to found out if
            # there is any view in the gGroup that is LESS
            # than the newView, in which case we will raise
            # an exception because the rule is violated.
            for existView in gGroup:
                existAcl = self.acls[existView.aclName]
                rela     = existAcl.compare(newAcl)
                if rela == Acl.LESS:
                    # attach the greater nets of the newAcl for split
                    nets = self.getNets(newAcl, existAcl, Network.GREATER)
                    raise ViewOrderException(nets)
            if len(lGroup) == 0 and len(gGroup) == 0:
                intactGroups.append(viewList)
            else:
                globalL.extend(lGroup)
                globalR.extend(gGroup)

        if len(globalL) == 0 and len(globalR) == 0:
            self.outData['free'].append(newView)
        else:
            self.outData['free'] = freeViews
            self.outData['ordered'] = []
            self.outData['ordered'].extend(intactGroups)
            newList = globalL + [newView] + globalR
            self.outData['ordered'].append(newList)

    def getNets(self, acl1, acl2, relation):
        """ Compare acl1 and acl2, and find all networks
        in acl1 that has 'relation' relationship with
        networks in acl2.
        """
        nets  = []
        nets1 = acl1.networks()
        nets2 = acl2.networks()
        for net1 in nets1:
            for net2 in nets2:
                if relation == net1.compare(net2):
                    nets.append(net1)
                    break
        return nets

    def enforceRules(self, views):
        """ Raise an exception if any violation detected
        Rules:
        - Only top acl can be referenced by a view,
          top acl is the one has no parent.
        """
        aclNames   = [x.aclName for x in views]
        aclObjects = [self.acls[x] for x in aclNames]
        m = [x for x in aclObjects if x.parent is not None]
        # zero length means no violation
        assert (len(m) == 0), "view config not complies with the rules"
