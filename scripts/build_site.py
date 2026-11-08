"""Build the dependency-free GitHub Pages site."""
import argparse
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=root / 'dist/site')
args = parser.parse_args()
shutil.copytree(root / 'site', args.output, dirs_exist_ok=True)
(args.output / '.nojekyll').touch()
print(args.output.resolve())
