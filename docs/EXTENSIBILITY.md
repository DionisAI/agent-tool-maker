# ATM v0.6 — 目录之外的能力

## 实现范围

目录是发现入口，不是只能接入这些公司的白名单。v0.6 将凭证、动作定义、运行权限、设备登录态分开管理。

| 资源 | 已实现 | 不代表什么 |
|---|---|---|
| 未知 API Key | 自定义名称槽、加密写入、有效期、同步及冲突、按动作引用 | 不自动知道鉴权协议或付费规则 |
| JSON HTTP API | 手写声明、OpenAPI 3 JSON 子集导入、固定 HTTPS 目的地址 | 不自动支持 HMAC、mTLS、OAuth、流式/二进制 API |
| 新 CLI | 声明 argv/输入/输出/凭证环境变量，批准后绑定已安装程序 | 不自动安装第三方程序，不是代码沙箱 |
| 只有网页 | `web_recipe`：Playwright 实际执行有限 DOM 操作和下载，生成 Python CLI | 不是官方 API，不是给任意 URL 就能保证成功 |
| Agent 制作 | 调用已登录 Claude Code/Codex 起草 manifest，再编译 CLI | 本轮没有实际模型调用；不会自动安装、授予权限或执行草稿 |
| 网页工坊 | 新凭证槽、JSON 验证、明确安装/更新、自定义目录、会话元数据 | 不提供网页任意 Shell 或模型调用按钮 |

原有157个内置动作未扩充。自定义动作只在安装到自己的状态库后进入该机目录。内置动作无法覆盖。

## 1. 不在目录中的 Key

```sh
atm credentials declare acme.production --label "Acme 生产账号"
# 审阅非秘密名称之后：
atm credentials declare acme.production --label "Acme 生产账号" --apply
atm connect acme.production
atm credentials list
```

`connect` 在用户自己的终端隐藏输入；也可以在本地管理台输入。已有 Key 不重问；轮换用 `--replace`。名称限2–80个小写字母/数字/点/连字符/下划线，首字符是字母。值是现有 vault 支持的单行凭证字符串（最多16 KiB），不是任意私钥文件。

`acme.production` 与 `acme.development` 是两个独立槽；在自定义工具的 `credential` 中选择。原有内置工具仍沿用原先固定槽，不是全局多账号自动路由。

新槽可以按原有 `atm sync trust --send acme.production` / `--receive acme.production` 范围同步；冲突规则不变。同步不授予新工具权限。接收端可以识别已收到的槽，无须改源码。标签、工具定义、CLI 路径、Agent授权不自动同步。

## 2. 把 API 变成工具

```sh
atm make new acme.translate --kind api --url https://api.example.com --out acme.json
```

这是**模板**，域名和路径必须根据目标服务的实际文档改写。`examples/extensions/acme-api.json` 是假想 JSON API 示例，不可当真实服务调用。典型定义：

```json
{
  "id": "acme.translate", "provider": "acme", "title": "Acme translation",
  "capabilities": ["translation"], "adapter": "rest", "credential": "acme.production",
  "paid": true,
  "schema": {"type":"object", "properties":{"text":{"type":"string"}}, "required":["text"], "additionalProperties":false},
  "request": {"origin":"https://api.example.com", "path":"/v1/translate", "method":"POST", "auth":"bearer", "body":{"text":"$text"}}
}
```

请求引用是 `$text` / `$body`，**不是**工作流中的 `$input.text`。`body`保留JSON类型；路径参数只允许单段。认证支持 bearer、basic、`header:X-Service-Key` 和 none。Key由运行器注入，不写在定义/包/命令参数里。静态 header 只允许有限非认证头。

有 OpenAPI 文件时，先在本地选择单个 operation：

```sh
atm make from-openapi examples/extensions/sample.openapi.json \
  --operation-id getRecord --id acme.get_record \
  --credential acme.production --out acme-record.json
```

导入器只处理一个固定 HTTPS server、简单 path/query 参数、必需的 application/json body、单一 bearer/basic/header API Key。支持无环本地 `$ref`，拒绝外部引用、多个认证选择、Cookie/query-key鉴权和不支持的参数序列化，不联网猜测。可选 query 未提供时不发送；boolean序列化为 `true/false`。

## 3. 任意已安装 CLI

```sh
atm make new mycli.inspect --kind cli --executable mycli --out mycli.json
```

