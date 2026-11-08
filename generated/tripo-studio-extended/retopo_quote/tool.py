#!/usr/bin/env python3
"""Generated ATM CLI. Uses only Python stdlib; delegates to an installed ATM executable."""
import argparse
import json
import os
import shutil
import subprocess
import sys

TOOL = 'tripo.studio.retopo_quote'
DEFINITION_SHA256 = '9edd306779c5eadbaa256885ecc91988b22898e681cdc2ca37c94c94ac41bd95'


def main(argv=None):
    p = argparse.ArgumentParser(description='Generated command for '+TOOL+'; install its reviewed manifest first.')
    p.add_argument('--atm', help='Exact installed ATM executable; otherwise discover atm on PATH')
    p.add_argument('--home')
    clients=p.add_mutually_exclusive_group()
    clients.add_argument('--client',choices=['claude','codex']);clients.add_argument('--client-profile')
    p.add_argument('--input',required=True,help='JSON file or - for stdin; never credential values')
    p.add_argument('--workspace',required=True);p.add_argument('--request-key')
    p.add_argument('--dry-run',action='store_true')
    for name in ['paid','write','code','production']:p.add_argument('--allow-'+name,action='store_true')
    args=p.parse_args(argv)
    executable=shutil.which(args.atm or 'atm')
    if not executable:
        print(json.dumps({'error':{'code':'atm_not_installed','message':'Install ATM >=0.6 or provide its exact --atm path. No automatic installer was run.'}}))
        return 2
    command=[os.path.abspath(executable)]
    for name in ['home','client','client_profile']:
        if getattr(args,name):command += ['--'+name.replace('_','-'),getattr(args,name)]
    command += ['run',TOOL,'--expect-definition',DEFINITION_SHA256,'--input',args.input,'--workspace',args.workspace]
    if args.request_key:command += ['--request-key',args.request_key]
    for name in ['dry_run','allow_paid','allow_write','allow_code','allow_production']:
        if getattr(args,name):command.append('--'+name.replace('_','-'))
    try:
        return subprocess.run(command,shell=False).returncode
    except OSError:
        print(json.dumps({'error':{'code':'atm_start_failed','message':'Configured ATM executable could not start.'}}))
        return 2


if __name__=='__main__':
    raise SystemExit(main())
