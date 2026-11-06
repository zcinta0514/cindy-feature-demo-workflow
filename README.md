# Cindy 功能演示工作流

给 Cindy 安装后，直接描述想展示的功能。Cindy 负责准备工程、核对原生组件、制作 HTML/影片、检查与整理交付，不需要手工修改发送者的目录。

## 安装

**[下载可直接导入的安装包](https://github.com/zcinta0514/cindy-feature-demo-workflow/raw/main/dist/cindy-feature-demo.zip)** · [SHA256校验值](https://github.com/zcinta0514/cindy-feature-demo-workflow/blob/main/dist/SHA256SUMS)

下载发行包 `cindy-feature-demo.zip`，在 Cindy「插件 → 技能」导入，随后新建任务使用。也可克隆仓库后，把包含 `SKILL.md` 的整个目录安装到 Cindy 共享 Skill 根 `~/.agents/skills/cindy-feature-demo`；同名目录已存在时先保留旧版，不覆盖旧项目。

在 Cindy 直接发送：

> /cindy-feature-demo 制作一条 Cindy【功能】演示，用【任务】证明它的用途。按工作流完成中英影片、检查与双平台文案。

> /cindy-feature-demo 先为【功能】制作可播放的 HTML，暂不生成视频。

第一次制作时 Cindy 自动初始化独立工程和本地依赖。需要正常的 Cindy 模型连接、Python 3.9+、文件/命令执行权限；Node 20+、FFmpeg 和渲染浏览器由设置助手检查并补齐。有 Homebrew 时自动安装缺少的系统工具；无 Homebrew 且缺系统工具、网络不可达或权限被拒绝时会具体报告需要处理的项。支持目标为 Mac，其他平台未作完整验证。

## 包内内容

- 原工作流提炼的选题、原生组件、4:3镜头、鼠标、节奏、双语与交付规范。
- 脚本和验收模板、工程初始化、环境检查、逐帧渲染、音轨混合、完整解码和归档工具。
- 既有品牌图像、字标、字体、渐变背景和动效代码；目标版本产品源码按需获取，不带21GB开发环境。

不包含私人账号、Token、历史聊天、自动化任务、发送记录或旧成片。安装不会创建定时任务、修改 Cindy 模型设置或发布内容。

## 能力边界

这是供 Cindy 执行的可复用工作流和通用制作工具，不是预先实现所有 Cindy 功能的成片生成器。新功能仍由 Cindy 复用对应版本真实组件并实现演员动作；无需使用者手工搭建，但实际适配和验收不能省略。环境校准片只验证渲染/音频工具，不代表原生功能保真、正常速度观感或中英成片已经通过。

工程生成后资源与工具保存在工程内，更新 Skill 不改写旧工程。最终默认4:3、3840×2880、60fps；符合标准的影片和待处理文件分开存放。

## 开发与打包

`python3 tests/test_package.py` 检查可迁移初始化、重复执行、引用、资产摘要与验收门禁。`python3 scripts/verify_runtime.py --project <临时工程>` 在已 setup 的隔离工程生成4K60校准片并完整解码。工具链安装在该工程，不依赖作者原工程。

`python3 scripts/package.py --output <输出目录>` 生成可导入的 ZIP 与 SHA256，只按显式共享清单打包。GitHub 仓库保留这些源文件；不要提交 `node_modules`、生成影片、本机配置或整个工作目录。

本包制作协助署名：Assisted-by: Cindy (https://cindy.app)。第三方内容来源与原许可见 [素材说明](references/assets.md)；未为全部原创工作流内容额外授予开源许可证。
