import os, sys, json
from pathlib import Path
root = Path(r'C:\Users\HP\Desktop\MajorProject\GreenLedger')
cord_dir = root / 'data' / 'public' / 'cord' / 'dataset_cord_v2'
cord_dir.mkdir(parents=True, exist_ok=True)
# attempt to install packages
import subprocess
def pip_install(packages):
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + packages)
        return True
    except Exception as e:
        print('pip install failed, trying --user', e)
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--user'] + packages)
            return True
        except Exception as e2:
            print('pip install --user failed', e2)
            return False

ok = pip_install(['datasets==2.14.5', 'huggingface_hub', 'requests'])
if not ok:
    print('ERROR: required packages could not be installed')
    sys.exit(1)
from datasets import load_dataset
print('Loading CORD v2 dataset...')
try:
    ds = load_dataset('naver-clova-ix/cord-v2')
except Exception as e:
    print('ERROR loading dataset:', e)
    sys.exit(2)
for split in ds.keys():
    out_dir = cord_dir / split
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / f'{split}.jsonl'
    with open(jsonl_path, 'w', encoding='utf-8') as f:
        for ex in ds[split]:
            f.write(json.dumps(ex, ensure_ascii=False) + '\n')
    print('Saved', jsonl_path)
# manifest
import os
total_files=0; total_bytes=0
for dirpath,_,filenames in os.walk(cord_dir):
    for fn in filenames:
        p = os.path.join(dirpath,fn)
        total_files+=1
        try:
            total_bytes+=os.path.getsize(p)
        except OSError:
            pass
manifest = {'path':str(cord_dir), 'total_files':total_files, 'total_bytes':total_bytes}
with open(root / 'data' / 'public' / 'cord' / 'DOWNLOAD_MANIFEST.json', 'w', encoding='utf-8') as mf:
    json.dump(manifest, mf)
print('CORD saved; files:', total_files, 'bytes:', total_bytes)
with open(root / 'data' / 'public' / 'cord' / 'VERIFIED.txt', 'w', encoding='utf-8') as v:
    v.write('CORD v2 downloaded and saved as JSONL per split. Manifest: ' + json.dumps(manifest))
print('Done')
