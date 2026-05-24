#!/usr/bin/env python3
"""Experimental indentation-based DOC frontend; lowers to the existing Rust kernel syntax."""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

IDENT = r"[A-Za-z_][A-Za-z_0-9]*"
SOURCE = re.compile(rf"source\s+({IDENT})\s*:\s*(int|bool)\s*=\s*(.+)\Z")
DERIVE = re.compile(rf"derive\s+({IDENT})\s*\(\s*([^()]*)\s*\)\s*:\s*(int|bool)\s*:\s*\Z")
LITERAL = re.compile(r"(?:-?[0-9]+|true|false)\Z")
EXPRESSION = re.compile(r"[A-Za-z_0-9(),\s-]+\Z")

class SyntaxErrorDOC(ValueError):
    pass

INTEGER_TOKEN = re.compile(r"(?<![A-Za-z_0-9])-?[0-9]+(?![A-Za-z_0-9])")

def check_i64_literal(literal: str, number: int) -> None:
    """Reject out-of-range integer tokens without converting huge decimal strings."""
    # Rust i64 parsing accepts leading zeroes, including very long zero-padded
    # literals. Compare only the significant digits, without int() conversion.
    digits = literal.lstrip('-').lstrip('0') or '0'
    limit = '9223372036854775808' if literal.startswith('-') else '9223372036854775807'
    if len(digits) > len(limit) or (len(digits) == len(limit) and digits > limit):
        raise SyntaxErrorDOC(f"line {number}: integer outside signed 64-bit range")

def lower(source: str) -> str:
    output = []
    names = set()
    pending = None
    for number, raw in enumerate(source.splitlines(), 1):
        if '\t' in raw:
            raise SyntaxErrorDOC(f"line {number}: tabs are not allowed")
        stripped = raw.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if '#' in raw:
            raw = raw.split('#', 1)[0].rstrip()
            stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip(' '))
        if pending is not None:
            name, kind, args, header_line = pending
            if indent != 4:
                raise SyntaxErrorDOC(f"line {number}: expected four-space expression body for line {header_line}")
            if not EXPRESSION.fullmatch(stripped):
                raise SyntaxErrorDOC(f"line {number}: unsupported expression characters")
            for integer in INTEGER_TOKEN.finditer(stripped):
                check_i64_literal(integer.group(), number)
            output.append(f"derive {name}: {kind} ({','.join(args)}) = {stripped}")
            pending = None
            continue
        if indent:
            raise SyntaxErrorDOC(f"line {number}: unexpected indentation")
        match = SOURCE.fullmatch(stripped)
        if match:
            name, kind, literal = match.groups()
            if name in names:
                raise SyntaxErrorDOC(f"line {number}: duplicate state {name}")
            if not LITERAL.fullmatch(literal.strip()):
                raise SyntaxErrorDOC(f"line {number}: source requires an int/bool literal")
            if (kind == 'bool') != (literal.strip() in ('true', 'false')):
                raise SyntaxErrorDOC(f"line {number}: source type mismatch")
            if kind == 'int':
                check_i64_literal(literal.strip(), number)
            names.add(name)
            output.append(f"source {name}: {kind} = {literal.strip()}")
            continue
        match = DERIVE.fullmatch(stripped)
        if match:
            name, args_text, kind = match.groups()
            if name in names:
                raise SyntaxErrorDOC(f"line {number}: duplicate state {name}")
            args = [a.strip() for a in args_text.split(',')] if args_text.strip() else []
            if any(not re.fullmatch(IDENT, a) for a in args) or len(args) != len(set(args)):
                raise SyntaxErrorDOC(f"line {number}: invalid or duplicate premise")
            if any(a not in names for a in args):
                raise SyntaxErrorDOC(f"line {number}: unknown or forward premise")
            names.add(name)
            pending = (name, kind, args, number)
            continue
        raise SyntaxErrorDOC(f"line {number}: expected source or derive declaration")
    if pending is not None:
        raise SyntaxErrorDOC(f"line {pending[3]}: missing indented expression body")
    return '\n'.join(output) + ('\n' if output else '')

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    parser.add_argument('--emit', action='store_true', help='print lowered legacy DOC text')
    parser.add_argument('--cargo-manifest', type=Path, default=Path(__file__).resolve().parents[1] / 'runtime-rust' / 'Cargo.toml')
    args, updates = parser.parse_known_args(argv)
    try:
        result = lower(args.file.read_text(encoding='utf-8'))
    except (OSError, SyntaxErrorDOC) as error:
        parser.error(str(error))
    if args.emit:
        if updates:
            parser.error('source updates require execution, not --emit')
        print(result, end='')
        return 0
    with tempfile.TemporaryDirectory(prefix='doc-') as temp:
        doc = Path(temp) / 'program.doc'
        doc.write_text(result, encoding='utf-8')
        command = ['cargo', 'run', '--quiet', '--manifest-path', str(args.cargo_manifest), '--bin', 'doc', '--', str(doc), *updates]
        try:
            return subprocess.run(command, check=False).returncode
        except FileNotFoundError:
            print('DOC: cargo not found; use --emit to inspect lowering', file=sys.stderr)
            return 127

if __name__ == '__main__':
    sys.exit(main())
