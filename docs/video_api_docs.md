# 豆包 Seedance 2.0 / 2.5 视频生成接口

# 豆包 Seedance 2.0 / 2.5 视频生成接口

豆包 Seedance 2.0 / 2.5 系列视频生成接口文档，支持标准版、快速版、精简版与 2.5 版共 4 个模型：`doubao-seedance-2-0-260128`、`doubao-seedance-2-0-fast-260128`、`doubao-seedance-2-0-mini-260615`、`doubao-seedance-2-5-260628`。

---

## 支持的模型

| 模型名称                         | 说明                                                                        | 支持分辨率                    |
| -------------------------------- | --------------------------------------------------------------------------- | ----------------------------- |
| doubao-seedance-2-0-260128       | Seedance 2.0 标准版，画质更优，生成较慢（约 5-8 分钟）                       | 480p、720p、**1080p、4k**      |
| doubao-seedance-2-0-fast-260128  | Seedance 2.0 快速版，速度更快（约 3-4 分钟），画质略低                       | 480p、720p                    |
| doubao-seedance-2-0-mini-260615  | Seedance 2.0 精简版，成本更低、速度更快，适合大批量生成                      | 480p、720p                    |
| doubao-seedance-2-5-260628       | Seedance 2.5，视频时长上限延长至 30 秒，素材上限提升至 50 个，原生多语言支持 | 480p、720p、1080p                    |

