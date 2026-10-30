import {existsSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
const local = process.platform === 'win32' ? '.venv-docs/Scripts/python.exe' : '.venv-docs/bin/python3';
const python = process.env.PYTHON || (existsSync(local) ? local : 'python3');
const result = spawnSync(python, process.argv.slice(2), {stdio: 'inherit'});
if (result.error) console.error(result.error.message);
process.exit(result.status ?? 1);
