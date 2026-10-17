# 小云雀媒体产物校验

## Strategy note

- Strategy: LOCAL；Contract: decoded local file + fixed tool definition。
- Evidence: 已安装Pillow；本机已安装FFmpeg/ffprobe 8.1.2，fd协议支持可寻址的已打开文件描述符。
- Auth source: 无。只读明确项目内选定的媒体文件，不读浏览器、vault、会话或profile，不联网。
- Replay: 先校验预期SHA，再由固定解码器读取同一打开的普通文件，末尾核对文件/路径仍一致。
  浏览器任务行/下载的实际UI合同尚待真实记录；本模块先接入交付链的字节/媒体验证，不伪造上游证据。

## 本期交付组件

只有atm命令，新增atm media inspect；工具工厂另生成xyq.media.artifact_inspect。
网页工具编译器维持原18个定义/路由，本地校验单独编译，不加载新浏览器适配器或扩大浏览器范围。
file是项目内相对路径，kind为image/audio/video，expected_sha256必填。
普通文件/目录逐级无symlink打开，文件大小、类型、容器完整性、解码及前后摘要分别核对。
HTML错误页、后缀伪装、截断文件、哈希/路径竞态和未知解码器结果不得记为媒体交付。

支持目标为PNG/JPEG/WebP静态图、PCM WAV、MP3、MP4；这是本地校验器范围，
不是已观察到网页全部输出格式。PNG/JPEG/WebP需verify后重新打开并实际load，
WAV校验RIFF长度与全部PCM帧；MP3/MP4需结构核对、ffprobe字段白名单及完整FFmpeg解码。
FFmpeg/ffprobe固定绝对路径和SHA写入定义；执行前后核对，不从输入传任意命令或切换工具。
仅fd输入协议，不给解码器媒体路径/URL；MOV外部引用与绝对外部路径读取保持关闭。
进程/输出/媒体大小、像素、声道、时长均有界；超限明确报错，不降级为只读头部成功。
媒体元数据只输出类型/格式/尺寸/采样率/声道/时长/帧数等白名单，不输出EXIF/标签/提示词/URL。

artifact_verified只证明所选本地字节通过校验，task_association_verified、
provider_generation_verified、download_verified保持false。
artifact_rejected是已完成的条件检查负例，reason/phase明确；生成ATM job的completed不是文件有效。
直接inspect负例退出2；内部固定adapter可返回明确负例列表，供ATM留存诊断，不伪造成功。
依赖/执行/协议故障保持错误，与媒体条件负例分开。新request-key才做新文件检查，
同键复用历史回执，不当作当下文件仍有效的证明。

## 实现与早期源码验收

新源码src/agent_tool_maker/media.py；仅在原CLI增加media解析与无Router的本地执行分支。
直接inspect不初始化ATM状态，不取Key；固定adapter经工具工厂/权限/job/产物回执运行。
单独编译器scripts/build_xyq_media.py，生成generated/xyq-media-delivery-stage/artifact_inspect/；
网页编译默认18个定义与各闭包保持，未加载新的浏览器注册。
validator pin：7ea6f054a0568b17de0554e44ad35c1b2027c968dfda11218b04c5782b292efd；
本机definition SHA：3f5d83af53a1ffcb8a50654b0b9738e995ca1f0832e259f2e08c3cacd2c629a4。
解码依赖本机既有Pillow12.3.0、FFmpeg/ffprobe8.1.2；没有安装或升级依赖。
路径与FFmpeg二进制SHA写入生成定义，移到另一机器应重新审阅并编译其本地工具路径，
不复制登录态，也不把此单包当作服务器浏览器或网页完整CLI。

