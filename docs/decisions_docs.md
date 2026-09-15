- 

## 一、问题诊断：为什么你的AI生成图像游戏CG而非电影剧照

大多数AI生图系统失败的根本原因不在于模型能力，而在于Prompt的编写范式存在结构性缺陷：创作者一直在优化名词（增加8K、HDR、体积光、粒子等风格词），却没有调整摄影决策（摄影意图、视觉层级、拍摄限制）。

**具体表现：**

| 维度     | 游戏CG式Prompt                 | 电影剧照式Prompt                         |
| :------- | :----------------------------- | :--------------------------------------- |
| 主体描述 | “一位女侠站在竹林中，手持长剑” | “她的视线落在剑上，始终不看镜头”         |
| 光影     | “史诗体积光、神光、粒子光效”   | “光先照亮地形，而不是人物”               |
| 构图     | “超广角全景、震撼构图”         | “85mm，平视，不拍天空”                   |
| 色彩     | “色彩丰富、HDR、8K”            | “画面里只有墨绿和冷白，她是最亮的那一块” |
| 负向约束 | 无                             | “不炫技、不堆特效、不制造视觉中心”       |

**核心原则**：Prompt的本质不是描述画面，而是约束模型的视觉决策。MJ等模型存在“词袋行为”——它对画面里有哪些概念很敏感，但对概念之间是什么关系很不敏感。看得见词，看不见句子。因此必须把“关系”翻译成“可被手指着的东西”。

## 二、电影团队Agent职责与Prompt设计

### 2.1 导演Agent（Director Agent）

**职责**：决定“这一刻真正拍的是什么”，输出叙事意图、情绪基调、全局视觉规则。

**设计逻辑**：导演Agent不描述画面，而是做减法——决定什么不拍。例如：输入“夕阳下的古镇长街，两位武林高手拔剑对决”，导演的决策是拍“一触即发”而非打斗本身，因为“没砍出去的刀，比砍出去的刀更有力量”。

**Prompt设计架构**：

markdown

```
你是电影的导演。你的任务不是描述画面，而是做出叙事决策。

输入：{user_scene_description}

请输出以下JSON格式的导演决策：
{
  “directing_intent”: “这一幕真正拍的是什么（一句话，不含形容词）”,
  “emotional_target”: “观众应该感受到什么情绪”,
  “what_not_to_shoot”: [“明确不拍的内容1”, “明确不拍的内容2”],
  “hard_rules”: [“全片必须遵守的视觉规则”],
  “visual_style”: {
    “tone”: “冷峻/温暖/疏离/亲密”,
    “reference_films”: [“参考电影1”, “参考电影2”]
  }
}

约束：禁止使用HDR、8K、Masterpiece、史诗、体积光等风格词。
所有决策必须是可观察、可验证的视觉选择。
```



**示例输出**：

json

```
{
  “directing_intent”: “拍的是回忆，不是战斗”,
  “emotional_target”: “安静中的紧张感”,
  “what_not_to_shoot”: [“不拍天空”, “不拍打斗动作”, “不制造视觉中心”],
  “hard_rules”: [“所有切点落在静默里”, “人物不做反应，禁止点头、皱眉”],
  “visual_style”: { “tone”: “清冷克制”, “reference_films”: [“卧虎藏龙”, “刺客聂隐娘”] }
}
```



### 2.2 摄影指导Agent（DP Agent）

**职责**：决定镜头如何观察——焦段、机位、光位、景深、运镜策略。摄影指导负责掌控摄影风格，参与镜头设计和实际拍摄。

**设计逻辑**：摄影指导的工作是把导演的叙事意图翻译成具体的摄影参数。摄影师不会写“一座山、一位修仙者、一片云海”，而是写“山才是主角，人物只是比例尺，光先照亮地形”。

**核心参数决策表**：

