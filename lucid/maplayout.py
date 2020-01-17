import collections
import copy
import logging

from qtpy import QtWidgets, QtGui, QtCore

from . import maploader


logger = logging.getLogger(__name__)


class MapConnector(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFixedSize(1, 1)


class DiagramNode:
    def __init__(self, idx, shape, *, parent=None):
        self.positioned = False
        self.idx = idx
        self.shape = shape
        self.connections = collections.defaultdict(list)
        self.parent = parent
        self.widget = shape.widget
        if isinstance(shape, _GroupWrapper):
            logger.error(f'DiagramNode: {self} group is GroupWrapper')
            self.group = shape
        else:
            logger.error(f'DiagramNode: {self} group is NOT GroupWrapper')
            self.group = QtWidgets.QGraphicsItemGroup()

    def get_direction_to_child(self, node):
        for direction, nodes in self.connections.items():
            if node in nodes:
                return direction
        raise ValueError('not connected')

    def get_nodes(self):
        nodes_list = []
        for direction, nodes in self.connections.items():
            nodes_list.extend(nodes)

        return nodes_list

    def get_bounding_rect(self):
        x = self.shape.scenePos().x()
        y = self.shape.scenePos().y()
        w = self.widget().width()
        h = self.widget().height()
        rect = self.group.sceneBoundingRect()
        return x, y, w, h, rect.x(), rect.y(), rect.width(), rect.height()

    def walk_depth_first(self, visited=None):
        if visited is None:
            visited = []
        for direction, nodes in self.connections.items():
            for node in nodes:
                if node in visited:
                    continue
                visited.append(node)
                yield from node.walk_depth_first(visited)
        visited.append(self)
        yield self

    def __repr__(self):
        # return f'<{self.idx} {dict(self.connections)} >'
        return f'<{self.idx} >'


def build_tree(shapes, connections):
    nodes = {idx: DiagramNode(idx=idx, shape=shape)
             for idx, shape in shapes.items()
             }

    for node in nodes.values():
        for direction, idx in connections.get(node.idx, {}).items():
            node.connections[direction].append(nodes[idx])
            nodes[idx].parent = node

    root = [node for node in nodes.values()
            if node.parent is None]

    if len(root) != 1:
        raise ValueError(f'Not only one root? Found: {root}')

    return root[0]


def calculate_position(parent, node, direction, min_spacing, parent_to_node=True):
    p_x, p_y, p_w, p_h, p_g_x, p_g_y, p_g_w, p_g_h = parent.get_bounding_rect()
    n_x, n_y, n_w, n_h, n_g_x, n_g_y, n_g_w, n_g_h = node.get_bounding_rect()

    if parent_to_node:
        logger.debug('Connecting Parent %s to Node %s via %s.',
                     parent, node, maploader._INVERT_DIRECTION[direction])
    else:
        logger.debug('Connecting Node %s to Parent %s via %s.',
                     node, parent, direction)

    logger.debug(f'Parent\tx: {p_x}\ty: {p_y}\tw: {p_w}\th: {p_h}\t\tgx: {p_g_x}\tgy: {p_g_y}\tgw: {p_g_w}\tgh: {p_g_h}')
    logger.debug(f'Node\t\tx: {n_x}\ty: {n_y}\tw: {n_w}\th: {n_h}\t\tgx: {n_g_x}\tgy: {n_g_y}\tgw: {n_g_w}\tgh: {n_g_h}')

    spacing_x = 0
    spacing_y = 0

    if parent_to_node:
        # We invert direction because we are connecting the parent into the
        # node and not the opposite.
        # That is because we need less moving pieces by traversing the tree
        # in a depth first method.
        inv_dir = maploader._INVERT_DIRECTION[direction]

        x = n_x
        y = n_y
        if 'e' in inv_dir:
            spacing_x = n_g_w - n_w if n_g_x - n_x == 0 else 0

        elif 'w' in inv_dir:
            spacing_x = n_g_w - n_w if n_g_x - n_x != 0 else 0

        if 'n' in inv_dir or 's' in inv_dir:
            if 'e' in inv_dir:
                x += n_w + spacing_x + min_spacing
            elif 'w' in inv_dir:
                x += -min_spacing - spacing_x - p_w
            else:
                x += n_w / 2.0 - p_w / 2.0

            if 'n' in inv_dir:
                spacing_y = n_g_h - n_h if n_y != n_g_y else 0
                y += -min_spacing - spacing_y - p_h
            elif 's' in inv_dir:
                spacing_y = n_g_h - n_h if n_y == 0 else 0
                y += n_h + min_spacing + spacing_y
        elif 'e' in inv_dir:
            x += n_w + spacing_x + min_spacing
            y += n_h / 2.0 - p_h / 2.0
        elif 'w' in inv_dir:
            x += -min_spacing - spacing_x - p_w
            y += n_h / 2.0 - p_h / 2.0
    else:
        x = p_x
        y = p_y
        if 'n' in direction or 's' in direction:
            if 'e' in direction:
                x += p_w + min_spacing
            elif 'w' in direction:
                x += -min_spacing - n_w
            else:
                x += p_w / 2.0 - n_w / 2.0  # ?

            if 'n' in direction:
                y = n_y - min_spacing - spacing_y - p_h
            elif 's' in direction:
                y += p_h + min_spacing
        else:
            if 'e' in direction:
                x += p_w + min_spacing
                y += p_h / 2.0 - n_h / 2.0
            elif 'w' in direction:
                x += -min_spacing - n_w
                y += p_h / 2.0 - n_h / 2.0

    return x, y


def _wrap_get_bounding_rect(group, shape):
    x = shape.scenePos().x()
    y = shape.scenePos().y()
    w = shape.widget().width()
    h = shape.widget().height()
    rect = group.group.sceneBoundingRect()
    return x, y, w, h, rect.x(), rect.y(), rect.width(), rect.height()


def layout(scene, root, parent, min_spacing=30, visited=[]):
    import functools
    connections = dict()
    if parent in visited:
        return
    visited.append(parent)
    for node in parent.walk_depth_first():
        try:
            dir = parent.get_direction_to_child(node)
        except ValueError:
            continue
        child = list(node.walk_depth_first())
        if len(child) > 1:
            layout(scene, root, node, min_spacing, visited=visited)
        connections[dir] = node

    for dir, node in connections.items():
        if parent.positioned:
            if node.group not in scene.items():
                logger.warning(f'Layout - Node {node} group not in scene')
                scene.addItem(node.group)
                node.group.addToGroup(node.shape)
                scene.update()

            x = 0
            y = 0
            pg_rel_x = 0
            pg_rel_y = 0
            ng_rel_x = 0
            ng_rel_y = 0
            _parent = parent
            _node = node

            group_parent = False
            if isinstance(parent.group, _GroupWrapper):
                group_parent = True
                p_x, p_y, *_ = parent.get_bounding_rect()
                parent = parent.group.anchors[dir]
                parent.get_bounding_rect = functools.partial(
                    _wrap_get_bounding_rect, _parent, parent)
                pa_x, pa_y, *_ = parent.get_bounding_rect()
                pg_rel_x = 0
                pg_rel_y = 0

            if isinstance(node.group, _GroupWrapper):
                nx, ny, *_ = node.get_bounding_rect()
                node = node.group.anchors[dir]
                node.get_bounding_rect = functools.partial(
                    _wrap_get_bounding_rect, _node, node)
                na_x, na_y, *_ = node.get_bounding_rect()
                ng_rel_x = nx - na_x
                ng_rel_y = ny - na_y

            c_x, c_y = calculate_position(parent, node, dir, min_spacing, parent_to_node=False)
            logger.critical(f'Layout - Calculated Position: ({c_x}, {c_y}) - Parent Factors: ({pg_rel_x}, {pg_rel_y}) - Node Factors: ({ng_rel_x}, {ng_rel_y}) ')

            x = c_x + pg_rel_x + ng_rel_x
            y = c_y + pg_rel_y + ng_rel_y

            parent = _parent
            node = _node

            logger.debug(f'Layout - Position Node: {node} to Parent: {parent} via {dir} at x: {x} , y: {y}')
            node.group.setPos(x, y)
            scene.update()
            logger.info(f'Layout - Real Position Node: {node} is: x {node.shape.scenePos().x()}  , y: {node.shape.scenePos().y()} ')
            logger.info(f'Layout - Real Position Node: {node} is: x {node.group.scenePos().x()}  , y: {node.group.scenePos().y()} ')


        else:
            if parent.group not in scene.items():
                logger.warning(f'Layout - Parent {parent} group not in scene')
                scene.addItem(parent.group)
                parent.group.addToGroup(parent.shape)
                scene.update()

            x = 0
            y = 0
            pg_rel_x = 0
            pg_rel_y = 0
            ng_rel_x = 0
            ng_rel_y = 0
            _parent = parent
            _node = node

            group_parent = False
            if isinstance(parent.group, _GroupWrapper):
                group_parent = True
                p_x, p_y, *_ = parent.get_bounding_rect()
                parent = parent.group.anchors[dir]
                parent.get_bounding_rect = functools.partial(_wrap_get_bounding_rect, _parent, parent)
                pa_x, pa_y, *_ = parent.get_bounding_rect()
                pg_rel_x = p_x-pa_x
                pg_rel_y = p_y-pa_y

            if isinstance(node.group, _GroupWrapper):
                nx, ny, *_ = node.get_bounding_rect()
                node = node.group.anchors[dir]
                node.get_bounding_rect = functools.partial(_wrap_get_bounding_rect, _node, node)
                ng_rel_x = 0
                ng_rel_y = 0

            c_x, c_y = calculate_position(parent, node, dir, min_spacing, parent_to_node=True)

            logger.critical(f'Layout - Calculated Position: ({c_x}, {c_y}) - Parent Factors: ({pg_rel_x}, {pg_rel_y}) - Node Factors: ({ng_rel_x}, {ng_rel_y}) ')

            x = c_x + pg_rel_x + ng_rel_x
            y = c_y + pg_rel_y + ng_rel_y
            parent = _parent
            node = _node
            logger.debug(f'Layout - Position Parent: {parent} to Node: {node} via {dir} at x: {x} , y: {y}')
            parent.group.setPos(x, y)
            scene.update()
            logger.info(f'Layout - Real Position Parent: {parent} is: x {parent.shape.scenePos().x()}  , y: {parent.shape.scenePos().y()} ')
            logger.info(f'Layout - Real Position Parent: {parent} is: x {parent.group.scenePos().x()}  , y: {parent.group.scenePos().y()} ')

            parent.positioned = True

        for item in node.get_nodes():
            logger.warning(f'Layout - Adding to Parent ({parent}) Group: {item}')
            parent.group.addToGroup(item.shape)

        logger.warning(f'Layout - Adding to Parent ({parent}) Group: {node}')
        parent.group.addToGroup(node.shape)
        scene.update()


def connect_widgets(scene, parent, visited=[]):
    if parent in visited:
        return
    visited.append(parent)

    pen = QtGui.QPen(QtGui.QColor("deepskyblue"), 3)
    pen.setCapStyle(QtCore.Qt.RoundCap)
    pen.setJoinStyle(QtCore.Qt.RoundJoin)

    connections = dict()
    for node in parent.walk_depth_first():
        try:
            dir = parent.get_direction_to_child(node)
        except ValueError:
            continue
        child = list(node.walk_depth_first())
        if len(child) > 1:
            connect_widgets(scene, node, visited=visited)
        connections[dir] = node

    for direction, node in connections.items():
        logger.info(f'Connecting parent ({parent}) to node ({node})')
        logger.info(f'Parent Group: {parent.group} / node group: {node.group}')
        _parent = parent
        _node = node
        parent_shape = parent.shape
        node_shape = node.shape
        if isinstance(parent.group, _GroupWrapper):
            parent = parent.group.anchors[direction]
            parent_shape = parent
        if isinstance(node.group, _GroupWrapper):
            node = node.group.anchors[direction]
            node_shape = node

        p_w = parent.widget().width()
        p_h = parent.widget().height()

        n_w = node.widget().width()
        n_h = node.widget().height()

        offsets = {
            'n': (p_w/2.0, 0.0, n_w/2.0, n_h),
            's': (p_w/2.0, p_h, n_w/2.0, 0.0),
            'e': (p_w, p_h/2.0, 0.0, n_h/2.0),
            'w': (0.0, p_h/2.0, n_w, n_h/2.0),
            'nw': (0, 0, n_w, n_h),
            'ne': (p_w, 0, 0, n_h),
            'sw': (0, p_h, n_w, 0),
            'se': (p_w, p_h, 0, 0),
        }

        offset = offsets[direction]
        scene.addLine(
            QtCore.QLineF(
                parent_shape.scenePos().x() + offset[0],
                parent_shape.scenePos().y() + offset[1],
                node_shape.scenePos().x() + offset[2],
                node_shape.scenePos().y() + offset[3],
            ),
            pen
        )
        parent = _parent
        node = _node


def remove_groups(scene, parent, visited=[]):
    for _, nodes in parent.connections.items():
        for node in nodes:
            if node in visited:
                continue
            visited.append(node)
            remove_groups(scene, node, visited)
    scene.destroyItemGroup(parent.group)


def validate(scene, shapes):
    for idx, shape in shapes.items():
        collisions = [x for x in scene.collidingItems(shape)
                      if not isinstance(x, QtWidgets.QGraphicsLineItem)]
        if len(collisions) > 0:
            for c in collisions:
                logger.debug('Item: %s bumped with: %s', idx, c)
            return False
    return True


class _GroupWrapper(QtWidgets.QGraphicsItemGroup):
    _default_margins = QtCore.QMarginsF(0, 0, 0, 0)

    def __init__(self, name, scene, group, groupd, name_to_proxy):
        # rect = group.childrenBoundingRect() | group.boundingRect()

        super().__init__()
        self.name = name + "()"
        self.groupd = groupd
        self.anchors = {dir: name_to_proxy[name] for dir, name in groupd['anchors'].items()}
        logger.critical(f"Creating GroupWrapper {name} with anchors: {self.anchors} and extra: {groupd}")

        scene.addItem(self)

        self._proxies = {
            widget_name: name_to_proxy[widget_name]
            for widget_name, widget in groupd['widgets'].items()
        }

        # self.container = QtWidgets.QGraphicsRectItem()

        for widget_name, proxy in self._proxies.items():
            self.addToGroup(proxy)
            scene.update()

        # margins = self._default_margins

        # self.container.setPen(QtCore.Qt.red)
        # self.container.setRect(
        #     self.container.childrenBoundingRect().marginsAdded(margins)
        # )

        # self.addToGroup(self.container)
        # scene.update()
        # self.label = QtWidgets.QGraphicsSimpleTextItem(name, self.container)
        # self.label.setPen(QtCore.Qt.white)
        # self.label.setPos(self.sceneBoundingRect().topLeft())


        class _FakeWidget:
            def width(_):  # noqa
                bounding_rect = self.sceneBoundingRect()
                return bounding_rect.width()

            def height(_):  # noqa
                bounding_rect = self.sceneBoundingRect()
                return bounding_rect.height()

        self._widget = _FakeWidget()

    def __repr__(self):
        return f'<GroupWrapper {self.name}>'

    def widget(self):
        return self._widget

    def setPos(self, *args, **kwargs) -> None:
        super(_GroupWrapper, self).setPos(*args, **kwargs)
        sp = self.scenePos()
        x = sp.x()
        y = sp.y()
        # t = self.label.text()
        # t = t[:t.rfind('(')]
        # self.label.setText(f'{t} ({x}, {y})')



def layout_instantiated_map(scene, instantiated):
    merged_layout = copy.deepcopy(instantiated['merged_layout'])
    maploader._dereference_anchors(instantiated['groups'], merged_layout)
    name_to_widget = instantiated['name_to_widget']

    name_to_proxy = {name: scene.addWidget(widget)
                     for name, widget in name_to_widget.items()}

    group_trees = {}
    for group_name, group in instantiated['groups'].items():
        logger.debug('Building a tree for group: %s', group_name)
        widgets = group['widgets']
        anchors = group['anchors']

        tree_name_to_proxy = {
            widget_name: name_to_proxy[widget_name]
            for widget_name, widget in widgets.items()
        }

        root = build_tree(tree_name_to_proxy, group['layout'])
        group_trees[group_name] = root

        layout(scene, root, root)

    def graphics_item_from_group(group_name, group):
        groupd = instantiated['groups'][group_name]
        gw = _GroupWrapper(group_name, scene, group.group, groupd,
                           name_to_proxy)
        return gw

    top_level_items = {
        group_name: graphics_item_from_group(group_name, group)
        for group_name, group in group_trees.items()
    }
    for name, component in instantiated['components'].items():
        if name not in top_level_items:
            top_level_items[name] = name_to_proxy[name]

    logger.debug('Working on the top level tree: %s', top_level_items)

    logging.error('Instantiated Components: %s',instantiated['groups'])
    logging.error('Top Level Items: %s', top_level_items)
    logging.error('Top Level Layout: %s', instantiated['layout'])

    top_level_tree = build_tree(top_level_items, instantiated['layout'])

    logger.debug('Top level tree: %s', top_level_tree)
    layout(scene, top_level_tree, top_level_tree)
    logger.debug('Done with all groups + outer layout')

    connect_widgets(scene, top_level_tree)

    for name, root in group_trees.items():
        connect_widgets(scene, root)
