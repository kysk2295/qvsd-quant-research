import importlib.util
import unittest
from datetime import datetime,timezone
import numpy as np
from nt8_mcp import nrd_offline as nrd
from research.nrd_trace import traced_decode,calendar_summary
from research.diagnose_nrd_oct23 import read,PLAN


def legacy_tests():
    from pathlib import Path
    path=Path(read(PLAN)['decoder']).parents[1]/'tests/test_nrd_offline.py'
    spec=importlib.util.spec_from_file_location('quality_legacy_nrd_tests',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    if module.N is None:raise RuntimeError('Decoder dependencies unavailable; cannot count skipped tests')
    return module


class TraceTests(unittest.TestCase):
    def test_trace_preserves_original_arrays(self):
        raw=legacy_tests().synthetic_nrd(); slots=nrd.parse_headers(raw[:3520])
        original=nrd.decode(raw[3520:],slots,salvage=False)
        traced,trace=traced_decode(nrd,raw[3520:],slots)
        for level in ('L1','L2'):
            for a,b in zip(original[level],traced[level]):np.testing.assert_array_equal(a,b)
        self.assertEqual(trace['first_outside_header'],{})
        self.assertEqual(trace['first_records'][2]['stream_offset'],0)

    def test_trace_identifies_first_bad_price_offset(self):
        raw=bytearray(legacy_tests().synthetic_nrd()); raw[3521]=0x50
        decoded,trace=traced_decode(nrd,bytes(raw[3520:]),nrd.parse_headers(raw[:3520]))
        self.assertFalse(decoded['integrity_ok'])
        self.assertEqual(trace['first_outside_header'][2]['record']['file_offset'],3520)
        self.assertEqual(trace['first_outside_header'][2]['record']['price'],21800.5)

    def test_trace_strict_truncation_unchanged(self):
        raw=legacy_tests().synthetic_nrd()
        with self.assertRaises(nrd.FormatError):traced_decode(nrd,raw[3520:-1],nrd.parse_headers(raw[:3520]))

    def test_calendar_uses_et_dst_and_excludes_close(self):
        for day,hour in [('2026-10-23',13),('2026-11-03',14)]:
            start=int(datetime.fromisoformat(f'{day}T{hour:02d}:30:00').replace(tzinfo=timezone.utc).timestamp())*10**9
            ts=np.array([start-1,start,start+390*60*10**9],dtype='int64')
            result=calendar_summary(ts,np.array([100,100,100]),np.array([1,2,3]),day)
            self.assertEqual((result['rth_minutes'],result['rth_ticks'],result['rth_volume']),(1,1,2))
            self.assertEqual(result['rth_missing_minutes'],list(range(1,390)))


def load_tests(loader,tests,pattern):
    suite=loader.loadTestsFromTestCase(TraceTests)
    module=legacy_tests()
    for name in sorted(dir(module)):
        if name.startswith('test_'):suite.addTest(unittest.FunctionTestCase(getattr(module,name)))
    return suite
