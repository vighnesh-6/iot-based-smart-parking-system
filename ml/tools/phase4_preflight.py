"""Record actual native-library readiness without installations or security changes."""

import argparse
from datetime import datetime,timezone
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Evidence exists; choose a new path')
    command=[sys.executable,'-B','-c',
        'from sklearn.linear_model import LinearRegression; from sklearn.ensemble import RandomForestRegressor; '
        'from sklearn.preprocessing import StandardScaler; import joblib; print("Required model imports passed")']
    result={'source':'actual_phase4_dependency_preflight','recorded_at_utc':datetime.now(timezone.utc).isoformat(),
            'platform':platform.platform(),'python':sys.version.split()[0],'command':command,
            'security_policy_modified':False,'dependencies_modified':False}
    result['versions']={}
    for name in ['scikit-learn','numpy','pandas','scipy','joblib','threadpoolctl']:
        try:result['versions'][name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:result['versions'][name]=None
    try:
        completed=subprocess.run(command,capture_output=True,text=True,timeout=180)
        result.update(returncode=completed.returncode,stdout=completed.stdout,stderr=completed.stderr,
                      native_imports_passed=completed.returncode==0)
    except subprocess.TimeoutExpired:
        result.update(returncode=None,stdout='',stderr='Native import preflight timed out after 180 seconds',native_imports_passed=False)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))
    return 0 if result['native_imports_passed'] else 2


if __name__=='__main__':raise SystemExit(main())
