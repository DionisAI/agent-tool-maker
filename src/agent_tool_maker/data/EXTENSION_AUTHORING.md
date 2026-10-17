# ATM extension authoring contract v1

One JSON manifest, no executable Python inside the manifest. Required keys: id, provider,
title, capabilities (list), schema (JSON Schema object with type=object), adapter.
paid (boolean; omitted means false, so set true whenever a call can spend money or credits).
Keep a seed's paid:true and permissions; drafts that drop them are refused. Inputs do not carry secrets.

- rest: request={origin:fixed HTTPS origin, path:/relative/{id}, method:GET/POST/PUT/PATCH/DELETE,
  auth:bearer/basic/header:X-Api-Key/none, query:{name:"$name"}, optional_query:[optional keys],
  body:"$body" or typed object}. `credential` is a vault SLOT NAME, never a value.
- command: executable=registered local alias, command={argv:[literal,{input:"field"},
  {json:"field"},{file:"path"},{dir:"project"},{output:"result.txt"}], output:text/json, timeout:1..900,
  credential_env:{SERVICE_KEY:"vault-slot"}, credential_required:true when the CLI requires this Key}.
  No Shell strings, eval, arbitrary plugin loaders. A newly installed command still needs binary binding.
- web_recipe: recipe={version:1,start_url:HTTPS URL,allowed_origins:[exact origins without slash],
  session:optional device-local login name,login_check:optional locator identifying login screen,
  timeout_ms:15000,total_timeout_ms:120000,steps:[...]}.
  locator is {css:"#id"}, {role:"button",name:"Generate"}, {label:"Prompt"} or {text:"Done"}.
  Supported steps: wait/click (op,target), fill/select/expect_text (op,target,value),
  extract (op,target,name), download (op,target,filename).
  value is a literal string or {input:"top_level_string_field"}. No arbitrary JavaScript or secret lookup.
  At least one extract/download step; max40. Download filename is a fixed simple name.
  Add every necessary asset/API/login origin explicitly; no wildcards. Service workers and websockets are blocked.
  Browser state is encrypted separately on this device; never put cookies into a manifest or source.
- browser/desktop/human: handoff only, not automatic execution.

Unknown details remain placeholders. A model-generated draft is NOT live verified. A website is not
an official API. Login/MFA/CAPTCHA is for the human. Paid/write/code approval is separate from installation.
Any repair produces a new candidate; active definitions and prior grants must never be silently rewritten.
