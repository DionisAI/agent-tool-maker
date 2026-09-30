# ATM v0.2 · 可发现动作目录

共 157 个入口。native = 执行适配器已实现；bridge = 通用 MCP 协议入口；handoff/browser = 任务交接，不能当作自动执行。

任何动作的账号、CLI、MCP 服务器或桌面应用仍需用户配置。`atm describe ID` 是输入 schema、例子和权限的可执行来源。

| ID | 适配器 / 实现 | 声明权限 | 可能计费 | 本版动作 | 来源 |
|---|---|---|---|---|
| `elevenlabs.tts` | elevenlabs / native | 按已配置权限读取/本地操作 | 是/未知价格 | ElevenLabs 文字转语音 / narration | [文档1](https://elevenlabs.io/docs/api-reference/text-to-speech/convert) |
| `fal.generate` | fal / native | 按已配置权限读取/本地操作 | 是/未知价格 | fal 多模型图片、视频、音频、3D | [文档1](https://fal.ai/docs/documentation/model-apis/inference/queue) |
| `higgsfield.generate` | higgsfield / native | 按已配置权限读取/本地操作 | 是/未知价格 | Higgsfield API 图片 / 视频 | [文档1](https://docs.higgsfield.ai/docs/quickstart) |
| `tripo.text_to_3d` | tripo / native | 按已配置权限读取/本地操作 | 是/未知价格 | Tripo 文本生成 GLB / text to 3D | [文档1](https://developers.tripo3d.ai/en/docs/sdk) |
| `exa.search` | exa / native | 按已配置权限读取/本地操作 | 是/未知价格 | Exa 网页搜索 / web research | [文档1](https://exa.ai/docs/reference/search) |
| `firecrawl.scrape` | firecrawl / native | 按已配置权限读取/本地操作 | 是/未知价格 | Firecrawl 网页转 Markdown | [文档1](https://docs.firecrawl.dev/api-reference/endpoint/scrape) |
| `xyq.image` | xyq / native | 按已配置权限读取/本地操作 | 是/未知价格 | 小云雀 CLI image | [文档1](https://github.com/Pippit-dev/cli) |
| `xyq.video` | xyq / native | 按已配置权限读取/本地操作 | 是/未知价格 | 小云雀 CLI video | [文档1](https://github.com/Pippit-dev/cli) |
| `ffmpeg.probe` | ffprobe / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | ffprobe 检查媒体格式与时长 | [文档1](https://ffmpeg.org/ffprobe.html) |
| `ffmpeg.audio_to_mp3` | ffmpeg / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | FFmpeg 本地音频转 MP3 | [文档1](https://ffmpeg.org/ffmpeg.html) |
| `tripo.web` | browser / browser | 按已配置权限读取/本地操作 | 是/未知价格 | Tripo Studio 网页生成 3D | [文档1](https://www.tripo3d.ai/help/api-plugins/how-to-use-tripo-api) |
| `higgsfield.web` | browser / browser | 按已配置权限读取/本地操作 | 是/未知价格 | Higgsfield 网页会员创作 | [文档1](https://higgsfield.ai/) |
| `elevenlabs.web` | browser / browser | 按已配置权限读取/本地操作 | 是/未知价格 | ElevenLabs 网页语音 | [文档1](https://elevenlabs.io/text-to-speech-api) |
| `meshy.web` | browser / browser | 按已配置权限读取/本地操作 | 是/未知价格 | Meshy 网页生成 3D | [文档1](https://www.meshy.ai/) |
| `suno.web` | browser / browser | 按已配置权限读取/本地操作 | 是/未知价格 | Suno 网页音乐 | [文档1](https://suno.com/) |
| `runway.web` | browser / browser | 按已配置权限读取/本地操作 | 是/未知价格 | Runway 网页视频 | [文档1](https://runway.com/) |
| `recraft.web` | browser / browser | 按已配置权限读取/本地操作 | 是/未知价格 | Recraft 网页图片设计 | [文档1](https://www.recraft.ai/) |
| `canva.web` | browser / browser | 按已配置权限读取/本地操作 | 是/未知价格 | Canva 网页排版与素材 | [文档1](https://www.canva.com/) |
| `spline.web` | browser / browser | 按已配置权限读取/本地操作 | 是/未知价格 | Spline 网页 3D 设计 | [文档1](https://spline.design/) |
| `photopea.web` | browser / browser | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Photopea 网页图片编辑 | [文档1](https://www.photopea.com/) |
| `pexels.web` | browser / browser | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Pexels 可授权图片与视频素材 | [文档1](https://www.pexels.com/license/) |
| `youtube.web` | browser / browser | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | YouTube 搜索、引用与嵌入 | [文档1](https://developers.google.com/youtube/terms/developer-policies) |
| `opencli.list` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | OpenCLI command registry | [文档1](https://github.com/jackwener/OpenCLI) |
| `opencli.doctor` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | OpenCLI browser connection diagnostics | [文档1](https://github.com/jackwener/OpenCLI) |
| `opencli.hackernews_top` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Hacker News top stories | [文档1](https://github.com/jackwener/OpenCLI) |
| `opencli.bilibili_hot` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Bilibili trending discussions | [文档1](https://github.com/jackwener/OpenCLI) |
| `opencli.zhihu_hot` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Zhihu trending discussions | [文档1](https://github.com/jackwener/OpenCLI) |
| `opencli.browser_state` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read an existing browser session state | [文档1](https://github.com/jackwener/OpenCLI) |
| `apify.run` | rest / native | external_write | 是/未知价格 | Start a selected Apify Actor | [文档1](https://docs.apify.com/cli/docs) |
| `apify.run_status` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read existing Actor run | [文档1](https://docs.apify.com/cli/docs) |
| `apify.dataset_items` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Retrieve one bounded dataset page | [文档1](https://docs.apify.com/cli/docs) |
| `dataforseo.search_volume` | rest / native | 按已配置权限读取/本地操作 | 是/未知价格 | Keyword search-volume request | [文档1](https://dataforseo.com/apis/keyword-data-api) |
| `youtube.search` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Search YouTube metadata (OAuth bearer) | [文档1](https://developers.google.com/youtube/v3/docs) |
| `youtube.comments` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read one page of YouTube comment threads | [文档1](https://developers.google.com/youtube/v3/docs) |
| `opencli.xiaohongshu_search` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | 小红书 search notes | [文档1](https://github.com/jackwener/OpenCLI) |
| `opencli.xiaohongshu_note` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | 小红书 read signed note URL | [文档1](https://github.com/jackwener/OpenCLI) |
| `opencli.xiaohongshu_comments` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | 小红书 comments and replies | [文档1](https://github.com/jackwener/OpenCLI) |
| `opencli.twitter_search` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | X/Twitter live search | [文档1](https://github.com/jackwener/OpenCLI) |
| `opencli.reddit_read` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read Reddit thread and bounded replies | [文档1](https://github.com/jackwener/OpenCLI) |
| `opencli.upwork_search` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read Upwork search via existing OpenCLI browser login | [文档1](https://support.upwork.com/hc/en-us/articles/115015857647-How-to-request-an-API-key-from-Upwork) / [文档2](https://support.upwork.com/hc/en-us/sections/17976982721555-Upwork-API) |
| `opencli.upwork_detail` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read Upwork job details without applying or hiring | [文档1](https://support.upwork.com/hc/en-us/articles/115015857647-How-to-request-an-API-key-from-Upwork) / [文档2](https://support.upwork.com/hc/en-us/sections/17976982721555-Upwork-API) |
| `gws.drive_files` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Google Workspace drive_files | [文档1](https://github.com/googleworkspace/cli) |
| `gws.gmail_messages` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Google Workspace gmail_messages | [文档1](https://github.com/googleworkspace/cli) |
| `gws.calendar_events` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Google Workspace calendar_events | [文档1](https://github.com/googleworkspace/cli) |
| `notion.search` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Search connected Notion workspace | [文档1](https://developers.notion.com/guides/mcp/overview) |
| `notion.create_page` | rest / native | external_write | 无额外计费标记，不等于服务免费 | Create a Notion page | [文档1](https://developers.notion.com/guides/mcp/overview) |
| `linear.issues` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read Linear issues | [文档1](https://linear.app/docs/mcp) |
| `linear.create_issue` | rest / native | external_write | 无额外计费标记，不等于服务免费 | Create a Linear issue | [文档1](https://linear.app/docs/mcp) |
| `typeform.forms` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | List Typeform forms | [文档1](https://www.typeform.com/developers/) |
| `typeform.responses` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read Typeform responses | [文档1](https://www.typeform.com/developers/) |
| `typeform.create` | rest / native | external_write | 无额外计费标记，不等于服务免费 | Create a Typeform survey | [文档1](https://www.typeform.com/developers/) |
| `pandoc.to_markdown` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Convert a local document to Markdown | [文档1](https://pandoc.org/MANUAL.html) |
| `pandoc.to_docx` | command / native | execute_code | 无额外计费标记，不等于服务免费 | Convert local Markdown to DOCX | [文档1](https://pandoc.org/MANUAL.html) |
| `freelancer.active_projects` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Search active Freelancer projects | [文档1](https://developers.freelancer.com/) |
| `figma.file` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read a Figma file tree | [文档1](https://developers.figma.com/docs/figma-mcp-server/tools-and-prompts/) / [文档2](https://developers.figma.com/docs/figma-mcp-server/write-to-canvas/) |
| `comfyui.queue` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read explicitly configured local ComfyUI queue | [文档1](https://docs.comfy.org/development/comfyui-server/comms_routes) |
| `comfyui.submit` | rest / native | execute_code | 是/未知价格 | Submit an approved local ComfyUI workflow | [文档1](https://docs.comfy.org/development/comfyui-server/comms_routes) |
| `comfyui.history` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Get completed ComfyUI history | [文档1](https://docs.comfy.org/development/comfyui-server/comms_routes) |
| `pexels.photos` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Search Pexels stock photos | [文档1](https://www.pexels.com/api/documentation/) |
| `pexels.videos` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Search Pexels stock video | [文档1](https://www.pexels.com/api/documentation/) |
| `imagemagick.resize` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Resize a local raster image | [文档1](https://imagemagick.org/command-line-tools/) |
| `imagemagick.webp` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Convert a raster image to WebP | [文档1](https://imagemagick.org/command-line-tools/) |
| `ffmpeg.trim` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Trim a local video or audio clip | [文档1](https://ffmpeg.org/ffmpeg.html) / [文档2](https://ffmpeg.org/ffprobe.html) |
| `ffmpeg.thumbnail` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Extract a video thumbnail | [文档1](https://ffmpeg.org/ffmpeg.html) / [文档2](https://ffmpeg.org/ffprobe.html) |
| `remotion.compositions` | command / native | execute_code | 无额外计费标记，不等于服务免费 | Inspect a trusted Remotion project | [文档1](https://www.remotion.dev/docs/cli) |
| `remotion.render` | command / native | execute_code | 无额外计费标记，不等于服务免费 | Render an existing Remotion composition | [文档1](https://www.remotion.dev/docs/cli) |
| `whisper.transcribe` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Transcribe local WAV with whisper.cpp | [文档1](https://github.com/ggml-org/whisper.cpp) |
| `blender.inspect` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Inspect a blend project without auto-run scripts | [文档1](https://docs.blender.org/api/current/) / [文档2](https://docs.blender.org/manual/zh-hans/4.4/advanced/command_line/arguments.html) |
| `blender.render` | command / native | execute_code | 无额外计费标记，不等于服务免费 | Render one frame of an approved blend project | [文档1](https://docs.blender.org/api/current/) / [文档2](https://docs.blender.org/manual/zh-hans/4.4/advanced/command_line/arguments.html) |
| `gltf.inspect` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Inspect glTF/GLB structure | [文档1](https://gltf-transform.dev/cli) |
| `gltf.optimize` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Optimize a GLB for web delivery | [文档1](https://gltf-transform.dev/cli) |
| `kicad.drc` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Run PCB design-rule checks | [文档1](https://docs.kicad.org/9.0/en/cli/cli.html) |
| `kicad.gerbers` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Export PCB Gerber files | [文档1](https://docs.kicad.org/9.0/en/cli/cli.html) |
| `github.repo` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | GitHub repo | [文档1](https://cli.github.com/manual/) |
| `github.issues` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | GitHub issues | [文档1](https://cli.github.com/manual/) |
| `github.runs` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | GitHub runs | [文档1](https://cli.github.com/manual/) |
| `github.pr_checks` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | GitHub pr_checks | [文档1](https://cli.github.com/manual/) |
| `github.create_issue` | command / native | external_write | 无额外计费标记，不等于服务免费 | Create GitHub issue | [文档1](https://cli.github.com/manual/) |
| `docker.ps` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Inspect Docker containers | [文档1](https://docs.docker.com/reference/cli/docker/) |
| `docker.build` | command / native | execute_code | 无额外计费标记，不等于服务免费 | Build an approved Docker project | [文档1](https://docs.docker.com/reference/cli/docker/) |
| `playwright.test` | command / native | execute_code | 无额外计费标记，不等于服务免费 | Run existing trusted Playwright tests | [文档1](https://github.com/microsoft/playwright-mcp) |
| `wrangler.deployments` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read Worker deployment history | [文档1](https://developers.cloudflare.com/workers/wrangler/) / [文档2](https://developers.cloudflare.com/workers/wrangler/commands/) |
| `wrangler.build` | command / native | execute_code | 无额外计费标记，不等于服务免费 | Build Worker without deployment | [文档1](https://developers.cloudflare.com/workers/wrangler/) / [文档2](https://developers.cloudflare.com/workers/wrangler/commands/) |
| `wrangler.preview` | command / native | external_write, execute_code | 是/未知价格 | Create Worker preview deployment (requires compatible Wrangler) | [文档1](https://developers.cloudflare.com/workers/wrangler/) / [文档2](https://developers.cloudflare.com/workers/wrangler/commands/) |
| `wrangler.deploy` | command / native | external_write, production, execute_code | 是/未知价格 | Deploy Worker to named environment | [文档1](https://developers.cloudflare.com/workers/wrangler/) / [文档2](https://developers.cloudflare.com/workers/wrangler/commands/) |
| `wrangler.d1_list` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | List D1 databases | [文档1](https://developers.cloudflare.com/workers/wrangler/) / [文档2](https://developers.cloudflare.com/workers/wrangler/commands/) |
| `wrangler.d1_local` | command / native | execute_code | 无额外计费标记，不等于服务免费 | Execute reviewed local D1 SQL | [文档1](https://developers.cloudflare.com/workers/wrangler/) / [文档2](https://developers.cloudflare.com/workers/wrangler/commands/) |
| `cloudflared.tunnels` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | List named Cloudflare tunnels | [文档1](https://developers.cloudflare.com/tunnel/get-started/) |
| `cloudflare.dns_list` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read Cloudflare DNS records | [文档1](https://developers.cloudflare.com/api/resources/dns/subresources/records/) |
| `cloudflare.dns_create` | rest / native | external_write, production | 无额外计费标记，不等于服务免费 | Create a Cloudflare DNS record | [文档1](https://developers.cloudflare.com/api/resources/dns/subresources/records/) |
| `vercel.list` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | List Vercel deployments | [文档1](https://vercel.com/docs/cli) |
| `vercel.preview` | command / native | external_write, execute_code | 是/未知价格 | Deploy Vercel preview | [文档1](https://vercel.com/docs/cli) |
| `vercel.production` | command / native | external_write, production, execute_code | 是/未知价格 | Deploy Vercel production | [文档1](https://vercel.com/docs/cli) |
| `supabase.projects` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | List Supabase projects | [文档1](https://supabase.com/docs/reference/cli/introduction) |
| `supabase.migrations` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | List linked Supabase migrations | [文档1](https://supabase.com/docs/reference/cli/introduction) |
| `supabase.db_push` | command / native | external_write, production, execute_code | 是/未知价格 | Apply linked remote database migrations | [文档1](https://supabase.com/docs/reference/cli/introduction) |
| `supabase.function_deploy` | command / native | external_write, production, execute_code | 是/未知价格 | Deploy one Supabase function | [文档1](https://supabase.com/docs/reference/cli/introduction) |
| `eas.build_list` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | List Expo EAS builds | [文档1](https://docs.expo.dev/eas/) |
| `eas.build` | command / native | external_write, execute_code | 是/未知价格 | Submit an Expo build, without waiting | [文档1](https://docs.expo.dev/eas/) |
| `godot.export` | command / native | execute_code | 无额外计费标记，不等于服务免费 | Export an existing Godot project | [文档1](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html) |
| `butler.status` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read itch.io channel status | [文档1](https://itch.io/docs/butler/) |
| `butler.push` | command / native | external_write | 无额外计费标记，不等于服务免费 | Upload a game archive to itch.io | [文档1](https://itch.io/docs/butler/) |
| `buffer.channels` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | List connected Buffer channels | [文档1](https://developers.buffer.com/guides/cli.html) / [文档2](https://buffer.com/resources/buffer-api-is-here/) |
| `buffer.posts` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read posts for a specific channel | [文档1](https://developers.buffer.com/guides/cli.html) / [文档2](https://buffer.com/resources/buffer-api-is-here/) |
| `buffer.schedule` | command / native | external_write | 是/未知价格 | Add a post to a channel queue | [文档1](https://developers.buffer.com/guides/cli.html) / [文档2](https://buffer.com/resources/buffer-api-is-here/) |
| `buffer.schema` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read post creation schema from installed Buffer version | [文档1](https://developers.buffer.com/guides/cli.html) / [文档2](https://buffer.com/resources/buffer-api-is-here/) |
| `postiz.integrations` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read Postiz connected channels | [文档1](https://github.com/gitroomhq/postiz-app) / [文档2](https://github.com/gitroomhq/postiz-agent) |
| `postiz.posts` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read Postiz scheduled posts | [文档1](https://github.com/gitroomhq/postiz-app) / [文档2](https://github.com/gitroomhq/postiz-agent) |
| `wordpress.posts` | command / native | execute_code | 无额外计费标记，不等于服务免费 | List WordPress posts | [文档1](https://developer.wordpress.org/cli/commands/) |
| `wordpress.draft` | command / native | external_write, execute_code | 无额外计费标记，不等于服务免费 | Create WordPress draft from local content | [文档1](https://developer.wordpress.org/cli/commands/) |
| `ghost.posts` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | List Ghost posts | [文档1](https://docs.ghost.org/admin-api/) |
| `ghost.draft` | rest / native | external_write | 无额外计费标记，不等于服务免费 | Create a Ghost draft | [文档1](https://docs.ghost.org/admin-api/) |
| `stripe.products` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | List Stripe products | [文档1](https://docs.stripe.com/cli) |
| `stripe.checkout_test` | rest / native | external_write | 无额外计费标记，不等于服务免费 | Create a Stripe test checkout session | [文档1](https://docs.stripe.com/cli) |
| `stripe.events` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | List Stripe events in CLI | [文档1](https://docs.stripe.com/cli) |
| `shopify.theme_list` | command / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | List Shopify themes | [文档1](https://shopify.dev/docs/api/shopify-cli) |
| `shopify.products` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read Shopify product records | [文档1](https://shopify.dev/docs/api/admin-graphql/latest) |
| `shopify.product_draft` | rest / native | external_write | 无额外计费标记，不等于服务免费 | Create a Shopify product draft | [文档1](https://shopify.dev/docs/api/admin-graphql/latest) |
| `printful.products` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read Printful product catalog | [文档1](https://developers.printful.com/docs/) |
| `printful.order_draft` | rest / native | external_write | 无额外计费标记，不等于服务免费 | Create an unconfirmed Printful order | [文档1](https://developers.printful.com/docs/) |
| `resend.send` | rest / native | external_write | 是/未知价格 | Send an explicitly approved email | [文档1](https://resend.com/docs/introduction) |
| `hubspot.contacts` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read one page of HubSpot contacts | [文档1](https://developers.hubspot.com/docs/api-reference/latest/overview) |
| `slack.history` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read authorized channel history | [文档1](https://docs.slack.dev/apis/) |
| `slack.send` | rest / native | external_write | 无额外计费标记，不等于服务免费 | Send an approved Slack message | [文档1](https://docs.slack.dev/apis/) |
| `telegram.me` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Inspect the configured Telegram bot | [文档1](https://core.telegram.org/bots/api) |
| `telegram.send` | rest / native | external_write | 无额外计费标记，不等于服务免费 | Send an approved message to a chat | [文档1](https://core.telegram.org/bots/api) |
| `posthog.query` | rest / native | 按已配置权限读取/本地操作 | 是/未知价格 | Run a project analytics query | [文档1](https://posthog.com/product-analytics) / [文档2](https://posthog.com/docs/model-context-protocol/cursor) |
| `sentry.issues` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read Sentry project issues | [文档1](https://mcp.sentry.dev/) |
| `search_console.sites` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | List authorized Search Console sites | [文档1](https://developers.google.com/webmaster-tools/) |
| `youtube.analytics` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read authorized channel analytics | [文档1](https://developers.google.com/youtube/analytics) |
| `n8n.workflows` | rest / native | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Read configured n8n workflow page | [文档1](https://docs.n8n.io/api) |
| `n8n.activate` | rest / native | external_write, production, execute_code | 是/未知价格 | Activate an existing n8n workflow | [文档1](https://docs.n8n.io/api) |
| `marvelous_designer.handoff` | desktop / handoff | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Marvelous Designer garment workflow | [文档1](https://developer.marvelousdesigner.com/) / [文档2](https://developer.marvelousdesigner.com/python.html) |
| `clo.handoff` | desktop / handoff | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | CLO garment and BOM workflow | [文档1](https://developer.clo3d.com/) / [文档2](https://support.clo3d.com/hc/en-us/articles/115000525207-BOM-XML-Export) |
| `freecad.handoff` | desktop / handoff | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | FreeCAD parametric engineering handoff | [文档1](https://www.freecad.org/features.php) |
| `photopea.handoff` | desktop / handoff | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Photopea layered source editing | [文档1](https://www.photopea.com/api/) |
| `upwork.handoff` | human / handoff | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Upwork quotation and expert handoff | [文档1](https://support.upwork.com/hc/en-us/articles/115015857647-How-to-request-an-API-key-from-Upwork) / [文档2](https://support.upwork.com/hc/en-us/sections/17976982721555-Upwork-API) |
| `fiverr.handoff` | human / handoff | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Fiverr expert handoff | [文档1](https://www.fiverr.com/) |
| `freelancer.handoff` | human / handoff | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Freelancer expert handoff | [文档1](https://developers.freelancer.com/) |
| `tally.handoff` | browser / handoff | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Tally survey and webhook setup | [文档1](https://tally.so/help/webhooks) |
| `google_trends.handoff` | browser / handoff | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Google Trends browser research | [文档1](https://developers.google.com/search/apis/trends) |
| `tiktok_posting.handoff` | browser / handoff | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | TikTok publishing approval | [文档1](https://developers.tiktok.com/docs/en/content-posting-api-get-started) |
| `google_ads.handoff` | browser / handoff | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | Google Ads review and reporting handoff | [文档1](https://developers.google.com/google-ads/api/docs/get-started/introduction) |
| `figma.mcp_tools` | mcp / bridge | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | figma MCP tools | [文档1](https://developers.figma.com/docs/figma-mcp-server/tools-and-prompts/) / [文档2](https://developers.figma.com/docs/figma-mcp-server/write-to-canvas/) |
| `figma.mcp_batch` | mcp / bridge | external_write, execute_code | 是/未知价格 | figma MCP batch | [文档1](https://developers.figma.com/docs/figma-mcp-server/tools-and-prompts/) / [文档2](https://developers.figma.com/docs/figma-mcp-server/write-to-canvas/) |
| `notion.mcp_tools` | mcp / bridge | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | notion MCP tools | [文档1](https://developers.notion.com/guides/mcp/overview) |
| `notion.mcp_batch` | mcp / bridge | external_write, execute_code | 是/未知价格 | notion MCP batch | [文档1](https://developers.notion.com/guides/mcp/overview) |
| `linear.mcp_tools` | mcp / bridge | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | linear MCP tools | [文档1](https://linear.app/docs/mcp) |
| `linear.mcp_batch` | mcp / bridge | external_write, execute_code | 是/未知价格 | linear MCP batch | [文档1](https://linear.app/docs/mcp) |
| `playwright.mcp_tools` | mcp / bridge | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | playwright MCP tools | [文档1](https://github.com/microsoft/playwright-mcp) |
| `playwright.mcp_batch` | mcp / bridge | external_write, execute_code | 是/未知价格 | playwright MCP batch | [文档1](https://github.com/microsoft/playwright-mcp) |
| `chrome_devtools.mcp_tools` | mcp / bridge | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | chrome_devtools MCP tools | [文档1](https://github.com/ChromeDevTools/chrome-devtools-mcp) |
| `chrome_devtools.mcp_batch` | mcp / bridge | external_write, execute_code | 是/未知价格 | chrome_devtools MCP batch | [文档1](https://github.com/ChromeDevTools/chrome-devtools-mcp) |
| `posthog.mcp_tools` | mcp / bridge | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | posthog MCP tools | [文档1](https://posthog.com/product-analytics) / [文档2](https://posthog.com/docs/model-context-protocol/cursor) |
| `posthog.mcp_batch` | mcp / bridge | external_write, execute_code | 是/未知价格 | posthog MCP batch | [文档1](https://posthog.com/product-analytics) / [文档2](https://posthog.com/docs/model-context-protocol/cursor) |
| `sentry.mcp_tools` | mcp / bridge | 按已配置权限读取/本地操作 | 无额外计费标记，不等于服务免费 | sentry MCP tools | [文档1](https://mcp.sentry.dev/) |
| `sentry.mcp_batch` | mcp / bridge | external_write, execute_code | 是/未知价格 | sentry MCP batch | [文档1](https://mcp.sentry.dev/) |
