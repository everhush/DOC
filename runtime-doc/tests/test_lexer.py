#!/usr/bin/env python3
"""Independent test oracle, not part of the DOC compiler or runtime."""
import argparse
import ast
import os
import re
import subprocess
import tempfile
from pathlib import Path

TOKEN = re.compile(rb'[ \t\r]+|\#[^\n]*|"[^"\r\n\\#]*"|[A-Za-z_][A-Za-z_0-9]*|[0-9]+|[\n:=(\)\[\],+\-./>]')


def oracle(data):
    data.decode('utf-8')
    tokens = []
    at = 0
    while at < len(data):
        match = TOKEN.match(data, at)
        if not match:
            raise ValueError(f'unsupported lexical byte at {at}')
        value = match.group()
        first = value[0]
        if first not in (9, 13, 32, 35):
            kind = 3 if first == 34 else 2 if 48 <= first <= 57 else 1 if (65 <= first <= 90 or 97 <= first <= 122 or first == 95) else first
            tokens.extend((kind, at, len(value)))
        at = match.end()
    return tokens


def run(command, values, workers, cwd, expected):
    argv = [*command, '--demand=tokens', 'input=[' + ','.join(map(str, values)) + ']']
    result = subprocess.run(argv, cwd=cwd, env={**os.environ, 'DOC_WORKERS': str(workers)}, text=True, capture_output=True, timeout=30)
    if expected is None:
        assert result.returncode != 0 and 'tokens:' not in result.stdout, (argv[:2], result.stdout, result.stderr)
        return
    assert result.returncode == 0, (argv[:2], result.stdout, result.stderr)
    records = [line.partition(': ')[2] for line in result.stdout.splitlines() if line.startswith('tokens: ')]
    assert len(records) == 1 and ast.literal_eval(records[0]) == expected, (argv[:2], values, result.stdout, expected)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--native', type=Path)
    parser.add_argument('--fixtures', type=Path, nargs='*', default=[])
    args = parser.parse_args()
    commands = [[str(args.reference.resolve()), str(args.source.resolve())]]
    if args.native:
        commands.append([str(args.native.resolve())])
    cases = [b'', b' # comment', b'\n\t\r\n', b'source x: int = -12\n', b'derive y: int (x) = add(x,1) # trailing\n', b'fn ident_2(a,b) = if(eq(a,b),-1,2)', b'source a: ints = [1,-2,+3]\n', b'""', 'source name: text = "你好 café"\n'.encode(), b'abc42 42abc\n', b'import data/name-v1.doc\n', b'native import close(i32) -> i32\n', b'a# comment\r\nb', b'"two words"# trailing']
    cases += [p.read_bytes() for p in args.fixtures]
    invalid = [list(b'"unterminated'), list(b'"a\nb"'), list(b'"a\\b"'), list(b'"a#b"'), list(b'@'), [255], [256], [-1], list('é'.encode())]
    with tempfile.TemporaryDirectory(prefix='doc11-lexer-source-free-') as cwd:
        for command in commands:
            for data in cases:
                expected = oracle(data)
                for workers in (1, 4):
                    run(command, list(data), workers, cwd, expected)
            for data in invalid:
                run(command, data, 1, cwd, None)
    print(f'DOC11_LEXER_PASS: {len(cases)} positive, {len(invalid)} negative, {len(commands)} execution paths, workers=1/4')


if __name__ == '__main__':
    main()
