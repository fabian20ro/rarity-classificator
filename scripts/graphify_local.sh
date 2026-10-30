#!/usr/bin/env bash
# Graphify from the user's checkout; structural extraction only, no model/backend calls.
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
graphify_source=${GRAPHIFY_SOURCE:-"$HOME/git/graphify"}
graphify_env=${GRAPHIFY_ENV:-"$repo_root/build/graphify-venv"}
output_parent=${1:-"$repo_root/build/graphify-local"}
export UV_CACHE_DIR=${UV_CACHE_DIR:-"$repo_root/build/graphify-cache"}
export UV_PROJECT_ENVIRONMENT="$graphify_env"
export PYTHONPATH="$graphify_source"
export GRAPHIFY_BACKEND=none
export PYTHONDONTWRITEBYTECODE=1
uv sync --project "$graphify_source" --frozen --no-dev --no-install-project
cd -- "$repo_root"
"$graphify_env/bin/python" -m graphify extract "$repo_root" \
  --code-only --max-workers 1 --max-concurrency 1 --no-dedup \
  --exclude docs --exclude configs --exclude skills --exclude prompts --out "$output_parent"
"$graphify_env/bin/python" -m graphify cluster-only "$output_parent" --no-label
"$graphify_env/bin/python" - "$repo_root" "$graphify_source" "$output_parent" <<'PY'
import hashlib, json, subprocess, sys
from pathlib import Path
repo, tool, output = map(lambda s: Path(s).resolve(), sys.argv[1:])
out = output / 'graphify-out'
def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args]).decode().strip()
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
graph = json.loads((out / 'graph.json').read_text())
ids = {node['id'] for node in graph['nodes']}
assert len(ids) == len(graph['nodes']), 'Duplicate node IDs'
assert all(e['source'] in ids and e['target'] in ids for e in graph['links']), 'Dangling edges'
inputs = {}
for name in git(repo, 'ls-files').splitlines():
    path = repo / name
    if path.is_file() and not path.is_symlink() and path.suffix in {'.py', '.js', '.cjs', '.sh', '.toml', '.yml', '.yaml'}:
        inputs[name] = sha(path)
receipt = dict(
    mode='Graphify local code-only; no LLM labeling or inference',
    repository=str(repo), repository_commit=git(repo, 'rev-parse', 'HEAD'),
    working_tree_status=git(repo, 'status', '--short'),
    graphify_source=str(tool), graphify_commit=git(tool, 'rev-parse', 'HEAD'),
    graphify_working_tree_status=git(tool, 'status', '--short'),
    graphify_lock_sha256=sha(tool / 'uv.lock'),
    wrapper_sha256=sha(repo / 'scripts/graphify_local.sh'),
    tracked_code_config_hashes=inputs,
    node_count=len(ids), edge_count=len(graph['links']),
    artifacts={n: sha(out/n) for n in ('graph.json', 'graph.html', 'GRAPH_REPORT.md', 'manifest.json')},
)
(out/'local-run.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(f'Verified {len(ids)} nodes / {len(graph["links"])} edges; {out}')
PY