| 参数     | 可选值                                                    | 决策依据                               |
| :------- | :-------------------------------------------------------- | :------------------------------------- |
| 焦段     | 24mm超广角 / 35mm广角 / 50mm标准 / 85mm中长焦 / 135mm长焦 | 广角强调空间，长焦压缩空间             |
| 机位高度 | 低角度 / 平视 / 高角度 / 俯拍                             | 低角度赋予力量，高角度表现脆弱         |
| 光位     | 伦勃朗光（4:30/7:30方向）/ 蝴蝶光 / 侧光 / 逆光 / 底光    | 伦勃朗光在阴影侧眼睛下方形成倒三角光斑 |
| 景深     | 浅景深（f/1.4-f/2.8）/ 深景深（f/8-f/16）                 | 浅景深隔离主体，深景深保持空间信息     |
| 色彩策略 | 限制在3-5种颜色                                           | 色彩越少，电影感越强                   |

**Prompt设计架构**：

markdown

```
你是电影的摄影指导。根据导演的决策，你需要做出具体的摄影参数选择。

导演决策：{director_output}

请输出以下JSON格式：
{
  “focal_length”: “85mm”,
  “camera_height”: “平视，机位在竹林内部”,
  “composition_rule”: {
    “subject_position”: “偏右下，占画面8%”,
    “environment_dominance”: “竹林占画面85%以上”
  },
  “lighting”: {
    “key_light_direction”: “从左上45度，伦勃朗光”,
    “light_priority”: “光先照剑，不照脸”,
    “light_ratio”: “面部暗部与亮部比例4:1”
  },
  “depth_of_field”: “浅景深，前景竹叶虚化，中景人物清晰，背景散焦”,
  “color_palette”: {
    “colors”: [“墨绿”, “冷白”, “银灰”],
    “max_colors”: 3,
    “brightest_element”: “剑身上的反光”
  },
  “camera_movement”: “{运镜决策，见第四节}”
}
```



### 2.3 美术指导Agent（Art Director Agent）

**职责**：决定色彩、材质、空间层次和道具。美术指导负责整部影片的美术风格，包括场景布置和道具设计。

**设计逻辑**：美术指导的工作不是“往画面里加东西”，而是做减法。核心策略是：把颜色压到五种以内，规定“整条街只许有一点红——街边那面被风掀起的酒旗”。

**Prompt设计架构**：

markdown

```
你是电影的美术指导。根据导演和摄影指导的决策，设计美术方案。

请输出：
{
  “color_scheme”: {
    “allowed_colors”: [“墨绿”, “冷白”, “银灰”, “深褐”],
    “accent_color”: “唯一的暖色是剑柄上的旧铜色”,
    “color_temperature”: “整体冷调，色温5600K偏蓝”
  },
  “material_language”: {
    “dominant_texture”: “湿润的竹叶、粗糙的岩石”,
    “surface_quality”: “哑光为主，唯一的高光是剑身”
  },
  “spatial_layers”: {
    “foreground”: “垂落的竹叶，虚焦”,
    “midground”: “人物站立的石台”,
    “background”: “竹林的暗色纵深”
  },
  “props”: {
    “essential”: [“长剑”, “旧铜剑鞘”],
    “forbidden”: [“发光特效”, “粒子飞舞”]
  }
}
```



### 2.4 创意总监Agent（Creative Director Agent）

**职责**：设计观众的第一眼体验——注意力如何在画面中流动。创意总监决定观众为什么停留。

**设计逻辑**：创意总监设计“视觉锚点”和“注意力路径”。例如：“第一眼看到的是灌满长街的金光，和光里两个黑色的人影；第二眼才会发现，整条街上唯一在动的是那面酒旗”。

**Prompt设计架构**：

markdown

```
你是电影的创意总监。设计观众的视觉注意力路径。

请输出：
{
  “first_glance”: “第一眼看到什么（最亮/最大的元素）”,
  “second_glance”: “第二眼发现什么（运动/细节元素）”,
  “visual_anchor”: “画面的绝对视觉锚点”,
  “negative_space”: “哪里有刻意的留白”,
  “attention_sequence”: [“第一眼”, “第二眼”, “第三眼”]
}
```



### 2.5 负向提示词Agent（Negative Prompt Agent）

**职责**：将所有否定式指令翻译成正面描述。这是电影感Prompt设计中最容易被忽略但最关键的一环。

**设计逻辑**：MJ不认识“不要幼态脸”，写成`not`，MJ收到的是`dolleyes`。要排除什么，就去正面描述它的反面。“不要幼态脸”要翻译成“面部精瘦，颧骨和下颌清晰可见”。否定式指令的翻译规则是：把“不要X”翻译成“要Y”，其中Y是X的精确对立面。