> **分辨率说明**：仅 `doubao-seedance-2-0-260128`（标准版）支持 **1080p** 与 **4k** 高分辨率；`doubao-seedance-2-0-fast-260128`、`doubao-seedance-2-0-mini-260615`、`doubao-seedance-2-5-260628` 仅支持 **480p** 与 **720p**。详见下方 [resolution 参数说明](#resolution)。

> **接口统一说明**：以上模型使用**基本相同**的请求参数（`metadata.content[]` + `metadata.ratio` + `metadata.duration`），大多数场景下只需切换 `model` 字段即可切换模型；但各模型在**分辨率、时长上限、素材数量**等方面存在差异，`doubao-seedance-2-5-260628` 另有独立的智能控制行为，详见下方对应章节。

### Seedance 2.5（doubao-seedance-2-5-260628）相较 2.0 系列的主要区别

1. **更长时长**：视频生成时长上限由 Seedance 2.0 系列的 15 秒延长至 **30 秒**，支持一次性生成长达 30 秒的连贯视频，无需多段拼接即可呈现完整故事。
2. **更多素材 + 纯音频参考**：单次输入素材上限提升至 **50 个（30 张图片 + 10 段视频 + 10 段音频）**，可自由组合图片、视频、音频等多模态素材。同时新增支持**纯音频参考生成视频**，无需搭配图片或视频素材。
3. **智能宽高比与时长**：支持通过配置 `ratio` 为 `adaptive`、`duration` 为 `-1` 智能控制输出视频的宽高比和时长；但在**视频编辑、视频延长、首帧或首尾帧生视频**任务中具有特殊的控制行为，详见下方[Seedance 2.5 智能控制行为](#seedance-25-智能控制行为)。
4. **原生多语言生成**：原生支持多种语言的提示词输入和有声视频生成，覆盖中文、英语、西班牙语、印度尼西亚语、马来语、泰语、阿拉伯语、葡萄牙语、越南语、日语、韩语。

---

## 接口地址

### 提交任务

```
POST {BASE_URL}/v1/video/generations
```

### 查询结果

```
GET {BASE_URL}/v1/video/generations/{task_id}
```

---

## 请求参数

### 顶级参数

| 参数     | 类型   | 必填 | 说明                                                                        |
| -------- | ------ | ---- | --------------------------------------------------------------------------- |
| model    | string | 是   | 模型名称：`doubao-seedance-2-0-260128`、`doubao-seedance-2-0-fast-260128`、`doubao-seedance-2-0-mini-260615` 或 `doubao-seedance-2-5-260628` |
| prompt   | string | 是   | 文本提示词（平台校验要求非空，实际提示词通过 metadata.content 传递）        |
| metadata | object | 是   | 扩展参数对象，包含所有 Seedance 2.0 / 2.5 参数                              |

### metadata 参数

| 参数           | 类型     | 必填 | 说明                                            | 默认值       |
| -------------- | -------- | ---- | ----------------------------------------------- | ------------ |
| content        | object[] | 是   | 输入给模型的内容数组，详见下方 content 参数说明 | -            |
| generate_audio | boolean  | 否   | 控制生成的视频是否包含与画面同步的声音          | `true`       |
| resolution     | string   | 否   | 视频分辨率，取值随模型而不同，详见下方 [resolution 参数说明](#resolution) | `"720p"`     |
| ratio          | string   | 否   | 视频宽高比                                      | `"adaptive"` |
| duration       | integer  | 否   | 视频时长（秒）                                  | `5`          |
| tools          | object[] | 否   | 配置模型要调用的工具                            | -            |
| output_format  | string   | 否   | 输出视频格式，`mp4` 或 `mov`，**仅 `doubao-seedance-2-5-260628` 支持**，详见下方 [output_format 参数说明](#output_format) | `"mp4"`      |
| omni_reference_task_type | string | 否 | 全模态参考生视频任务类型引导，`auto` / `reference` / `edit` / `extend`，**仅 `doubao-seedance-2-5-260628` 支持**，详见下方 [omni_reference_task_type 参数说明](#omni_reference_task_type) | `"auto"` |

> **注意**：`prompt` 字段必须非空（平台校验要求），但实际发送给上游的提示词来自 `metadata.content` 中的文本内容。如果未传 `metadata.content`，平台会自动将 `prompt` 转换为 `content` 数组。

---

## content 参数详细说明

`metadata.content` 为对象数组，输入给模型生成视频的信息，支持文本、图片、音频、视频。支持以下几种组合：

- 文本
- 文本（可选）+ 图片
- 文本（可选）+ 视频
- 文本（可选）+ 图片 + 音频
- 文本（可选）+ 图片 + 视频
- 文本（可选）+ 视频 + 音频
- 文本（可选）+ 图片 + 视频 + 音频

---

### 文本信息

输入给模型的提示词信息。

| 字段 | 类型   | 必填 | 说明                                                                                                                                                  |
| ---- | ------ | ---- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| type | string | 是   | 固定为 `"text"`                                                                                                                                       |
| text | string | 是   | 文本提示词，描述期望生成的视频。支持中英文。建议中文不超过 500 字，英文不超过 1000 词。字数过多信息容易分散，模型可能忽略细节，造成视频缺失部分元素。 |

示例：

```json
{
  "type": "text",
  "text": "清晨的海边，金色阳光照耀在海面上，一只海豚跃出水面，水花四溅"
}
```

---

### 图片信息

输入给模型的图片信息。

| 字段          | 类型   | 必填     | 说明                                         |
| ------------- | ------ | -------- | -------------------------------------------- |
| type          | string | 是       | 固定为 `"image_url"`                         |
| image_url     | object | 是       | 图片对象                                     |
| image_url.url | string | 是       | 图片 URL、Base64 编码或素材 ID（见下方说明） |
| role          | string | 条件必填 | 图片的位置或用途（见下方说明）               |

**image_url.url 支持的格式：**

- **图片 URL**：填入图片的公网 URL
- **Base64 编码**：格式 `data:image/<图片格式>;base64,<Base64编码>`，如 `data:image/png;base64,{base64_image}`
- **素材 ID**：格式 `asset://<ASSET_ID>`

**传入单张图片要求：**

- 格式：jpeg、png、webp、bmp、tiff、gif
- 宽高比（宽/高）：(0.4, 2.5)
- 宽高长度（px）：(300, 6000)
- 大小：单张图片小于 30 MB，请求体大小不超过 64 MB。大文件请勿使用 Base64 编码
- 图片数量：
  - 图生视频-首帧：1 张
  - 图生视频-首尾帧：2 张
  - 多模态参考生视频：Seedance 2.0 系列（标准版 / fast / mini）1~9 张；Seedance 2.5 最多 30 张

**role 取值说明：**

> 图生视频-首帧、图生视频-首尾帧、多模态参考生视频为 3 种互斥场景，不可混用。

| 场景             | 图片数量                            | role 取值                                               | 说明                     |
| ---------------- | ----------------------------------- | ------------------------------------------------------- | ------------------------ |
| 图生视频-首帧    | 1 张                                | `first_frame` 或不填                                    | 以该图片作为视频首帧     |
| 图生视频-首尾帧  | 2 张                                | 首帧：`first_frame`（必填），尾帧：`last_frame`（必填） | 指定视频的首帧和尾帧图片 |
| 多模态参考生视频 | 2.0 系列（标准版 / fast / mini）1~9 张；2.5 最多 30 张 | `reference_image`（必填）                               | 作为参考图片生成视频     |

示例（首帧图生视频）：

```json
{
  "type": "image_url",
  "image_url": { "url": "https://example.com/image.jpg" },
  "role": "first_frame"
}
```

示例（参考图）：

```json
{
  "type": "image_url",
  "image_url": { "url": "https://example.com/ref.jpg" },
  "role": "reference_image"
}
```

---

### 视频信息

输入给模型的视频信息。Seedance 2.0 系列（`doubao-seedance-2-0-260128`、`doubao-seedance-2-0-fast-260128`、`doubao-seedance-2-0-mini-260615`）与 Seedance 2.5（`doubao-seedance-2-5-260628`）均支持。

> 支持使用本账号下上述模型产出的视频作为输入素材，进行视频编辑或延长，其中的真人人脸可正常使用，不会触发审核拦截。

| 字段          | 类型   | 必填     | 说明                                            |
| ------------- | ------ | -------- | ----------------------------------------------- |
| type          | string | 是       | 固定为 `"video_url"`                            |
| video_url     | object | 是       | 视频对象                                        |
| video_url.url | string | 是       | 视频 URL 或素材 ID（格式 `asset://<ASSET_ID>`） |
| role          | string | 条件必填 | 当前仅支持 `"reference_video"`                  |

**传入视频要求：**

- 格式：mp4、mov
- 分辨率：480p、720p
- 时长：单个视频 [2, 15] 秒，Seedance 2.0 系列（标准版 / fast / mini）最多传入 3 个参考视频（总时长不超过 15s），Seedance 2.5 最多传入 10 个参考视频
- 宽高比（宽/高）：[0.4, 2.5]
- 宽高长度（px）：[300, 6000]
- 画面像素（宽 × 高）：[409600, 927408]
  - 示例：640×640=409600（最小值），834×1112=927408（最大值）
- 大小：单个视频不超过 50 MB
- 帧率 (FPS)：[24, 60]

示例：

```json
{
  "type": "video_url",
  "video_url": { "url": "https://example.com/video.mp4" },
  "role": "reference_video"
}
```

---

### 音频信息

输入给模型的音频信息。Seedance 2.0 系列（`doubao-seedance-2-0-260128`、`doubao-seedance-2-0-fast-260128`、`doubao-seedance-2-0-mini-260615`）与 Seedance 2.5（`doubao-seedance-2-5-260628`）均支持。

> Seedance 2.0 系列不可单独输入音频，应至少包含 1 个参考视频或图片；Seedance 2.5（`doubao-seedance-2-5-260628`）新增支持**纯音频参考生成视频**，无需搭配图片或视频素材。

| 字段          | 类型   | 必填     | 说明                           |
| ------------- | ------ | -------- | ------------------------------ |
| type          | string | 是       | 固定为 `"audio_url"`           |
| audio_url     | object | 是       | 音频对象                       |
| audio_url.url | string | 是       | 音频 URL、Base64 编码或素材 ID |
| role          | string | 条件必填 | 当前仅支持 `"reference_audio"` |

**audio_url.url 支持的格式：**

- **音频 URL**：填入音频的公网 URL
- **Base64 编码**：格式 `data:audio/<音频格式>;base64,<Base64编码>`，如 `data:audio/wav;base64,{base64_audio}`
- **素材 ID**：格式 `asset://<ASSET_ID>`

**传入音频要求：**

- 格式：wav、mp3
- 时长：单个音频 [2, 15] 秒，Seedance 2.0 系列（标准版 / fast / mini）最多传入 3 段参考音频（总时长不超过 15s），Seedance 2.5 最多传入 10 段参考音频
- 大小：单个音频不超过 15 MB，请求体大小不超过 64 MB。大文件请勿使用 Base64 编码

示例：

```json
{
  "type": "audio_url",
  "audio_url": { "url": "https://example.com/audio.wav" },
  "role": "reference_audio"
}
```

---

## 其他参数详细说明

### generate_audio

| 取值           | 说明                                                                                                                                                                                                           |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `true`（默认） | 模型输出的视频包含同步音频。模型会基于文本提示词与视觉内容，自动生成与之匹配的人声、音效及背景音乐。建议将对话部分置于双引号内，以优化音频生成效果。例如：`男人叫住女人说："你记住，以后不可以用手指指月亮。"` |
| `false`        | 模型输出的视频为无声视频                                                                                                                                                                                       |

> 生成的有声视频均为单声道，和传入的音频声道数无关。

### resolution

视频分辨率，默认值 `"720p"`。**不同模型支持的分辨率不同：**

| 模型                              | 支持的分辨率              |
| --------------------------------- | ------------------------- |
| `doubao-seedance-2-0-260128`      | `480p`、`720p`、`1080p`、`4k` |
| `doubao-seedance-2-0-fast-260128` | `480p`、`720p`            |
| `doubao-seedance-2-0-mini-260615` | `480p`、`720p`            |
| `doubao-seedance-2-5-260628`      | `480p`、`720p`            |

| 取值      | 说明                                                    |
| --------- | ------------------------------------------------------- |
| `"480p"`  | 低分辨率，生成速度较快，成本最低                         |
| `"720p"`  | 高分辨率，画质更好（默认值）                             |
| `"1080p"` | 全高清，画质更细腻，**仅 `doubao-seedance-2-0-260128` 支持** |
| `"4k"`    | 超高清，最高画质，**仅 `doubao-seedance-2-0-260128` 支持** |

> **注意**：向不支持高分辨率的模型（`fast` / `mini` / `2.5`）传入 `1080p` 或 `4k` 会导致请求被拒绝或自动降级，请根据所选模型传入合法取值。分辨率越高，生成耗时越长、计费越高。

### ratio

视频宽高比，默认值 `"adaptive"`。

| 取值         | 说明                           |
| ------------ | ------------------------------ |
| `"16:9"`     | 横屏宽幅                       |
| `"4:3"`      | 横屏标准                       |
| `"1:1"`      | 正方形                         |
| `"3:4"`      | 竖屏标准                       |
| `"9:16"`     | 竖屏全屏                       |
| `"21:9"`     | 超宽屏 / 电影比例              |
| `"adaptive"` | 根据输入自动选择最合适的宽高比 |

**adaptive 适配规则：**

- 文生视频：根据提示词智能选择最合适的宽高比
- 首帧/首尾帧生视频：根据上传的首帧图片比例，自动选择最接近的宽高比
- 多模态参考生视频：根据用户提示词意图判断，以传入的第一个媒体文件为准（优先级：视频 > 图片）选择最接近的宽高比

**不同宽高比对应的宽高像素值：**

| 分辨率 | 宽高比 | 宽高像素值 |
| ------ | ------ | ---------- |
| 480p   | 16:9   | 864×496    |
| 480p   | 4:3    | 752×560    |
| 480p   | 1:1    | 640×640    |
| 480p   | 3:4    | 560×752    |
| 480p   | 9:16   | 496×864    |
| 480p   | 21:9   | 992×432    |
| 720p   | 16:9   | 1280×720   |
| 720p   | 4:3    | 1112×834   |
| 720p   | 1:1    | 960×960    |
| 720p   | 3:4    | 834×1112   |
| 720p   | 9:16   | 720×1280   |
| 720p   | 21:9   | 1470×630   |

> 上表为 `480p` / `720p` 的宽高像素对照，所有模型均支持。`1080p` 与 `4k` 仅 `doubao-seedance-2-0-260128` 支持，其像素值按对应宽高比等比放大（如 `1080p` 16:9 约 1920×1080，`4k` 16:9 约 3840×2160）。

### duration

视频时长（秒），默认值 `5`，仅支持整数。**时长上限随模型而不同：**

| 模型                              | 时长范围        |
| --------------------------------- | --------------- |
| `doubao-seedance-2-0-260128`      | `4`~`15` 秒     |
| `doubao-seedance-2-0-fast-260128` | `4`~`15` 秒     |
| `doubao-seedance-2-0-mini-260615` | `4`~`15` 秒     |
| `doubao-seedance-2-5-260628`      | `4`~`30` 秒     |

| 取值       | 说明                                                                                                                                      |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| 指定时长   | 指定具体时长，支持有效范围内的任一整数。Seedance 2.0 系列（标准版 / fast / mini）为 `4`~`15` 秒；Seedance 2.5（`doubao-seedance-2-5-260628`）上限延长至 **30 秒** |
| `-1`       | 智能指定，由模型在有效范围内自主选择合适的视频长度。实际时长可通过查询 API 返回的 `duration` 字段获取。注意视频时长与计费相关，请谨慎设置 |

### tools

配置模型要调用的工具。仅 Seedance 2.0 标准版与快速版（`doubao-seedance-2-0-260128`、`doubao-seedance-2-0-fast-260128`）支持；`doubao-seedance-2-0-mini-260615` 与 `doubao-seedance-2-5-260628` 暂不支持。

| 字段 | 类型   | 说明                                                          |
| ---- | ------ | ------------------------------------------------------------- |
| type | string | 工具类型，当前支持 `"web_search"`（联网搜索，仅文生视频支持） |

> 开启联网搜索后，模型会根据提示词自主判断是否搜索互联网内容（如商品、天气等）。可提升生成视频的时效性，但也会增加一定的时延。
>
> 实际搜索次数可通过查询视频生成任务接口返回的 `usage.tool_usage.web_search` 字段获取，为 `0` 表示未搜索。

示例（放在 `metadata` 内）：

```json
{
  "model": "doubao-seedance-2-0-260128",
  "prompt": "占位",
  "metadata": {
    "content": [{ "type": "text", "text": "今天北京的天气播报" }],
    "tools": [{ "type": "web_search" }]
  }
}
```

### output_format

输出视频格式，默认值 `"mp4"`。**仅 `doubao-seedance-2-5-260628` 支持**，2.0 系列（标准版 / fast / mini）不支持该参数。

| 取值           | 编码与色彩            | 适用场景                               |
| -------------- | --------------------- | -------------------------------------- |
| `"mp4"`（默认） | H.264、AAC、yuv420p   | 兼容性较好，适合播放、交付和分发        |
| `"mov"`        | H.264、PCM、yuv444p   | 色彩精度较高，适合延长、拼接、调色、抠像和合成 |

> `mov` 文件通常体积更大；视频延长场景建议输入和输出均使用 `mov`，以提升声画衔接与色彩一致性。

示例（放在 `metadata` 内）：

```json
{
  "model": "doubao-seedance-2-5-260628",
  "prompt": "占位",
  "metadata": {
    "content": [{ "type": "text", "text": "清晨的海边，一只海豚跃出水面" }],
    "duration": 5,
    "output_format": "mov"
  }
}
```

### omni_reference_task_type

全模态参考生视频任务类型引导，默认值 `"auto"`。**仅 `doubao-seedance-2-5-260628` 支持**。

Seedance 2.5 全模态参考生视频任务包括**参考生视频、视频编辑和视频延长** 3 类子任务。不同任务类型对参数有特殊限制，为减少任务创建后异步报错的情况，可通过本参数指定子任务类型，以提前校验对应限制。

- 默认情况下（`omni_reference_task_type=auto`）：模型根据输入素材和提示词自动判定任务类型，再校验参数取值。如果参数与实际任务类型不兼容，任务将触发异步报错。
- 显式指定任务类型（`reference` / `edit` / `extend`）：接口在提交任务时提前校验对应任务的特殊参数限制，不符合要求时立即报错，任务不会创建。

> **注意**：实际处理任务时，模型仍会进一步结合提示词判断任务类型。若实际判定的任务类型与指定的不一致，仍会触发异步报错。建议遵循各任务类型的提示词写法，降低报错概率。

| 取值          | 说明                                                                                       |
| ------------- | ------------------------------------------------------------------------------------------ |
| `"auto"`（默认） | 由模型根据输入素材和提示词自动判定任务类型                                                  |
| `"reference"` | 参考生视频任务，即基于参考图片、参考视频或参考音频生成新视频。设 `reference` 时，`ratio` 或 `duration` 无特殊限制 |
| `"edit"`      | 视频编辑任务，即对原视频的画面或音频进行编辑操作。设 `edit` 时，`content` 中必须至少包含一个 `reference_video`，且视频时长必须为 4~30 秒；`ratio` 必须为 `adaptive`；`duration` 必须为 `-1` |
| `"extend"`    | 视频延长任务，即对原视频向前或向后延长。设 `extend` 时，`content` 中必须至少包含一个 `reference_video`；`ratio` 必须为 `adaptive` |

示例（放在 `metadata` 内）：

```json
{
  "model": "doubao-seedance-2-5-260628",
  "prompt": "占位",
  "metadata": {
    "content": [
      { "type": "text", "text": "延长这段视频" },
      { "type": "video_url", "video_url": { "url": "https://example.com/video.mp4" }, "role": "reference_video" }
    ],
    "ratio": "adaptive",
    "duration": -1,
    "omni_reference_task_type": "extend"
  }
}
```

---

## Seedance 2.5（doubao-seedance-2-5-260628）专属参数说明

`doubao-seedance-2-5-260628` 与 2.0 系列共用同一套请求结构，但在**素材数量、参考图、时长、宽高比、音频、语言**等参数上有独立行为，使用前请重点关注以下差异。

### 1. 参考图与素材数量

| 素材类型       | Seedance 2.0 系列（标准版 / fast / mini）     | Seedance 2.5（doubao-seedance-2-5-260628） |
| -------------- | --------------------------------------------- | ------------------------------------------ |
| 参考图片（`reference_image`） | 多模态参考生视频 1~9 张                        | 多模态参考生视频最多 **30 张**             |
| 参考视频（`reference_video`） | 最多 3 个，总时长 ≤ 15s                        | 最多 **10 个**                             |
| 参考音频（`reference_audio`） | 最多 3 段，总时长 ≤ 15s，且不可单独输入        | 最多 **10 段**，且支持**纯音频参考生成视频** |
| 单次素材总量   | -                                             | 最多 **50 个（30 图 + 10 视频 + 10 音频）** |

> 首帧（`first_frame`）、首尾帧（`first_frame` + `last_frame`）、多模态参考（`reference_image`）三种场景互斥，不可混用，此规则对所有模型一致。

### 2. 时长（duration）

- Seedance 2.5 时长范围为 `4`~`30` 秒（2.0 系列为 `4`~`15` 秒），可一次性生成长达 30 秒的连贯视频，无需多段拼接。
- 支持传入 `-1` 让模型智能决定时长；但在**视频编辑、视频延长**任务中，`duration` 默认且仅支持 `-1`，输出时长与输入视频基本保持一致，不支持另行指定（见下方智能控制行为）。

### 3. 宽高比（ratio）

- 常规文生视频 / 图生视频场景中，`ratio` 取值与 2.0 系列一致，支持 `16:9`、`4:3`、`1:1`、`3:4`、`9:16`、`21:9`、`adaptive`。
- 在**视频编辑、视频延长**任务中，`ratio` 默认且仅支持 `adaptive`，输出宽高比自动与输入视频保持一致，不支持另行指定（见下方智能控制行为）。

### 4. 分辨率（resolution）

- Seedance 2.5 仅支持 `480p` 与 `720p`，**不支持 `1080p` 与 `4k`**（仅 `doubao-seedance-2-0-260128` 支持高分辨率）。

### 5. 纯音频参考生成视频

- Seedance 2.5 新增支持仅凭音频素材（`reference_audio`）生成视频，无需搭配任何图片或视频；2.0 系列则必须至少包含 1 个参考视频或图片。

### 6. 原生多语言生成

- Seedance 2.5 原生支持多种语言的提示词输入和有声视频生成，覆盖：中文、英语、西班牙语、印度尼西亚语、马来语、泰语、阿拉伯语、葡萄牙语、越南语、日语、韩语。

---

## Seedance 2.5 智能控制行为

`doubao-seedance-2-5-260628` 支持通过配置 `ratio` 为 `adaptive`、`duration` 为 `-1` 以智能控制输出视频的宽高比和时长；但在**视频编辑、视频延长、首帧或首尾帧生视频**任务中，具有特殊的控制行为，详情参考以下示例。

### 使用示例 - 视频编辑

**仅 `doubao-seedance-2-5-260628` 支持视频编辑 / 视频延长**。在视频编辑任务中，输出视频宽高比将自动和输入视频的宽高比保持一致（参数 `ratio` 默认且仅支持配置为 `adaptive`），输出视频时长自动和输入视频时长基本保持一致（参数 `duration` 默认且仅支持配置为 `-1`）。上述两项均不支持另行设置。

| 任务类型                | ratio                          | duration                       |
| ----------------------- | ------------------------------ | ------------------------------ |
| 视频编辑                | 默认且仅支持 `adaptive`，与输入视频宽高比一致 | 默认且仅支持 `-1`，与输入视频时长基本一致 |

### 使用示例 - 首帧 / 首尾帧生视频

**仅 `doubao-seedance-2-5-260628`** 在首帧或首尾帧生视频任务中支持以下智能控制；2.0 系列无此行为，需显式指定 `ratio` 与 `duration`。

| 任务类型                  | ratio                    | duration        |
| ------------------------- | ------------------------ | --------------- |
| 首帧生视频                | 支持配置，建议 `adaptive` | 支持 `-1` 智能决定 |
| 首尾帧生视频（视频延长）  | 默认且仅支持 `adaptive`，与输入视频宽高比一致 | 默认且仅支持 `-1`，与输入视频时长基本一致 |

---

## 原生多语言生成

Seedance 2.5 原生支持多种语言的提示词输入和有声视频生成，覆盖支持：中文、英语、西班牙语、印度尼西亚语、马来语、泰语、阿拉伯语、葡萄牙语、越南语、日语、韩语。

---

## 重要提示：关于提示词传递

> **在 Windows 命令行（cmd / PowerShell）中使用 curl 直接传递中文提示词可能出现编码问题，导致生成内容与提示词不符。**
>
> **推荐做法**：先将请求 JSON 写入 UTF-8 编码的文件，再使用 `--data-binary @文件名` 发送请求。
>
> 通过 Python、Java、前端应用等编程语言调用 API 不受此影响，因为这些语言默认使用 UTF-8 编码。

### 错误示例（Windows 下中文可能乱码）

```bash
# 不推荐：Windows 命令行直接传中文可能编码错误
curl -X POST "{BASE_URL}/v1/video/generations" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"doubao-seedance-2-0-260128","prompt":"海豚跃出水面",...}'
```

### 正确示例（使用文件方式）

```bash
# 推荐：先写入 UTF-8 文件，再用 --data-binary 发送
printf '{"model":"doubao-seedance-2-0-260128","prompt":"占位","metadata":{"content":[{"type":"text","text":"清晨的海边，金色阳光照耀在海面上，一只海豚跃出水面，水花四溅"}],"duration":8,"resolution":"480p","ratio":"9:16","generate_audio":true}}' > request.json

curl -X POST "{BASE_URL}/v1/video/generations" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary @request.json
```

---

## 请求示例

### cURL（推荐文件方式）

#### 文生视频

```bash
printf '{"model":"doubao-seedance-2-0-260128","prompt":"果茶广告","metadata":{"content":[{"type":"text","text":"全程第一人称视角果茶宣传广告，你的手摘下一颗带晨露的红苹果，将苹果块投入雪克杯加入冰块与茶底用力摇晃，分层果茶倒入透明杯轻挤奶盖在顶部铺展，最后手持举杯到镜头前"}],"duration":8,"resolution":"480p","ratio":"9:16","generate_audio":true}}' > request.json

curl -X POST "{BASE_URL}/v1/video/generations" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary @request.json
```

#### 图生视频（首帧）

```bash
printf '{"model":"doubao-seedance-2-0-260128","prompt":"图生视频","metadata":{"content":[{"type":"text","text":"让画面中的猫咪缓缓走动，阳光洒落"},{"type":"image_url","image_url":{"url":"https://example.com/cat.jpg"},"role":"first_frame"}],"duration":5,"resolution":"720p","ratio":"adaptive"}}' > request.json

curl -X POST "{BASE_URL}/v1/video/generations" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary @request.json
```

#### 多模态参考生视频（图片+音频+文本）

```bash
printf '{"model":"doubao-seedance-2-0-260128","prompt":"多模态","metadata":{"content":[{"type":"text","text":"一个女孩在弹吉他唱歌"},{"type":"image_url","image_url":{"url":"https://example.com/girl.jpg"},"role":"reference_image"},{"type":"audio_url","audio_url":{"url":"https://example.com/song.mp3"},"role":"reference_audio"}],"duration":10,"resolution":"720p","ratio":"9:16","generate_audio":true}}' > request.json

curl -X POST "{BASE_URL}/v1/video/generations" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary @request.json
```

### Python

```python
import requests
import time

BASE_URL = "{BASE_URL}"
API_KEY = "YOUR_API_KEY"
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# ========== 文生视频 ==========
payload = {
    "model": "doubao-seedance-2-0-260128",
    "prompt": "果茶广告",
    "metadata": {
        "content": [
            {
                "type": "text",
                "text": "全程第一人称视角果茶宣传广告，你的手摘下一颗带晨露的红苹果，"
                        "将苹果块投入雪克杯加入冰块与茶底用力摇晃，"
                        "分层果茶倒入透明杯轻挤奶盖在顶部铺展，最后手持举杯到镜头前"
            }
        ],
        "duration": 8,
        "resolution": "480p",
        "ratio": "9:16",
        "generate_audio": True
    }
}

response = requests.post(f"{BASE_URL}/v1/video/generations", headers=headers, json=payload)
result = response.json()
print(f"任务ID: {result['task_id']}")

# ========== 图生视频（首帧） ==========
payload_i2v = {
    "model": "doubao-seedance-2-0-260128",
    "prompt": "图生视频",
    "metadata": {
        "content": [
            {"type": "text", "text": "让画面中的猫咪缓缓走动，阳光洒落"},
            {"type": "image_url", "image_url": {"url": "https://example.com/cat.jpg"}, "role": "first_frame"}
        ],
        "duration": 5,
        "resolution": "720p",
        "ratio": "adaptive"
    }
}

# ========== 多模态参考（图片+视频+音频） ==========
payload_multi = {
    "model": "doubao-seedance-2-0-260128",
    "prompt": "多模态",
    "metadata": {
        "content": [
            {"type": "text", "text": "一个女孩在弹吉他唱歌，背景是夕阳海滩"},
            {"type": "image_url", "image_url": {"url": "https://example.com/girl.jpg"}, "role": "reference_image"},
            {"type": "video_url", "video_url": {"url": "https://example.com/ref.mp4"}, "role": "reference_video"},
            {"type": "audio_url", "audio_url": {"url": "https://example.com/song.mp3"}, "role": "reference_audio"}
        ],
        "duration": 10,
        "resolution": "720p",
        "ratio": "9:16",
        "generate_audio": True
    }
}

# ========== 轮询查询任务结果 ==========
task_id = result["task_id"]
while True:
    query_resp = requests.get(
        f"{BASE_URL}/v1/video/generations/{task_id}",
        headers={"Authorization": f"Bearer {API_KEY}"}
    )
    task_data = query_resp.json()
    status = task_data["data"]["status"]
    progress = task_data["data"]["progress"]
    print(f"状态: {status}, 进度: {progress}")

    if status == "SUCCESS":
        video_url = task_data["data"]["data"]["content"]["video_url"]
        print(f"视频地址: {video_url}")
        break
    elif status == "FAILURE":
        print(f"生成失败: {task_data['data']['fail_reason']}")
        break

    time.sleep(15)
```

### Java

```java
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;

public class SeedanceVideoGen {
    private static final String BASE_URL = "{BASE_URL}";
    private static final String API_KEY = "YOUR_API_KEY";

    public static void main(String[] args) throws Exception {
        HttpClient client = HttpClient.newHttpClient();

        // 文生视频
        String requestBody = """
            {
                "model": "doubao-seedance-2-0-260128",
                "prompt": "果茶广告",
                "metadata": {
                    "content": [
                        {
                            "type": "text",
                            "text": "全程第一人称视角果茶宣传广告，你的手摘下一颗带晨露的红苹果，将苹果块投入雪克杯加入冰块与茶底用力摇晃"
                        }
                    ],
                    "duration": 8,
                    "resolution": "480p",
                    "ratio": "9:16",
                    "generate_audio": true
                }
            }
            """;

        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(BASE_URL + "/v1/video/generations"))
            .header("Authorization", "Bearer " + API_KEY)
            .header("Content-Type", "application/json; charset=utf-8")
            .POST(HttpRequest.BodyPublishers.ofString(requestBody, StandardCharsets.UTF_8))
            .build();

        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
        System.out.println("提交结果: " + response.body());

        // 图生视频（首帧）
        String i2vBody = """
            {
                "model": "doubao-seedance-2-0-260128",
                "prompt": "图生视频",
                "metadata": {
                    "content": [
                        {"type": "text", "text": "让画面中的猫咪缓缓走动，阳光洒落"},
                        {"type": "image_url", "image_url": {"url": "https://example.com/cat.jpg"}, "role": "first_frame"}
                    ],
                    "duration": 5,
                    "resolution": "720p",
                    "ratio": "adaptive"
                }
            }
            """;

        // 查询任务状态
        String taskId = "cgt-xxxxx"; // 替换为实际 task_id
        HttpRequest queryRequest = HttpRequest.newBuilder()
            .uri(URI.create(BASE_URL + "/v1/video/generations/" + taskId))
            .header("Authorization", "Bearer " + API_KEY)
            .GET()
            .build();

        HttpResponse<String> queryResponse = client.send(queryRequest, HttpResponse.BodyHandlers.ofString());
        System.out.println("查询结果: " + queryResponse.body());
    }
}
```

---

## 查询结果

### 查询请求

```bash
curl "{BASE_URL}/v1/video/generations/{task_id}" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### 查询响应示例

#### 生成中

```json
{
  "code": "success",
  "data": {
    "task_id": "cgt-20260326182734-68xp4",
    "status": "IN_PROGRESS",
    "progress": "30%",
    "data": {
      "model": "doubao-seedance-2-0-260128",
      "status": "running",
      "generate_audio": true
    }
  }
}
```

#### 生成成功

```json
{
  "code": "success",
  "data": {
    "task_id": "cgt-20260326182734-68xp4",
    "status": "SUCCESS",
    "progress": "100%",
    "data": {
      "model": "doubao-seedance-2-0-260128",
      "ratio": "9:16",
      "duration": 8,
      "resolution": "480p",
      "generate_audio": true,
      "framespersecond": 24,
      "content": {
        "video_url": "https://...mp4?..."
      },
      "usage": {
        "total_tokens": 80770,
        "completion_tokens": 80770
      }
    }
  }
}
```

#### 生成失败

```json
{
  "code": "success",
  "data": {
    "task_id": "cgt-xxxxx",
    "status": "FAILURE",
    "fail_reason": "task failed",
    "data": {
      "error": {
        "code": "OutputVideoSensitiveContentDetected",
        "message": "The request failed because the output video may contain sensitive information."
      }
    }
  }
}
```

### 任务状态说明

| 状态        | 说明                       |
| ----------- | -------------------------- |
| NOT_START   | 任务已提交，尚未开始       |
| IN_PROGRESS | 任务正在生成中             |
| SUCCESS     | 生成成功，可获取视频 URL   |
| FAILURE     | 生成失败，查看 fail_reason |



sdk接口规范文档如下：
# SDK接口规范文档

> 版本：v1.1.0
> 唯一依赖：`pip install requests`
> 使用方式：将 `moyuai/` 目录复制到项目中，`from moyuai import MoyuAI`

---

## 通用说明

所有 SDK 函数的返回值均包含 `.status` 字段（`bool` 类型），用于判断本次调用是否成功：

```python
result = client.account.temp_register()
if result.status:
    print("调用成功")
else:
    print("调用失败")
```

每个函数的文档分为三部分：

- **输入** — 调用时传入的参数
- **输出** — 返回对象中的业务数据字段
- **返回** — `.status` 字段，表示调用成功或失败

---

## 1. 初始化

```python
from moyuai import MoyuAI

client = MoyuAI()
```

SDK初始化，无需传入任何参数，同时，魔芋平台域名已内置。

---

## 2. 账务功能

> 所有账务函数通过 `client.account.xxx()` 调用。
> 需要先通过 `temp_register()` 或 `login()` 获得认证，认证后 SDK 自动保存凭证，后续调用无需再传认证参数。

---

### 2.1 临时注册

```python
result = client.account.temp_register(appid=1)
```

**输入：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `appid` | int | 否 | 智能体应用 ID，传入后自动绑定到默认令牌 |

**输出：`TempRegisterResult` 对象**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.user_id` | int | 用户 ID |
| `.username` | str | 随机用户名（`tmp_` 前缀） |
| `.password` | str | 随机密码（仅此一次返回，需保存） |
| `.access_token` | str | 账务接口认证凭证 |
| `.api_key` | str | 对话接口凭证（`sk-xxx` 格式） |

**返回：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.status` | bool | `True`=注册成功，`False`=注册失败 |

**示例：**

```python
result = client.account.temp_register()
if result.status:
    print(f"注册成功，api_key: {result.api_key}")

# 注册后 SDK 内部自动设置了认证凭证，可直接调用账务接口
balance = client.account.get_balance()

# 绑定智能体应用（注册时自动将 appid 绑定到默认令牌）
result = client.account.temp_register(appid=1)
```

---

### 2.2 临时用户转正式用户

临时注册用户通过绑定手机号转为正式用户，绑定后可使用手机号 + 密码登录。

分两步调用：

```python
# 第一步：发送验证码（只传手机号）
result = client.account.bind_phone(phone="13800138000")

# 第二步：输入验证码完成绑定（可选绑定智能体 appid）
result = client.account.bind_phone(phone="13800138000", code="123456", appid=1)
```

**输入：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `phone` | str | 是 | 要绑定的手机号 |
| `code` | str | 否 | 6位短信验证码（不传则自动发送验证码） |
| `appid` | int | 否 | 智能体应用 ID，绑定成功后自动绑定到默认令牌 |

**输出：`Result` 对象**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.message` | str | 提示信息（发送验证码时返回"验证码已发送，请查收短信"） |

**返回：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.status` | bool | `True`=操作成功，`False`=操作失败 |

**示例：**

```python
# 临时注册 → 绑定手机号 → 转为正式用户
reg = client.account.temp_register()

client.account.bind_phone(phone="13800138000")           # 发送验证码
result = client.account.bind_phone(phone="13800138000", code="123456")  # 绑定
if result.status:
    print("绑定成功")

# 之后可用手机号 + 密码登录（密码为 reg.password）
```

---

### 2.3 正式用户注册

分两步调用，无需手动发送验证码：

```python
# 第一步：发送验证码（只传手机号）
result = client.account.register(phone="13800138000")

# 第二步：输入验证码和密码完成注册（可选传入邮箱、用户名、邀请码、智能体 appid）
result = client.account.register(
    phone="13800138000",
    password="mypassword123",
    verification_code="123456",
    email="user@example.com",
    username="myuser",
    aff_code="INV123",
    appid=1
)
```

**输入：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `phone` | str | 是 | 手机号 |
| `password` | str | 第二步必填 | 密码（8-20字符，发送验证码时无需传入） |
| `verification_code` | str | 否 | 6位短信验证码（不传则自动发送验证码） |
| `email` | str | 否 | 邮箱 |
| `username` | str | 否 | 用户名（默认用手机号） |
| `aff_code` | str | 否 | 邀请码 |
| `appid` | int | 否 | 智能体应用 ID，传入后自动绑定到默认令牌 |

**输出：`Result` 对象**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.message` | str | 提示信息（发送验证码时返回"验证码已发送，请查收短信"） |

**返回：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.status` | bool | `True`=操作成功，`False`=操作失败 |

**示例：**

```python
# 注册新用户
client = MoyuAI()
result = client.account.register(phone="13800138000")  # 发送验证码
if result.status:
    print("验证码已发送")

result = client.account.register(phone="13800138000", password="mypass123", verification_code="123456")
if result.status:
    print("注册成功")

# 注册后用手机号 + 密码登录
client.account.login(username="13800138000", password="mypass123")
```

---

### 2.4 用户登录

```python
result = client.account.login(username="13800138000", password="mypassword123")
```

**输入：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `username` | str | 是 | 用户名、手机号或邮箱（三者任一均可） |
| `password` | str | 是 | 密码 |

**输出：`LoginResult` 对象**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.user_id` | int | 用户 ID |
| `.username` | str | 用户名 |
| `.display_name` | str | 显示名称 |
| `.user_status` | int | 用户状态：1=启用, 2=禁用 |
| `.access_token` | str | 认证凭证 |

**返回：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.status` | bool | `True`=登录成功，`False`=登录失败 |

**示例：**

```python
# 三种登录方式
result = client.account.login(username="myuser", password="pass123")
if result.status:
    print(f"登录成功: {result.username}")

client.account.login(username="13800138000", password="pass123")
client.account.login(username="user@example.com", password="pass123")

# 登录后自动认证，直接调账务接口
balance = client.account.get_balance()
```

---

### 2.5 查询余额

```python
balance = client.account.get_balance()
```

**输入：** 无参数。

**输出：`Balance` 对象**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.username` | str | 用户名 |
| `.phone` | str | 手机号 |
| `.balance_yuan` | float | 当前剩余额度（人民币元） |
| `.used_yuan` | float | 历史消耗额度（人民币元） |
| `.topup_yuan` | float | 历史充值额度（人民币元） |
| `.request_count` | int | 总请求次数 |

**返回：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.status` | bool | `True`=查询成功，`False`=查询失败 |

**示例：**

```python
balance = client.account.get_balance()
if balance.status:
    print(f"当前余额: ¥{balance.balance_yuan}")
    print(f"历史消耗: ¥{balance.used_yuan}")
    print(f"历史充值: ¥{balance.topup_yuan}")
```

---

### 2.6 充值

支持两种充值方式：兑换码充值和在线支付。

> **前置条件：** 充值前 SDK 会自动检查用户是否已绑定手机号（正式用户）。临时用户需先调用 `bind_phone()` 绑定手机号后才能充值，否则抛出 `MoyuAIError` 异常。

#### 方式一：兑换码充值

```python
result = client.account.topup(key="REDEEM_CODE_HERE")
```

**输入：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `key` | str | 是 | 兑换码 |

**输出：`TopupResult` 对象**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.message` | str | 提示信息 |
| `.added_yuan` | float | 本次充值金额（单位：元） |

**返回：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.status` | bool | `True`=充值成功，`False`=充值失败 |

**示例：**

```python
result = client.account.topup(key="ABC123")
if result.status:
    print(f"充值成功: +¥{result.added_yuan}")

# 临时用户充值会报错，需先绑定手机号
reg = client.account.temp_register()
client.account.bind_phone(phone="13800138000")
client.account.bind_phone(phone="13800138000", code="123456")
result = client.account.topup(key="ABC123")  # 绑定后可充值
```

#### 方式二：在线支付（支付宝/微信）

```python
record = client.account.online_topup(amount=10, payment_method="alipay", timeout=180, poll_interval=3)
```

调用后自动打开浏览器支付页面，等待用户完成支付，支付成功后返回充值记录。

**输入：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `amount` | int | 是 | 充值金额（元） |
| `payment_method` | str | 是 | 支付方式：`alipay`（支付宝）或 `wxpay`（微信） |
| `timeout` | int | 否 | 最长等待时间（秒），默认 180 |
| `poll_interval` | int | 否 | 轮询间隔（秒），默认 3 |

**输出：`TopUpRecord` 对象**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.amount` | int | 充值金额（元） |
| `.money` | float | 实际支付金额（元） |
| `.trade_no` | str | 订单号 |
| `.payment_method` | str | 支付方式 |
| `.pay_status` | str | 支付状态：`success`=已完成, `pending`=待支付 |
| `.create_time` | int | 创建时间（Unix 时间戳） |
| `.complete_time` | int | 完成时间 |

**返回：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.status` | bool | `True`=调用成功，`False`=调用失败 |

> 超时未支付将抛出 `MoyuAIError` 异常，异常信息中包含订单号。

**示例：**

```python
# 在线支付 10 元
record = client.account.online_topup(amount=10, payment_method="alipay")
if record.status:
    print(f"充值成功: {record.amount}元, 订单号: {record.trade_no}")

# 查询充值后余额
balance = client.account.get_balance()
print(f"当前余额: ¥{balance.balance_yuan}")
```

---

### 2.7 查询账单

```python
bills = client.account.get_bills(
    model_name="gpt-4o",
    token_name="my-key",
    start_time=1710000000,
    end_time=1710086400,
    bill_type="consume"
)
```

默认查询**今天 00:00:00 到当前时间**的全部记录（消费+充值），无需传时间参数。返回最新记录，上限 500 条。

**输入：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `model_name` | str | 否 | 按模型名称过滤 |
| `token_name` | str | 否 | 按令牌名称过滤 |
| `start_time` | int | 否 | 开始时间（Unix 时间戳秒），默认今天 00:00:00 |
| `end_time` | int | 否 | 结束时间（Unix 时间戳秒），默认当前时间 |
| `bill_type` | str | 否 | 账单类型：`"consume"`=消费，`"topup"`=充值，不传则返回全部 |

**输出：`BillResult` 对象**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.total` | int | 时间范围内总记录数 |
| `.bills` | list[BillRecord] | 账单列表（最多 500 条） |

每个 `BillRecord` 包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `.time` | str | 记录时间（`2026-03-12 14:30:00` 格式） |
| `.model` | str | 使用的模型名称 |
| `.prompt_tokens` | int | 输入 token 数 |
| `.completion_tokens` | int | 输出 token 数 |
| `.cost_yuan` | float | 金额（人民币元） |
| `.token_name` | str | 使用的令牌名称 |
| `.use_time_ms` | int | 请求耗时（毫秒） |

**返回：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.status` | bool | `True`=查询成功，`False`=查询失败 |

**示例：**

```python
# 查询今日全部记录（消费+充值，默认）
bills = client.account.get_bills()
if bills.status:
    print(f"总记录: {bills.total}")
    print(f"金额: ¥{bills.bills[0].cost_yuan}")

# 只查询消费记录
bills = client.account.get_bills(bill_type="consume")

# 只查询充值记录
bills = client.account.get_bills(bill_type="topup")

# 按模型过滤
bills = client.account.get_bills(model_name="moonshot-v1-8k")

# 按令牌过滤
bills = client.account.get_bills(token_name="my-key")

# 指定时间范围（Unix 时间戳）
import time
bills = client.account.get_bills(
    start_time=int(time.time()) - 86400 * 7,  # 最近7天
    end_time=int(time.time())
)
```

---

### 2.8 查看令牌

```python
result = client.account.get_tokens(page=1, page_size=10)
```

**输入：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page` | int | 否 | 页码，默认 1 |
| `page_size` | int | 否 | 每页条数，默认 10 |

**输出：`TokensResult` 对象**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.items` | list[TokenInfo] | 令牌列表 |

每个 `TokenInfo` 包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `.id` | int | 令牌 ID |
| `.name` | str | 令牌名称 |
| `.key` | str | API Key（`sk-xxx` 格式） |
| `.token_status` | int | 令牌状态：1=启用, 2=禁用, 3=已过期, 4=额度耗尽 |
| `.remain_yuan` | float | 剩余额度（单位：元） |
| `.used_yuan` | float | 已用额度（单位：元） |
| `.unlimited_quota` | bool | 是否无限额度 |
| `.expired_time` | int | 过期时间（-1=永不过期） |
| `.created_time` | int | 创建时间（Unix 时间戳） |
| `.appid` | int | 绑定的智能体应用 ID（0表示未绑定） |
| `.group` | str | 令牌所属分组（空字符串表示默认分组） |

**返回：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.status` | bool | `True`=查询成功，`False`=查询失败 |

**示例：**

```python
result = client.account.get_tokens()
if result.status:
    for t in result.items:
        print(f"{t.name} | {t.key[:20]}... | 状态:{t.token_status} | 剩余:¥{t.remain_yuan} | 已用:¥{t.used_yuan}")
```

---

### 2.9 创建令牌

```python
result = client.account.create_token(
    name="my-agent-key",
    remain_yuan=10,
    unlimited_quota=False,
    expired_time=-1,
    model_limits_enabled=False,
    model_limits="",
    appid=1,
    group="default"
)
```

**输入：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | str | 是 | 令牌名称（最长 50 字符） |
| `remain_yuan` | float | 否 | 令牌额度（单位：元，`unlimited_quota=False` 时生效） |
| `unlimited_quota` | bool | 否 | 是否无限额度，默认 True |
| `expired_time` | int | 否 | 过期时间（Unix 时间戳，-1=永不过期），默认 -1 |
| `model_limits_enabled` | bool | 否 | 是否启用模型限制，默认 False |
| `model_limits` | str | 否 | 允许的模型列表（逗号分隔） |
| `appid` | int | 否 | 智能体应用 ID |
| `group` | str | 否 | 分组名称（不传则使用默认分组，可通过 `get_groups()` 查看可用分组） |

**输出：`Result` 对象**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.message` | str | 提示信息 |

**返回：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.status` | bool | `True`=创建成功，`False`=创建失败 |

> 创建后通过 `get_tokens()` 获取新令牌的 key。

---

### 2.10 更新令牌

```python
result = client.account.update_token(
    id=10,
    name="renamed-key",
    status=1,
    remain_yuan=10,
    unlimited_quota=False,
    expired_time=-1,
    model_limits_enabled=False,
    model_limits="gpt-4o,claude-opus-4-6",
    appid=2,
    group="vip"
)
```

**输入：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | int | 是 | 令牌 ID |
| `name` | str | 否 | 新名称 |
| `status` | int | 否 | 1=启用, 2=禁用 |
| `remain_yuan` | float | 否 | 令牌额度（单位：元） |
| `unlimited_quota` | bool | 否 | 是否无限额度 |
| `expired_time` | int | 否 | 过期时间 |
| `model_limits_enabled` | bool | 否 | 是否启用模型限制 |
| `model_limits` | str | 否 | 允许的模型列表 |
| `appid` | int | 否 | 智能体应用 ID（传0可清除绑定） |
| `group` | str | 否 | 分组名称（传空字符串可清除分组回到默认） |

> 注意：输入参数中的 `status` 是传给服务端的令牌启用/禁用状态（int），与返回值中的 `.status`（bool，表示调用是否成功）含义不同。

**输出：`UpdateTokenResult` 对象**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.data` | dict | 更新后的完整令牌信息 |

**返回：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.status` | bool | `True`=更新成功，`False`=更新失败 |

**示例：**

```python
result = client.account.update_token(id=10, name="renamed-key", appid=2)
if result.status:
    print(f"更新后 appid: {result.data.get('appid')}")
```

---

### 2.11 删除令牌

```python
result = client.account.delete_token(id=10)
```

**输入：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | int | 是 | 令牌 ID |

**输出：`Result` 对象**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.message` | str | 提示信息 |

**返回：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.status` | bool | `True`=删除成功，`False`=删除失败 |

**示例：**

```python
result = client.account.delete_token(id=10)
if result.status:
    print("删除成功")
```

---

### 2.12 查看可用分组

```python
result = client.account.get_groups()
```

**输入：** 无

**输出：`GroupsResult` 对象**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.items` | list[GroupInfo] | 分组列表 |

每个 `GroupInfo` 包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `.name` | str | 分组名称（创建/更新令牌时传入的 group 参数值） |
| `.ratio` | any | 分组倍率（数字或 "自动"） |
| `.desc` | str | 分组描述 |

**返回：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.status` | bool | `True`=查询成功，`False`=查询失败 |

**示例：**

```python
result = client.account.get_groups()
if result.status:
    for g in result.items:
        print(f"分组: {g.name} | 倍率: {g.ratio} | 描述: {g.desc}")

# 创建令牌时指定分组
client.account.create_token(name="vip-key", group="vip")
```

---

## 3. 使用模型

> 认证方式：请求头 `Authorization: Bearer <api_key>`（api_key 通过 `temp_register()` 或 `get_tokens().items` 获取）。
> 基础地址：`https://www.moyu.cn`

---

### 3.1 获取模型列表

```python
result = client.account.get_models(api_key="sk-xxxx")
```

**输入：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `api_key` | str | 是 | API Key（sk-xxx 格式） |

**输出：`ModelsResult` 对象**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.items` | list[ModelInfo] | 模型列表 |

每个 `ModelInfo` 包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `.id` | str | 模型名称（如 `claude-opus-4-6`） |
| `.object` | str | 类型（固定为 `model`） |
| `.owned_by` | str | 模型归属标识。命中内置映射时为供应商名（如 `openai`、`deepseek`、`coze`），**未命中映射的模型统一返回 `custom`**（如示例中的 `claude-opus-4-6`）|
| `.raw` | dict | API 原始返回的完整字段（预留，后续新增字段可直接从此取） |

**返回：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `.status` | bool | `True`=查询成功，`False`=查询失败 |

**示例：**

```python
reg = client.account.temp_register()
result = client.account.get_models(api_key=reg.api_key)
if result.status:
    for m in result.items:
        print(f"{m.id} | {m.owned_by}")
    # → claude-opus-4-6 | custom
    # → deepseek-v3 | coze
    # → chatgpt-4o-latest | openai

    # 通过 raw 访问 API 返回的任意字段（无需等 SDK 更新）
    print(result.items[0].raw)
```

---

### 3.2 文本对话

```
POST /v1/chat/completions
```

兼容 OpenAI Chat Completions 格式，支持所有文本模型。

**Python 示例：**

```python
import requests

api_key = "sk-xxxx"  # 你的 API Key

# 单轮对话
response = requests.post(
    "https://www.moyu.cn/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "你好"}]
    }
)
data = response.json()
print(data["choices"][0]["message"]["content"])

# 多轮对话（携带历史消息）
response = requests.post(
    "https://www.moyu.cn/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": "你是一个助手"},
            {"role": "user", "content": "什么是机器学习？"},
            {"role": "assistant", "content": "机器学习是人工智能的一个分支..."},
            {"role": "user", "content": "有哪些常见算法？"}
        ]
    }
)

# 流式输出
response = requests.post(
    "https://www.moyu.cn/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "写一首诗"}],
        "stream": True
    },
    stream=True
)
for line in response.iter_lines():
    if line:
        print(line.decode("utf-8"))
