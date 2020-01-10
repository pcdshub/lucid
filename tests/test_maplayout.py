import inspect
import pytest

from qtpy import QtCore, QtGui, QtWidgets

import lucid


class _TestBase:
    ...


class Test1(_TestBase):
    connections = {
        0: {'w': 1, 'e': 2, 'n': 3, 's': 4},
        1: {},
        2: {},
        3: {},
        4: {}
    }

    sizes = [(12, 3), (21, 3), (12, 6), (3, 3), (9, 3)]


class Test11(_TestBase):
    connections = {
        0: {'w': 1},
        1: {'n': 2, 's': 3},
        2: {},
        3: {}
    }

    # node = scene.create_node(MyDataModel)
    sizes = [(3, 3), (12, 6), (3, 3), (9, 3)]
    # sizes = [(12, 3), (3, 3), (3, 6), (3, 3), (9, 3), (3, 6), (3, 3)]
    # sizes = [(21, 3), (3, 3), (3, 6), (3, 3), (7, 3), (3, 6), (3, 3)]
    # sizes = [(12, 3), (3, 3), (3, 6), (3, 3), (9, 3), (3, 6), (3, 3)]
    # sizes = [(12, 3), (21, 3), (12, 6), (3, 3), (9, 3), (3, 6), (9, 3)]


class Test12(_TestBase):
    connections = {
        0: {'s': 1},
        1: {'w': 2},
        # 2: {}
        2: {'w': 3},
        3: {}
    }

    # node = scene.create_node(MyDataModel)
    sizes = [(3, 3), (3, 3), (3, 3), (3, 3)]
    # sizes = [(3, 3), (3, 3), (3, 3), (3, 3)]
    # sizes = [(12, 3), (3, 3), (3, 6), (3, 3), (9, 3), (3, 6), (3, 3)]
    # sizes = [(21, 3), (3, 3), (3, 6), (3, 3), (7, 3), (3, 6), (3, 3)]
    # sizes = [(12, 3), (3, 3), (3, 6), (3, 3), (9, 3), (3, 6), (3, 3)]
    # sizes = [(12, 3), (21, 3), (12, 6), (3, 3), (9, 3), (3, 6), (9, 3)]


class Test2(_TestBase):
    connections = {
        0: {'n': 1},
        1: {'e': 2},
        2: {'n': 3, 's': 4},
        3: {},
        4: {}
    }

    # node = scene.create_node(MyDataModel)
    # sizes = [(3, 3),(3, 3),(3, 3),(3, 3),(3, 3)]
    sizes = [(12, 3), (3, 3), (12, 6), (3, 3), (9, 3)]
    # sizes = [(12, 3), (3, 3), (3, 6), (3, 3), (9, 3), (3, 6), (3, 3)]
    # sizes = [(21, 3), (3, 3), (3, 6), (3, 3), (7, 3), (3, 6), (3, 3)]
    # sizes = [(12, 3), (3, 3), (3, 6), (3, 3), (9, 3), (3, 6), (3, 3)]
    # sizes = [(12, 3), (21, 3), (12, 6), (3, 3), (9, 3), (3, 6), (9, 3)]


class TestSquare(_TestBase):
    connections = {
        0: {'s': 1},
        1: {'w': 2},
        2: {'s': 3},
        3: {'e': 4},
        4: {}
    }
    sizes = [(3, 3),(3, 3),(3, 3),(3, 3), (3, 3)]

class TestKen(_TestBase):
    connections = {
        0: {'n': 1},
        1: {'e': 2},
        2: {'s': 3},
        3: {'w': 4},
        4: {'n': 5},
        5: {}
    }
    sizes = [(3, 3),(3, 3),(3, 3),(3, 3), (3, 3), (3, 3)]

class TestKen2(_TestBase):
    connections = {
        0: {'e': 1},
        1: {'s': 2},
        2: {'w': 3},
        3: {'s': 4},
        4: {'e': 5},
        5: {}
    }
    sizes = [(3, 3),(3, 3),(3, 3),(3, 3), (3, 3), (3, 3)]

class TestLoopConnection(_TestBase):
    connections = {
        0: {'n': 1},
        1: {'e': 2},
        2: {'n': 3},
        3: {'w': 4},
        4: {'s': 1}
    }
    sizes = [(3, 3),(3, 3),(3, 3),(3, 3), (3, 3)]


class TestIntercardinal(_TestBase):
    connections = {
        0: {'ne': 1},
        1: {'se': 2},
        2: {'sw': 3},
        3: {'nw': 4},
        4: {},
    }
    sizes = [(3, 3),(3, 3),(3, 3),(3, 3),(3, 3)]


def save_image(scene, view, fn, bg=QtCore.Qt.black):
    area = scene.itemsBoundingRect()
    image = QtGui.QImage(area.width(), area.height(), QtGui.QImage.Format_ARGB32_Premultiplied)
    image.fill(bg)
    painter = QtGui.QPainter(image)
    scene.render(painter, QtCore.QRectF(image.rect()), area)
    painter.end()
    image.save(fn)
    print(f'saved image to {fn}')


@pytest.mark.parametrize(
    'cls',
    [cls for name, cls in globals().items()
     if inspect.isclass(cls) and issubclass(cls, _TestBase) and
     cls is not _TestBase]
)
def test_layouts(qtbot, cls):
    print('test', cls)

    sizes = cls.sizes
    connections = cls.connections
    shapes = {
        idx: QtWidgets.QLabel(f'{idx}: {connections[idx]}')
        for idx in range(len(sizes))
    }

    scene = QtWidgets.QGraphicsScene()
    view = QtWidgets.QGraphicsView(scene)

    for size, (idx, shape) in zip(sizes, shapes.items()):
        # shape.setFixedSize(size[0] * 10, size[1] * 10)
        # shape.setStyleSheet(
        #     "border: 2px solid white; border-radius: 5px; background: transparent; color: red;")

        proxy = scene.addWidget(shape)
        shapes[idx] = proxy
        proxy.setPos(0, 0)

    root = lucid.maplayout.build_tree(shapes, connections)
    lucid.maplayout.layout(scene, root, root)
    lucid.maplayout.remove_groups(scene, root)
    assert lucid.maplayout.validate(scene, shapes)
    lucid.maplayout.connect_widgets(scene, root)

    save_image(scene, view, fn=f"tests/test_maplayout_{cls.__name__}.png")
