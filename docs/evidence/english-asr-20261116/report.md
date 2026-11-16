<a id="english-asr-selection-evidence-20261116"></a>
# 本地英文识别小模型选型与本机基线

**2026-11-16结论：先评估 Moonshine Streaming Small 的当前INT8原生运行版本，Medium作为准确率增强候选；Whisper base.en保留为已有环境基线。** 本机为Ryzen AI Max+ 395 / AMD 8060S / 约64GB内存，当前没有CUDA。默认从CPU、2—4线程、单路短语音开始，使语音识别与Jarvis、模型和绘图任务可以共存。

本轮是按本人“先推荐小模型”的要求开展选型。只准备了项目外的Whisper候选数据并完成五段合成录音的离线探测；**没有更换日用识别器、没有升级应用、没有录取本人声音或修改学习成绩**。推荐状态proposed，不能写成已实现自动ASR。权威选择与后续准入在[模型章节](../../models-offline.md#english-asr-model-selection)。

后续需求已扩展为Jarvis通用中文、英文与混说语音聊天；以下保留纯英文阶段的候选对照，Moonshine不据此成为通用默认。最新分工及离线实施门归[共用语音底座](../../models-offline.md#shared-speech-foundation)。

## 对候选的判断

| 候选 | 推荐用途 | 资源和最新进展 | 当前限制 |
|---|---|---|---|
| Moonshine Streaming Small，模型卡123M | 英语情境游戏默认首选候选 | CPU原生/ONNX INT8；实时中间文本；库0.1.6于2026-11-06有Windows x64轮子，推理无需PyTorch/Transformers | 本机未安装/实测；英文模型；需测本人停顿和中国口音 |
| Moonshine Streaming Medium，245M | Small关键内容错误偏多时增强 | 更大的英文流式模型；可同样先走CPU | 不应每句话与Small并跑；额外内存/延迟须实测 |
| Qwen3-ASR-0.6B | 中英切换或中文解释的扩展候选 | 2026系列，30语言及22种中文方言；固定仓库BF16文件约1.876GB | “0.6B”不是整套部署成本；仓库tensor统计约938M，不能按600MB内存估计；本机AMD路径未验 |
| Granite Speech 5.0 470M TurboCTC | 新近准确率/速度对照候选 | 模型卡列2026-10-21多语更新，Apache-2.0；官方BF16权重约946MB | 需要更新的独立运行环境；不能把H200批处理吞吐套到本机单人对话 |
| Parakeet TDT 0.6B v3 | 英文准确率和多欧洲语言对照 | 官方模型卡及2026-11-10 Google LiteRT/MediaPipe部署更新值得跟踪 | 不是新发布的模型本身；当前FP32官方权重约2.508GB，量化/转换产物须另验 |
| Moonshine Streaming Tiny，34M | 极低资源或设备端兜底 | 可CPU运行、更小；英文流式 | 较高识别错误可能把错误转写当学习问题，不优先作为唯一评分输入 |
| Whisper base.en，74M | 不安装新依赖的工程基线 | 已在现有CPU运行时探测，模型数据约294MB | 非最新模型，不是真人准确率证明，现有PyTorch进程开销仍明显 |

以上资源分为权重、运行时和实际进程内存。HF模型卡规模与仓库tensor统计并非总是同一口径：Small仓库序列化tensor统计约140M，Medium约266M；不据此推断架构说明有误，但必须按实际部署产物计算磁盘和内存。HF的FP32文件不是Moonshine原生INT8文件，不能混用体积或准确率。

主要来源：[Moonshine官方模型表](https://github.com/moonshine-ai/moonshine/blob/main/docs/models/available-models.md)、[原生运行库0.1.6](https://pypi.org/project/moonshine-voice/0.1.6/)、[Qwen模型卡](https://huggingface.co/Qwen/Qwen3-ASR-0.6B)、[Granite最新模型卡](https://huggingface.co/ibm-granite/granite-speech-5.0-470m-turboctc)、[Parakeet模型卡](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)、[Google设备端更新](https://developers.googleblog.com/en/on-device-speech-recognition-and-text-to-speech-in-google-ai-edge-gallery/)。固定修订、权重体积及摘要见[candidate-metadata.json](candidate-metadata.json)，运行库发行资料见[moonshine-runtime-candidate.json](moonshine-runtime-candidate.json)。

## 准确率怎样读

| 官方英文对照 | Tiny Streaming | Small Streaming | Medium Streaming |
|---|---|---|---|
| 八数据集平均WER，浮点参考 | 12.00% | 7.84% | 6.65% |
| LibriSpeech test-clean，实际发布INT8版本 | 4.83% | 2.61% | 2.17% |

这些是[官方英文模型表](https://github.com/moonshine-ai/moonshine/blob/main/docs/models/available-models.md)与[官方精度复现说明](https://github.com/moonshine-ai/moonshine/blob/main/docs/models/accuracy.md)中的不同评测口径。WER越低越好，但不能用“100%-WER”称为本人正确率。后者是干净朗读集，不是中国学习者自由口语；官方还明确区分量化前后的结果。应避开2026-07-30前效果较差的旧量化产物，以固定摘要的新产物复验。

Granite当前模型卡的5.51%英文平均WER涉及九个测试集，且最新多语结果仍为其未正式入榜结果；Parakeet的6.34%和Moonshine的八集平均不能拼成严格同场排名。Moonshine论文的延迟测试机器为MacBook Pro M3，也不能当成AMD Windows的本机延迟。[Moonshine论文](https://download.moonshine.ai/docs/moonshine_streaming_paper.pdf)、[Granite结果口径](https://huggingface.co/ibm-granite/granite-speech-5.0-470m-turboctc)。

## 当前机器的真实探测

基线为官方 `openai/whisper-base.en`，修订 `911407f4214e0e1d82085af863093ec0b66f9cd6`。模型data/safetensors在 `E:/Jarvis/software/english-speech/models`，第一方探测程序在该软件的 `research`；都在Jarvis项目目录外。大权重按上游LFS SHA256，小文件按上游Git blob摘要核对；运行指定本地文件，未启用远端Python代码、未安装依赖或从运行时下载模型。[下载与摘要](model-acquisition.json)。

| 真实测量 | 本轮值 | 范围 |
|---|---|---|
| GPU使用 | ASR进程固定CPU，未使用GPU | 不是全机显存占用为零 |
| CPU推理线程 | 4 | 单模型、单路 |
| 五段录音长度 | 2.675—6.155秒 | Windows本机合成英文，不是真人声音 |
| 每段推理耗时 | 0.422—0.647秒 | 模型导入、冷启动和UI延迟不计在这段时间内 |
| 实时率RTF | 0.090—0.158 | 推理耗时/录音时长，越低越快 |
| OS记录的进程峰值工作集 | 约793MiB | 不是只算权重 |
| 结束时私有提交量 | 约2.17GiB | 与驻留物理工作集是不同指标，不是测得的峰值私有提交量 |
| 外部ASR/模型调用 | 0 | 所有探测离线；原剧情评价仍有其原模型成本 |

五个样本分别为咖啡店、改约、工作日期、故意保留的语法错误和否定表达。输出保留了关键日期、否定及“He go to work yesterday.”，但只是一轮人工核对合成输入，不能推出真人低WER。[逐条结果](whisper-local-baseline.json)。简单分词口径WER为6/51（11.76%），这六处都是数字/时间书写格式差异；不改参考文本把它刷成“零错误”，也不拿此口径与官方榜单比较。

最初清理环境变量后，PyTorch导入因未指定其缓存路径而失败。后补明确E盘Torch缓存目录，不恢复凭据变量或扩大外部访问。原失败保留在[stderr](whisper-probe-stderr.txt)，后续输出见[第二轮stderr](whisper-probe-stderr-r2.txt)。本机硬件与依赖资料见[hardware-runtime.json](hardware-runtime.json)。没有证明干净的新机器无需安装运行时。

## 后续本机对照与上线条件

| 项目 | 事前验收目标（proposed，不是实测） |
|---|---|
| 资源 | Small先争取峰值工作集≤1GiB、私有提交峰值≤1.5GiB；Medium独立测量，不承诺沿用此预算；记录冷/热态和全流程延迟 |
| 热态响应 | 5—10秒短句结束到最终转写p95≤1.5秒；CPU2/4线程各测，先保证业务前台不卡顿 |
| 准确性 | 同一批经核对真实口语，同时测Small/Medium/Whisper基线；分别记录数字、日期、否定、停顿、口音、语法错误和中英切换 |
| 样本 | 先小规模人工核对，再至少50段跨场景真人录音；不以TTS代替本人表现，不使用该批调试样本冒充未见样本 |
| 安全推进 | 静音、低置信或关键约束冲突时不自动推进/评分；保留原音频、原始转写、更正、模型版本和来源 |
| 成长记录 | 识别错误单列；更正识别不等于英语纠错。只有可追溯的本人表达进入口语内容统计；文字、口语、发音评价分开 |
| 版本 | 外部软件独立环境与固定产物，不能升级Jarvis共用Transformers/PyTorch来迁就候选；沿原控制器、预算、STOP/UNKNOWN、备份与旧版回退验收 |

建议的实施顺序是：固定Moonshine原生INT8产物与独立运行时 → Small/Medium在本机同样本对照 → 实现录音后的自动转写/更正及低置信出口 → 原学习记录、错题复习与口语统计绑定 → 相容恢复和原数据核对 → 才升级日用。不能因已经有一个可运行的Whisper基线就提前宣告新的自动ASR已上线。
