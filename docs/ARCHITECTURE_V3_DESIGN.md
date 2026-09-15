# AI视频生成完整架构设计 V3

> 基于真实电影制作流程和视觉连续性需求的完整架构

---

## 一、核心问题分析

### 当前架构的致命缺陷：

1. **连续性断裂**：
   - ❌ 每个镜头独立生成，没有视觉遗传
   - ❌ 角色在不同镜头中外观差异大
   - ❌ 场景转场生硬，没有过渡设计

2. **伪协作问题**：
   - ❌ Agent只是顺序执行，没有真正讨论
   - ❌ 没有反馈循环和迭代优化
   - ❌ 缺少"创作会议"机制

3. **缺失关键环节**：
   - ❌ 没有分镜设计
   - ❌ 没有预演（Animatic）
   - ❌ 没有剪辑和节奏控制
   - ❌ 没有连续性协调员

---

## 二、新架构核心理念

### 1. 三阶段工作流

```
┌──────────────────────────────────────────────────────┐
│  Phase 1: CREATIVE DEVELOPMENT (创意开发阶段)         │
│  目标：确定故事、角色、世界观                         │
└──────────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│  Phase 2: PRE-VISUALIZATION (预演阶段)               │
│  目标：分镜设计、动态预览、确定镜头序列               │
└──────────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│  Phase 3: PRODUCTION & POST (制作与后期阶段)          │
│  目标：逐镜头生成、实时质检、剪辑合成                 │
└──────────────────────────────────────────────────────┘
```

### 2. 创作会议机制（Creative Session）

**不是线性流程，而是讨论式协作**：

```python
class CreativeSession:
    """模拟真实创作会议"""
    
    def brainstorm(self, topic: str) -> Decision:
        """
        各Agent提出方案 → 讨论 → 投票 → 达成共识
        """
        proposals = []
        
        # 1. 各Agent独立提案
        for agent in self.agents:
            proposal = agent.propose(topic)
            proposals.append(proposal)
        
        # 2. 交叉评审
        for proposal in proposals:
            for agent in self.agents:
                feedback = agent.review(proposal)
                proposal.add_feedback(feedback)
        
        # 3. 修订提案
        revised_proposals = []
        for proposal in proposals:
            revised = proposal.author.revise(proposal)
            revised_proposals.append(revised)
        
        # 4. 投票决定
        decision = self.vote(revised_proposals)
        
        return decision
```

### 3. 视觉连续性系统（Visual Continuity System）

#### 核心机制：

**A. Shot Inheritance（镜头遗传）**
```python
shot_n = generate_video(
    prompt="埃利走入废墟",
    inherit_from={
        "last_frame": shot_n_1.get_last_frame(),  # 上一镜头最后一帧
        "character_pose": shot_n_1.character_final_pose,
        "lighting": shot_n_1.lighting_setup,
        "color_palette": shot_n_1.color_grading
    }
)
```

**B. Visual DNA（视觉基因）**
```python
class VisualDNA:
    """确保整部短剧视觉统一"""
    
    color_palette: List[str]  # 锁定色调
    lighting_style: str       # 光线风格
    camera_language: dict     # 镜头语言
    character_models: dict    # 角色模型ID
    
    def apply_to_shot(self, shot_prompt: str) -> str:
        """将视觉基因注入每个镜头提示词"""
        return f"""
        {shot_prompt}
        
        [Visual Consistency]
        - Color palette: {self.color_palette}
        - Lighting: {self.lighting_style}
        - Character model ID: {self.character_models['protagonist']}
        """
```

**C. Character Model Bank（角色模型库）**
```python
class CharacterBank:
    """角色一致性管理"""
    
    def create_character(self, name: str, ref_image: str):
        """创建角色视觉档案"""
        character_id = api.create_character_model(ref_image)
        self.characters[name] = {
            "id": character_id,
            "ref_image": ref_image,
            "visual_features": extract_features(ref_image),
            "poses": [],  # 收集所有出现过的姿态
            "expressions": []  # 收集所有表情
        }
    
    def get_character_for_shot(self, name: str, shot_num: int):
        """为镜头获取角色一致性参数"""
        char = self.characters[name]
        return {
            "character_id": char["id"],
            "reference_pose": char["poses"][-1] if shot_num > 0 else None
        }
```

