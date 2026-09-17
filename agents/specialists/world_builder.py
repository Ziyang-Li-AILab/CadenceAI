# -*- coding: utf-8 -*-
"""
世界观构建Agent - 创建和管理故事世界观
"""

import sys
from typing import Dict
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from core.base_agent import BaseAgent, AgentResponse
from core.world_database import WorldDatabase, Character, Location, Prop


class WorldBuilderAgent(BaseAgent):
    """
    世界观构建Agent - 电影的"世界观架构师"

    职责：
    1. 解析用户输入的故事想法
    2. 构建完整的世界观（世界总纲、故事线、角色、地点）
    3. 保持世界观字段与下游剧本制作的一致性
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



    def _build_prompt(
        self, story_idea: str, target_format: str, target_duration: int = 60
    ) -> str:
        """构建完整世界观提示词（包含所有字段和分镜）"""

        json_schema = '''
        
        {
// 世界总纲：生成剧本前先读此层，关键锚点，不得偏离。
"world": {
"name": "", // 世界正式名称，台词与旁白中以此为准。
"era": "", // 当前时代，背景、台词、道具均须锚定此时代。
"premise": "", // 世界基础状态，任何剧情不得违背此前提。
"tone": [], // 整体情绪基调，台词与场景情绪须符合。
"genre": [] // 类型范围，叙事模式、节奏、冲突类型须限定其中。
},
// 故事线：主线目标、核心冲突、主题、幕结构与结局。
"storyline": {
"logline": "", // 主角、目标、阻碍、代价，剧本主线须与此一致。
"central_conflict": "", // 核心矛盾，每场戏须直接或间接服务此冲突。
"themes": [], // 反复回扣的母题，每三场戏至少触及一次。
"acts": [
{
"id": "", // 幕唯一标识。
"name": "", // 幕名称。
"summary": "", // 幕概要。
"key_events": [] // 关键事件，推动主线发展。
}
],
"ending": "" // 最终结局或主线收束状态。
},
// 角色层：台词、动作、心理、弧光须从此层提取，不得凭空造人。
"characters": [
{
"id": "", // 角色唯一标识。
"name": "", // 角色名，称呼时以此为准。
"aliases": [], // 别名，特定情境下可用，不得混淆身份。
"role": "", // 故事定位，决定叙事功能。
"affiliation": "", // 所属势力或阵营。
"desire": "", // 欲望，行动须指向此，禁止无动机行为。
"fear": "", // 恐惧，脆弱、逃避、失误时从此入手。
"flaw": "", // 缺陷，失误、成长、悲剧时从此展开。
"strength": "", // 优势，高光、破局、胜利时从此展开。
"secret": "", // 秘密，伏笔、反转、揭露时从此展开。
"arc": {
"start": "", // 初始状态。
"end": "", // 最终状态。
"turning_points": [] // 转变须经过的节点。
},
"speech_style": "", // 语言风格，每句台词须符合。
"visual_anchors": [] // 出场画面须保留的识别特征。
}
],
// 地点层：场景须从此层选择，不得凭空造景。
"locations": [
{
"id": "", // 地点唯一标识。
"name": "", // 地点名，称呼时以此为准。
"type": "", // 地点类别，决定功能与叙事用途。
"description": "", // 场景描述基础素材。
"atmosphere": "", // 场景情绪基调。
"dangers": [], // 威胁来源，意外与伤亡从此选择。
"resources": [], // 可利用元素，从此选择。
"visual_elements": [] // 画面细节须保留的识别元素。
}
],
// 道具层：剧本中反复出现或对剧情有显著意义的关键物品；用于资产阶段生成参考图，确保跨镜头视觉一致。
// 普通物品（一次性使用、可隐含的）无需列入；只有会被特写或反复出现的"标识物"才放进来。
"props": [
{
"id": "", // 道具唯一标识。
"name": "", // 道具名，称呼时以此为准。
"type": "", // 道具类别：weapon / vehicle / emblem / container / relic / armor ...
"description": "", // 视觉描述基础素材。
"visual_key": "", // 视觉识别关键词（颜色 / 形状 / 铭文 / 材质 等），用于镜头中检索参考图。
"significance": "", // 剧情意义：为何重要、归属、流转。
"owner": "", // 所属角色 / 阵营；公共物品留空。
"era": "", // 时代锚定。
"visual_elements": [], // 画面细节须保留的识别元素。
"color_palette": [], // 主色调，与整体世界观保持一致。
"atmosphere": "" // 道具携带的氛围（沉重 / 诡异 / 庄严 等）。
}
]
}
        
        '''  # noqa: E501

        prompt = f"""基于以下story idea，构建{target_format}完整世界观。只输出JSON，不要其他额外的东西：

