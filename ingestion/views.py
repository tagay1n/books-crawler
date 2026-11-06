"""Bounded JSON previews with explicit omission locations."""
from itertools import islice


def bounded_view(value, *, omitted_keys=(), max_nodes=250):
    omissions = {}
    remaining = max_nodes

    def visit(item, path, depth):
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or depth > 5:
            omissions[path] = 'content omitted: preview budget'
            return None
        if isinstance(item, str):
            if len(item) > 500:
                omissions[path] = {'characters_omitted': len(item) - 500}
            return item[:500]
        if isinstance(item, dict):
            result = {}
            for key, child in item.items():
                location = f'{path}.{key}'
                if key in omitted_keys:
                    omissions[location] = 'history omitted'
                elif len(result) >= (50 if depth == 0 else 30) or remaining <= 0:
                    omissions[path] = {'fields_omitted': len(item) - len(result)}
                    break
                else:
                    result[key] = visit(child, location, depth + 1)
            return result
        if isinstance(item, list):
            result = []
            for index, child in enumerate(islice(item, 10)):
                if remaining <= 0:
                    break
                result.append(visit(child, f'{path}[{index}]', depth + 1))
            if len(result) < len(item):
                omissions[path] = {'items_omitted': len(item) - len(result)}
            return result
        return item

    result = visit(value, '$', 0)
    return result, omissions


def preview(value, *, omitted_keys=()):
    result, omissions = bounded_view(value, omitted_keys=omitted_keys)
    if omissions:
        result['_truncation'] = omissions
    return result
