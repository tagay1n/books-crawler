"""Bounded source-code navigation without importing provider implementations."""
import ast


def symbol_map(root, paths):
    """Show adapter entry points and helper definitions, with explicit omissions."""
    files = []
    for index, name in enumerate(paths[:16]):
        tree = ast.parse((root / name).read_text(encoding='utf-8'))
        definitions = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                definitions[node.name] = node.lineno
                if isinstance(node, ast.ClassDef):
                    for method in node.body:
                        if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            definitions[f'{node.name}.{method.name}'] = method.lineno
        limit = 40 if index == 0 else 12
        files.append({'path': name, 'definitions': dict(list(definitions.items())[:limit]),
                      'definitions_omitted': max(0, len(definitions) - limit)})
    return {'files': files, 'files_omitted': max(0, len(paths) - len(files))}
