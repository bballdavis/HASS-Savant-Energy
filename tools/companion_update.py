"""Decide whether upstream main advances the pinned companion (never downgrade)."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def needs_build(source, pinned):
    if not re.fullmatch(r'[a-f0-9]{40}', pinned):
        raise ValueError('Expected a full pinned commit')
    candidate = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    # A reviewed fix may be pinned before upstream merges it. Do not replace it
    # with its older main ancestor. Missing history is an error, not an update.
    subprocess.run(['git', '-C', str(source), 'cat-file', '-e', pinned + '^{commit}'], check=True)
    ancestor = subprocess.run(['git', '-C', str(source), 'merge-base', '--is-ancestor', candidate, pinned])
    if ancestor.returncode not in (0, 1):
        raise RuntimeError('Could not compare upstream history')
    return ancestor.returncode == 1


def artifact_changed(source, metadata):
    built = (source / 'dist/Savant-Card.js').read_bytes()
    return hashlib.sha256(built).hexdigest() != metadata['upstream_artifact_sha256']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--metadata', type=Path, default=Path('custom_components/savant_energy/www/bundle.json'))
    parser.add_argument('--after-build', action='store_true')
    args = parser.parse_args()
    metadata = json.loads(args.metadata.read_text())
    needed = artifact_changed(args.source, metadata) if args.after_build else needs_build(args.source, metadata['commit'])
    print('true' if needed else 'false')