---

## 三、完整Agent架构

### Phase 1: Creative Development Agents

#### 1. **CreativeDirector** (创意总监)
- **角色**：项目总负责人，主持创作会议
- **职责**：
  - 解析用户故事想法
  - 主持brainstorming session
  - 协调各Agent工作
  - 把控整体质量

#### 2. **Screenwriter** (编剧)
- **角色**：故事专家
- **职责**：
  - 创作完整剧本
  - 设计对话（不只是旁白）
  - 设计叙事节奏
  - 确保3秒hook

#### 3. **ConceptArtist** (概念艺术家)
- **角色**：视觉开发
- **职责**：
  - 设计角色外观
  - 设计场景概念
  - 定义色调和光线风格
  - 创建"Visual DNA"

#### 4. **WorldBuilder** (世界观构建师)
- **角色**：世界观设计
- **职责**：
  - 构建故事世界
  - 设计地点和道具
  - 管理角色关系

### Phase 2: Pre-visualization Agents

#### 5. **StoryboardArtist** (分镜师)
- **角色**：镜头设计
- **职责**：
  - 将剧本转化为分镜脚本
  - 设计镜头序列
  - 标注转场方式
  - 规划镜头连续性

```python
class Shot:
    shot_num: int
    duration: float
    action: str
    dialogue: str
    camera: CameraSetup
    transition_from_previous: str  # "cut", "dissolve", "match_cut"
    inherit_elements: List[str]     # 从上一镜头继承的元素
```

#### 6. **Cinematographer** (摄影指导)
- **角色**：视觉执行
- **职责**：
  - 定义每个镜头的摄影参数
  - 确保镜头间视觉连贯
  - 设计光线和构图

#### 7. **ContinuityCoordinator** (连续性协调员)
- **角色**：连续性专家
- **职责**：
  - 检查角色服装、道具一致性
  - 确保时间线连续
  - 标记需要共享的视觉元素

### Phase 3: Production & Post Agents

#### 8. **ProductionDirector** (制作导演)
- **角色**：生成执行
- **职责**：
  - 将分镜转化为API调用
  - 管理镜头遗传机制
  - 实时质检生成结果

#### 9. **Editor** (剪辑师)
- **角色**：节奏控制
- **职责**：
  - 审查生成镜头
  - 调整节奏和时长
  - 设计转场效果

#### 10. **MusicDirector** (音乐总监)
- **角色**：音频设计
- **职责**：
  - 设计配乐风格
  - 管理音效
  - 同步音画

---

## 四、工作流程详解

### Phase 1: Creative Development

```python
# Step 1.1: Creative Kickoff Meeting
session = CreativeSession(agents=[
    creative_director,
    screenwriter,
    concept_artist,
    world_builder
])

decision = session.brainstorm("用户故事想法：{user_input}")

# Step 1.2: Script Development (多轮迭代)
draft_1 = screenwriter.write_script(decision)
feedback = session.review(draft_1)
final_script = screenwriter.revise(draft_1, feedback)

# Step 1.3: Visual Development
visual_dna = concept_artist.create_visual_dna(final_script)
character_bank = concept_artist.design_characters(final_script)
world = world_builder.build_world(final_script, visual_dna)
```

### Phase 2: Pre-visualization

```python
# Step 2.1: Storyboarding Session
storyboard_meeting = CreativeSession(agents=[
    creative_director,
    storyboard_artist,
    cinematographer,
    continuity_coordinator
])

# 分镜设计会议：讨论每个镜头
shots = []
for scene in final_script.scenes:
    # 各Agent提出分镜方案
    proposals = storyboard_meeting.brainstorm(f"如何拍摄场景：{scene}")
    
    # 达成共识
    shot_design = proposals.consensus
    
    # 连续性检查
    if len(shots) > 0:
        continuity = continuity_coordinator.check(shots[-1], shot_design)
        shot_design.inherit_from = continuity.elements_to_inherit
    
    shots.append(shot_design)

# Step 2.2: Animatic (动态分镜预览)
animatic = create_animatic(shots, audio=temp_voiceover)
creative_director.review(animatic)  # 审查节奏和流畅度
```

