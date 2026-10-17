# tripo.studio.viewer_camera

Generated stdlib-only Python CLI. Requires an installed ATM >=0.6.0 command and the reviewed manifest. Use --atm /absolute/path/to/atm when PATH differs (including pipx).
No credential, browser session, binary, account, permission or dependency is embedded.

```sh
atm make validate manifest.json
atm make install manifest.json --approve c687aa1daae4b42353bd9ae7ae48bdca8af49352880f139e5afded3412b6c62b
python tool.py --input inputs.example.json --workspace /your/project --dry-run
```

For scoped execution add `--client claude` or `--client codex` and a stable `--request-key`; never bypass Broker refusal.
Review paid/write/code grants separately. Pass actual schema-valid inputs; examples may be empty.
Manifest or runtime changes need review; a hash proves consistency, not safety or publisher identity.