{story_idea}

JSON格式：
{json_schema}

关键要求：
1. 根据story idea设计适当的角色和场景，确保每个场景的视觉风格丰富具体
2. 根据目标视频时长{target_duration}秒设计完整的故事线与幕结构
3. 根据目标视频风格{target_format}设计合适的世界、角色和场景特征
4. 只输出JSON中定义的字段，不添加分镜、音频或其他额外层级
5. 确保JSON格式完整有效
6. props 必须列出故事中会被特写或反复出现、对剧情有显著意义的标识性物品（武器、徽记、载具、容器、法器等），普通物品不要列入

"""
        return prompt

    def _build_world_database(self, data: Dict, _story_idea: str) -> WorldDatabase:
        """将四层世界观 JSON 原样保存，并映射到共享数据库模型。"""
        if not isinstance(data, dict):
            raise TypeError("世界观数据必须是对象")

        # 兼容模型偶尔返回的外层包装，但不改变四层内容。
        if isinstance(data.get("world_data"), dict):
            data = data["world_data"]
        elif isinstance(data.get("data"), dict) and "world" not in data:
            data = data["data"]

        world = WorldDatabase()
        world_info = data.get("world") or {}
        storyline = data.get("storyline") or {}

        # 原始四层结构是唯一事实来源；story_idea 是运行上下文，不注入世界观结构。
        world.structured_data = {
            "world": world_info,
            "storyline": storyline,
            "characters": data.get("characters", []) or [],
            "locations": data.get("locations", []) or [],
            "props": data.get("props", []) or [],
        }

        world.title = world_info.get("name", "")
        world.genre = world_info.get("genre", []) or []
        world.setting = "；".join(
            value for value in (world_info.get("era", ""), world_info.get("premise", "")) if value
        )
        world.themes = storyline.get("themes", []) or []
        tone = world_info.get("tone", []) or []
        world.tone = "、".join(tone) if isinstance(tone, list) else tone

        for char_data in data.get("characters", []) or []:
            if not isinstance(char_data, dict) or not char_data.get("name"):
                continue
            arc = char_data.get("arc") or {}
            visual_anchors = char_data.get("visual_anchors", []) or []
            visual_features = {
                "id": char_data.get("id", ""),
                "aliases": char_data.get("aliases", []) or [],
                "affiliation": char_data.get("affiliation", ""),
                "desire": char_data.get("desire", ""),
                "fear": char_data.get("fear", ""),
                "flaw": char_data.get("flaw", ""),
                "strength": char_data.get("strength", ""),
                "secret": char_data.get("secret", ""),
                "arc": arc,
                "visual_anchors": visual_anchors,
            }
            personality = [
                value for value in (
                    char_data.get("desire", ""), char_data.get("fear", ""), char_data.get("flaw", "")
                ) if value
            ]
            character = Character(
                name=char_data["name"],
                role=char_data.get("role", "supporting"),
                visual_features=visual_features,
                personality=personality,
                speech_pattern=char_data.get("speech_style", ""),
            )
            world.add_character(character)

        for loc_data in data.get("locations", []) or []:
            if not isinstance(loc_data, dict) or not loc_data.get("name"):
                continue
            world.add_location(Location(
                name=loc_data["name"],
                description=loc_data.get("description", ""),
                type=loc_data.get("type", "场景"),
                visual_elements=loc_data.get("visual_elements", []) or [],
                atmosphere=loc_data.get("atmosphere", ""),
            ))

        for prop_data in data.get("props", []) or []:
            if not isinstance(prop_data, dict) or not prop_data.get("name"):
                continue
            world.add_prop(Prop(
                name=prop_data["name"],
                description=prop_data.get("description", ""),
                significance=prop_data.get("significance", ""),
                visual_key=prop_data.get("visual_key", ""),
                type=prop_data.get("type", "道具"),
                visual_elements=prop_data.get("visual_elements", []) or [],
                color_palette=prop_data.get("color_palette", []) or [],
                owner=prop_data.get("owner", ""),
                era=prop_data.get("era", ""),
                atmosphere=prop_data.get("atmosphere", ""),
            ))

        # 视觉风格 / 音频 / 时间线 / 技术规格等未在 JSON 中定义，保持数据库默认值。
        world.pacing = {
            "acts": storyline.get("acts", []) or [],
            "ending": storyline.get("ending", ""),
        }
        return world