**核心翻译规则表**：

| 否定式指令   | 错误写法         | 正确翻译                                       |
| :----------- | :--------------- | :--------------------------------------------- |
| 不要英雄感   | `not heroic`     | “她此刻刚停下脚步，剑还垂在身侧”               |
| 不要摆拍     | `not posed`      | “肩膀放松，重心偏向一侧，一只手自然下垂”       |
| 不要CG感     | `no CGI`         | “皮肤有毛孔和细微纹理，衣料有自然褶皱”         |
| 不要大眼睛   | `not big eyes`   | “面部精瘦，颧骨和下颌清晰可见”                 |
| 不要视觉中心 | `no focal point` | “画面最亮的区域在左上角，人物处于中间调的暗部” |
| 不要HDR      | `no HDR`         | “高光有自然溢出，阴影保留细节但不死黑”         |

**Prompt设计架构**：

markdown

```
你是负向提示词翻译专家。将以下否定式指令翻译成MJ能理解的正面描述。

输入否定列表：{negative_directives}

翻译规则：
1. 情绪→翻译成可观察的身体动作
2. 否定→翻译成对立面的正面描述
3. 比例→翻译成百分比
4. 色板→翻译成明暗关系
5. 抽象概念→翻译成具体的视觉证据

输出格式：
{
  “translation_table”: [
    { “original”: “不要英雄感”, “translated”: “她刚停下脚步，剑还垂在身侧，肩膀放松” },
    { “original”: “不拍天空”, “translated”: “竹梢在画面顶端合拢，遮住全部天空区域” }
  ],
  “final_negative_prompt”: “(汇总后的负向提示词字符串)”
}
```



## 三、镜头运镜系统：设计逻辑与架构

### 3.1 运镜的核心认知

运镜不是装饰品。它改变框架中谁拥有权力、观众注意到什么以及信息到达的时间。**摄影机绝对不是为了运动而运动**，所有推拉跟拍均服务于情绪表达。

### 3.2 运镜决策树

基于电影摄影理论，建立以下决策逻辑：

**第一层：情绪目标判断**

- 想拉近观众与角色的情感距离 → **推镜头（Push In / Dolly In）**
- 想揭示角色的渺小或环境的宏大 → **拉镜头（Pull Out / Dolly Out）或升镜头（Crane Up）**
- 想跟随角色的运动 → **跟拍（Tracking / Following）**
- 想在空间中发现新信息 → **摇镜（Pan / Tilt）**
- 想创造第一人称的紧迫感 → **POV或克制的手持（Handheld）**
- 想建立地理关系 → **航拍（Drone/Aerial）**
- 想传达权威/冷静/客观 → **固定镜头（Locked Frame）**



**第二层：技术参数细化**

| 运动类型       | 物理描述       | 速度     | 景别变化    | 情绪效果   |
| :------------- | :------------- | :------- | :---------- | :--------- |
| Dolly In       | 摄影机物理前移 | 缓慢     | 中景→特写   | 亲密、认同 |
| Dolly Out      | 摄影机物理后退 | 缓慢     | 特写→全景   | 孤立、后果 |
| Pan Left/Right | 水平旋转       | 匀速     | 不变        | 连接、发现 |
| Tilt Up/Down   | 垂直旋转       | 匀速     | 不变        | 揭示、压迫 |
| Tracking       | 与主体同速移动 | 匹配主体 | 不变        | 陪伴、动力 |
| Crane Up       | 垂直上升       | 可加速   | 全景→大全景 | 规模、告别 |
| Handheld       | 模拟人体晃动   | 不规则   | 灵活        | 临场、紧张 |
| Locked         | 三脚架固定     | 零       | 不变        | 权威、客观 |



**第三层：速度曲线与身体感**

运镜不应是机械的匀速运动。摄影师的身体有反应时间。加入“摄影师误判”可以增加真实感：摄影机慢半拍、提前、减速、落后等；追上人物后又因为惯性多走10-15厘米，再进行小幅回收。

### 3.3 运镜Prompt的完整结构

综合多个AI视频生成模型的最佳实践，一个完整的运镜Prompt应包含以下要素：

text

