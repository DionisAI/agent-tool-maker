# tripo.studio.rig

Generated stdlib-only Python CLI. Requires an installed ATM >=0.6.0 command and the reviewed manifest. Use --atm /absolute/path/to/atm when PATH differs (including pipx).
No credential, browser session, binary, account, permission or dependency is embedded.

```sh
atm make validate manifest.json
atm make install manifest.json --approve 175171d986cc09bcc89eb13eaddd66f0e97c1ce88e6cbd46eab858c7f58090c2
python tool.py --input inputs.example.json --workspace /your/project --dry-run
```

For scoped execution add `--client claude` or `--client codex` and a stable `--request-key`; never bypass Broker refusal.
Review paid/write/code grants separately. Pass actual schema-valid inputs; examples may be empty.
Manifest or runtime changes need review; a hash proves consistency, not safety or publisher identity.