### Phase 3: Production & Post

```python
# Step 3.1: Shot-by-Shot Generation with Inheritance
generated_shots = []

for i, shot_design in enumerate(shots):
    # 准备连续性参数
    inheritance = None
    if i > 0:
        inheritance = {
            "last_frame": generated_shots[-1].get_last_frame(),
            "character_state": generated_shots[-1].character_final_state,
            "lighting": generated_shots[-1].lighting_setup
        }
    
    # 生成镜头
    video = production_director.generate(
        shot_design=shot_design,
        visual_dna=visual_dna,
        character_bank=character_bank,
        inherit_from=inheritance
    )
    
    # 实时质检
    quality = editor.review(video, shot_design)
    if quality.score < 0.7:
        # 重新生成
        video = production_director.regenerate(shot_design, quality.feedback)
    
    generated_shots.append(video)

# Step 3.2: Editing & Post
final_video = editor.assemble(
    shots=generated_shots,
    audio=final_audio,
    transitions=shots.transitions,
    color_grading=visual_dna.color_palette
)
```

---

## 五、技术实现关键点

### 1. 视觉遗传技术方案

```python
def generate_shot_with_inheritance(
    prompt: str,
    previous_shot: Optional[VideoShot],
    visual_dna: VisualDNA,
    character_bank: CharacterBank
) -> VideoShot:
    """
    生成具有视觉连续性的镜头
    """
    
    # 构建增强提示词
    enhanced_prompt = f"""
    {prompt}
    
    [Character Consistency]
    {character_bank.get_consistency_prompt()}
    
    [Visual Style]
    Color palette: {visual_dna.color_palette}
    Lighting: {visual_dna.lighting_style}
    
    """
    
    # 准备API参数
    api_params = {
        "prompt": enhanced_prompt,
        "model": "seedance-1.5-pro"
    }
    
    # 如果有前序镜头，添加遗传参数
    if previous_shot:
        api_params.update({
            "image_prompt": previous_shot.last_frame,  # 关键：使用上一镜头最后一帧
            "image_prompt_weight": 0.5,  # 遗传强度
            "character_reference": character_bank.get_reference_id()
        })
    else:
        # 首镜使用角色参考图
        api_params.update({
            "image_prompt": character_bank.get_init_reference(),
            "image_prompt_weight": 0.8
        })
    
    # 调用API生成
    video = video_api.generate(**api_params)
    
    # 提取最后一帧供下一镜头使用
    video.last_frame = extract_last_frame(video)
    video.character_final_state = detect_character_state(video.last_frame)
    
    return video
```

### 2. 创作会议实现

```python
class CreativeSession:
    """模拟真实创作会议"""
    
    def __init__(self, agents: List[Agent], orchestrator: Agent):
        self.agents = agents
        self.orchestrator = orchestrator
    
    def brainstorm(self, topic: str, max_rounds: int = 3) -> Decision:
        """
        多轮讨论达成共识
        """
        conversation_history = []
        
        for round_num in range(max_rounds):
            # 1. 各Agent发言
            for agent in self.agents:
                opinion = agent.speak(
                    topic=topic,
                    context=conversation_history
                )
                conversation_history.append({
                    "agent": agent.role,
                    "opinion": opinion,
                    "round": round_num
                })
            
            # 2. Orchestrator总结当前共识度
            consensus = self.orchestrator.analyze_consensus(conversation_history)
            
            if consensus.agreement_level > 0.8:
                break
            
            # 3. 针对分歧点继续讨论
            if consensus.disagreements:
                topic = f"继续讨论：{consensus.disagreements[0]}"
        
        # 3. 最终决策
        decision = self.orchestrator.make_decision(conversation_history)
        
        return decision
```

### 3. 连续性检查系统