```
[摄影机起始位置] + [运镜类型] + [运动路径] + [速度曲线] + [焦点变化] + [结束状态] + [约束条件]
```



**示例Prompt（竹林女侠场景）** ：

text

```
摄影机起始位置：竹林内部，85mm焦段，平视高度，机位在人物右后方3米处。
运镜类型：缓慢Dolly In，单一摄影机运动，不叠加其他运动。
运动路径：从人物右后方沿直线向人物左前方移动，移动距离1.5米。
速度曲线：前2秒极慢（约0.3米/秒），第3秒微微加速到0.5米/秒，最后1秒减速停稳。
焦点变化：起始时前景竹叶清晰，人物柔焦；运动中焦点缓慢转移到人物持剑的手上。
结束状态：最终停在人物左侧45度位置，画面中人物占15%，竹林占85%，剑身上的反光成为最亮区域。
约束条件：无突然变焦，无镜头畸变，摄影机运动稳定如轨道上的dolly，禁止手持晃动。
```



### 3.4 运镜与光影的联动

动态光线是运镜的重要配合要素。运镜过程中，光照条件应随摄影机位置变化而变化：

- 人物从较亮区域走入屋檐附近时，脸部亮度应自然下降
- 处于遮阴区域时，顶部更暗、侧脸接受墙面反光
- 跨越警戒线后，随着人物与建筑位置改变，脸部光比也要变化

**Prompt写法**：

text

```
动态光照约束：随着摄影机前移，前方竹林间隙透过的月光逐渐减少，
人物面部从半亮逐渐过渡到明暗对比3:1的伦勃朗光。
当摄影机越过竹叶遮挡层时，摄影机本身应短暂进入阴影区域，
画面整体亮度下降约1档曝光。
```



### 3.5 运镜与人物调度的配合

多人场景中，运镜必须与人物调度联动。提示词需要像做场面调度一样明确空间关系：

text

```
空间关系锁定：A永远在B左边，B永远在C左边。
运镜过程中，A从画面右侧进入，形成浅三角站位（A前、B中、C后，前后差异5-15厘米）。
摄影机运动路径绕三人形成90度弧线，始终保持B在画面中心偏左。
焦点始终落在A的眼睛上，B和C保持柔焦但轮廓可辨识。
```



## 四、系统级约束：负向提示词与全局规则

### 4.1 负向提示词的分类体系

负向提示词不应被当作“垃圾桶”，而应精准排除干扰项。建议分为三层：

**第一层：技术保底（所有场景通用）**

text

```
deformed hands, extra fingers, bad anatomy, blurry background,
watermark, text, logo, low quality, jpeg artifacts,
overexposed, underexposed, flat lighting
```



**第二层：风格排除（根据目标风格选择）**

text

```
// 排除CG感
3D render, CGI, cartoon, anime, plastic skin, game art,
oversaturated, HDR, lens flare, particle effects, volumetric light

// 排除摆拍感
posed, stiff, mannequin, artificial smile, looking at camera
```



**第三层：场景特化（根据具体场景定制）**

text

```
// 竹林武侠场景
no sky visible, no bright sky, no sun, no clouds,
no modern elements, no western architecture
```



### 4.2 全局硬约束系统

借鉴`cinematic-compiler`项目的架构，在每个Agent的输出中嵌入`must_preserve`契约：

json

```
{
  “shot_id”: “SHOT_03”,
  “must_preserve”: {
    “character_identity”: “23岁清冷女侠，面部精瘦，颧骨清晰”,
    “costume_invariants”: “墨绿色交领长袍，银灰色腰带”,
    “prop_state”: “长剑未出鞘，剑柄旧铜色”,
    “lighting_continuity”: “月光从左上方45度入射”,
    “color_palette_lock”: [“墨绿”, “冷白”, “银灰”]
  },
  “repair_trigger”: “任何一项must_preserve被违反时，触发重新生成”
}
```



## 五、完整Agent协作流水线示例

以“23岁清冷女侠站在竹林中，月夜，看剑”为输入，展示完整的Agent协作输出：

### Step 1：导演Agent输出

json

```
{
  “directing_intent”: “拍的是回忆，不是战斗”,
  “what_not_to_shoot”: [“不拍天空”, “不拍打斗”],
  “emotional_target”: “安静的紧张感”
}
```



