"""Attach preregistration and analysis source without changing existing evidence."""
from pathlib import Path
import argparse,shutil
p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--registration',required=True,type=Path)
p.add_argument('--analysis',type=Path);a=p.parse_args()
for src,name in [(a.registration,'preregistration.md')]+([(a.analysis,a.analysis.name)] if a.analysis else []):
    dst=a.folder/name
    if dst.exists():raise FileExistsError(dst)
    shutil.copy2(src,dst)
