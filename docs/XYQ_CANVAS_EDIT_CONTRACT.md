# 小云雀画布编辑契约

**当前暂缓**：用户已将本期范围收敛到图像/视频/音频生成，见 XYQ_MEDIA_CONTRACT.md。
以下保存已完成实验的源码合同与证据，不再扩展复杂工作区。

## Strategy note

- Strategy: UI_SELECTOR
- Contract: visible-ui
- Evidence: 获准测试项目内 `react-flow__node-biz/text` 的
  `.xyq-text-node-editor`，选中编辑时 true、只读时 false。
  浮动工具栏的语义锚点是 `[data-xyq-text-toolbar="true"]` 与 `button[aria-label][aria-pressed]`。
- Auth source: browser-owned; no authentication capture or state copying.
- Replay: 当前纯文本已通过真实 UI 创建/编辑与新页面回读；CLI 源操作和格式更改各自验收。

## 文本读取和准备

绑定当前 project_id/canvas_id/node_id 和 `expected_content_sha256`。
摘要覆盖完整 HTML 内容，不只是可见纯文本；同文本不同格式属于不同原稿。
`text_inspect` 不激活编辑器、不输出 HTML/文本原文。
`text_prepare` 只发原生编辑输入，不调用生成按钮。目标及其它节点、未提交的编辑器、已有弹层均受检查。
`text` 表示显式替换该节点的全部内容；现存链接、媒体或非文本结构保留并报需专门编辑契约。
传入文本按文字键入，不作为 HTML 执行。

格式作用于整个节点文本，而非当前光标未来输入状态。
原生全选后必须读到选区在目标编辑器内且覆盖全部文字；未知选区立即停止。
每次格式设置后读取实际内容标签与全量覆盖，不将工具栏 aria-pressed 当成文本已变更的证明。
CUA 的 DOM 重建不返回 Selection；只切换粗体开关时，文本没有 strong 标签。
原生全选加 tab-scoped CDP **只读** Selection 后，实际源码验证了完整 body 格式。
CUA 不支持原始 CDP Input，使用其公开高层原生快捷键；仍要求全选回读，未伪造成功。
普通未暴露选区的后端继续报 selection_unknown。

标题/引用格式会让 Tiptap 添加尾部空段落。完整 HTML 仍进入原稿摘要；
字面 text node/显式 hard-break 流与 innerText 排版换行分别观测。
格式变更必须保持前者，后者的变化返回 implicit_changes.rendered_text，
不静默把新增实际字符或硬换行当成格式成功。
文本节点自带的非模态生成 footer 以确切双 data 属性和唯一活动编辑器识别；
其中草稿进入上下文保护，其他 dialog/menu/listbox 仍拦住编辑。生成按钮不操作。

支持的语义字段为 heading（null/1/2/3）、quote、bold、italic、underline、strike。
颜色、链接、横线、局部选区和混合样式另建对应合同，不假称全部格式已完成。
错误含 phase/completed_steps，既有内容不自动回滚、不重试未知结果的输入。
`saving=false` 或准备完成不构成服务端持久化；使用独立页面回读验证。

## 画布与后续节点

节点新增、移动、缩放、连线、3D 导演台、多轨和删除分别验收。
创建操作使用稳定请求键、写前回执和不确定结果检查；当前项目不重复创建。
删除保持产品恢复机制和用户确认门槛。上传、生成、消费及发布各自批准。

## 暂缓前的实验验收

- Node 文本协议 16 项；隔离原生 Chrome 7 项，包括部分/折叠选区、光标假成功、
  自带 footer 草稿与其它弹层。综合回归见 XYQ_WEB_COVERAGE.md。
- 首轮 Quote 假夹具 innerHTML 替换破坏 live Range；改用夹具的原生编辑操作后原断言通过，
  没有移除 collapsed/full 选区保护。假标题的默认 CSS 粗体与显式标记也分开处理。
- 实际获准测试节点：heading=2、quote/bold/italic/underline/strike=true 均读到 body 标签；
  整段原生输入与回读经过实际 text.mjs，不是已安装 OpenCLIApp CLI 的验收。
- 测试文字与全部格式已恢复原值，完整 HTML 摘要回到
  `f0c63fb32a2b02f51a3aa96e83db626b969cbcb5822ad7fcb1be5bdefe4bac79`。
  没有进一步新建节点或开展 3D/故事板/时间线。此前文本持久化与本轮格式 DOM 验收分开。
