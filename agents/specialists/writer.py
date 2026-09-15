# -*- coding: utf-8 -*-
"""
编剧Agent - 创作剧本和角色对话

【核心设计原则】
支持两种输入模式：
1. 详细模式：用户提供了完整的镜头设计、故事线、音乐等 → 尽可能保留原始内容
2. 简短模式：用户只提供了一句话或简单描述 → 让 LLM 发挥创意

【关键修复】
- 移除所有硬性截断（字数、人数限制）
- story_idea 贯穿整个流程，不被简化
"""

import json
import re
from typing import Dict, List, Optional
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from core.base_agent import BaseAgent, AgentResponse
from core.world_database import WorldDatabase


class WriterAgent(BaseAgent):
    """
    编剧Agent - 电影的"编剧"
    
    职责：
    1. 基于世界观和原始故事想法创作完整剧本
    2. 编写角色对话（不仅仅是旁白）
    3. 设计叙事结构和节奏
    4. 确保故事有情感张力和悬念
    """
    
    SYSTEM_PROMPT = """你是一位资深电影分镜师与视觉编剧，专精于镜头表（shot list）格式的剧本创作与编辑。

你的核心能力：
1. 将静态画面描述转化为有因果链的动作事件
2. 维护镜头之间的空间逻辑与剪辑连贯性
3. 设计有层次、有留白的声音方案
4. 严格遵循用户指定的镜头表格式，不擅自更改结构

关键原则：
- 每个镜头必须有主动词：谁想做什么，什么阻挡，结果如何
- 镜头之间的转场必须基于画面内动作、声音先入、图形匹配或遮挡物，禁止"进入下一镜"式空转
- 音效设计必须有动态范围：静—响—更静—爆，禁止每镜堆叠低频嗡鸣
- 旁白只保留必要信息，优先用画面动作和声音叙事
- 格式字段必须完整、统一、可执行

禁止事项：
- 不擅自增加对白
- 不擅自删改世界观设定
- 不将镜头表改写成小说或对话剧本
- 不在输出中添加解释性文字"""
    
    def execute(self, context: Dict) -> AgentResponse:
        """
        执行剧本创作
        
        Args:
            context: 包含以下键的字典:
                - world: WorldDatabase, 世界观
                - target_duration: int, 目标时长（秒）
                - story_idea: str, 原始故事想法（新增）
        
        Returns:
            AgentResponse: 包含剧本数据
        """
        world = context.get("world")
        target_duration = context.get("target_duration", 60)
        story_idea = context.get("story_idea", "")  # 【修复】接收原始 story_idea
        
        try:
            if self._is_detailed_story(story_idea):
                script_data = self._write_detailed_story_in_batches(
                    world, target_duration, story_idea
                )
            else:
                prompt = self._build_prompt(world, target_duration, story_idea)
                response = self._call_llm(
                    prompt, self.SYSTEM_PROMPT, temperature=0.7, max_tokens=16000
                )
                script_data = self._extract_json(response)

            if not script_data:
                return AgentResponse(
                    success=False,
                    error="无法解析剧本数据"
                )

            has_dialogue = self._check_dialogue(script_data)
            if not has_dialogue:
                return AgentResponse(
                    success=False,
                    error="剧本缺少角色对话，仅有旁白",
                    suggestions=["为关键场景添加角色对话"]
                )

            return AgentResponse(
                success=True,
                data=script_data
            )

        except Exception as e:
            return AgentResponse(
                success=False,
                error=f"剧本创作失败: {str(e)}"
            )
    
    def _write_detailed_story_in_batches(
        self, world: WorldDatabase, target_duration: int, story_idea: str
    ) -> Optional[Dict]:
        """Extract the supplied shot descriptions and structure them in small batches."""
        shots = self._extract_detailed_shots(story_idea)
        if not shots:
            print(" [详细模式] 未找到可提取的镜头，回退到常规生成")
            prompt = self._build_prompt(world, target_duration, story_idea)
            return self._extract_json(
                self._call_llm(prompt, self.SYSTEM_PROMPT, temperature=0.7, max_tokens=16000)
            )

        batch_size = 6  # Keep each response well below the model output limit.
        all_shots = []
        characters_info = self._format_all_characters(world, mode="index")
        locations_info = self._format_all_locations(world, mode="index")
        print(f" [详细模式] 已提取 {len(shots)} 个镜头，按每批最多 {batch_size} 个镜头处理")

        for batch_start in range(0, len(shots), batch_size):
            batch = shots[batch_start:batch_start + batch_size]
            first_number = batch[0]["shot_number"]
            last_number = batch[-1]["shot_number"]
            print(f" [详细模式] 处理镜头 {first_number}-{last_number} ({batch_start // batch_size + 1}/{(len(shots) + batch_size - 1) // batch_size})")
            batch_prompt = self._build_batch_prompt(
                world, target_duration, characters_info, locations_info, batch
            )
            response = self._call_llm(
                batch_prompt, self.SYSTEM_PROMPT, temperature=0.7, max_tokens=12000
            )
            batch_data = self._extract_json(response)

            # JSON 解析失败时尝试修复截断的响应
            if not batch_data:
                batch_data = self._try_fix_truncated_json(response, batch)

            # 仍然失败则记录错误但继续（不中断整条流水线）
            if not batch_data:
                debug_file = Path(f"debug_writer_response_batch_{first_number}_{last_number}.txt")
                debug_file.write_text(response, encoding="utf-8")
                print(f" [详细模式] 警告：镜头 {first_number}-{last_number} 批次 JSON 解析失败，原始响应已保存至 {debug_file}")
                # 从原始 story_idea 提取该批次的镜头基本信息，继续处理
                fallback_shots = self._fallback_shots_from_story_idea(batch, story_idea)
                all_shots.extend(fallback_shots)
                continue

            all_shots.extend(self._flatten_batch_shots(batch_data))

        all_shots.sort(key=lambda shot: int(shot.get("shot_number", 0)))
        all_shots = self._deduplicate_shots(all_shots)
        self._normalize_shot_timing(all_shots)
        return {
            "title": self._extract_story_title(story_idea),
            "duration": max(
                target_duration,
                max((shot.get("end_time", 0) for shot in all_shots), default=target_duration),
            ),
            "original_story_idea": story_idea,
            "segments": [{
                "name": "详细故事镜头",
                "duration": max((shot.get("end_time", 0) for shot in all_shots), default=target_duration),
                "location": "",
                "shots": all_shots,
            }],
        }

    def _extract_detailed_shots(self, story_idea: str) -> List[Dict[str, str]]:
        """Split markdown shot sections locally so the full story is never sent at once."""
        pattern = re.compile(r"(?m)^\s*(?:#{1,6}\s*)?镜(?:号|头)\s*(\d+)\s*[｜|].*$")
        matches = list(pattern.finditer(story_idea))
        shots = []
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(story_idea)
            section = story_idea[match.start():end].strip()
            shots.append({"shot_number": int(match.group(1)), "text": section})
        return shots

    def _try_fix_truncated_json(self, response: str, batch: List[Dict[str, str]]) -> Optional[Dict]:
        """尝试修复被截断的 JSON 响应。"""
        import re as _re

        # 尝试 1: 追加缺失的闭合括号
        try:
            # 找到最后一个完整闭合的大括号位置
            fixed = response.rstrip()
            depth = 0
            last_complete_pos = -1
            for i, ch in enumerate(fixed):
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        last_complete_pos = i

            # 如果末尾不完整，截取到最后一个完整闭合位置并补全
            if last_complete_pos >= 0 and last_complete_pos < len(fixed) - 1:
                candidate = fixed[:last_complete_pos + 1]
                # 补全缺失的闭合
                while candidate.count('{') > candidate.count('}'):
                    candidate += '}'
                result = json.loads(candidate)
                if result:
                    return result
        except Exception:
            pass

        # 尝试 2: 正则提取所有 shot 对象
        try:
            shot_pattern = _re.compile(
                r'\{\s*"shot_number"\s*:\s*(\d+)\s*,\s*"duration"\s*:.*?"visual_details"\s*:.*?"sound_design"\s*:.*?"music_mood"\s*:\s*("[^"]*")\s*\}',
                _re.DOTALL
            )
            shots_raw = _re.findall(
                r'\{\s*"shot_number"\s*:\s*(\d+)[^}]*\}',
                response
            )
            # 构造简化的 segments 结构
            found = []
            for shot_num_str in shots_raw:
                # 找到对应的 shot 内容块
                pattern = _re.compile(
                    r'\{\s*"shot_number"\s*:\s*' + shot_num_str + r'\s*,.*?(?=\{\s*"shot_number"\s*:|\}\s*\]\s*\})',
                    _re.DOTALL
                )
                match = pattern.search(response)
                if match:
                    try:
                        obj = json.loads(match.group(0) + '}')
                        if obj.get("shot_number") is not None:
                            found.append(obj)
                    except json.JSONDecodeError:
                        continue
            if found:
                return {"segments": [{"name": "原始镜头所属段落", "duration": 0, "location": "", "shots": found}]}
        except Exception:
            pass

        return None

    def _fallback_shots_from_story_idea(
        self, batch: List[Dict[str, str]], story_idea: str
    ) -> List[Dict]:
        """批次 JSON 解析完全失败时，从原始 story_idea 提取基本信息。"""
        fallback = []
        for shot_info in batch:
            num = shot_info["shot_number"]
            text = shot_info["text"]

            # 从文本中提取时长（秒）
            duration = 4
            duration_match = re.search(r'([0-9]+)\s*[秒s]?', text)
            if duration_match:
                duration = max(1, int(duration_match.group(1)))

            # 提取运镜信息作为 visual_details
            camera_match = re.search(r'运镜[：:]\s*(.+?)(?=\n|$)', text)
            scene_match = re.search(r'画面[：:]\s*(.+?)(?=\n|$)', text)

            shot = {
                "shot_number": num,
                "duration": duration,
                "start_time": 0,
                "end_time": 0,
                "scene_description": text[:500] if text else "",
                "character_dialogue": None,
                "key_action": camera_match.group(1).strip() if camera_match else "",
                "narration": "",
                "visual_details": {
                    "camera_angle": camera_match.group(1).strip() if camera_match else "",
                    "lighting": "",
                    "props": [],
                    "atmosphere": ""
                },
                "sound_design": {
                    "background": "",
                    "music_mood": ""
                }
            }
            fallback.append(shot)
        return fallback

    def _build_batch_prompt(
        self, world: WorldDatabase, target_duration: int,
        characters_info: str, locations_info: str, batch: List[Dict[str, str]]
    ) -> str:
        shot_text = "\n\n".join(
            f"===== 原始镜头 {shot['shot_number']} =====\n{shot['text']}"
            for shot in batch
        )
        return f"""【任务】仅将下面 {len(batch)} 个原始镜头转换为结构化 JSON。
不要遗漏、合并、重排或改写镜头；每个原始镜头必须输出一个 shot，shot_number 必须保持不变。
只输出合法 JSON，不要 Markdown 代码块，不要解释文字。

【世界观索引】
标题：{world.title}
可用角色：{characters_info}
可用场景：{locations_info}

【原始镜头】
{shot_text}

【输出格式】
{{
  "segments": [{{
    "name": "原始镜头所属段落",
    "duration": 0,
    "location": "场景名称",
    "shots": [{{
      "shot_number": 1,
      "duration": 0,
      "start_time": 0,
      "end_time": 0,
      "scene_description": "保留原始画面、承接和转场描述",
      "character_dialogue": null,
      "key_action": "保留原始动作",
      "narration": "旁白，没有则为空字符串",
      "visual_details": {{"camera_angle": "", "lighting": "", "props": [], "atmosphere": ""}},
      "sound_design": {{"background": "", "music_mood": ""}}
    }}]
  }}]
}}
如果原始镜头含有对白，必须填入 character_dialogue 对象，字段为 speaker、text、emotion；没有对白则为 null。
目标总时长参考：{target_duration} 秒。"""

    def _flatten_batch_shots(self, batch_data: Dict) -> List[Dict]:
        return [
            shot
            for segment in batch_data.get("segments", [])
            for shot in segment.get("shots", [])
            if isinstance(shot, dict) and shot.get("shot_number") is not None
        ]

    def _deduplicate_shots(self, shots: List[Dict]) -> List[Dict]:
        """Prevent duplicated source shot numbers from reaching later pipeline stages."""
        unique = []
        seen = set()
        duplicates = []
        for shot in shots:
            number = shot.get("shot_number")
            if number in seen:
                duplicates.append(number)
                continue
            seen.add(number)
            unique.append(shot)
        if duplicates:
            print(f" [详细模式] 发现重复镜头编号，已保留首次出现: {sorted(set(duplicates))}")
        return unique

    def _normalize_shot_timing(self, shots: List[Dict]) -> None:
        """Use source timings when present and make missing timings locally consistent."""
        current_time = 0
        for shot in shots:
            duration = shot.get("duration")
            try:
                duration = max(1, int(float(duration)))
            except (TypeError, ValueError):
                duration = 1
            start = shot.get("start_time")
            end = shot.get("end_time")
            try:
                start = int(float(start))
                end = int(float(end))
                if end <= start:
                    raise ValueError
            except (TypeError, ValueError):
                start, end = current_time, current_time + duration
            shot["start_time"], shot["end_time"] = start, end
            shot["duration"] = end - start
            current_time = end

    def _extract_story_title(self, story_idea: str) -> str:
        match = re.search(r"^\s*#\s*[《「]?(.+?)[》」]?\s*$", story_idea, re.MULTILINE)
        return match.group(1).strip() if match else "未命名剧本"

    def _is_detailed_story(self, story_idea: str) -> bool:
        """
        详细模式的特征：
        - 包含明确的镜头划分
        - 包含时间标记（如 "0-8秒"）
        - 包含具体的场景描述
        - 包含具体的台词内容
        - 包含镜头数量或段落标记
        """
        if not story_idea or len(story_idea.strip()) < 100:
            return False
        
        # 检测详细模式的关键词
        detailed_indicators = [
            "镜头", "shot", "画面", "场景", "描述",
            "秒", "时间", "duration",
            "台词", "对白", "dialogue", "角色说",
            "特写", "远景", "中景", "全景",
            "动态", "运镜", "机位"
        ]
        
        indicator_count = sum(1 for indicator in detailed_indicators if indicator.lower() in story_idea.lower())
        
        # 如果包含超过3个详细指示词，认为是详细模式
        return indicator_count >= 3
    
    def _build_prompt(self, world: WorldDatabase, target_duration: int, story_idea: str) -> str:
        """
        【重构】构建LLM提示词 - 兼容简化和详细模式
        
        策略：
        - 详细模式：直接使用原始 story_idea，让 LLM 从中提取/补充剧本结构
        - 简短模式：提供完整的角色和场景信息，让 LLM 发挥创意
        """
        
        is_detailed = self._is_detailed_story(story_idea)
        
        if is_detailed:
            print("[详细模式]")
            return self._build_prompt_for_detailed_story(world, target_duration, story_idea)
        else:
            print("[简短模式]")
            return self._build_prompt_for_simple_story(world, target_duration, story_idea)
    
    def _build_prompt_for_detailed_story(self, world: WorldDatabase, 
                                         target_duration: int, 
                                         story_idea: str) -> str:
        """
        【新增】为详细模式构建提示词
        
        核心原则：story_idea 已包含完整分镜脚本，世界观仅作索引参考
        """
        
        # 使用索引模式：只提供角色名和场景名列表
        characters_info = self._format_all_characters(world, mode="index")
        locations_info = self._format_all_locations(world, mode="index")
        
        genre_str = ", ".join(world.genre) if isinstance(world.genre, list) else world.genre
        
        prompt = f"""【任务】基于以下原始故事想法，将其转化为结构化的剧本JSON。

【重要原则】
1. 尽可能保留原始故事中的所有详细描述（场景、动作、台词、光影等）
2. 只进行必要的结构化处理，不要简化或重写原始内容
3. 如果原始描述不够详细注意进行补充

【原始故事想法】
====================
{story_idea}
====================

【世界观索引】（仅供角色名和场景名参考，不要覆盖原始描述）
标题：{world.title}
类型：{genre_str}

可用角色：
{characters_info}

可用场景：
{locations_info}

【输出要求】
请将上述故事想法转化为剧本JSON，保持所有原始细节：

输出JSON格式：
{{
    "title": "章节标题",
    "duration": {target_duration},
    "original_story_idea": "{story_idea[:500]}...",  // 保留原始故事引用
    "segments": [
        {{
            "name": "段落名称",
            "duration": 秒数,
            "location": "场景名称",
            "shots": [
                {{
                    "shot_number": 1,
                    "duration": 秒数,
                    "start_time": 开始时间,
                    "end_time": 结束时间,
                    "scene_description": "【优先使用原始描述】场景详细描述",
                    "character_dialogue": {{
                        "speaker": "角色名",
                        "text": "【优先使用原始台词】台词内容",
                        "emotion": "情绪"
                    }},
                    "key_action": "【优先使用原始动作】关键动作",
                    "narration": "旁白（如有）",
                    "visual_details": {{
                        "camera_angle": "机位角度",
                        "lighting": "光线描述",
                        "props": ["道具"],
                        "atmosphere": "氛围"
                    }},
                    "sound_design": {{
                        "background": "背景音",
                        "music_mood": "音乐情绪"
                    }}
                }}
            ]
        }}
    ]
}}

【关键】如果原始故事中有以下内容，必须保留：
- 具体的场景描述（光线、色调、材质等）
- 具体的转场细节，比如上一镜头结尾和下一镜头开头的描述是类似的
- 具体的时间标记（如 "0-8秒"）
- 具体的台词内容
- 具体的动作设计
- 具体的视觉风格要求
- 具体的运镜手法
如果没有则你自己看着生成
"""
        
        return prompt
    
    def _build_prompt_for_simple_story(self, world: WorldDatabase, 
                                       target_duration: int, 
                                       story_idea: str) -> str:
        """
        【重构】为简短模式构建提示词
        
        核心原则：story_idea 简单，需要完整的世界观信息来指导创作
        """
        
        # 使用完整模式：提供所有角色和场景的详细信息
        characters_info = self._format_all_characters(world, mode="full")
        locations_info = self._format_all_locations(world, mode="full")
        
        # 修复：genre 可能是列表
        genre_str = ", ".join(world.genre) if isinstance(world.genre, list) else world.genre
        
        prompt = f"""【任务】基于以下故事想法和世界观，创作{target_duration}秒电影级剧本。

【故事想法】
{story_idea if story_idea else "（未提供具体故事想法，基于世界观自由发挥）"}

【世界观】（这是你的创作依据，请充分利用所有信息）
标题：{world.title}
类型：{genre_str}
设定：{world.setting}

角色详情（全部角色，充分利用其特征）：
{characters_info}

场景详情（全部场景，充分利用其视觉元素）：
{locations_info}

【创作要求】
1. 总时长{target_duration}秒，设计约10-12个镜头
2. 每个镜头4-8秒
3. 自行决定该片段是角色对话还是旁白
4. 场景描述要丰富具体，点明关键视觉元素
5. 动作要具体可视化
6. 要有情感节奏和叙事张力

【输出JSON格式】
{{
    "title": "章节标题",
    "duration": {target_duration},
    "segments": [
        {{
            "name": "段落名称",
            "duration": 秒数,
            "location": "场景名称",
            "shots": [
                {{
                    "shot_number": 1,
                    "duration": 秒数,
                    "start_time": 开始时间,
                    "end_time": 结束时间,
                    "scene_description": "详细场景描述（包含光线、色调、空间布局等，80-150字）",
                    "character_dialogue": {{
                        "speaker": "角色名",
                        "text": "台词内容",
                        "emotion": "情绪"
                    }},
                    "key_action": "详细动作描述（肢体动作、表情变化、60-100字）",
                    "narration": "旁白（如有）",
                    "visual_details": {{
                        "camera_angle": "机位角度",
                        "lighting": "光线描述",
                        "props": ["道具1", "道具2"],
                        "atmosphere": "氛围"
                    }}
                }}
            ]
        }}
    ]
}}

【质量标准】
- 场景描述要有画面感（光线、色彩、材质）
- 动作要可拍摄（不是抽象描述）
- 对话要符合角色性格
- 叙事要有节奏感"""
        
        return prompt
    
    def _format_all_characters(self, world: WorldDatabase, mode: str = "index") -> str:
        """
        格式化角色信息
        
        Args:
            world: 世界观数据库
            mode: "index" - 索引模式（仅名称+定位）
                  "full" - 完整模式（包含外貌、性格等所有信息）
        """
        if not world.characters:
            return "未定义角色"
        
        lines = []
        for name, char in world.characters.items():
            parts = [f"- {name}"]
            
            # 角色定位（两种模式都包含）
            if char.role:
                parts.append(f"  定位：{char.role}")
            
            # 完整模式：添加所有详细信息
            if mode == "full":
                if char.visual_features:
                    if isinstance(char.visual_features, dict):
                        if char.visual_features.get("face"):
                            parts.append(f"  外貌：{char.visual_features['face']}")
                        if char.visual_features.get("clothing"):
                            parts.append(f"  服装：{char.visual_features['clothing']}")
                    elif hasattr(char.visual_features, 'get') and callable(getattr(char.visual_features, 'get', None)):
                        parts.append(f"  外观特征：{char.visual_features.get('face', '')} {char.visual_features.get('clothing', '')}")
                
                if char.personality:
                    if isinstance(char.personality, list):
                        parts.append(f"  性格：{', '.join(char.personality)}")
                    else:
                        parts.append(f"  性格：{char.personality}")
                
                if char.speech_pattern:
                    parts.append(f"  说话方式：{char.speech_pattern}")
            
            lines.append("\n".join(parts))
        
        return "\n".join(lines)
    
    def _format_all_locations(self, world: WorldDatabase, mode: str = "index") -> str:
        """
        格式化场景信息
        
        Args:
            world: 世界观数据库
            mode: "index" - 索引模式（仅名称+基本氛围）
                  "full" - 完整模式（包含描述、色调、视觉元素等所有信息）
        """
        if not world.locations:
            return "未定义场景"
        
        lines = []
        for name, loc in world.locations.items():
            parts = [f"- {name}"]
            
            # 索引模式：只保留基本氛围和光线
            if mode == "index":
                if loc.atmosphere:
                    parts.append(f"  氛围：{loc.atmosphere}")
                if loc.lighting_type:
                    parts.append(f"  光线：{loc.lighting_type}")
            
            # 完整模式：添加所有详细信息
            else:  # mode == "full"
                if loc.description:
                    parts.append(f"  描述：{loc.description}")
                
                if loc.color_palette:
                    if isinstance(loc.color_palette, list):
                        parts.append(f"  色调：{', '.join(loc.color_palette)}")
                    else:
                        parts.append(f"  色调：{loc.color_palette}")
                
                if loc.lighting_type:
                    parts.append(f"  光线：{loc.lighting_type}")
                
                if loc.atmosphere:
                    parts.append(f"  氛围：{loc.atmosphere}")
                
                if loc.visual_elements:
                    if isinstance(loc.visual_elements, list):
                        parts.append(f"  视觉元素：{', '.join(loc.visual_elements)}")
                    else:
                        parts.append(f"  视觉元素：{loc.visual_elements}")
            
            lines.append("\n".join(parts))
        
        return "\n".join(lines)
    
    def _check_dialogue(self, script_data: Dict) -> bool:
        """检查剧本是否有角色对话"""
        for segment in script_data.get("segments", []):
            for shot in segment.get("shots", []):
                dialogue = shot.get("character_dialogue") or {}  # 修复：可能为None
                if dialogue:
                    if dialogue.get("speaker") and dialogue.get("text"):
                        speaker = dialogue.get("speaker", "").lower()
                        if "旁白" not in speaker and "vo" not in speaker and "narrator" not in speaker:
                            return True
        return False
