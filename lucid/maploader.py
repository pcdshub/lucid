import logging
import yaml

logger = logging.getLogger(__name__)


_INVERT_DIRECTION = {
    'n': 's',
    'e': 'w',
    'w': 'e',
    's': 'n',
    'nw': 'se',
    'ne': 'sw',
    'sw': 'ne',
    'se': 'nw',
}


def _load_and_combine_layouts(layouts, valid_names):
    'Load a list of layouts and combine them into one main layout'
    if not isinstance(layouts, list):
        raise ValueError('Layout should be a list of dictionaries')

    layout = {}
    all_connections = {}
    connectors = set()

    for item in layouts:
        _load_single_layout(item, layout, all_connections, valid_names,
                            connectors)

    return layout, connectors


def _is_connector_name(name):
    'Is it a connector name?'
    return name.endswith('*')


def _load_single_layout(layoutd, layout, all_connections, valid_names,
                        connectors):
    'Load a single layout, making it into a directional list'
    if not isinstance(layoutd, dict):
        raise ValueError('Layout should be a dictionary')

    valid_keys = {'vertical', 'horizontal', 'directional', 'diagonal'}

    try:
        key, = list(layoutd)
    except ValueError:
        raise ValueError('Layout should only have only one key: {'
                         ', '.join(valid_keys) + '}')

    def check_connection(item, direction, new):
        try:
            already = all_connections[(item, direction)]
        except KeyError:
            ...
        else:
            raise ValueError(
                f'{item}/{direction} already connected to {already}.'
                f'Attempting to connect to {new}'
            )

    def connect(direction, items):
        try:
            inv_dir = _INVERT_DIRECTION[direction]
        except KeyError:
            raise ValueError(
                f'Invalid direction connecting {items}: {direction}')

        for itema, itemb in items:
            if _is_connector_name(itema):
                connectors.add(itema)
            elif itema not in valid_names:
                raise ValueError(f'Unexpected item name: {itema}')

            if _is_connector_name(itemb):
                connectors.add(itemb)
            elif itemb not in valid_names:
                raise ValueError(f'Unexpected item name: {itemb}')

            check_connection(itema, direction, itemb)
            check_connection(itemb, inv_dir, itema)

            if itema not in layout:
                layout[itema] = {}

            layout[itema][direction] = itemb

            all_connections[(itema, direction)] = itemb
            all_connections[(itemb, inv_dir)] = itema

    if 'vertical' in layoutd:
        connect('s', zip(layoutd['vertical'], layoutd['vertical'][1:]))
    elif 'horizontal' in layoutd:
        connect('e', zip(layoutd['horizontal'], layoutd['horizontal'][1:]))
    elif 'diagonal' in layoutd:
        # TODO - southeast?
        connect('se', zip(layoutd['diagonal'], layoutd['diagonal'][1:]))
    elif 'directional' in layoutd:
        directional = layoutd['directional']
        for itema, connections in directional.items():
            for direction, itemb in connections.items():
                connect(direction, [(itema, itemb)])

    return layout


def _load_map_component(name, componentd, groupd):
    'Load a single component with `name`, given its dictionary `componentd`'
    if groupd is not None and name in groupd:
        raise ValueError(
            f'Component name {name!r} clashes with existing group')

    if 'group' in componentd:
        main_key = 'group'
    elif 'class' in componentd:
        main_key = 'class'
    else:
        keys = ', '.join(componentd.keys())
        raise ValueError(f'Expected group or class in component dictionary; '
                         f'found only: {{{keys}}}')

    # TODO: verify names of class/group, properties
    properties = dict(componentd)
    return {
        main_key: properties.pop(main_key),  # group or class
        'macros': properties.pop('macros', {}),
        'properties': properties,
    }


def _make_components_from_connectors(connectors):
    'Make component dictionaries given an iterable of "connector*" names'
    return {
        connector: _load_map_component(
            connector, {'class': 'connector'}, None
        )
        for connector in connectors
    }


def _load_map_group(name, groupd):
    'Load a group given its name and dictionary'
    if not isinstance(groupd, dict):
        raise ValueError(f'Group should be a dictionary: {name}')

    keys = {'components', 'layout', 'macros', 'anchors'}
    other_keys = set(groupd) - keys
    if other_keys:
        raise ValueError(f'Found unexpected keys in group {name} {other_keys}')

    components = {
        name: _load_map_component(name, componentd, groupd)
        for name, componentd in groupd.get('components', {}).items()
    }

    layout, connectors = _load_and_combine_layouts(
        groupd['layout'], valid_names=set(components))

    components.update(_make_components_from_connectors(connectors))

    anchors = groupd.get('anchors', {})
    for anchor in anchors.values():
        if anchor not in components:
            raise ValueError(f'Unexpected anchor name: {anchor}')

    return dict(
        components=components,
        macros=groupd.get('macros', {}),
        layout=layout,
        anchors=anchors,
    )



def load_map_from_dict(mapd):
    'Load a maplayout from a dictionary'
    groups = {
        name: _load_map_group(name, groupd)
        for name, groupd in mapd.get('groups', {}).items()
    }

    components = {
        name: _load_map_component(name, componentd, mapd)
        for name, componentd in mapd.get('components', {}).items()
    }

    valid_names = set(components).union(set(groups))
    layout, connectors = _load_and_combine_layouts(mapd['layout'], valid_names)
    components.update(_make_components_from_connectors(connectors))

    logger.debug('groups: %s', groups)
    logger.debug('valid names: %s', valid_names)
    logger.debug('components: %s', components)
    logger.debug('layout: %s', layout)

    return dict(
        groups=groups,
        components=components,
        valid_names=valid_names,
        layout=layout
    )


def load_map(file):
    'Load a maplayout from a provided yaml file or file-like object'
    return load_map_from_dict(
        yaml.safe_load(file)
    )
