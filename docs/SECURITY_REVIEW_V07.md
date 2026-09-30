# ATM v0.7 — 安全审查（本轮作者自审，非第三方审计）

日期：2026-09-30。基线：交付的 v0.6源码树 `4d0d096bf87062653cf43ebb341750c7f897a656`。
范围：新增 `secrets_provider.py`、`session.py`、`secrets_cli.py`；Broker、vault、CLI/Web与Skill的相应变更。
不声称重新完成全部历史供应商代码、依赖、密码学协议或生产部署审计。测试只用假凭证。

## 威胁模型与结论

目标：避免凭证落入项目env、模型对话及新exec原始日志；在同一Owner的本机环境中，对获准客户端按命令/凭证/项目/期限控制正常调用；失败不降级。

**不是**同UID恶意代码、root、被控制的Owner浏览器/终端、任意批准的脚本、供应商或操作系统内存泄露的防线。默认客户端profile和Ownerprofile虽然用途分离，但同UID恶意进程可能读取它们或直接修改本地数据；JSON批准摘要并不认证“真人”。

一般程序最终必须拿到所选Key。它可以自行编码输出、写磁盘或联网。不会因输出字段 `secrets_returned:false` 就声称信息论意义上没有秘密外流；该字段仅表示ATM没有设计原文取Key接口。额外字段明确标记 `output_redaction=best_effort_not_a_sandbox`。

## 检查项目及修复

| 风险 | 本版控制 | 验证 |
|---|---|---|
| 保存有效期但实际读取忽略过期 | Vault.get统一检查期限；conflict/meta/cipher在同一个SQLite读事务 | legacy直接读、exec过期、解密中失效回归 |
| 读取凭证后授权被撤销或规则更新仍启动 | 接纳时重新读取授权，确认相同规则仍存在；再次核对加密行版本和过期/冲突状态 | 解密期间轮换、到期、规则移除、撤销四种拒绝 |
| 客户端只看socket文件属性，不看实际对端 | Linux有SO_PEERCRED时连接后再次核验服务端UID | 原有真实跨UID验收与本轮调用路径；macOS此层未实测 |
| 新服务到期后命令自动退回直接密码/Owner | 持久化session opt-in；profile删除不取消模式；客户端失败不回退 | profile删除、锁定、自然到期、缺少授权 |
| 首次授权后同时锁定，空master引用触发普通Vault重新输密码 | 请求专用SessionVault只接受已解锁快照；无密码/keyring降级，open时再检查租期 | 并发lock与空请求vault两个回归 |
| Agent借元数据接口枚举全部Key或改库 | 按grant取名，元数据不解密；管理RPC只接受本次Ownerprofile | 隐藏Stripe、禁止读原文/改/删/锁/同步 |
| 普通程序入口扩大到任意Shell或环境控制 | exact argv、精确映射、workspace、执行器/文件SHA；禁proxy/LD/PYTHON/NODE/ATM控制变量；shell=False | 命令/目录/映射替换、20种控制变量、symlink和..路径 |
| 解析解释器链接后丢失venv，同时存在链接目标漂移 | 保留原调用路径，单独pin真实执行器与pyvenv.cfg | 真实临时venv加载只存在其中的依赖；配置变化/链接重定向拒绝 |
| 通用代码以跨UID Owner权限运行 | 新generic exec明确拒绝不同UID；不从老tool权限推导exec | 跨UID拒绝、旧grant不能genericexec |
| 输出先明文落盘再脱敏 | 新exec只用有界内存pipe，256KiB合计上限；超量/超时完全抑制输出 | stdout/stderr分块回显、base64、超量/超时、状态库无输出 |
| 重试造成重复调用/消费 | 稳定task key、原子create_job；不保存输出供重播，不盲目重发 | 同key任务ID相同、任务计数不增 |
| Web解锁成为任意远端控制 | 原有严格Host/Origin、bearer、JSON限制、CSP保留；无Web exec/get-key接口 | HTTP/CSRF回归，真实Chromium组件操作 |

## 新exec运行合同

