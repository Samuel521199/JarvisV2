"""The pure-tool recipe's static gate must not hand candidates a route to os/sys.

The LPAC worker remains the real boundary; this gate is defence in depth and
should reject the known stdlib escape hatches before anything is executed.
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.release_recovery.packages import MODULE_ESCAPES, validate_candidate
from sdk.protocol import CoreError


def candidate(source):
    return {'schema': 'jarvis.code-candidate.v1', 'summary': 'probe', 'files': [{'path': 'main.py', 'content': source}]}


ESCAPES = {
    'vars_private_alias': "import collections\ndef run(text):\n    return str(vars(collections)['_sys'].modules['os'])",
    'private_attribute': "import collections\ndef run(text):\n    return str(collections._sys.modules['os'])",
    'statistics_sys': "import statistics\ndef run(text):\n    return str(statistics.sys.modules['os'])",
    'from_statistics_import_sys': "from statistics import sys\ndef run(text):\n    return str(sys.modules['os'])",
    'json_codecs_builtins': "import json\ndef run(text):\n    return str(json.codecs.builtins)",
    'formatter_get_field': "import string, statistics\ndef run(text):\n    return str(string.Formatter().get_field('0.sys', (statistics,), {})[0])",
    'csv_types': "import csv\ndef run(text):\n    return str(csv.types.FunctionType)",
    'star_import': "from statistics import *\ndef run(text):\n    return text",
    'help_imports_modules': "def run(text):\n    help('os')\n    return text",
    'dir_probe': "import re\ndef run(text):\n    return str(dir(re))",
    'formatter_subclass_hook': ("import string, statistics\nclass F(string.Formatter):\n    def format_field(self, value, spec):\n"
                                "        self.got = value\n        return ''\ndef run(text):\n    f = F()\n    f.format('{0.sys}', statistics)\n"
                                "    return str(f.got.modules)"),
    'from_string_import_formatter': "from string import Formatter\ndef run(text):\n    return Formatter().format('{0}', text)",
}


class CandidateValidation(unittest.TestCase):
    def test_known_stdlib_escape_routes_are_rejected(self):
        for label, source in ESCAPES.items():
            with self.subTest(label), self.assertRaises(CoreError):
                validate_candidate(candidate(source))

    def test_escape_names_are_derived_from_the_interpreter(self):
        self.assertTrue({'sys', 'codecs', 'types'} <= MODULE_ESCAPES)
        self.assertNotIn('abc', MODULE_ESCAPES)

    def test_ordinary_pure_text_tools_still_pass(self):
        source = ("import collections, json, re, statistics, string\nfrom collections.abc import Mapping\n"
                  "def run(text):\n    words = re.findall(r'\\w+', text)\n    counts = collections.Counter(words)\n"
                  "    mean = statistics.fmean([len(w) for w in words]) if words else 0\n"
                  "    return json.dumps({'top': counts.most_common(3), 'mean': mean, 'map': isinstance({}, Mapping),\n"
                  "                       'title': string.capwords(text[:20]), 'fmt': '{0:>4}'.format(len(text)),\n"
                  "                       'row': collections.namedtuple('Row', 'a b')(1, 2)._asdict()}, ensure_ascii=False)\n")
        self.assertIn('main.py', validate_candidate(candidate(source)))


if __name__ == '__main__':
    unittest.main()