```

**主要参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model | string | 是 | 模型名称，如 `gpt-4o`、`claude-opus-4-6`、`deepseek-v3` 等 |
| messages | array | 是 | 对话消息列表，每条包含 `role`（system/user/assistant）和 `content` |
| stream | bool | 否 | 是否流式输出，默认 false |
| temperature | number | 否 | 采样温度 0-2，默认 1 |
| max_tokens | int | 否 | 最大生成 token 数 |

**响应格式：**

```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "model": "gpt-4o",
  "choices": [{
    "index": 0,
    "message": {"role": "assistant", "content": "你好！有什么可以帮你的？"},
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 9,
    "completion_tokens": 12,
    "total_tokens": 21
  }
}
```

---

### 3.3 图片生成

```
POST /v1/images/generations
```

使用豆包 Seedream 模型生成图片。

**Python 示例：**

```python
import requests

api_key = "sk-xxxx"

response = requests.post(
    "https://www.moyu.cn/v1/images/generations",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "model": "doubao-seedream-4-5-251128",
        "prompt": "星际穿越，黑洞，电影大片，超现实主义，极致的光影",
        "size": "2K",
        "response_format": "url"
    }
)
data = response.json()
print(data["data"][0]["url"])  # 图片下载地址
```

**主要参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model | string | 是 | 固定为 `doubao-seedream-4-5-251128` |
| prompt | string | 是 | 图片描述提示词 |
| size | string | 否 | 图片尺寸，如 `2K`、`2048x2048`、`2848x1600`，默认 2K |
| quality | string | 否 | `standard`(标准) 或 `hd`(高清)，默认 standard |
| response_format | string | 否 | `url`(返回链接) 或 `b64_json`(返回 Base64) |

**响应格式：**

```json
{
  "model": "doubao-seedream-4-5-251128",
  "created": 1770558368,
  "data": [
    {"url": "https://...", "size": "2048x2048"}
  ],
  "usage": {
    "generated_images": 1,
    "output_tokens": 16384,
    "total_tokens": 16384
  }
}
```

---

### 3.4 视频生成

视频生成为**异步接口**，提交任务后通过轮询获取结果。

#### 视频生成

```
POST /v1/video/generations
```

**Python 示例（文生视频）：**

```python
import requests
import time

