"""Shared JSONB projections for read-only status and inspection queries."""
from sqlalchemy import case, func


def object_fields(value, names):
    """Keep selected fields while preserving absent keys versus JSON null."""
    result = func.jsonb_build_object()
    for name in names:
        result = result.op('||')(case((value.bool_op('?')(name),
                                      func.jsonb_build_object(name, value.op('->')(name))),
                                     else_=func.jsonb_build_object()))
    return result


def latest_array(value):
    return case((func.jsonb_typeof(value) == 'array',
                 case((func.jsonb_array_length(value) > 0,
                       func.jsonb_build_array(value[-1])), else_=func.jsonb_build_array())),
                else_=func.jsonb_build_array())


def without_histories(value):
    """Replace history fields with placeholders for preview omission reporting."""
    result = value
    for name in ('observations', 'results', 'current_results'):
        result = result.op('-')(name)
        result = result.op('||')(case((value.bool_op('?')(name), func.jsonb_build_object(name, None)),
                                     else_=func.jsonb_build_object()))
    return case((func.jsonb_typeof(value) == 'object', result), else_=value)


def discovery_scan(value):
    return object_fields(value, ('id', 'started_at', 'pending_records', 'frontier'))
