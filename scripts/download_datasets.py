import os, sys, json
from pathlib import Path
root = Path(r'C:\Users\HP\Desktop\MajorProject\GreenLedger')
cord_dir = root / 'data' / 'public' / 'cord' / 'dataset_cord_v2'
cord_dir.mkdir(parents=True, exist_ok=True)
# install datasets
import subprocess
try:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'datasets==2.14.5', 'huggingface_hub', 'requests'], stdout=subprocess.DEVNULL)
except Exception as e:
    print('ERROR: pip install failed', e)
    sys.exit(1)
from datasets import load_dataset
print('Loading CORD v2 dataset from Hugging Face...')
try:
    ds = load_dataset('naver-clova-ix/cord-v2')
except Exception as e:
    print('ERROR loading dataset:', e)
    sys.exit(2)
# Save dataset as JSON lines per split
for split in ds.keys():
    out_dir = cord_dir / split
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / f'{split}.jsonl'
    with open(jsonl_path, 'w', encoding='utf-8') as f:
        for ex in ds[split]:
            f.write(json.dumps(ex, ensure_ascii=False) + '\n')
    print('Saved', jsonl_path)
# compute size and counts
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
print('CORD dataset saved; files:', total_files, 'bytes:', total_bytes)
# write brief verification file
with open(root / 'data' / 'public' / 'cord' / 'VERIFIED.txt', 'w', encoding='utf-8') as v:
    v.write('CORD v2 downloaded and saved as JSONL per split. Manifest: ' + json.dumps(manifest))
print('Done')
