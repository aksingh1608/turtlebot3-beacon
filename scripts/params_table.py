#!/usr/bin/env python3
"""Print the Beacon parameter table as Markdown.

Run from the repo root:
    python3 scripts/params_table.py
"""

import os

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMS = os.path.join(REPO, 'beacon', 'config', 'params.yaml')


def fmt(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, float):
        return format(value, 'g')
    if isinstance(value, list):
        return '[' + ', '.join(fmt(item) for item in value) + ']'
    if value is None or value == '':
        return '""'
    return str(value)


def main():
    with open(PARAMS, 'r') as handle:
        data = yaml.safe_load(handle)
    print('| Parameter | Default | Section |')
    print('|---|---|---|')
    for section, body in data.items():
        values = body.get('ros__parameters', {})
        for name, value in values.items():
            print('| %s | %s | %s |' % (name, fmt(value), section))


if __name__ == '__main__':
    main()
