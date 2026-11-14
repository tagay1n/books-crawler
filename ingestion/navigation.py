"""Bounded source-code navigation without importing provider implementations."""
import ast
from pathlib import Path


def _definitions(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    definitions = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions[node.name] = node.lineno
            if isinstance(node, ast.ClassDef):
                for method in node.body:
                    if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        definitions[f'{node.name}.{method.name}'] = method.lineno
    return definitions


def symbol_map(root, paths, *, module=None, symbol=None):
    """Filter known source files and definitions before applying preview limits."""
    for label, value in (('--module', module), ('--symbol', symbol)):
        if value is not None and not value.strip():
            raise ValueError(f'{label} must not be empty')
    candidates = [(index, name) for index, name in enumerate(paths)
                  if module is None or module in {name, Path(name).name, Path(name).stem}]
    if module is not None and not candidates:
        raise ValueError(f'Unknown source module {module!r}. Allowed: {", ".join(Path(name).stem for name in paths)}')
    files, matched = [], 0
    # A symbol search must inspect all candidates to find matches beyond file cutoffs.
    selected = candidates if symbol is not None else candidates[:16]
    for index, name in selected:
        definitions = _definitions(root / name)
        if symbol is not None:
            definitions = {name: line for name, line in definitions.items() if symbol in name}
            if not definitions:
                continue
        matched += 1
        if len(files) >= 16:
            continue
        limit = 40 if index == 0 else 12
        files.append({'path': name, 'definitions': dict(list(definitions.items())[:limit]),
                      'definitions_omitted': max(0, len(definitions) - limit)})
    if symbol is None:
        matched = len(candidates)
    result = {'files': files, 'files_omitted': matched - len(files)}
    if module is not None or symbol is not None:
        result.update(filters={key: value for key, value in (('module', module), ('symbol', symbol))
                               if value is not None}, files_filtered=len(paths) - matched)
    return result
