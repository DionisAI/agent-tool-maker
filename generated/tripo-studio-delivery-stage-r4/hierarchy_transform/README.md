# tripo.studio.hierarchy_transform

Generated stdlib-only Python CLI. Requires an installed ATM >=0.6.0 command and the reviewed manifest. Use --atm /absolute/path/to/atm when PATH differs (including pipx).
No credential, browser session, binary, account, permission or dependency is embedded.

```sh
atm make validate manifest.json
atm make install manifest.json --approve bad229fadb9a5435c9455b4e321484f87e5bf98949cb0f0643c9c8f776bd7758
python tool.py --input inputs.example.json --workspace /your/project --dry-run
```

For scoped execution add `--client claude` or `--client codex` and a stable `--request-key`; never bypass Broker refusal.
Review paid/write/code grants separately. Pass actual schema-valid inputs; examples may be empty.
Manifest or runtime changes need review; a hash proves consistency, not safety or publisher identity.