限制：文件512MiB、图像/视频4000万像素、时长3600秒、声道最多16、采样率8–384kHz，
单解码进程120秒、诊断合计128KiB、容器chunk/box最多10000。
PCM逐帧长度验证；MP3 Layer-III帧边界/ID3长度与MP4每个顶层box长度先检查。
动画图/未知格式/自由MP3码率/未知stream布局明确分列，不猜网页其它输出格式。
FFprobe的container duration和FFmpeg解码output timestamp分开保留，均非计费时长。
依赖改变、进程崩溃/超时/输出超限、协议形状错误不转换为条件负例或成功。

新增56项本地单元/实际子进程测试；扩展小云雀/CLI/quickstart全套422通过，零失败/跳过。
覆盖六格式实际解码、CRC正确但像素流损坏、box完整但packet损坏、截断/伪后缀/HTML、
符号/硬链接/FIFO、字节/叶路径/祖先路径竞态、哈希/pin/依赖保护、进程/隐私边界、
直接CLI退出码、条件负例与生成CLI同键历史复用/新键新检查。
现有232项原生浏览器测试仍使用夹具响应或终止供应商请求；浏览器策略保持。
Node源码未变，沿用与原各闭包一致的218通过回执，并非本轮新增Node回归。

首轮focused2失败根因是测试用-m agent_tool_maker.cli仅导入模块而没有调用main；
改用既有-m agent_tool_maker入口，保留全部退出码/JSON断言及旧失败记录。
初轮扩展3失败为旧TemporaryDirectory的/var符号链接路径和README106行；
用TMPDIR=/private/tmp保持原路径保护，README收敛至90行，细节留在合同/Skill，
原断言和安全检查保持。初轮运行期间有最后的duration类型/输出时长补充，故终验以完整fresh r2为准。
最终回归/private/tmp/atm-xyq-media-delivery-all-20261007-r2.xml与同名txt；
历史focused/扩展失败回执均保留。

## 实际本地生成 CLI 链路

临时source-atm可执行包装实际仓库CLI，不是返回固定结果的假程序。
生成tool.py→新隔离ATM（仅1定义）→真实源码ATM media adapter→本地解码器通过：
PNG/JPEG/WebP蓝色图、1秒PCM WAV、由测试WAV编码的MP3、0.5秒蓝色视频MP4。
6个有效媒体job及1个新键哈希冲突job，共7个不同job；仅execute_code，paid_granted=false。
每个返回摘要/类型/解码信息与限定路径artifact的字节数/SHA/JSON一致，标签不回传。
改变测试PNG后原键仍返回旧job/旧valid=true历史回执；新键返回artifact_rejected/
media_hash_mismatch/valid=false，直接inspect同一负例退出2。原PNG副本仍在测试目录。
completed负例只是检查完成，不是媒体验证通过，也没有任何上游重提。

本轮生产ATM包、vault、用户级Skill、OpenCLIApp与现有注册保持原状；
现有安装来自pipx site-packages，新能力仅仓库源码与隔离包装验收，未升级生产ATM。
没有浏览器操作/下载、上传、生成或扣分，余额没有新读数。
真实回执/private/tmp/atm-xyq-media-delivery-e2e-20261007/verification.json；
详细job/input/产物及合成文件在同目录的work/。最终核对另见
/private/tmp/atm-xyq-media-delivery-final-verification-20261007.json。

真实网页task关联、来源确认、实际下载事件/文件落盘和该文件的本校验链仍待验收。
测试图片准备/用户最终生成许可仍待回复，本轮未新建网页节点或提交生成；完整目标保持进行中。

## 官方依据

[ffprobe](https://ffmpeg.org/ffprobe.html)支持JSON与指定输出字段；
[MOV选项](https://ffmpeg.org/ffmpeg-formats.html#mov_002fmp4_002f3gp)说明外部引用的默认关闭行为；
[Pillow Image](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.verify)
区分结构verify与实际像素load。
[FFmpeg MPEG audio header实现](https://github.com/FFmpeg/FFmpeg/blob/master/libavcodec/mpegaudiodecheader.c)
用于核对Layer-III采样率与帧字节数公式；没有引入新第三方执行代码。