编辑定义里的固定命令与参数。输入 token 支持 `input`、`json`、`file`、`dir`、`output`、`workspace`。不是拼接 Shell 命令字符串；不会 `eval` 或加载任意Python插件。

```json
"command": {
  "argv": ["inspect", "--input", {"file":"path"}],
  "output": "json",
  "credential_env": {"MY_SERVICE_KEY":"acme.production"},
  "credential_required": true,
  "timeout": 60
}
```

`credential_required:true` 在缺 Key 时不启动进程；省略则保留原来的“CLI自己已登录”路线。只有选中的映射会注入该子进程，不向主Agent暴露Key。第三方CLI本身能接触注入的凭证；它是被信任的执行程序，不是不可泄露的黑盒。

安装批准后的工具再绑定实际程序：

```sh
atm make validate mycli.json
atm make install mycli.json --approve REVIEWED_SHA256
atm cli bind mycli /absolute/path/to/installed/mycli
```

自定义 CLI 无条件要求 `execute_code` 权限。固定入口会记录哈希；升级后重新审阅绑定。

## 4. 网页真的执行，而不是只写交接单

```sh
atm make new studio.export --kind web --url https://your-service.example/ --out studio.json
```

按**实际观察**的表单、按钮和输出修改配方。没有观察到的选择器是待补证据，不该由模型虚构。

当前操作：`wait`、`fill`、`select`、`click`、`expect_text`、`extract`、`download`。定位支持 CSS、role+name、label、text；值是有限常量或顶层 string 输入引用。最多40步，单步最长60秒，总步骤预算最长300秒；文本字段20,000字符，下载交付64 MiB。下载大小在下载完成后检查，不是磁盘硬配额；浏览器启动、下载内部等待也不等同于整进程强制终止时限。

每个配方声明固定 start_url 和1–12个确切 HTTPS origin，开始前检查地址；请求逐个经过相同 origin 白名单。禁用 service workers，拦截 WebSocket。不是OS防火墙或DNS绑定；已批准网站仍运行自己的JavaScript。配方不支持任意JS/eval，也不接管默认浏览器个人资料。

原有 `browser` 类型仍是 computer-use 交接；新 `web_recipe` 才是真正的程序执行器。Canvas/复杂跨frame、扫码/验证码、平台审批、依赖WebSocket的网站，可能需要继续交给主Agent的computer use或专门适配器。不得绕过平台或浏览器策略。

### 登录一次，正常任务复用

配方增加 `session:"studio"`，可选 `login_check:{"role":"heading","name":"Sign in"}`。

```sh
# 安装已审阅定义之后：
python -m pip install '.[web]'       # 从本源码目录安装可选依赖
python -m playwright install chromium
atm web login studio.export
atm web sessions
```

Owner在自己终端启动新的可见浏览器，完成官方登录/MFA后键入SAVE。浏览器storage state用AES-GCM和当前设备vault主密钥加密，认证附加数据包括会话名、origin和有效期。没有原始会话导出API，不读取现有Chrome/Cookie文件，不把会话混进API Key同步。

已安装为 pipx 时，可用 `pipx inject agent-tool-maker-local "playwright>=1.51" --include-apps`，然后 `playwright install chromium`。如果同名命令已被其他环境占用，先检查路径，不覆盖未知安装。不要让Agent改动系统浏览器策略。

多个任务复用这个会话；供应商过期/撤销、频繁cookie轮换或设备绑定仍可能要求重新登录。SessionStorage/硬件passkey等未支持；没有通用登录自动刷新。浏览器仍在执行期间持有登录态，临时浏览器资料和内存不是强隔离。`atm web remove-session studio --apply`只删本地副本，不代表供应商登出。

### 执行和失败

```sh
atm run studio.export --input task.json --workspace /your/project --dry-run
# 真实操作须已有付费/写入授权，按配方实际要求加旗标：
atm run studio.export --input task.json --workspace /your/project \
  --request-key stable-task-id --allow-write --allow-paid
```

`completed`只表示声明的步骤与文件交付通过，不代表商业订单完成或生成内容满意。没有内容/文件输出的纯点击配方被拒绝。登录检查命中返回login_required，不伪造成功。

点击等可能已经产生副作用时遇到错误，标记submission_unknown；同一个request-key不会自动重发。不要换key绕过失败：先查看供应商任务记录确认，再决定是否新建任务。修复选择器不应该隐含重新下单。

## 5. 程序生成程序：两种路径

**不调用模型的确定性路径：**模板或OpenAPI → 验证manifest → `make pack` → 输出 `tool.py`、manifest、输入示例、README和哈希锁。

