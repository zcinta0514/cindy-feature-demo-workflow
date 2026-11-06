# 工程和逐帧重演接口

`workflow.py init PROJECT` 会复制本包资源/模板/工具，生成 `demo.config.json`，本地交付默认在 `PROJECT/deliveries`。工程可以移动，所有用户资源、入口和输出采用工程相对路径。依赖安装在工程目录，更新 Skill 不影响旧工程。生产与测试输出不写进已安装 Skill。

## 页面契约

本片 HTML 使用真实产品组件，Agent 提供统一帧时钟。页面暴露：

```js
window.__DEMO_EXPORT__ = {
  ready: Promise.resolve(),
  frameCount: 600, // 完整影片总帧数，包含首尾
  async render(frame) {
    // t=frame/60；按固定次序执行到该帧的演员事件、原生状态、镜头、字幕。
    // 等 React/布局/字体真正完成，不能只等待任意时间后截图。
  },
  async finish() {
    return {complete: true, assertions: [], audioCues: []};
  }
};
```

`render` 必须支持从0开始严格递增调用；每帧不能跳过状态。不要把低帧率视频重复截图当高清60fps源。含真实CSS/WAAPI动效时需要同步设置其当前时间，或在actor中建立受控时钟；未同步的随机动画、Date.now、计时器和流式响应不允许决定成片帧。字体和图片全部本地加载后 ready 才完成。页面启动错误、资源404、外网请求会使渲染失败，不默默丢内容。

渲染器启动独立、无登录态的离线 Chromium，仅服务工程目录并阻断外网；这是逐帧媒体渲染，不接管 Cindy 已有浏览器会话。默认逻辑1440×1080、设备像素比8/3，生成3840×2880原生帧；同一场景的QA检查可先用较低输出，但不得拿低清片放大交付。

```sh
node tools/render.mjs --project . --entry scene/index.html --output output/en/silent.mp4
python3 tools/mix_audio.py --video output/en/silent.mp4 --music audio/music.wav --cues output/en/audio-cues.json --output output/en/final.mp4
python3 tools/check_video.py output/en/final.mp4
python3 tools/archive_delivery.py --manifest output/en/delivery-manifest.json --config demo.config.json
```

工具拒绝覆盖已有最终输出；修订用新版本目录。不要把工具返回的技术检查记录自动填成七类验收通过。

## 演员、镜头、品牌

使用已附 `assets/brand/motion.js`（GSAP已在assets内）和 `assets/brand/style.css`；创建1920×1080的 `.cindy-motion`，内部包含 `.mesh`、`.brand-icon`、`.brand-wordmark`、`.brand-feature`、`.brand-closing`、`.content-stage` 和 `.cursor-shape`，品牌图像由随包文件加载。`CindyMotion.create(stage,{duration,feature,closing})` 返回 `.seek(seconds)`。

输出4:3时以逻辑1440宽视口取 stage 中央，水平偏移 -240；这只定义品牌设计坐标，不授权盲裁产品。正文完整边界、字幕留白和镜头按 [camera.md](camera.md) 在可视区域内计算。品牌资源保留原动效，文字实测居中；每种语言单独验证。

演员输入、点击、聚焦、菜单展开及保存必须通过真实组件事件产生状态，必要时使用原生宿主桥接。触发事件后等具体状态，再推进下一步；为本地演示提供明确模拟适配，不能显示真实外部发送成功。

`finish()` 应包含关键断言及本次实际事件。键鼠音效文件格式：`[{"frame":120,"kind":"click"},{"frame":180,"kind":"key"}]`，60fps，事件必须对应可见行为。声音混合器允许空事件数组，但成片有键鼠操作却无同步音效应在验收中处理。

## 原生源码

运行环境不含产品源码大仓库。首次涉及某功能时，按目标 Cindy 版本用 GitHub 工具或对应源码获取方式在 `sources/` 固定提交，安装该仓库锁定依赖，读取它的真实组件和宿主构建入口。记录来源、构建身份与差异；不要求接收者手工搬运发送者的工作树。不把随包历史参考commit误称为最新版本。

手机/设备变体适用同一导出契约，但要单独补齐原生安全区、键盘/弹层和动作映射；此包未附带已验证的iOS运行适配器，不能沿用发送者“已接入”的状态。
