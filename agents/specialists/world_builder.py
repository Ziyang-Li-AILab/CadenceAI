# -*- coding: utf-8 -*-
"""
世界观构建Agent - 创建和管理故事世界观
"""

import json
import re
from typing import Dict, List, Optional
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from core.base_agent import BaseAgent, AgentResponse
from core.world_database import WorldDatabase, Character, Location, Prop


class WorldBuilderAgent(BaseAgent):
    """
    世界观构建Agent - 电影的"世界观架构师"

    职责：
    1. 解析用户输入的故事想法
    2. 构建完整的世界观（角色、场景、道具）
    3. 定义视觉风格和音频风格
    4. 建立角色关系和故事时间线
    """

    SYSTEM_PROMPT = """你是一位资深的世界观架构师，擅长为影视作品构建完整、连贯、富有细节的世界观。

你的职责：
1. 深入分析故事背景，创建详细的场景描述
2. 设计角色的视觉特征（外貌、服装、标志性道具）
3. 定义统一的视觉风格（色调、光影、质感）
4. 确保世界观内部一致性

输出格式：
- 角色：详细的外貌描述、服装风格、标志性特征
- 场景：具体的视觉元素、空间布局、环境氛围
- 风格：可量化的视觉参数（颜色代码、光影类型）
- 细节：增强沉浸感的微小元素

注意保持世界观内部逻辑一致"""

    def execute(self, context: Dict) -> AgentResponse:
        """
        执行世界观构建

        Args:
            context: 包含以下键的字典:
                - story_idea: str, 用户的故事想法
                - target_format: str, 目标格式（抖音短视频/电影/剧集）
                - target_duration: int, 目标时长（秒）
                - existing_world: WorldDatabase, 可选，已有世界观（续写时）

        Returns:
            AgentResponse: 包含构建好的WorldDatabase
        """
        story_idea = context.get("story_idea", "")
        target_format = context.get("target_format", "史诗级电影震撼大片")
        target_duration = max(1, int(context.get("target_duration", 60)))

        try:
            # 🔥 单次完整生成策略：使用600秒超时
            print(f"\n  [策略] 一次性完整生成")
            print(f"  [生成] 完整世界观（包含所有字段）...", end="", flush=True)

            # 构建完整提示词
            prompt = self._build_prompt(story_idea, target_format, target_duration)
            print(f"  [构建提示词] {prompt[:100]}...", end="", flush=True)


            # 调用LLM（使用600秒超时）
            response = self._call_llm(prompt, self.SYSTEM_PROMPT, temperature=0.7)
            world_data = self._extract_json(response)

            if not world_data:
                world_data = self._generate_in_chunks(
                    story_idea, target_format, response, target_duration
                )

            if not world_data:
                # 【调试】保存原始响应以便分析
                debug_file = Path("debug_world_builder_response.txt")
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(f"=== LLM原始响应 ===\n{response}\n")
                print(f"\n [调试] LLM响应已保存至: {debug_file}")
                return AgentResponse(
                    success=False,
                    error="无法解析世界观数据"
                )

            # 构建完整世界观数据库
            world = self._build_world_database(world_data, story_idea)
            print(f" ✓ 构建世界观数据库完成")

            return AgentResponse(
                success=True,
                data=world
            )

        except Exception as e:
            return AgentResponse(
                success=False,
                error=f"世界观构建失败: {str(e)}"
            )

    def _build_prompt(
        self, story_idea: str, target_format: str, target_duration: int = 60
    ) -> str:
        """构建完整世界观提示词（包含所有字段和分镜）"""

        json_schema = '''
        
        {
  "world": { // 世界总纲。生成任何剧本前先读此层，内容不得偏离此处定义。
    "name": "", // 世界正式名称，台词与旁白中以此为准，禁止另造新名。
    "aliases": [], // 旧称、民间叫法、代号，可用于特定情境，不得替代正式名。
    "era": "", // 当前时代，背景、台词、道具均须锚定此时代，禁止时代错位。
    "premise": "", // 世界基础状态，任何剧情不得违背此前提。
    "logline": "", // 主角、目标、阻碍、代价，剧本主线须与此一致。
    "central_conflict": "", // 核心矛盾，每场戏须直接或间接服务此冲突。
    "themes": [], // 反复回扣的母题，每三场戏至少触及一次。
    "tone": [], // 整体情绪基调，台词与场景情绪须符合，禁止跳脱。
    "genre": [], // 类型范围，叙事模式、节奏、冲突类型须限定其中。
    "target_audience": "", // 受众定位，控制复杂度、尺度与语言难度。
    "content_rating": "", // 分级上限，暴力、语言、恐怖、性暗示不得越界。
    "description": "" // 世界全貌摘要，供快速理解，不直接生成内容。
  },
  "laws": { // 法则层。任何行为须符合此规则，违规须付出对应代价。
    "rule_sets": [ // 独立规则体系，不得凭空创造规则之外的能力或事件。
      {
        "id": "", // 引用此规则时的唯一标识。
        "name": "", // 规则名称，台词或旁白中提及时的称呼。
        "category": "", // 规则类别，据此选择对应冲突类型。
        "statement": "", // 规则陈述，行为、事件、能力须符合，禁止违反。
        "scope": "", // 适用范围，超出范围即不可用。
        "mechanics": "", // 运作机制，推演因果须遵循，不得随意更改。
        "cost": "", // 使用代价，每次触发须付出，禁止无代价使用。
        "limit": "", // 硬性限制，任何角色不得突破。
        "weakness": "", // 弱点，制造破局、反转、失败时从此入手。
        "counter": "", // 反制手段，制造对抗、压制时使用。
        "violation": "", // 违规后果，写出违规行为须写出对应后果。
        "narrative_use": "" // 可直接套用的冲突生成方式。
      }
    ],
    "interactions": [ // 规则交互，制造复杂局面与连锁反应的依据。
      {
        "id": "", // 引用此交互时的标识。
        "rule_ids": [], // 须同时涉及这些规则方可触发。
        "result": "", // 交互结果，推演须符合此结论。
        "conflict": "" // 可据此直接生成一场冲突戏。
      }
    ]
  },
  "conflicts": { // 冲突引擎。生成剧情时从此层提取对抗、赌注与压力。
    "factions": [ // 势力，群体行为的行动主体。
      {
        "id": "", // 引用此势力的唯一标识。
        "name": "", // 势力名称，称呼时以此为准。
        "type": "", // 势力类别，决定行为逻辑与行动方式。
        "goal": "", // 势力目标，行动须指向此目标，禁止无动机行为。
        "method": "", // 势力手段，行动方式须符合，不得越界。
        "resources": [], // 可调用资源上限。
        "weakness": "", // 弱点，制造失败、被破局时从此入手。
        "stake": "", // 赌注，输赢须写出对应代价。
        "relationship_ids": [], // 结盟、敌对关系依据。
        "narrative_use": "" // 可直接套用的冲突生成方式。
      }
    ],
    "conflict_list": [ // 正在发生的冲突，剧本主线或支线须从此选择。
      {
        "id": "", // 引用此冲突的唯一标识。
        "name": "", // 冲突名称。
        "parties": [], // 参与方，须涉及这些势力或角色。
        "cause": "", // 起因，须符合此设定。
        "stake": "", // 赌注，须明确写出。
        "status": "", // 当前状态，局势须符合。
        "possible_outcomes": [] // 可能结果，结局或分支只能从此选择。
      }
    ],
    "pressure_sources": [ // 持续施压因素，制造紧张感与倒计时的来源。
      {
        "id": "", // 引用此压力源的唯一标识。
        "name": "", // 压力源名称。
        "type": "", // 压力类型，决定表现形式。
        "effect": "", // 效果，须写出此影响。
        "frequency": "" // 出现频率，控制压力节奏。
      }
    ]
  },
  "characters": [ // 角色层。台词、动作、心理、弧光须从此层提取，不得凭空造人。
    {
      "id": "", // 引用此角色的唯一标识。
      "name": "", // 角色名，称呼时以此为准。
      "aliases": [], // 别名，特定情境下可用，不得混淆身份。
      "role": "", // 故事定位，决定叙事功能。
      "affiliation_ids": [], // 所属势力，立场与行为须符合。
      "desire": "", // 欲望，行动须指向此，禁止无动机行为。
      "fear": "", // 恐惧，脆弱、逃避、失误时从此入手。
      "flaw": "", // 缺陷，失误、成长、悲剧时从此展开。
      "strength": "", // 优势，高光、破局、胜利时从此展开。
      "weakness": "", // 弱点，危机、失败、被压制时从此入手。
      "ability": "", // 能力上限。
      "limit": "", // 硬性限制，禁止越界。
      "secret": "", // 秘密，伏笔、反转、揭露时从此展开。
      "relationship_ids": [], // 互动对象与互动方式依据。
      "arc": { // 角色弧，成长或堕落须遵循此路径。
        "start": "", // 初始状态。
        "end": "", // 最终状态。
        "turning_points": [] // 转变须经过的节点。
      },
      "speech": { // 语言风格，每句台词须符合此约束。
        "style": "", // 句式、用词、节奏依据。
        "tone": "", // 情绪色彩依据。
        "sample": "" // 语感样本。
      },
      "visual_anchors": [] // 出场画面须保留的识别特征。
    }
  ],
  "locations": [ // 地点层。场景须从此层选择，不得凭空造景。
    {
      "id": "", // 引用此地点的唯一标识。
      "name": "", // 地点名，称呼时以此为准。
      "type": "", // 地点类别，决定功能与叙事用途。
      "layer": "", // 空间层级。
      "parent_id": "", // 上级地点，决定归属与包含关系。
      "description": "", // 场景描述基础素材。
      "conditions": [], // 环境限制，决定行动难度。
      "dangers": [], // 威胁来源，意外与伤亡从此选择。
      "resources": [], // 可利用元素，从此选择。
      "faction_ids": [], // 控制方，决定势力冲突。
      "atmosphere": "", // 场景情绪基调。
      "visual_elements": [] // 画面细节须保留的识别元素。
    }
  ],
  "history": { // 历史层。背景、伏笔、前因后果须从此层提取。
    "eras": [ // 时代，宏观背景须锚定此层。
      {
        "id": "", // 引用此时代的唯一标识。
        "name": "", // 时代名称。
        "time_range": "", // 时间范围，时间线须符合。
        "summary": "", // 时代背景摘要。
        "key_event_ids": [] // 关键事件须从此列表选择。
      }
    ],
    "events": [ // 事件，前因、后果、伏笔须从此层提取。
      {
        "id": "", // 引用此事件的唯一标识。
        "name": "", // 事件名称。
        "time": "", // 时间点，时间顺序须符合。
        "type": "", // 事件性质，决定叙事功能。
        "cause": "", // 起因，须符合此设定。
        "effect": "", // 后果，须符合此设定。
        "character_ids": [], // 涉及角色。
        "faction_ids": [], // 涉及势力。
        "location_ids": [], // 发生地点。
        "secret": "" // 隐藏真相，伏笔、反转时从此展开。
      }
    ],
    "current_situation": { // 当前局势，故事起点从此处开始。
      "summary": "", // 开局背景摘要。
      "active_conflict_ids": [], // 当前冲突，从此列表选择。
      "pressure_source_ids": [], // 当前压力，从此列表选择。
      "open_questions": [] // 悬念与伏笔，从此列表选择。
    },
    "secrets": [ // 秘密，伏笔、反转、揭露须从此层提取。
      {
        "id": "", // 引用此秘密的唯一标识。
        "secret": "", // 秘密内容，须符合此设定。
        "known_by": [], // 知情者，行为须符合此列表。
        "reveal_condition": "" // 揭露条件，不得提前或无故揭露。
      }
    ]
  },
  "assets": { // 叙事资产层。场景、事件、象征须从此层调用。
    "items": [ // 道具，关键物件从此选择。
      {
        "id": "", // 引用此道具的唯一标识。
        "name": "", // 道具名称。
        "type": "", // 道具类别，决定功能。
        "function": "", // 功能，作用须符合。
        "significance": "", // 象征意义，须符合。
        "owner_ids": [], // 持有者。
        "location_ids": [] // 所在地。
      }
    ],
    "technologies": [ // 技术，科技、能力、系统从此选择。
      {
        "id": "", // 引用此技术的唯一标识。
        "name": "", // 技术名称。
        "type": "", // 技术类别。
        "function": "", // 功能，须符合。
        "cost": "", // 使用代价，须写出。
        "limit": "" // 限制，不得突破。
      }
    ],
    "systems": [ // 系统，跨角色、跨地点机制从此选择。
      {
        "id": "", // 引用此系统的唯一标识。
        "name": "", // 系统名称。
        "type": "", // 系统类别，决定叙事功能。
        "function": "", // 运作方式，须符合。
        "control_side": "", // 控制方，决定冲突。
        "affected_ids": [], // 影响对象。
        "weakness": "" // 弱点，破坏、反制、利用时从此入手。
      }
    ],
    "symbols": [ // 符号，视觉、文化、主题象征从此选择。
      {
        "id": "", // 引用此符号的唯一标识。
        "name": "", // 符号名称。
        "meaning": "", // 含义，出现时须传递。
        "usage": "" // 使用方式，须符合。
      }
    ],
    "legends": [ // 传说，民间流传、悬念、误导从此选择。
      {
        "id": "", // 引用此传说的唯一标识。
        "name": "", // 传说名称。
        "content": "", // 内容，须符合。
        "truth": "" // 真实程度，不得随意更改。
      }
    ],
    "signals": [ // 信号，推动角色行动的提示从此选择。
      {
        "id": "", // 引用此信号的唯一标识。
        "name": "", // 信号名称。
        "form": "", // 表现形式，须符合。
        "meaning": "" // 含义，须符合。
      }
    ]
  },
  "narrative_contract": { // 叙事契约。硬性边界，违反即视为生成失败。
    "canon": [], // 不得违背的正典事实。
    "forbidden": [], // 不得出现的内容。
    "required": [], // 必须保留的元素。
    "rating": "", // 分级上限，暴力、语言、恐怖、性暗示不得越界。
    "themes_allowed": [], // 可使用的主题范围。
    "themes_forbidden": [], // 不得使用的主题范围。
    "character_death_policy": "", // 谁能死、何时死、如何死的规则。
    "power_scale_policy": "", // 战斗、能力、冲突上限规则。
    "continuity_rules": [] // 前后一致的硬性规则。
  },
  "style_contract": { // 风格契约。表现形式约束。
    "visual": { // 视觉，场景、画面、动作须符合。
      "palette": [], // 色彩限定范围。
      "lighting": "", // 光照风格约束。
      "composition": "", // 构图风格约束。
      "texture": "", // 材质风格约束。
      "camera": "", // 镜头运动、视角风格约束。
      "aspect_ratio": "" // 画幅约束。
    },
    "audio": { // 音频，声音、音乐、静默须符合。
      "ambience": [], // 环境声限定范围。
      "sfx": [], // 音效限定范围。
      "music": "", // 音乐风格约束。
      "silence": "" // 静默使用规则。
    },
    "pacing": { // 节奏，叙事速度须符合。
      "default": "", // 普通段落默认节奏。
      "action": "", // 动作段落节奏。
      "dialogue": "", // 对话段落节奏。
      "reveal": "" // 揭露段落节奏。
    },
    "language": { // 语言，旁白、对白、用词须符合。
      "narration": "", // 旁白风格约束。
      "dialogue": "", // 对白风格约束。
      "vocabulary": "", // 词汇规范。
      "forbidden_words": [] // 不得使用的词汇。
    }
  }
}
        
        '''  # noqa: E501

        prompt = f"""基于以下story idea，构建{target_format}完整世界观。只输出JSON，不要其他额外的东西：

{story_idea}

JSON格式：
{json_schema}

关键要求：
1. 角色、场景、道具、视觉风格要丰富具体
2. shots生成足够的镜头，覆盖{target_duration}秒时长
3. 确保JSON格式完整有效

"""
        return prompt

    def _build_world_database(self, data: Dict, story_idea: str) -> WorldDatabase:
        """将新版分层世界观 JSON 映射为现有 WorldDatabase。"""

        # 某些模型会把完整结果包在 ``world_data`` 或 ``data`` 中，兼容这两种包装。
        if isinstance(data.get("world_data"), dict):
            data = data["world_data"]
        elif isinstance(data.get("data"), dict) and "world" not in data:
            data = data["data"]

        world = WorldDatabase()
        world_info = data.get("world") or {}
        laws = data.get("laws") or {}
        conflicts = data.get("conflicts") or {}
        history = data.get("history") or {}
        assets = data.get("assets") or {}
        narrative_contract = data.get("narrative_contract") or {}
        style_contract = data.get("style_contract") or {}

        # 保留新版结构，供后续需要规则、冲突、历史或叙事契约的模块使用。
        world.structured_data = {
            "world": world_info,
            "laws": laws,
            "conflicts": conflicts,
            "history": history,
            "assets": assets,
            "narrative_contract": narrative_contract,
            "style_contract": style_contract,
            "story_idea": story_idea,
        }

        world.title = world_info.get("name", "")
        world.genre = world_info.get("genre", [])
        world.setting = "；".join(
            value for value in (
                world_info.get("era", ""),
                world_info.get("premise", ""),
                world_info.get("description", ""),
            ) if value
        )
        world.themes = world_info.get("themes", [])
        tone = world_info.get("tone", [])
        world.tone = "、".join(tone) if isinstance(tone, list) else tone
        world.target_audience = world_info.get("target_audience", "")

        for char_data in data.get("characters", []) or []:
            if not isinstance(char_data, dict):
                continue
            speech = char_data.get("speech") or {}
            arc = char_data.get("arc") or {}
            visual_anchors = char_data.get("visual_anchors", []) or []
            visual_features = {
                "visual_anchors": visual_anchors,
                "desire": char_data.get("desire", ""),
                "fear": char_data.get("fear", ""),
                "strength": char_data.get("strength", ""),
                "weakness": char_data.get("weakness", ""),
                "ability": char_data.get("ability", ""),
                "limit": char_data.get("limit", ""),
                "secret": char_data.get("secret", ""),
                "arc": arc,
            }
            character = Character(
                name=char_data.get("name", ""),
                role=char_data.get("role", "supporting"),
                visual_features=visual_features,
                personality=[
                    value for value in (
                        char_data.get("desire", ""),
                        char_data.get("fear", ""),
                        char_data.get("flaw", ""),
                    ) if value
                ],
                speech_pattern="；".join(
                    value for value in (speech.get("style", ""), speech.get("tone", "")) if value
                ),
            )
            world.add_character(character)

        visual = style_contract.get("visual") or {}
        default_lighting = visual.get("lighting", "")
        for loc_data in data.get("locations", []) or []:
            if not isinstance(loc_data, dict):
                continue
            location = Location(
                name=loc_data.get("name", ""),
                description=loc_data.get("description", ""),
                type=loc_data.get("type", "场景"),
                visual_elements=loc_data.get("visual_elements", []) or [],
                lighting_type=default_lighting,
                atmosphere=loc_data.get("atmosphere", ""),
            )
            world.add_location(location)

        for prop_data in assets.get("items", []) or []:
            if not isinstance(prop_data, dict):
                continue
            prop = Prop(
                name=prop_data.get("name", ""),
                description=prop_data.get("function", ""),
                significance=prop_data.get("significance", ""),
                visual_key=prop_data.get("type", ""),
            )
            world.add_prop(prop)

        world.set_visual_style(
            color_palette=visual.get("palette", []),
            lighting_style=visual.get("lighting", ""),
            camera_movement=visual.get("camera", ""),
            texture=visual.get("texture", ""),
            composition=visual.get("composition", ""),
            aspect_ratio=visual.get("aspect_ratio", "9:16"),
        )
        audio = style_contract.get("audio") or {}
        world.audio_style = {
            "ambience": audio.get("ambience", []),
            "sound_effects": audio.get("sfx", []),
            "music_genre": audio.get("music", ""),
            "silence": audio.get("silence", ""),
        }

        world.timeline = history.get("events", []) or []
        world.relationships = {
            faction.get("id", faction.get("name", "")): faction.get("relationship_ids", [])
            for faction in conflicts.get("factions", []) or []
            if isinstance(faction, dict)
        }
        world.pacing = style_contract.get("pacing") or {}
        world.technical_specs = {
            "aspect_ratio": visual.get("aspect_ratio", ""),
            "content_rating": world_info.get("content_rating", ""),
            "rating": narrative_contract.get("rating", ""),
        }
        world.style_references = []
        return world
