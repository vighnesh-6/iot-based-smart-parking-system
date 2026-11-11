"""Archive actual Phase 4 tests; native cases are never silently skipped."""

import argparse
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import time
import unittest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native',action='store_true',help='Include real sklearn fitting/reload tests; requires permitted runtime')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Choose a new evidence output')
    from ml.tests.test_phase4 import ContractTests,NativeModelTests
    suite=unittest.TestSuite()
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(ContractTests))
    if args.native:suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(NativeModelTests))
    ids=[test.id() for test in suite]
    stream=io.StringIO();start=time.monotonic()
    result=unittest.TextTestRunner(stream=stream,verbosity=2,failfast=args.native).run(suite)
    record={'source':'actual_phase4_test_execution','recorded_at_utc':datetime.now(timezone.utc).isoformat(),
            'native_tests_requested':args.native,'passed':result.wasSuccessful(),'tests_run':result.testsRun,
            'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
            'seconds':round(time.monotonic()-start,3),'test_ids':ids,'runner_output':stream.getvalue(),
            'source_sha256':{p.as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [
                Path('ml/phase4_models.py'),Path('ml/train_phase4.py'),Path('ml/tests/test_phase4.py'),Path('ml/tools/verify_phase4.py')]}}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as output:json.dump(record,output,indent=2);output.write('\n')
    print(stream.getvalue())
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
