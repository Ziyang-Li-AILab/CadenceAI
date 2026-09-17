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
from typing import Any, Dict, List, Optional
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
    
    SYSTEM_PROMPT = """你是一位资深电影编剧，专精于镜头表格式的剧本创作与编辑。

你的核心能力：
1. 将静态画面描述转化为有因果链的动作事件
2. 维护镜头之间的空间逻辑与剪辑连贯性
3. 设计有层次、有留白的声音方案

关键原则：
- 每个镜头必须有主动词：谁想做什么，什么阻挡，结果如何
- 镜头之间的转场必须基于画面内动作、声音先入、图形匹配或遮挡物，禁止"进入下一镜"式空转
- 音效设计必须有动态范围：静—响—更静—爆，禁止每镜堆叠低频嗡鸣
- 旁白若有只保留必要信息，优先用画面动作和声音叙事
- 格式字段必须完整、统一、可执行

禁止事项：
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
        story_idea = context.get("story_idea", "")
        target_format = context.get("target_format", "史诗级电影震撼大片")

        budget = self._compute_shot_budget(target_duration)
        print(f"\n[Writer] 镜头预算: {budget['rationale']}")
        print(f"   数量区间: {budget['min_shots']}-{budget['max_shots']} (推荐 {budget['recommended']})")
        print(f"   单镜头时长: {budget['per_shot_min']}-{budget['per_shot_max']}s")
        print(f"   目标视觉风格: {target_format}")

        max_internal_retries = 2
        last_validation: Optional[Dict[str, Any]] = None
        effective_story_idea = story_idea

        for attempt in range(max_internal_retries + 1):
            prompt = self._build_prompt(world, target_duration, effective_story_idea, target_format)
            response = self._call_llm(
                prompt, self.SYSTEM_PROMPT, temperature=0.7, max_tokens=16000
            )
            script_data = self._extract_json(response)

            if not script_data:
                if attempt < max_internal_retries:
                    print(f"   [Writer] JSON 解析失败，准备重试 ({attempt + 1}/{max_internal_retries})")
                    effective_story_idea = self._append_correction_hint(
                        story_idea, last_validation, budget,
                        parse_failure=True, attempt=attempt + 1,
                    )
                    continue
                return AgentResponse(
                    success=False,
                    error="无法解析剧本数据",
                    suggestions=["降低 temperature 后重试", "检查 LLM 是否返回有效 JSON"],
                )

            validation = self._validate_shot_budget(target_duration, script_data)
            last_validation = validation
            stats = validation["stats"]

            if validation["passed"]:
                if validation["warnings"]:
                    print(
                        f"   [Writer] 镜头预算校验通过（含警告）: "
                        f"{stats['total_shots']} 镜头, 总时长 {stats['total_duration']}s, "
                        f"最长 {stats['max_per_shot']}s | {'; '.join(validation['warnings'])}"
                    )
                else:
                    print(
                        f"   [Writer] 镜头预算校验通过: {stats['total_shots']} 镜头, "
                        f"总时长 {stats['total_duration']}s, 最长 {stats['max_per_shot']}s"
                    )
                break

            # 校验未通过：最后一轮直接接受（带强警告），否则追加纠正提示再试
            print(
                f"   [Writer] 镜头预算校验未通过（第{attempt + 1}次）: "
                f"{stats['total_shots']} 镜头 / {stats['total_duration']}s / "
                f"最长 {stats['max_per_shot']}s"
            )
            for issue in validation["issues"]:
                print(f"     - {issue}")
            if attempt >= max_internal_retries:
                print("   [Writer] 已达最大重试次数，接受当前结果并以警告形式上报")
                break
            effective_story_idea = self._append_correction_hint(
                story_idea, validation, budget,
                parse_failure=False, attempt=attempt + 1,
            )
            print(f"   [Writer] 追加镜头预算纠正指令后重试 ({attempt + 1}/{max_internal_retries})")

        if not self._check_dialogue(script_data):
            return AgentResponse(
                success=False,
                error="剧本缺少角色对话，仅有旁白",
                suggestions=["为关键场景添加角色对话"],
            )

        response_warnings: List[str] = []
        if last_validation and not last_validation["passed"]:
            response_warnings.append(
                "镜头预算偏差: " + "; ".join(last_validation["issues"])
            )
            response_warnings.extend(last_validation.get("warnings", []))
        elif last_validation and last_validation["warnings"]:
            response_warnings.extend(last_validation["warnings"])

        if response_warnings:
            return AgentResponse(
                success=True,
                data=script_data,
                warnings=response_warnings,
                suggestions=(
                    [
                        f"建议手动把镜头数收敛到 {budget['min_shots']}-{budget['max_shots']} 个，"
                        f"单镜头 {budget['per_shot_min']}-{budget['per_shot_max']}s"
                    ]
                    if last_validation and not last_validation["passed"]
                    else None
                ),
            )

        return AgentResponse(
            success=True,
            data=script_data
        )

       
    
    def _write_detailed_story_in_batches(
        self, world: WorldDatabase, target_duration: int, story_idea: str
    ) -> Optional[Dict]:
        """Extract the supplied shot descriptions and structure them in small batches."""
        shots = self._extract_detailed_shots(story_idea)
        if not shots:
            print(" [详细模式] 未找到可提取的镜头，回退到常规生成")
            prompt = self._build_prompt(world, target_duration, story_idea, target_format)
            return self._extract_json(
                self._call_llm(prompt, self.SYSTEM_PROMPT, temperature=0.7, max_tokens=16000)
            )

        batch_size = 6  # Keep each response well below the model output limit.
        all_shots = []
        characters_info = self._format_all_characters(world)
        locations_info = self._format_all_locations(world)
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

{self._format_budget_block(target_duration, self._compute_shot_budget(target_duration))}"""

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
    
    def _build_prompt(self, world: WorldDatabase, target_duration: int, story_idea: str,
                      target_format: str = "史诗级电影震撼大片") -> str:
        """
        【重构】构建LLM提示词 - 兼容简化和详细模式

        策略：
        - 详细模式：直接使用原始 story_idea，让 LLM 从中提取/补充剧本结构
        - 简短模式：提供完整的角色和场景信息，让 LLM 发挥创意

        target_format: 用户指定的目标视觉风格（如"中东废土风"、"史诗级电影震撼大片"），
                       必须注入到提示词，确保 LLM 写出的所有视觉描述（场景、镜头、
                       光影、色调）都贴合该风格。
        """

        return self._build_prompt_for_simple_story(world, target_duration, story_idea, target_format)
    
    def _build_prompt_for_detailed_story(self, world: WorldDatabase, 
                                         target_duration: int, 
                                         story_idea: str) -> str:
        """
        【新增】为详细模式构建提示词
        
        核心原则：story_idea 已包含完整分镜脚本，世界观仅作索引参考
        """
        
        # 使用索引模式：只提供角色名和场景名列表
        characters_info = self._format_all_characters(world)
        locations_info = self._format_all_locations(world)
        
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
                                       story_idea: str,
                                       target_format: str = "史诗级电影震撼大片") -> str:
        """
        【重构】为简短模式构建提示词

        核心原则：story_idea 简单，需要完整的世界观信息来指导创作
        """
        
        # 使用完整模式：提供所有角色和场景的详细信息
        characters_info = self._format_all_characters(world)
        locations_info = self._format_all_locations(world)
        
        # 修复：genre 可能是列表
        genre_str = ", ".join(world.genre) if isinstance(world.genre, list) else world.genre
        
        prompt = f"""【任务】基于以下故事想法和世界观，创作{target_duration}秒电影级剧本。

【目标视觉风格（最高优先级）】
所有场景描述、镜头语言、光影、色调、材质、景别都必须严格服从目标风格："{target_format}"。
不要折衷、不要用其它风格覆盖、不要使用与目标风格冲突的视觉词汇。

【故事想法】
{story_idea if story_idea else ""}

【世界观】（这是你的创作依据，请充分利用所有信息）
标题：{world.title}
类型：{genre_str}
设定：{world.setting}

角色详情（全部角色，充分利用其特征，根据具体镜头和时间来选择哪个角色参与）：
{characters_info}

场景详情（全部场景，充分利用其视觉元素，根据具体镜头和时间来选择哪个场景参与）：
{locations_info}

{self._format_budget_block(target_duration, self._compute_shot_budget(target_duration))}

【创作要求】
1. 总时长 EXACTLY {target_duration} 秒（见上方镜头预算硬约束，违反即作废）
2. 自行决定该片段是角色对话还是旁白还是战斗还是过渡用
3. 场景描述要点明关键视觉元素、特别是光线和运镜
4. 动作要具体可视化，特别是战斗场景要具体到每个角色的动作每个细节并思考其合理性
5. 要有情感节奏和叙事张力

除此之外，还有一些额外的建议参考事项：
从镜头角度，好剧本不是每行都写“特写/摇镜/推轨”，而是让导演能直接画出分镜。每个镜头/段落对应的剧本文字应该是：

可拍
只写摄影机拍得到的东西。
不写“他意识到自己不被爱”，写“他看到她手机亮起，名字不是他；他把手机扣在桌上”。

一个镜头一个主要视觉信息
主体、动作、对象、变化。不要一个镜头塞三件事。
镜头要么给信息，要么给反应，要么给情绪转折。

空间关系清楚
谁在哪、朝向哪、距离多远、有没有遮挡、怎么进出。
导演能据此画调度图，而不是靠猜。

视线与反应明确
谁看谁、谁避开、谁在画外。
A 看画外，B 的反应就是下一个镜头。视线匹配是剪辑基础。

动作有起止和剪辑点
动作完成、被打断、或发生反转，切才有理由。
不要写一大段没有停顿、没有变化的连续动作。

视觉冲突可见
场景里要有目标、障碍、道具、争夺物、身体距离变化。
不是两个人坐着解释剧情。

对白配身体行为
台词说一套，身体做一套；潜台词靠动作和反应。
好剧本不靠台词硬灌信息。

景别变化有情感逻辑
建立—推进—强调—反应—转场。
景别变化不是随机切，而是心理距离变化。

角度和运动有动机
推近因为心理逼近，拉远因为孤立，跟拍因为追逐，俯拍因为压迫。
不是为炫技写镜头。

声音参与叙事
环境声、画外音、沉默、声音桥、先入声。
声音也是镜头角度的一部分。

关键提示节制
可以写 insert、POV、蒙太奇、声音桥。
不要写死普通正反打，把导演空间留出来。

每场戏有视觉中心/图像系统
一个物件、颜色、空间、动作母题贯穿。
观众看完能记住一个画面，而不是只记住台词。

给导演留空间，但不模糊
导演要知道该看谁、看什么、情绪往哪走。
好剧本是开放但有方向，不是空洞文学描写。

节奏可剪
段落长短、动静、对白密度、沉默，都在暗示剪辑节奏。
编剧不剪，但要让剪辑师有节奏可接。

差 vs 好，简单示例：

差：
他很难过，觉得她不爱他了。两人沉默。

好：
他把冷掉的咖啡推回桌子中央。杯底刮过木面。她没碰。他看她的手，她把手缩进口袋。他点头，起身，椅子向后刮响。

这段可以直接拆：特写杯子、手、反应、椅子、转场。每个镜头都有视觉信息，不靠解释。

如果只留三条：
可拍、可剪、可看。
可拍＝外在动作；可剪＝动作有起止、视线能匹配；可看＝每场有视觉推进，不靠台词解释。

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
                    "scene_description": "当前镜头下的详细场景描述（包含光线、色调、空间布局等，必须是上述提供的场景）",
                    "character_dialogue": {{
                        "speaker": "角色名",
                        "text": "台词内容(如有)",
                        "emotion": "情绪"
                    }},
                    "key_action": "详细动作描述（肢体动作、表情变化、越详细越好）",
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
- 场景描述和相关特效要有画面感（光线、色彩、材质）
- 动作要可拍摄（不是抽象描述）
- 对话要符合角色性格
- 叙事要有节奏感
"""
        
        return prompt
    
    def _format_all_characters(self, world: WorldDatabase) -> str:
        """格式化完整角色信息，兼容新版 structured_data 和旧版对象字段。"""
        if not world.characters:
            return "未定义角色"

        structured_characters = {}
        raw_characters = getattr(world, "structured_data", {}).get("characters", [])
        if isinstance(raw_characters, list):
            structured_characters = {
                item.get("name"): item
                for item in raw_characters
                if isinstance(item, dict) and item.get("name")
            }

        lines = []
        for name, char in world.characters.items():
            raw = structured_characters.get(name, {})
            features = getattr(char, "visual_features", {}) or {}
            if not isinstance(features, dict):
                features = {}

            parts = [f"- {name}"]
            role = raw.get("role", getattr(char, "role", ""))
            if role:
                parts.append(f"  定位：{role}")

            aliases = raw.get("aliases", features.get("aliases", [])) or []
            if aliases:
                parts.append(f"  别名：{', '.join(map(str, aliases))}")

            affiliation = raw.get("affiliation", features.get("affiliation", ""))
            if affiliation:
                parts.append(f"  阵营：{affiliation}")

            for label, key in (("欲望", "desire"), ("恐惧", "fear"), ("缺陷", "flaw"),
                               ("优势", "strength"), ("秘密", "secret")):
                value = raw.get(key, features.get(key, ""))
                if value:
                    parts.append(f"  {label}：{value}")

            arc = raw.get("arc", features.get("arc", {})) or {}
            if isinstance(arc, dict):
                if arc.get("start"):
                    parts.append(f"  弧光起点：{arc['start']}")
                if arc.get("end"):
                    parts.append(f"  弧光终点：{arc['end']}")
                if arc.get("turning_points"):
                    parts.append(f"  转变节点：{'、'.join(map(str, arc['turning_points']))}")

            anchors = raw.get("visual_anchors", features.get("visual_anchors", [])) or []
            if anchors:
                parts.append(f"  视觉锚点：{'、'.join(map(str, anchors))}")

            for label, key in (("外貌", "face"), ("服装", "clothing")):
                value = features.get(key, "")
                if value:
                    parts.append(f"  {label}：{value}")

            personality = getattr(char, "personality", []) or []
            if personality:
                value = ", ".join(map(str, personality)) if isinstance(personality, list) else str(personality)
                parts.append(f"  性格：{value}")

            speech_style = raw.get("speech_style", getattr(char, "speech_pattern", ""))
            if speech_style:
                parts.append(f"  说话方式：{speech_style}")

            lines.append("\n".join(parts))

        return "\n".join(lines)

    def _format_all_locations(self, world: WorldDatabase) -> str:
        """格式化完整地点信息，兼容新版 structured_data 和旧版对象字段。"""
        if not world.locations:
            return "未定义场景"

        structured_locations = {}
        raw_locations = getattr(world, "structured_data", {}).get("locations", [])
        if isinstance(raw_locations, list):
            structured_locations = {
                item.get("name"): item
                for item in raw_locations
                if isinstance(item, dict) and item.get("name")
            }

        lines = []
        for name, loc in world.locations.items():
            raw = structured_locations.get(name, {})
            parts = [f"- {name}"]

            loc_type = raw.get("type", getattr(loc, "type", ""))
            if loc_type:
                parts.append(f"  类型：{loc_type}")

            atmosphere = raw.get("atmosphere", getattr(loc, "atmosphere", ""))
            if atmosphere:
                parts.append(f"  氛围：{atmosphere}")

            description = raw.get("description", getattr(loc, "description", ""))
            if description:
                parts.append(f"  描述：{description}")

            visual_elements = raw.get("visual_elements", getattr(loc, "visual_elements", [])) or []
            if visual_elements:
                parts.append(f"  视觉元素：{', '.join(map(str, visual_elements))}")

            dangers = raw.get("dangers", []) or []
            if dangers:
                parts.append(f"  威胁：{', '.join(map(str, dangers))}")

            resources = raw.get("resources", []) or []
            if resources:
                parts.append(f"  可利用元素：{', '.join(map(str, resources))}")

            color_palette = getattr(loc, "color_palette", []) or []
            if color_palette:
                value = ", ".join(map(str, color_palette)) if isinstance(color_palette, list) else str(color_palette)
                parts.append(f"  色调：{value}")

            lighting = getattr(loc, "lighting_type", "")
            if lighting:
                parts.append(f"  光线：{lighting}")

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

    # ======================== 镜头预算 ========================
    @staticmethod
    def _compute_shot_budget(target_duration: int) -> Dict[str, Any]:
        """根据目标时长推导镜头预算。

        返回值包含:
        - min_shots / max_shots: 镜头数量硬性区间
        - recommended: 推荐镜头数（中位）
        - per_shot_min / per_shot_max: 单镜头时长允许区间
        - important_min: 重要动作/对白镜头的最短时长
        - transition_max: 过渡/建立镜头的最长时长
        - target_duration: 透传原始目标时长
        - rationale: 给 LLM 看的分档说明
        """
        if target_duration <= 0:
            return {
                "min_shots": 4, "max_shots": 8, "recommended": 6,
                "per_shot_min": 2.0, "per_shot_max": 4.0,
                "important_min": 3.0, "transition_max": 3.0,
                "target_duration": 0, "rationale": "目标时长未知，按 6 镜兜底",
            }

        if target_duration <= 15:
            tier = "超短视频(预告/广告)"
            min_shots = max(3, int(target_duration / 4))
            max_shots = max(5, int(target_duration / 2.5))
            per_shot_min, per_shot_max = 2.0, 4.0
            important_min, transition_max = 2.5, 3.0
        elif target_duration <= 30:
            tier = "抖音/短视频"
            min_shots = max(6, int(target_duration / 4))      # 30s -> 7
            max_shots = max(10, int(target_duration / 2.5))    # 30s -> 12
            per_shot_min, per_shot_max = 2.5, 5.0
            important_min, transition_max = 3.0, 3.5
        elif target_duration <= 60:
            tier = "中等视频"
            min_shots = max(10, int(target_duration / 5))     # 60s -> 12
            max_shots = max(18, int(target_duration / 3))     # 60s -> 20
            per_shot_min, per_shot_max = 3.0, 6.0
            important_min, transition_max = 4.0, 4.0
        elif target_duration <= 120:
            tier = "长视频"
            min_shots = max(18, int(target_duration / 6))     # 120s -> 20
            max_shots = max(30, int(target_duration / 4))     # 120s -> 30
            per_shot_min, per_shot_max = 3.5, 7.0
            important_min, transition_max = 4.5, 4.5
        else:
            tier = "超长视频"
            scale = target_duration / 60.0
            min_shots = max(20, int(12 * scale))
            max_shots = max(40, int(20 * scale))
            per_shot_min, per_shot_max = 4.0, 8.0
            important_min, transition_max = 5.0, 5.0

        # 推荐值取区间中位数，并向下取整以贴合 min 下限
        recommended = max(min_shots, min(max_shots, int(target_duration / 3.5)))

        return {
            "min_shots": min_shots,
            "max_shots": max_shots,
            "recommended": recommended,
            "per_shot_min": per_shot_min,
            "per_shot_max": per_shot_max,
            "important_min": important_min,
            "transition_max": transition_max,
            "target_duration": target_duration,
            "rationale": f"{tier} {target_duration}s：{min_shots}-{max_shots} 个镜头，单镜头 {per_shot_min}-{per_shot_max} 秒",
        }

    @staticmethod
    def _format_budget_block(target_duration: int, budget: Dict[str, Any]) -> str:
        """把镜头预算格式化为注入 prompt 的中文段落。"""
        return (
            f"【镜头预算（硬约束，必须严格遵守）】\n"
            f"本视频总时长必须 EXACTLY 等于 {target_duration} 秒。\n"
            f"- 镜头数量区间：{budget['min_shots']} ~ {budget['max_shots']} 个"
            f"（推荐约 {budget['recommended']} 个）\n"
            f"- 单镜头时长区间：{budget['per_shot_min']} ~ {budget['per_shot_max']} 秒\n"
            f"- 重要动作/对白镜头：{budget['important_min']} ~ {budget['per_shot_max']} 秒\n"
            f"- 过渡/建立/空镜头：不超过 {budget['transition_max']} 秒\n"
            f"- 所有 shot.duration 之和必须 EXACTLY 等于 {target_duration} 秒\n"
            f"- 镜头之间通过时长组合自然分配，禁止全部用相同 duration 拼凑\n\n"
            f"【判断准则】\n"
            f"- 镜头数 < {budget['min_shots']}：每个镜头太长，观众来不及反应\n"
            f"- 镜头数 > {budget['max_shots']}：每个镜头太碎，变成幻灯片\n"
            f"- 单镜头 > {budget['per_shot_max']}s：镜头疲软，必须拆分或加速\n"
            f"- duration 之和 ≠ {target_duration}：整段节奏错位，必须修正\n"
        )

    @staticmethod
    def _append_correction_hint(
        base_story_idea: str,
        last_validation: Optional[Dict[str, Any]],
        budget: Dict[str, Any],
        parse_failure: bool,
        attempt: int,
    ) -> str:
        """把上一轮失败原因追加到 story_idea 末尾，作为下轮 LLM 的硬纠正指令。"""
        hint_lines = [
            "",
            "",
            f"【强制纠正 - 第 {attempt} 次重试】",
            f"上一轮你没有遵守镜头预算。本视频目标时长 {budget['target_duration']} 秒，"
            f"镜头预算区间如下：",
            f"- 镜头数量必须在 {budget['min_shots']} ~ {budget['max_shots']} 个之间（推荐 {budget['recommended']}）",
            f"- 单镜头时长必须在 {budget['per_shot_min']} ~ {budget['per_shot_max']} 秒之间",
            f"- 所有 shot.duration 之和必须 EXACTLY 等于 {budget['target_duration']} 秒",
        ]
        if parse_failure:
            hint_lines.append(
                "- 上一轮返回的不是合法 JSON，请只输出一个合法 JSON 对象，不要 Markdown 代码块、不要解释文字"
            )
        elif last_validation:
            stats = last_validation.get("stats", {})
            for issue in last_validation.get("issues", []):
                hint_lines.append(f"- 上轮问题：{issue}")
            hint_lines.append(
                f"- 上轮实际产出：{stats.get('total_shots', '?')} 个镜头 / "
                f"总时长 {stats.get('total_duration', '?')}s / "
                f"最长镜头 {stats.get('max_per_shot', '?')}s"
            )
        hint_lines.append(
            "请严格按上述区间重新分配镜头数量和 duration，"
            "宁可合并相邻场景的镜头也不要拆碎动作。"
        )
        return base_story_idea + "\n".join(hint_lines)

    @staticmethod
    def _collect_shot_durations(script_data: Dict) -> List[float]:
        """提取剧本中所有 shot.duration 为 float 列表（跳过无法解析的值）。"""
        durations: List[float] = []
        for segment in script_data.get("segments", []) or []:
            for shot in segment.get("shots", []) or []:
                if not isinstance(shot, dict):
                    continue
                value = shot.get("duration")
                try:
                    durations.append(float(value))
                except (TypeError, ValueError):
                    # 缺少 duration 时跳过；校验阶段会另外报错
                    continue
        return durations

    def _validate_shot_budget(
        self, target_duration: int, script_data: Dict
    ) -> Dict[str, Any]:
        """校验剧本是否符合镜头预算。

        返回结构:
        {
            "passed": bool,           # 是否无 issues
            "issues": List[str],      # 硬错误（数量越界 / 总时长严重偏差）
            "warnings": List[str],    # 软警告（轻微偏差 / 单镜头略超）
            "stats": {...},
            "budget": {...},
        }
        """
        budget = self._compute_shot_budget(target_duration)
        durations = self._collect_shot_durations(script_data)
        total_shots = len(durations)
        total_duration = round(sum(durations), 2) if durations else 0.0
        max_per_shot = round(max(durations), 2) if durations else 0.0
        min_per_shot = round(min(durations), 2) if durations else 0.0

        issues: List[str] = []
        warnings: List[str] = []

        # 1. 镜头数量硬区间
        if total_shots == 0:
            issues.append("剧本没有任何 shot")
        elif total_shots < budget["min_shots"]:
            issues.append(
                f"镜头数 {total_shots} 少于预算下限 {budget['min_shots']}（目标 {target_duration}s）"
            )
        elif total_shots > budget["max_shots"]:
            issues.append(
                f"镜头数 {total_shots} 超过预算上限 {budget['max_shots']}（目标 {target_duration}s）"
            )

        # 2. duration 之和 vs target_duration
        if total_duration and abs(total_duration - target_duration) > 3:
            issues.append(
                f"所有 shot.duration 之和 {total_duration}s 与目标 {target_duration}s "
                f"偏差 {round(total_duration - target_duration, 2)}s 超过 3s"
            )
        elif total_duration and total_duration != target_duration:
            warnings.append(
                f"所有 shot.duration 之和 {total_duration}s 与目标 {target_duration}s "
                f"偏差 {round(total_duration - target_duration, 2)}s"
            )

        # 3. 单镜头时长
        if max_per_shot > budget["per_shot_max"] + 1.5:
            issues.append(
                f"最长镜头 {max_per_shot}s 超过单镜头上限 {budget['per_shot_max']}s 过多"
            )
        elif max_per_shot > budget["per_shot_max"]:
            warnings.append(
                f"最长镜头 {max_per_shot}s 略超单镜头上限 {budget['per_shot_max']}s"
            )

        if 0 < min_per_shot < 1.5:
            warnings.append(f"最短镜头 {min_per_shot}s 不足 1.5s，可能闪切")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "stats": {
                "total_shots": total_shots,
                "total_duration": total_duration,
                "max_per_shot": max_per_shot,
                "min_per_shot": min_per_shot,
            },
            "budget": budget,
        }
