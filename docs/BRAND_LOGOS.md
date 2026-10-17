# 本地管理台品牌图标

## 显示合同

- 总览“你的工具箱”从当前工具目录分组，展示前 12 个提供方；点击进入已过滤的工具目录，查看全部入口保留。
- 工具目录、供应商连接、Higgsfield OAuth、Agent 客户端和 CLI 列表复用相同图标组件。目录保留精确工具 ID；连接保留精确凭证槽位。
- 当前打包 **55 个品牌图标**。别名复用同一图标，覆盖内置目录 **73 个 provider 中的 59 个**；其余使用明确的名称缩写，不借用其他品牌图标。
- 缩写项：Firecrawl、小云雀、Spline、OpenCLI、Apify、DataForSEO、ImageMagick、Remotion、Playwright、itch.io、Printful、Marvelous Designer、CLO、Tally。新增自定义提供方也使用缩写。
- `studio` / `local` 只有精确 `tripo.studio.*` / `tripo.server.*` 工具命名空间显示 Tripo3D；其他扩展保留自己的标识。
- 图标仅用于识别，不表示登录、安装、授权或可用。所有状态、确认、凭证写入和 30 分钟授权边界保持原样。

## 资源与来源

`src/agent_tool_maker/data/web/brand-data.js` 保存经过检查的 SVG image data URL；`brands.js` 负责静态映射与缩写。运行时不查询外部图标服务、不接受供应商指定的图片地址。原有 CSP 的 `img-src 'self' data:` 和其他限制保持原样。

`brand-sources.json` 保存每项来源、上游 SHA-256、打包 SVG SHA-256 与许可元数据。`brand-licenses.txt` 随 wheel 保留完整 CC0 和 MIT 文本。品牌商标归各自所有者；显示不代表合作关系。

- [Simple Icons](https://github.com/simple-icons/simple-icons)：固定提交 `98820a4dc8c363ca72fa2c0d294ea4a0a9bba75d`；Canva / Slack 来自固定 `13.21.0` 静态集合。
- [Lobe Icons](https://github.com/lobehub/lobe-icons)：仅静态 SVG，固定 `@lobehub/icons-static-svg@1.95.1`，保留 MIT 声明。
- Higgsfield：2026-10-05 [官方公开首页](https://higgsfield.ai/)导航中的矢量标识；保存来源快照摘要。

维护者先审核下载目录的 `inventory.json`、来源与每项摘要，再运行 `python scripts/build_brand_assets.py /absolute/reviewed/inventory.json`。该构建器没有网络访问，只接受有 viewBox 的 SVG/path/title、有限属性，拒绝主动内容、外部引用、样式注入、实体声明及超限文件。

## 验收（2026-10-05）

- Node：31 项通过（8 项品牌映射/摘要测试、23 项现有 Passkey 前端回归）。
- Python：60 项通过（14 项 SVG 边界、39 项真实本地 HTTP、2 项原生 Chrome 品牌页面、4 项原生虚拟认证器 Passkey、1 项 HTTP 桥接 UI）。
- 原生 Chrome 使用隔离假凭证，检查 1440px / 390px 总览、工具目录、连接、客户端；图标解码、搜索、图标导航、工具开关、详情、锁定通过；截图已目视检查。
- 图标/导航只读路径没有 POST 或供应商请求；假凭证前后字节相同。虚拟认证器不是 1Password 实际验收。
- 回执与隔离截图：`/private/tmp/atm-brand-logos-20261005/`。真实账户登录/扣费未参与这些测试。
- 本机现有运行时已做可恢复更新，安装包 83 个代码/资源文件与测试 wheel 逐字节一致；实际安装包再次运行 46 项原生/HTTP/UI 回归全部通过。备份：`~/.local/pipx/upgrade-backups/20261005-brand-logos/`。wheel SHA-256：`08d19e58eee1a72ad1526d05e0bc01a0a526cecdcc9ef4b0b226d08917c305b5`；保留已有 vault、登录文件、依赖和旧窗口。