### Step 2：摄影指导Agent输出

json

```
{
  “focal_length”: “85mm”,
  “camera_height”: “平视，机位留在竹林里面”,
  “lighting_priority”: “光先照剑，不照脸”,
  “color_palette”: [“墨绿”, “冷白”, “银灰”],
  “subject_scale”: “人物占画面8%”
}
```



### Step 3：美术指导Agent输出

json

```
{
  “color_scheme”: [“墨绿”, “冷白”, “银灰”],
  “accent”: “剑身上的月光反射”,
  “spatial_layers”: {
    “foreground”: “垂落的竹叶，虚焦”,
    “background”: “竹林的暗色纵深，顶端合拢遮住天空”
  }
}
```



### Step 4：运镜Agent输出

json

```
{
  “camera_start”: “竹林内部，右后方3米”,
  “movement”: “Dolly In，前2秒0.3m/s，第3秒0.5m/s，最后减速停稳”,
  “focus_shift”: “从前景竹叶→剑身”,
  “end_state”: “人物占15%，剑身反光为最亮区域”
}
```



### Step 5：最终MJ Prompt组装

text

```
85mm lens, eye-level, inside bamboo forest, moonlight from upper left at 45 degrees.
A young woman in dark green robes stands still, her gaze fixed on a sword
she holds at her side, never looking at the camera.
The sword's copper hilt catches the only warm highlight in the frame.
Bamboo leaves fill 85% of the frame, obscuring the sky completely.
Color palette limited to: dark green, cold white, silver gray.
Shallow depth of field: foreground bamboo leaves blurred, midground figure sharp, background soft.
The brightest point in the frame is the reflection on the sword blade.
Low contrast, muted tones, the figure is the brightest element but occupies only 8% of frame.
Camera: slow dolly in from 3 meters behind, starting at 0.3m/s, accelerating slightly then decelerating to a stop. Focus pulls from foreground leaves to the sword. No sudden zoom. Stable, like a dolly on tracks.
```



### Step 6：负向提示词

text

```
3D render, CGI, cartoon, plastic skin, game art, oversaturated,
HDR, lens flare, particle effects, volumetric light, epic,
sky visible, sun, clouds, modern elements, posed, stiff,
looking at camera, big eyes, doll face, visual center, bright background
```



## 六、给质量门控检查的优化建议

将本文档作为上下文提供给质量门控单元时，建议附加以下元指令：

markdown

```
你是一个多Agent电影生成系统的架构优化师。请根据以下技术文档，
审查并优化我的项目中的Prompt设计。具体任务：

1. 检查每个Agent的Prompt是否包含“摄影决策”而非“物体清单”
2. 检查是否使用了负向提示词翻译机制（将“不要X”翻译成“要Y”）
3. 检查运镜Prompt是否包含：起始位置、运动类型、路径、速度曲线、焦点变化、结束状态、约束
4. 检查是否有must_preserve契约机制来保证跨镜头的一致性
5. 检查色彩策略是否做了主动限制（3-5种颜色）而非无限增加
6. 检查是否使用了“视觉层级”概念（主体占画面百分比、最亮元素是什么）
7. 为每个Agent生成优化后的Prompt模板，保持与现有项目结构兼容
```



## 七、关键概念速查表

| 概念          | 含义                 | Prompt写法                               |
| :------------ | :------------------- | :--------------------------------------- |
| 摄影意图      | 为什么这样拍         | “拍的是回忆，不是战斗”                   |
| 视觉层级      | 谁才是主角           | “竹林占85%，人物占8%”                    |
| 拍摄限制      | 什么不拍             | “不拍天空，不制造视觉中心”               |
| 词袋行为      | MJ只认名词，不认关系 | 把“沉默”翻译成“只有竹叶在晃，别的全停住” |
| 伦勃朗光      | 面部三角光斑         | “主光在4:30方向，面部阴影侧有倒三角亮区” |
| 动态光比      | 运镜中光照变化       | “随着靠近屋檐，脸部亮度自然下降”         |
| Must-Preserve | 跨镜头一致性契约     | 角色外貌、服装、道具状态锁定             |
| 负向翻译      | 否定式转正面         | “不要幼态脸”→“面部精瘦，颧骨清晰”        |