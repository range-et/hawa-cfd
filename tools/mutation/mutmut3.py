"""Run pinned mutmut 3.7.0 for one reviewed study and export its exact evidence.

Run with the Python 3.12 `.venv-dev` interpreter from inside a study's
disposable copy. mutmut 3 has no patch mode and names a mutant after the module
path of its file, so this launcher adds two things around the pinned release:

- `--scope FILE` limits mutation to the lines a JSON map ({path: [lines]})
  names; every other line, including whole files missing from the map, gets no
  mutant. `changed-lines` writes that map from a `git diff --no-prefix` patch.
- `--import-root DIR` names a directory that tests put on `sys.path` (such as
  `scripts`), so `scripts/device_smoke.py` is the module `device_smoke`, as the
  tests import it, and its mutated copy is imported before the original.

`export` writes every mutant's raw exit code and diff; `check_results.py` judges
them. Nothing here interprets an exit code as a kill.
"""
import argparse
import json
from pathlib import Path
import re
import sys

MUTMUT_VERSION = '3.7.0'
HUNK = re.compile(r'@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')


def changed_lines(patch):
    """Return {path: sorted new-side line numbers} that a `--no-prefix` unified diff adds."""
    lines, path, old_left, new_left, number = {}, None, 0, 0, 0
    for text in patch.splitlines():
        if old_left or new_left:
            if text.startswith('+'):
                lines.setdefault(path, set()).add(number)
                number, new_left = number + 1, new_left - 1
            elif text.startswith('-'):
                old_left -= 1
            elif text.startswith(' '):
                number, old_left, new_left = number + 1, old_left - 1, new_left - 1
            elif not text.startswith('\\'):
                raise ValueError('Truncated hunk in patch: ' + text)
        elif text.startswith('+++ '):
            path = text[4:].split('\t')[0]
        elif text.startswith('@@'):
            match = HUNK.match(text)
            if match is None or path is None:
                raise ValueError('Unreadable hunk header: ' + text)
            old_left = 1 if match.group(1) is None else int(match.group(1))
            number = int(match.group(2))
            new_left = 1 if match.group(3) is None else int(match.group(3))
    if old_left or new_left:
        raise ValueError('Patch ends inside a hunk')
    return {name: sorted(numbers) for name, numbers in lines.items()}


def module_name(path, import_roots):
    """Return the dotted module that tests import for a source path below an import root."""
    parts = Path(path).with_suffix('').parts
    # Reverse order tries a nested root (tools/mutation) before its parent (tools).
    for root in sorted((Path(r).parts for r in import_roots), reverse=True):
        if parts[:len(root)] == root and len(parts) > len(root):
            parts = parts[len(root):]
            break
    if parts[-1] == '__init__':
        parts = parts[:-1]
    return '.'.join(parts)


def install(main, file_mutation, import_roots, scope, mutated_files):
    """Patch the pinned mutmut modules for import roots and line scope."""
    def get_mutant_name(path, method):
        return module_name(path, import_roots) + '.' + method

    original_setup = main.setup_source_paths

    def setup_source_paths():
        original_setup()
        for root in import_roots:
            original = Path(root).resolve()
            sys.path[:] = [p for p in sys.path if Path(p).resolve() != original]
            sys.path.insert(0, str((Path('mutants')/root).absolute()))
        if scope is not None:
            unknown = set(scope) - set(mutated_files)
            if unknown:
                raise ValueError('Scope names files outside the mutated sources: '+', '.join(sorted(unknown)))
            main.mutmut._covered_lines = {
                str((Path('mutants')/name).absolute()): set(scope.get(name, ())) for name in mutated_files}

    main.get_mutant_name = file_mutation.get_mutant_name = get_mutant_name
    main.setup_source_paths = setup_source_paths


def export(main, data_type, directory):
    """Write mutants.json (raw exit code and diff per mutant) and the readable diffs."""
    rows = {}
    for path in main.walk_mutatable_files():
        data = data_type(path=path)
        data.load()
        for name, exit_code in data.exit_code_by_key.items():
            rows[name] = dict(path=str(path), exit_code=exit_code, diff=main.get_diff_for_mutant(name, path=path))
    directory = Path(directory)
    (directory/'mutants.json').write_text(json.dumps(rows, indent=1, sort_keys=True)+'\n')
    (directory/'mutations.diff').write_text(''.join(
        '# {} exit {}\n{}\n\n'.format(name, row['exit_code'], row['diff']) for name, row in sorted(rows.items())))
    return len(rows)


def load_mutmut():
    """Import the pinned mutmut release, refusing any other version."""
    import importlib.metadata
    if importlib.metadata.version('mutmut') != MUTMUT_VERSION:
        raise SystemExit('Install mutmut=='+MUTMUT_VERSION+' (the tools group in .venv-dev)')
    import mutmut.__main__ as main
    import mutmut.mutation.file_mutation as file_mutation
    from mutmut.mutation.data import SourceFileMutationData
    return main, file_mutation, SourceFileMutationData


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest='command', required=True)
    lines = commands.add_parser('changed-lines', help='write the scope map for a --no-prefix patch')
    lines.add_argument('patch', type=Path)
    lines.add_argument('output', type=Path)
    run = commands.add_parser('run', help='run mutmut in the current study directory')
    run.add_argument('--import-root', action='append', default=[])
    run.add_argument('--scope', type=Path)
    run.add_argument('--max-children', type=int, required=True)
    commands.add_parser('export', help='write mutants.json and mutations.diff here')
    args = parser.parse_args(argv)
    if args.command == 'changed-lines':
        scope = changed_lines(args.patch.read_text())
        args.output.write_text(json.dumps(scope, indent=1, sort_keys=True)+'\n')
        return 0
    mutmut_main, file_mutation, data_type = load_mutmut()
    mutmut_main.Config.ensure_loaded()
    mutated_files = [str(p) for p in mutmut_main.walk_mutatable_files()]
    if args.command == 'export':
        print(export(mutmut_main, data_type, '.'), 'mutants exported')
        return 0
    scope = None if args.scope is None else json.loads(args.scope.read_text())
    # mutmut itself treats src/ as an import root; keep that convention.
    install(mutmut_main, file_mutation, ['src'] + args.import_root, scope, mutated_files)
    return mutmut_main.cli(['run', '--max-children', str(args.max_children)], standalone_mode=False) or 0


if __name__ == '__main__':
    raise SystemExit(main())