api_key = "sk-xxxx"

# 提交视频生成任务
response = requests.post(
    "https://www.moyu.cn/v1/video/generations",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "model": "doubao-seedance-1-5-pro-251215",
        "prompt": "一只橘色的猫咪在阳光下的花园里追逐蝴蝶",
        "duration": 5
    }
)
task_id = response.json()["task_id"]
print(f"任务已提交: {task_id}")

# 轮询查询结果
while True:
    result = requests.get(
        f"https://www.moyu.cn/v1/video/generations/{task_id}",
        headers={"Authorization": f"Bearer {api_key}"}
    ).json()
    print(f"状态: {result}")
    # 根据返回状态判断是否完成，完成后 break
    time.sleep(5)
```

**图生视频示例：**

```python
response = requests.post(
    "https://www.moyu.cn/v1/video/generations",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "model": "doubao-seedance-1-5-lite-i2v-250428",
        "prompt": "让画面中的人物缓缓转头微笑",
        "images": ["https://example.com/image.jpg"],
        "duration": 5
    }
)
```

**提交任务参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model | string | 是 | 模型名称，见下方列表 |
| prompt | string | 是 | 视频内容描述 |
| images | string[] | 图生视频时必填 | 输入图片 URL 数组 |
| duration | int | 否 | 视频时长（秒），默认 5 |

**支持的模型：**

| 模型名称 | 说明 |
|---------|------|
| doubao-seedance-1-5-pro-251215 | Seedance 1.5 Pro（推荐） |
| doubao-seedance-1-5-lite-t2v-250428 | Seedance 1.5 Lite 文生视频 |
| doubao-seedance-1-5-lite-i2v-250428 | Seedance 1.5 Lite 图生视频 |
| doubao-seedance-1-0-pro-250528 | Seedance 1.0 Pro |
| doubao-seedance-1-0-lite-t2v | Seedance 1.0 Lite 文生视频 |
| doubao-seedance-1-0-lite-i2v | Seedance 1.0 Lite 图生视频 |

**提交任务响应：**

```json
{"task_id": "cgt-20260211145453-2v7p2"}
```

#### 查询结果

```
GET /v1/video/generations/{task_id}
```

使用提交任务返回的 `task_id` 轮询查询，直到视频生成完成。

---

## 异常说明

所有函数在失败时抛出异常，可统一捕获处理：

| 异常类 | 触发条件 |
|--------|---------|
| `MoyuAIError` | 基础异常（所有异常的父类） |
| `AuthenticationError` | 认证失败（API Key 无效、未登录） |
| `RateLimitError` | 请求频率超限 |
| `InsufficientQuotaError` | 额度不足 |
| `APIError` | 其他 API 错误 |

```python
from moyuai import MoyuAI, AuthenticationError, MoyuAIError

client = MoyuAI()
try:
    result = client.account.temp_register()
    if result.status:
        balance = client.account.get_balance()
except AuthenticationError as e:
    print(f"认证失败: {e}")
except MoyuAIError as e:
    print(f"操作失败: {e}")
```