Owner先批准精确程序。批准记录不含Key，含命令参数；**命令参数应只包含非秘密数据**。没有自动读取.env，注入只接受精确`atm://`引用。
默认grant7天（最大30天），session30分钟（最多24小时），子进程60秒（最多300秒），输出256KiB，单profile最多32规则，单规则最多64项目文件，固定文件每个最大256MiB。

同一服务同时最多接纳两个新的有界凭证操作。使用新环境，不继承父进程的其他Key、ATM密码或代理/解释器注入设置。stdin关闭、close_fds、新process group。退出时清理同组后代；这不是应对恶意setsid/逃逸的进程沙箱。

应用程序由同UID Broker执行。用户应审查实际Python环境、依赖和项目代码，不应对不可信仓库直接批准高权限Key。可执行文件和识别到的普通文件参数被SHA固定，但import、动态库、`--script=...`字符串内隐藏路径、插件以及全依赖树不自动全部固定。可用`--pin-file`补充已知依赖，仍不是完整依赖验证。

文件在检查后到exec之间可能被拥有足够本机权限的恶意进程更换；lease/grant在接纳后也可能撤销。本版定义接纳点，已接纳的任务可以完成，不声称消除了全局TOCTOU或能收回已交付字节。

## 秘密如何存在

- 本地供应商Key沿用AES-256-GCM；密码模式scrypt，未更改已有密文格式。
- 跨设备沿用签名加密文件包，各设备独立主密钥和scope。别名、grant、profile、主密钥和解锁密码不自动同步。
- 单次Owner解锁服务持有主密钥引用；单请求/子进程短时持有具体Key。Python引用清除不保证物理零化、swap或core dump不可恢复。
- scoped profile是明文受限bearer（0600），Owner session profile是另一个更高权限bearer（0600）。都不能进入Git/共享目录/模型对话。
- 新exec不持久记录原始stdout/stderr，仅将尽力遮蔽后的有界输出返回调用者。旧注册CLI输出路径仍有历史临时文件边界，不把新保护外推到所有代码。
- metadata、命令、项目路径和规则不是加密秘密；业务敏感参数仍要另行处理。

## 残余风险／未通过的外部门槛

没有独立密码学或依赖漏洞审计；没有实际Passkey/OAuth刷新、两台公网真机、真实Claude/Codex加载、Windows或真实keyring锁屏/重启测试。
不保证env在系统process inspection/dumps中不可见。不保证程序不自己写.env。不保证输出经过未知变换仍能遮蔽。不保证设备撤销能抹掉其已拿到的Key。
同UID使用scope是减少误用的接口，不是隔离恶意本机代码。需要更强边界时，应采用独立低权限运行环境与网络/文件约束，且不应把新genericexec改成以更高Owner权限执行任意请求。

## 资料

实现取舍参考以下一手/官方资料；资料不是对ATM的认证：
- Python subprocess：结构化args、env和shell安全语义。https://docs.python.org/3/library/subprocess.html
- OWASP Secrets Management Cheat Sheet：最小权限、生命周期、日志/内存及环境变量的暴露边界。https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html

实际测试回执、源码一致性和未验证项见 `TEST_REPORT_V07.md`，不是只凭静态检查宣布安全。

## 测试过程中暴露的问题

带覆盖率的早期全量运行在一个旧扩展页面测试及旧模型起草测试中失败，记录保留。页面原样单独复测通过，尚不能由此断言失败原因。旧起草测试单独复测确认：本来验证错误退出/无效JSON的fixture因统一1秒预算先触发了`draft_timeout`。仅将非超时语义场景的测试预算设为10秒；真正超时场景仍为1秒预算对10秒sleep，保留全部错误码断言，产品timeout没有改变。最终套件必须独立完整复跑，不能把这些早期失败计为通过。

客户端名Claude/Codex是profile标签，不是被鉴定的模型或进程身份。权限由持有的bearer、对应本地grant和支持时的Unix UID共同决定；不能区分已被同一UID恶意程序窃取的合法profile。