```sh
atm make pack examples/extensions/ffprobe-cli.json --out ./media-cli
atm make check-bundle ./media-cli
atm make validate ./media-cli/manifest.json
atm make install ./media-cli/manifest.json --approve REVIEWED_SHA256
atm cli bind ffprobe "$(command -v ffprobe)"
python ./media-cli/tool.py --input ./task.json --workspace /your/project --dry-run
```

生成的是**只需 Python 标准库、调用已安装 ATM>=0.6 命令的真实 CLI**，不是独立供应商SDK。ATM 在 pipx 的独立环境也可用；找不到入口时通过 `--atm /absolute/path/to/atm` 指定，不要求生成脚本和 ATM 安装在同一个Python环境。它固定tool ID和定义摘要；定义不同就拒绝运行，不偷偷安装或换版本。实际CLI也支持 `--client claude` / `--client codex` / `--client-profile`，继承Broker scope。包里没有Key、Cookie、权限或外部可执行文件。hash只证明文件一致，不是作者签名或安全审计。`make pack` 写入中途失败时返回 `bundle_incomplete`：部分目录原样保留在 `--out` 供检查，`check-bundle` 判为无效且不会被复用，请换一个新的 `--out`。

**可选模型路径：**ATM自己调用已安装并登录的Claude Code或Codex，只接收结构化工具定义，再使用同一编译器生成CLI。

```sh
atm cli bind claude "$(command -v claude)"
atm make draft --agent claude --seed studio.json --brief observed-page.txt --out candidate.json
# 审阅输入，明确授权一次可能收费的模型调用：
atm make draft --agent claude --seed studio.json --brief observed-page.txt --out candidate.json --allow-agent
# --agent codex 同样支持；先绑定已安装的 codex。
```

只把指定seed和非秘密brief发给所选模型。程序不读取供应商Key、不扫描环境找Key；复用CLI自己的官方登录。Claude请求关闭工具与用户自定义来源，Codex请求read-only、忽略用户配置、禁用shell/search；必须使用支持这些旗标的版本。它们仍是可信本地程序，组织管理策略仍适用；本版不声称完整模型进程隔离。命令/鉴权不支持时明确失败，不降级到更宽权限。

本版没有内置“访问任意网站、探索全部功能、自动找到选择器”的Agent循环。已有主Agent可以用它拥有的浏览器收集观察结果，再交给factory；已有API文档、CLI --help的非秘密输出也可作为brief。代码厂是可执行子步骤，不是另一个无边界自主Agent。

结果只是草稿：不自动安装、不授予权限、不立即访问目标站点。`make validate`与`check-bundle`只是结构与一致性验证，真实行为需独立验收。本轮模型调用只做了CLI协议替身测试，未连接真实Claude/Codex账号。

## 6. 更新、修复与分发

```sh
atm make validate candidate.json
atm make update candidate.json --approve NEW_REVIEWED_SHA --expected OLD_INSTALLED_SHA
```

只更新自定义工具；旧定义保留历史。旧Broker grant的定义pin随之失效，需要Owner重新审阅；不能通过“自修复”扩大站点或工具权限。生成的旧CLI也会拒绝悄悄运行新定义。

跨机器分发无秘密bundle即可；目标机仍须独立批准定义、绑定本机CLI、批准Broker权限。Key可走v0.5密文同步；网页登录由目标设备自己完成。不将所有代码/可执行文件/权限通过同步自动信任。

## 7. 本地开发与依赖

完整源码开发环境：

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[secure,test,web]'
python -m playwright install chromium
python -m pytest -q
```

已用pipx管理时，从项目源码执行 `pipx install --force '.[secure]'`，按上面 `pipx inject ... --include-apps` 暴露该环境的Playwright入口并安装Chromium。不假定所有系统pipx目录一致。CLI实际路径与状态目录不移动，升级不重建vault。

## 8. 证据与下一步

见 TEST_REPORT_V06.md。主要验收：新槽跨进程和同步、固定请求编码、真实CLI执行、定义更新使旧授权失效、加密设备会话、真实浏览器DOM和下载、网页管理API、模型CLI协议替身。

本环境管理策略禁止Chromium导航。内存页面测试明确替换导航层，仍执行真实DOM与下载；不算原生导航、生产网站或登录实测。提供独立 `acceptance/test_recipe_native_v06.py` 在允许的环境或GitHub CI运行，不在本地通过数里。没有更改策略来通过测试。