```python
class ContinuityCoordinator(Agent):
    """连续性协调员"""
    
    def check_continuity(
        self,
        shot_a: ShotDesign,
        shot_b: ShotDesign
    ) -> ContinuityReport:
        """
        检查两个镜头之间的连续性
        """
        issues = []
        inheritance_plan = {}
        
        # 1. 时间连续性
        if shot_b.time - shot_a.time > 5 and shot_b.transition != "dissolve":
            issues.append("时间跳跃过大，建议添加dissolve转场")
        
        # 2. 空间连续性
        if shot_a.location == shot_b.location:
            # 同一场景，需要继承环境
            inheritance_plan["environment"] = shot_a.environment
            inheritance_plan["lighting"] = shot_a.lighting
        
        # 3. 角色连续性
        common_characters = set(shot_a.characters) & set(shot_b.characters)
        for char in common_characters:
            inheritance_plan[f"character_{char}"] = {
                "pose": shot_a.character_poses[char],
                "costume": shot_a.character_costumes[char],
                "position": shot_a.character_positions[char]
            }
        
        # 4. 道具连续性
        if shot_a.props and shot_b.props:
            common_props = set(shot_a.props) & set(shot_b.props)
            if common_props:
                inheritance_plan["props"] = list(common_props)
        
        return ContinuityReport(
            issues=issues,
            inheritance_plan=inheritance_plan,
            transition_suggestion=self._suggest_transition(shot_a, shot_b)
        )
```

---

## 六、配置文件设计

```json
{
  "project": {
    "name": "无名之人_第一章",
    "target": "douyin_vertical_video",
    "total_duration": 60
  },
  
  "visual_continuity": {
    "enable_shot_inheritance": true,
    "inheritance_weight": 0.5,
    "character_consistency_mode": "strict",
    "color_palette_lock": true
  },
  
  "creative_process": {
    "enable_creative_sessions": true,
    "max_brainstorm_rounds": 3,
    "consensus_threshold": 0.8,
    "enable_feedback_loops": true
  },
  
  "quality_gates": {
    "min_shot_quality_score": 0.7,
    "enable_auto_regeneration": true,
    "max_regeneration_attempts": 2
  },
  
  "agents": {
    "creative_director": {"enabled": true},
    "screenwriter": {"enabled": true},
    "concept_artist": {"enabled": true},
    "world_builder": {"enabled": true},
    "storyboard_artist": {"enabled": true},
    "cinematographer": {"enabled": true},
    "continuity_coordinator": {"enabled": true},
    "production_director": {"enabled": true},
    "editor": {"enabled": true},
    "music_director": {"enabled": true}
  }
}
```

---

## 七、目录结构

```
D:\cg_create\
├── core/
│   ├── session.py              # CreativeSession
│   ├── visual_dna.py            # VisualDNA
│   ├── character_bank.py        # CharacterBank
│   ├── continuity.py            # ContinuitySystem
│   └── inheritance.py           # ShotInheritance
│
├── agents/
│   ├── phase1_creative/
│   │   ├── creative_director.py
│   │   ├── screenwriter.py
│   │   ├── concept_artist.py
│   │   └── world_builder.py
│   ├── phase2_previz/
│   │   ├── storyboard_artist.py
│   │   ├── cinematographer.py
│   │   └── continuity_coordinator.py
│   └── phase3_production/
│       ├── production_director.py
│       ├── editor.py
│       └── music_director.py
│
├── pipeline/
│   ├── phase1_creative_dev.py
│   ├── phase2_previz.py
│   └── phase3_production.py
│
└── run_complete_pipeline.py
```

---

## 八、核心优势

| 特性 | 实现方式 | 效果 |
|------|---------|------|
| **视觉连续性** | Shot Inheritance + Visual DNA | 镜头间平滑过渡 |
| **角色一致性** | Character Model Bank | 同一角色外观统一 |
| **真实协作** | Creative Session + 多轮讨论 | 高质量创意决策 |
| **质量保证** | 每阶段质检 + 自动重生成 | 输出质量稳定 |
| **完整流程** | 三阶段工作流 | 专业电影制作流程 |

---

## 九、下一步实现计划

1. ✅ 设计完整架构
2. ⏳ 实现核心系统（visual_dna, character_bank, session）
3. ⏳ 实现10个专业Agent
4. ⏳ 实现三阶段流水线
5. ⏳ 测试与优化
