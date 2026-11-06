# 复现、迁移与同等效果

v2 保留实际实现，不仅共享规范。Cindy 执行下面的命令，用户只需要描述任务。`SKILL` 为已安装目录，`PROJECT` 为新的独立工程；所有路径由 Cindy 按接收方机器生成。

## 首次准备

```sh
python3 "$SKILL/scripts/workflow.py" init "$PROJECT"
python3 "$SKILL/scripts/workflow.py" setup "$PROJECT"
python3 "$SKILL/scripts/library.py" restore --project "$PROJECT" --case all --with-sources
```

从小安装包调用时，restore 自动下载固定版本资源并验证 SHA256，缓存到工程内，不修改已安装 Skill。离线可在 restore 命令追加 `--resources <已下载的资源ZIP>`。完整 GitHub 仓库已有资源则直接恢复，无需重复下载。

`production-library/` 是恢复的原制作库，`product-source/` 是固定公开版本 v0.1.125 的源码。预构建 HTML 不需要安装庞大的产品开发依赖。源码重建时再执行 `library.py bind --project "$PROJECT"`，读取源码自身的构建指引，按它的 pnpm 锁文件安装依赖。旧案例渲染脚本仍有独立入口，运行前在接收方副本中接好浏览器、Python 音频依赖和输出路径；不要直接对原件执行覆盖式旧脚本。源码恢复并不代表所有历史编译入口均已重新构建验收。

## 接收方对照检查

```sh
node "$SKILL/scripts/replay.mjs" --project "$PROJECT" --output "$PROJECT/evidence/baseline-replay"
python3 "$SKILL/scripts/compare_baseline.py" "$PROJECT/evidence/baseline-replay"
node "$SKILL/scripts/check_library.mjs" "$PROJECT"
```

标准参考帧在包内，比较要求操作时间线一致、抽样帧 SSIM ≥ 0.995。对比失败时保留报告并定位环境/字体/组件差异，不忽略失败后承诺效果一致。SSIM 是结构相似度，不是总体质量评分；正常速度观看和音频检查仍独立进行。

## 当前标准样片

```sh
node "$SKILL/scripts/replay.mjs" --project "$PROJECT" --render --output "$PROJECT/output/baseline-v1"
python3 "$SKILL/scripts/mix_reference.py" --project "$PROJECT" --folder "$PROJECT/output/baseline-v1" --output "$PROJECT/output/baseline-v1/plan-4x3.mp4"
python3 "$SKILL/scripts/check_video.py" "$PROJECT/output/baseline-v1/plan-4x3.mp4" --report "$PROJECT/evidence/baseline-video.json"
```

输出目录必须是新版本目录。此入口逐帧运行认可的 HTML 自身：保留原生组件、原镜头、大鼠标和完整操作；录制时移除审片工具栏，输出 3840×2880 / 60fps。基准音轨直接调用原计划模式的 score.py / mix-audio.py，只改输出路径；沿原随机种子和 114 BPM，为实际片长生成完整乐曲，音效按本次操作帧定位。原版声音引擎固定 NumPy 2.0.2，需要 Python 3.9–3.12；缺包时安装到工程独立 venv，较新 Python 的机器由 Cindy 准备兼容 Python 3.12，不覆盖系统环境。浏览器在线听感与最终混音分别检查。

只要 HTML 时直接打开 catalog 的入口；不要为 HTML 安装仅用于编码的工具。协作案例有完整回放页；额外目录条目是原生宿主预览，其完整操作编排在相应 capture.mjs，不能把宿主静态加载当作完整影片通过。邮件、界面设置及其他旧案例保留历史比例和已知限制。

## 质量证据与限制

随包 `verification/` 记录本版实际执行范围。通过资源摘要检查只是确认文件完整；原生功能完成、抽样像素接近、完整编码解码和主观观感是不同检查。基准的源页面与恢复页面同浏览器对比；这不是已在同事 Mac 实测。Mac/Intel、系统字体、GPU 和浏览器差异仍须在接收方运行基准确认。

不得声称任意新题材可以自动复制既有影片质量。优先复用已验证实现；每条新片都重新验证内容、组件、镜头、节奏、中英文与音画。自动放行只接受本版真实证据，未做的观感和听审保持未完成。

## 本地与共享版的范围

保留：最新工作流全文及模板、各功能成熟源码和适配器、可运行原生构建与字体、共用品牌、合成配乐及生成脚本、当前 4:3 样片、历史中英案例、移动端框架、固定公开产品源码。

不携带：作者账号、密钥、私人会话、日程/定时任务、发布状态、失败渲染缓存、node_modules、产品开发环境和所有旧 MP4。历史代码已保留，旧视频缓存不影响重新制作。当前标准的参考成片单独随 GitHub Release 提供。安装不会发布内容、启用自动任务或修改模型设置。

现有项目不会因 Skill 升级自动改写；后续共享规范更新应发布新版本，接收方有选择地迁移。
