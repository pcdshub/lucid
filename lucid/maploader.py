import importlib
import logging
import string
import sys

import qtpy
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


def _replace_macros_in_value(initial_value, macros):
    'Recursively evaluate macros in `initial_value`'
    current = string.Template(str(initial_value))
    previous = string.Template("")

    for i in range(100):
        value = current.safe_substitute(macros)
        if current.template == previous.template:
            break

        previous = current
        current = string.Template(value)
    else:
        logger.warning('Excessive macro recursion found in string: %s',
                       initial_value)

    return value


def _combine_macros(*mdicts):
    'Combine macro dictionaries, ordered by least-to-most specific'
    result = {}
    for d in mdicts:
        result.update(d)
    return result


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
            connector, {'class': 'lucid.maplayout.MapConnector'}, None
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



def _load_map_from_dict(mapd):
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


def _load_class_by_name(classname):
    'Get a class object by name'
    if '.' in classname:
        module_name, classname = classname.rsplit('.', 1)
        module = importlib.import_module(module_name)
    else:
        module = qtpy.QtWidgets

    return getattr(module, classname)


def _add_prefix(prefix, s):
    return f'{prefix}.{s}' if prefix else s


def _prefixed_layout(layout, prefix):
    'Add a prefix to all device names in a layout'

    return {
        _add_prefix(prefix, dev): {
            direction: _add_prefix(prefix, dev2)
            for direction, dev2 in values.items()
        }
        for dev, values in layout.items()
    }


def _instantiate_group(name, groups, group_name, component_macros):
    'Instantiate a component group given macros'
    groupd = groups[group_name]
    macros = _combine_macros(groupd['macros'], component_macros)

    # TODO: should this really be possible... ?
    group_name = _replace_macros_in_value(group_name, macros)

    components = groupd['components']
    result = {}
    for component_name in components:
        logger.debug('Instantiating component %s of group %s', component_name,
                     group_name)
        prefixed_name = _add_prefix(name, component_name)
        result[prefixed_name] = instantiate(component_name, groups, components,
                                            macros=macros, prefix=name)

    return dict(type='group', components=result,
                layout=_prefixed_layout(groupd['layout'], name)
                )


def _instantiate_component(name, classname, properties, macros):
    classname = _replace_macros_in_value(classname, macros)
    cls = _load_class_by_name(classname)
    instance = cls()
    instance.setObjectName(name.replace('*', '_'))

    properties = {_replace_macros_in_value(prop_name, macros):
                  _replace_macros_in_value(value, macros)
                  for prop_name, value in properties.items()}

    for prop_name, value in properties.items():
        prop = getattr(cls, prop_name)
        if callable(prop) and not isinstance(prop, qtpy.QtCore.Property):
            logger.debug('Calling set method: %s.%s(%s)',
                         classname, prop_name, value)
            setter = getattr(cls, prop_name)
            setter(instance, value)
        else:
            logger.debug('Setting property: %s.%s = %s',
                         classname, prop_name, value)
            setattr(instance, prop_name, value)

    logger.debug('Instantiated class %s -> %s (properties=%s)',
                 classname, instance, properties)
    return dict(type='component', instance=instance, properties=properties)


def instantiate(name, groups, components, *, macros=None, prefix=''):
    'Instantiate a group or component, given a name'
    componentd = components[name]
    try:
        full_name = f'{prefix}.{name}' if prefix else name
        macros = _combine_macros(macros or {}, componentd['macros'])
        logger.debug('Instantiate %s (%s) (macros=%s)', full_name, name,
                     macros)
        if 'group' in componentd:
            return _instantiate_group(full_name, groups, componentd['group'],
                                      component_macros=macros)
        if 'class' in componentd:
            return _instantiate_component(full_name, componentd['class'],
                                          properties=componentd['properties'],
                                          macros=macros)
    except Exception as ex:
        raise RuntimeError(
            f'Error while instantiating component {name!r}: {ex}'
        ) from ex
    raise ValueError(f'Unknown group/component name: {name!r}')


def merge_layout(layout, other):
    'In-place merge `other` into `layout`'
    collisions = set(layout).intersection(other)

    # new items
    layout.update({key: other[key] for key in set(other) - collisions})

    for name in collisions:
        for key in other:
            assert key not in layout[name]
        layout[name].update(other[name])


def _get_component_to_widget_dict(components):
    res = {}
    for name, componentd in components.items():
        if componentd['type'] == 'group':
            res.update(_get_component_to_widget_dict(componentd['components']))
        else:
            res[name] = componentd['instance']

    return res


def instantiate_map(groups, components, valid_names, layout, *, macros=None,
                    prefix=''):
    results = {}
    macros = macros or {}
    merged_layout = {}
    for component in components:
        logger.debug('Instantiating top-level map component: %s ', component)
        res = instantiate(component, groups, components, macros=macros,
                          prefix=prefix)
        results[_add_prefix(prefix, component)] = res
        if 'layout' in res:
            merge_layout(merged_layout, res['layout'])

    merge_layout(merged_layout, layout)
    return dict(merged_layout=merged_layout,
                layout=_prefixed_layout(layout, prefix),
                components=components,
                name_to_widget=_get_component_to_widget_dict(results),
                )


def load_map(file):
    'Load a maplayout from a provided yaml file or file-like object'
    return _load_map_from_dict(
        yaml.safe_load(file)
    )
