# -*- coding: utf-8 -*-
"""
Storyboard Artist - 分镜师

负责将剧本转化为具体的分镜设计
"""

import json
import re
from typing import Dict, List, Optional
from pathlib import Path

from core.base_agent import BaseAgent, AgentResponse
from core.world_database import WorldDatabase


class StoryboardArtist(BaseAgent):
    """
    分镜师 - 将剧本转化为分镜
    
    核心职责：
    1. 设计每个镜头的构图和景别
    2. 确定镜头运动和转场
    3. 控制节奏和时长分配
    4. 考虑视觉叙事的流畅性
    
    输入：剧本 + 世界观
    输出：详细的分镜设计
    """
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "分镜师"
        self.SYSTEM_PROMPT = """你是专业的电影分镜师，负责将剧本转化为详细的视觉描述。
你需要丰富场景细节、道具、光影、角色状态，确保每个镜头都具有电影级的视觉冲击力。"""
    
    def execute(self, context: Dict) -> AgentResponse:
        """执行分镜设计"""
        
        script = context.get("script")
        world = context.get("world")
        visual_style = context.get("visual_style", {})
        story_idea = context.get("story_idea", "") 
        
        quality_feedback = context.get("quality_feedback")
        is_rework = context.get("rework", False)
        
        if not script:
            return AgentResponse(
                success=False,
                data=None,
                error="缺少剧本数据"
            )
        
        if not world:
            return AgentResponse(
                success=False,
                data=None,
                error="缺少世界观数据"
            )
        
        # [新增]如果是返工,记录质量反馈
        if is_rework and quality_feedback:
            print(f"\n🔄 分镜设计返工模式")
            print(f"   - 质量问题: {len(quality_feedback.get('issues', []))}个")
            print(f"   - 改进建议: {len(quality_feedback.get('suggestions', []))}个")
            
            # 打印具体反馈
            for issue in quality_feedback.get("issues", [])[:3]:  # 只显示前3个
                print(f"     问题: {issue}")
            for suggestion in quality_feedback.get("suggestions", [])[:3]:
                print(f"     建议: {suggestion}")
        
        # 设计分镜(如果是返工,会考虑质量反馈)
        storyboard = self._design_storyboard(script, world, visual_style, quality_feedback, story_idea)
        
        # 验证分镜
        validation = self._validate_storyboard(storyboard, script)
        
        if not validation["valid"]:
            return AgentResponse(
                success=False,
                data=None,
                error=f"分镜验证失败: {validation['issues']}"
            )
        
        return AgentResponse(
            success=True,
            data=storyboard,
            warnings=validation.get("warnings", []),
            suggestions=validation.get("suggestions", [])
        )
    
    def _design_storyboard(self, script: Dict, world: WorldDatabase, 
                          visual_style: Dict, quality_feedback: Optional[Dict] = None,
                          story_idea: str = "") -> Dict:
        """设计分镜"""
        
        shots = []
        shot_number = 0
        
        # 遍历剧本的每个段落
        for seg_idx, segment in enumerate(script.get("segments", [])):
            segment_shots = segment.get("shots", [])
            segment_location = segment.get("location", "")  # 从segment获取location
            
            for shot_idx, script_shot in enumerate(segment_shots):
                shot_number += 1
                
                # 设计这个镜头的分镜（传递质量反馈、segment信息和story_idea）
                storyboard_shot = self._design_shot(
                    shot_number=shot_number,
                    script_shot=script_shot,
                    segment_index=seg_idx,
                    shot_index=shot_idx,
                    world=world,
                    visual_style=visual_style,
                    total_segments=len(script.get("segments", [])),
                    quality_feedback=quality_feedback,
                    segment_location=segment_location,  # 传递segment的location
                    story_idea=story_idea  # 【修复】传递原始 story_idea
                )
                
                shots.append(storyboard_shot)
        
        # 将相邻镜头的真实结尾/开头描述连成可审计的交接链。
        for index, shot in enumerate(shots):
            if index == 0:
                shot["previous_ending_description"] = ""
                shot["inherits_from_previous"] = False
            else:
                previous = shots[index - 1]
                shot["previous_ending_description"] = previous.get("ending_description", "")
                shot["current_opening_description"] = shot.get("opening_description", "")
                shot["inherits_from_previous"] = False

        # 计算总时长
        total_duration = sum(shot.get("duration", 0) for shot in shots)
        
        storyboard = {
            "title": script.get("title", "未命名"),
            "total_shots": len(shots),
            "total_duration": total_duration,
            "shots": shots,
            "visual_style": visual_style
        }
        
        return storyboard
    
    def _enhance_shot_with_llm(self, script_shot: Dict, world: WorldDatabase, 
                               quality_feedback: Optional[Dict] = None, 
                               segment_location: str = "",
                               story_idea: str = "") -> Dict:
        """使用LLM增强镜头细节"""
        
        location = segment_location if segment_location else script_shot.get("location", "未指定")
        scene_desc = script_shot.get("scene_description", "")
        action = script_shot.get("key_action", "")
        dialogue = script_shot.get("character_dialogue") or {}  # 修复：可能为None
        
        # 【关键修复】安全获取对话信息，避免AttributeError
        speaker = dialogue.get('speaker', '') if isinstance(dialogue, dict) else ''
        text = dialogue.get('text', '') if isinstance(dialogue, dict) else ''
        
        # 获取场景信息
        location_info = world.locations.get(location, {})
        
        # [新增]构建质量反馈提示
        feedback_hint = ""
        if quality_feedback:
            issues = quality_feedback.get("issues", [])
            suggestions = quality_feedback.get("suggestions", [])
            if issues or suggestions:
                feedback_hint = "\n\n【质量反馈-需要改进】:\n"
                for issue in issues[:2]:
                    feedback_hint += f"- 问题: {issue}\n"
                for suggestion in suggestions[:2]:
                    feedback_hint += f"- 建议: {suggestion}\n"
                feedback_hint += "\n请在设计时特别注意以上反馈。"
        
        # 【修复】获取完整的场景信息
        location_type = "未知"
        location_description = ""
        if location_info:
            if isinstance(location_info, dict):
                location_type = location_info.get('type', '未知')
                location_description = location_info.get('description', '')
            else:
                location_type = getattr(location_info, 'type', '未知')
                location_description = getattr(location_info, 'description', '')
        
        # 【核心修复】构建 story_idea 提示：不仅传参考文本，还要求提取旁白
        story_hint = ""
        if story_idea:
            story_hint = f"""

【原始故事想法参考】
以下是原始的故事描述：
---
{story_idea}
---
"""
        
        prompt = f"""基于以下基础信息，丰富这个电影镜头的视觉细节：

场景：{location}
场景类型：{location_type}
场景详细描述：{location_description}
基础描述：{scene_desc}
详细动作：{action}
对话：{speaker}说"{text}"
{feedback_hint}
{story_hint}

请提供详细的视觉描述，输出JSON格式：
{{
    "scene_description": "详细场景描述（包括：空间布局、材质质感、环境氛围、光影效果，建议100-200字）",
    "key_action": "详细动作描述（包括：肢体动作、面部表情、眼神变化、手势细节、身体姿态，建议80-120字）",
    "narration": "旁白/解说词（完整原文，逐字保留；无旁白则写'无'）",
    "props": ["道具1", "道具2", "道具3"],
    "foreground": ["前景元素1", "前景元素2"],
    "background": ["后景元素1", "后景元素2"],
    "lighting_hint": "光线描述（色温、方向、强度、阴影）",
    "sound_effects": ["环境音1", "环境音2"],
    "character_states": {{
        "角色名": {{
            "posture": "身体姿态",
            "expression": "面部表情",
            "gaze": "眼神方向",
            "gesture": "手势动作"
        }}
    }}
}}
"""

        try:
            response = self._call_llm(prompt, self.SYSTEM_PROMPT, temperature=0.7, max_tokens=800)
            enhanced_data = self._extract_json(response)
            
            if enhanced_data:
                return enhanced_data
            else:
                # LLM失败，返回原始数据
                return {
                    "scene_description": scene_desc,
                    "key_action": action,
                    "props": [],
                    "lighting_hint": "",
                    "sound_effects": [],
                    "character_states": {},
                    "narration": "",
                    "foreground": [],
                    "background": [],
                }
        except Exception as e:
            print(f"  [警告] LLM增强失败: {e}，使用原始数据")
            return {
                "scene_description": scene_desc,
                "key_action": action,
                "props": [],
                "lighting_hint": "",
                "sound_effects": [],
                "character_states": {},
                "narration": "",
                "foreground": [],
                "background": [],
            }
    
    def _design_shot(self, shot_number: int, script_shot: Dict, 
                    segment_index: int, shot_index: int,
                    world: WorldDatabase, visual_style: Dict,
                    total_segments: int, quality_feedback: Optional[Dict] = None,
                    segment_location: str = "",
                    story_idea: str = "") -> Dict:
        """设计电影级分镜 - 使用LLM增强细节"""
        
        # 使用LLM丰富场景细节（传递质量反馈和story_idea）
        enhanced_shot = self._enhance_shot_with_llm(script_shot, world, quality_feedback, segment_location, story_idea)
        
        # 基础信息
        shot = {
            "shot_number": shot_number,
            "segment_index": segment_index,
            "shot_index": shot_index,
            "duration": script_shot.get("duration", 3.0)
        }
        
        # 场景和角色 - 从segment获取location，从对话中提取角色
        shot["location"] = segment_location if segment_location else script_shot.get("location", "")
        
        # 从角色对话中提取角色名
        characters = []
        dialogue = script_shot.get("character_dialogue") or {}  # 修复：可能为None
        if dialogue and dialogue.get("speaker"):
            speaker = dialogue.get("speaker", "")
            # 提取角色名（去掉括号内的角色类型）
            if "（" in speaker:
                character_name = speaker.split("（")[0].strip()
            elif "(" in speaker:
                character_name = speaker.split("(")[0].strip()
            else:
                character_name = speaker.strip()
            
        shot["characters"] = characters
        
        # **使用LLM增强的详细描述**
        shot["scene_description"] = enhanced_shot.get("scene_description", script_shot.get("scene_description", ""))
        shot["key_action"] = enhanced_shot.get("key_action", script_shot.get("key_action", ""))
        shot["props"] = enhanced_shot.get("props", [])
        shot["lighting_hint"] = enhanced_shot.get("lighting_hint", "")
        shot["character_states"] = enhanced_shot.get("character_states", {})

        handoff = self._extract_frame_handoff(script_shot, story_idea, shot_number)
        shot["opening_description"] = handoff["opening"]
        shot["ending_description"] = handoff["ending"]
        shot["previous_ending_description"] = ""
        shot["current_opening_description"] = handoff["opening"]

        # 【核心修复】音频：优先使用 LLM 从 story_idea 提取的旁白，再 fallback 到脚本字段
        extracted_narration = self._extract_narration_from_story_idea(story_idea, shot_number)
        script_narration = script_shot.get("narrator_vo", "") or script_shot.get("narration", "")
        if extracted_narration:
            shot["narration"] = extracted_narration
        elif script_narration:
            shot["narration"] = script_narration
        else:
            shot["narration"] = ""

        shot["character_dialogue"] = script_shot.get("character_dialogue") or {}
        shot["sound_effects"] = enhanced_shot.get("sound_effects", [])

        # 【核心修复】前景/后景
        foreground = enhanced_shot.get("foreground")
        background = enhanced_shot.get("background")
        if foreground:
            shot["foreground"] = foreground if isinstance(foreground, list) else [foreground]
        if background:
            shot["background"] = background if isinstance(background, list) else [background]
        
        # 设计视觉元素
        shot_type = self._determine_shot_type(
            shot_number, segment_index, total_segments,
            shot["key_action"]
        )
        shot["shot_type"] = shot_type
        
        # 摄影机角度
        angle = self._determine_camera_angle(shot_type, shot["key_action"])
        shot["camera_angle"] = angle
        
        # 摄影机运动（更专业的运动方式）
        movement = self._determine_camera_movement_professional(
            shot_type, shot["key_action"], shot.get("duration", 3.0), shot_number
        )
        shot["camera_movement"] = movement
        
        # **【新增】详细运镜描述**
        shot["camera_description"] = self._build_camera_description(
            shot_type, angle, movement, shot
        )
        
        # 构图
        composition = self._determine_composition(shot_type, len(shot["characters"]))
        shot["composition"] = composition
        
        # 转场（使用专业转场方式）
        if shot_number > 1:
            transition = self._determine_transition_professional(shot_number, segment_index)
            shot["transition"] = transition
        else:
            shot["transition"] = "fade_in"
        
        # **添加摄影机设备建议**
        shot["camera_equipment"] = self._suggest_camera_equipment(shot_type, movement)
        
        return shot
    
    def _extract_frame_handoff(self, script_shot: Dict, story_idea: str = "", shot_number: int = 0) -> Dict[str, str]:
        """从剧本或原始故事提取完整的镜头开头/结尾交接状态。"""
        opening = (
            script_shot.get("opening_description")
            or script_shot.get("current_opening_description")
            or script_shot.get("shot_opening")
            or ""
        )
        ending = (
            script_shot.get("ending_description")
            or script_shot.get("previous_ending_description")
            or script_shot.get("shot_ending")
            or ""
        )
        source = script_shot.get("scene_description", "") or ""
        sources = [source]
        if story_idea:
            sources.insert(0, self._story_idea_shot_section(story_idea, shot_number))
        for text in sources:
            if not text:
                continue
            if not opening:
                opening_match = re.search(
                    r"镜头开头[：:]\s*(.*?)(?=\n\s*(?:画面内容|前景|运镜|音效|旁白|镜头结尾状态|$))",
                    text, re.DOTALL)
                opening = opening_match.group(1).strip() if opening_match else ""
            if not ending:
                ending_match = re.search(
                    r"镜头结尾状态[：:]\s*(.*?)(?=\n\s*(?:镜头\s*\d+|结尾标题卡|$))",
                    text, re.DOTALL)
                ending = ending_match.group(1).strip() if ending_match else ""
        return {"opening": opening, "ending": ending}

    @staticmethod
    def _story_idea_shot_section(story_idea: str, shot_number: int) -> str:
        """按原始镜头标题切出单个镜头，避免交接信息串到其他镜头。"""
        if not story_idea or shot_number is None:
            return ""

        heading_pattern = re.compile(
            r"(?m)^\s*(?:#{1,6}\s*)?镜(?:头|号)\s*(\d+)\s*(?:[｜|：:]|$).*$"
        )
        matches = list(heading_pattern.finditer(story_idea))
        wanted_number = int(shot_number)
        for index, match in enumerate(matches):
            if int(match.group(1)) != wanted_number:
                continue
            end = matches[index + 1].start() if index + 1 < len(matches) else len(story_idea)
            return story_idea[match.start():end].strip()
        return ""

    @staticmethod
    def _extract_narration_from_story_idea(story_idea: str, pipeline_shot_number: int) -> str:
        """从原始故事按标题卡偏移提取旁白，避免依赖一次性外部脚本。"""
        if not story_idea or pipeline_shot_number <= 1:
            return ""
        source_shot_number = pipeline_shot_number - 1
        section = StoryboardArtist._story_idea_shot_section(story_idea, source_shot_number)
        if not section:
            return ""
        matches = re.findall(r"旁白(?:[（(][^）)]*[）)])?\s*[：:]\s*\n?\s*[\"“](.*?)[\"”]", section, re.DOTALL)
        return matches[-1].strip() if matches else ""

    def _build_camera_description(self, shot_type: str, angle: str, 
                                  movement: str, shot: Dict) -> Dict:
        """
        【新增】构建详细的摄像机运镜描述
        
        根据decisions_docs.md的建议，运镜Prompt应包含：
        - 起始位置
        - 运动类型
        - 路径
        - 速度曲线
        - 焦点变化
        - 结束状态
        - 约束条件
        """
        duration = shot.get("duration", 3.0)
        action = shot.get("key_action", "")
        location = shot.get("location", "")
        
        description = {}
        
        # 1. 摄影机起始位置
        description["start_position"] = self._generate_start_position(
            shot_type, angle, location, shot.get("characters", [])
        )
        
        # 2. 运镜类型和路径
        description["movement"] = self._generate_movement_description(
            movement, duration, action
        )
        
        # 3. 速度曲线
        description["speed_curve"] = self._generate_speed_curve(movement, duration)
        
        # 4. 焦点变化
        description["focus_shift"] = self._generate_focus_shift(
            shot_type, shot.get("characters", [])
        )
        
        # 5. 结束状态
        description["end_state"] = self._generate_end_state(
            shot_type, shot.get("characters", [])
        )
        
        # 6. 约束条件
        description["constraints"] = self._generate_movement_constraints(movement)
        
        # 7. 组合成完整的运镜描述文本
        description["full_description"] = self._combine_camera_description(description)
        
        return description
    
    def _generate_start_position(self, shot_type: str, angle: str, 
                                 location: str, characters: List) -> str:
        """生成摄影机起始位置描述"""
        # 根据景别确定焦段
        focal_length_map = {
            "extreme_wide_shot": "24mm超广角",
            "wide_shot": "35mm广角",
            "medium_shide": "50mm标准",
            "medium_shot": "50mm标准",
            "close_up": "85mm中长焦",
            "extreme_close_up": "135mm长焦"
        }
        focal = focal_length_map.get(shot_type, "50mm标准镜头")
        
        # 根据角度确定高度
        height_map = {
            "eye_level": "平视高度",
            "low_angle": "低角度仰拍",
            "high_angle": "高角度俯拍",
            "bird_eye_view": "鸟瞰高度",
            "dutch_angle": "倾斜角度"
        }
        height = height_map.get(angle, "平视高度")
        
        # 基础位置
        position = f"{focal}，{height}"
        
        # 如果有角色，确定与角色的相对位置
        if characters:
            position += f"，机位在角色附近"
        
        # 根据场景类型微调
        if location:
            if "室内" in location:
                position += "，机位靠近墙面"
            elif "户外" in location or "室外" in location:
                position += "，利用环境自然框架"
        
        return position
    
    def _generate_movement_description(self, movement: str, duration: float, 
                                       action: str) -> str:
        """生成运镜运动描述"""
        movement_map = {
            "static": "固定机位，三脚架稳定拍摄",
            "dolly_in": "摄影机沿轨道缓慢前移",
            "dolly_out": "摄影机沿轨道缓慢后移",
            "tracking": "斯坦尼康跟踪拍摄，与角色保持同速",
            "pan": "水平摇镜，匀速跟随",
            "tilt": "垂直升降摇臂",
            "crane_up": "摇臂匀速上升",
            "crane_down": "摇臂匀速下降",
            "slow_pan": "缓慢稳定器环绕",
            "handheld": "手持摄影，轻微晃动增加临场感"
        }
        
        base = movement_map.get(movement, "稳定器拍摄")
        
        # 根据动作描述调整
        if "跟随" in action or "追踪" in action:
            base += "，紧随角色运动"
        elif "靠近" in action or "推进" in action:
            base += "，目标明确"
        elif "对话" in action:
            base += "，保持对话双方在画面中"
        
        return base
    
    def _generate_speed_curve(self, movement: str, duration: float) -> Dict:
        """
        生成速度曲线描述
        
        运镜不应是机械的匀速运动，需要有速度变化
        """
        if movement == "static":
            return {"type": "无运动", "description": "零速度，完全静止"}
        
        if duration < 3.0:
            # 短镜头通常匀速
            return {
                "type": "匀速",
                "description": "全程匀速运动"
            }
        
        # 长镜头可以有速度变化
        if movement in ["dolly_in", "dolly_out"]:
            return {
                "type": "缓起缓停",
                "description": "前1秒缓慢启动，中间匀速，最后1秒减速停止",
                "start_speed": "慢",
                "middle_speed": "中",
                "end_speed": "慢"
            }
        elif movement == "tracking":
            return {
                "type": "跟随节奏",
                "description": "跟随角色移动速度，必要时微调",
                "start_speed": "匹配角色",
                "middle_speed": "稳定跟随",
                "end_speed": "自然停止"
            }
        elif movement == "handheld":
            return {
                "type": "不规则",
                "description": "模拟人体自然晃动，有轻微随机性",
                "note": "晃动幅度控制在5%以内，避免过度晃动"
            }
        else:
            return {
                "type": "平滑",
                "description": "平滑稳定运动",
                "start_speed": "缓",
                "middle_speed": "稳",
                "end_speed": "缓"
            }
    
    def _generate_focus_shift(self, shot_type: str, characters: List) -> str:
        """生成焦点变化描述"""
        if not characters:
            return "单点对焦，环境清晰"
        
        if shot_type in ["extreme_wide_shot", "wide_shot"]:
            # 广角通常深景深
            return f"深景深，{len(characters)}个角色和背景环境全部清晰"
        elif shot_type in ["close_up", "extreme_close_up"]:
            # 特写浅景深
            return f"浅景深，焦点锁定在角色面部，眼睛清晰，耳朵轻微虚化"
        else:
            # 中景可选择
            return "中景深，主体角色清晰，背景轻微虚化"
    
    def _generate_end_state(self, shot_type: str, characters: List) -> str:
        """生成结束状态描述"""
        if not characters:
            return "环境完整入画，画面构图平衡"
        
        # 根据景别确定角色占比
        scale_map = {
            "extreme_wide_shot": "角色占画面5%以内，作为环境中的比例尺",
            "wide_shot": "角色占画面15-20%",
            "medium_shot": "角色占画面40-50%",
            "close_up": "角色占画面70-80%",
            "extreme_close_up": "角色占画面90%以上"
        }
        scale = scale_map.get(shot_type, "角色占画面30-50%")
        
        return f"镜头结束时，{scale}"
    
    def _generate_movement_constraints(self, movement: str) -> List[str]:
        """生成运镜约束条件"""
        constraints = []
        
        # 通用约束
        constraints.append("无突然变焦")
        constraints.append("无镜头畸变")
        
        if movement == "static":
            constraints.append("三脚架完全固定")
        elif movement in ["dolly_in", "dolly_out"]:
            constraints.append("轨道运动稳定，无颠簸")
            constraints.append("摄影机高度保持恒定")
        elif movement == "tracking":
            constraints.append("斯坦尼康运动流畅")
            constraints.append("与角色保持恒定距离")
        elif movement == "handheld":
            constraints.append("晃动自然可控")
            constraints.append("避免大步幅移动")
        else:
            constraints.append("运动稳定如轨道")
        
        return constraints
    
    def _combine_camera_description(self, description: Dict) -> str:
        """
        组合完整的运镜描述文本
        
        格式：[起始位置] + [运镜类型] + [运动路径] + [速度曲线] + [焦点变化] + [结束状态] + [约束条件]
        """
        parts = []
        
        # 起始位置
        if description.get("start_position"):
            parts.append(f"起始位置：{description['start_position']}")
        
        # 运镜运动
        if description.get("movement"):
            parts.append(f"运镜方式：{description['movement']}")
        
        # 速度曲线
        speed = description.get("speed_curve", {})
        if speed.get("description"):
            parts.append(f"速度曲线：{speed['description']}")
        
        # 焦点变化
        if description.get("focus_shift"):
            parts.append(f"焦点变化：{description['focus_shift']}")
        
        # 结束状态
        if description.get("end_state"):
            parts.append(f"结束状态：{description['end_state']}")
        
        # 约束条件
        constraints = description.get("constraints", [])
        if constraints:
            parts.append(f"约束：{'，'.join(constraints)}")
        
        return "；".join(parts)
    
    def _determine_shot_type(self, shot_number: int, segment_index: int,
                            total_segments: int, action: str) -> str:
        """确定景别"""
        
        # 开场 - 使用大全景建立环境
        if shot_number == 1:
            return "extreme_wide_shot"
        
        # 结尾 - 通常用特写或中景
        if segment_index == total_segments - 1:
            return "close_up"
        
        # 根据动作判断
        if "细节" in action or "表情" in action or "眼神" in action:
            return "close_up"
        elif "环境" in action or "远处" in action or "全貌" in action:
            return "wide_shot"
        elif "动作" in action or "移动" in action:
            return "medium_shot"
        else:
            # 默认使用中景，最常用
            return "medium_shot"
    
    def _determine_camera_angle(self, shot_type: str, action: str) -> str:
        """确定摄影机角度"""
        
        # 根据动作判断
        if "俯视" in action or "从上" in action:
            return "high_angle"
        elif "仰视" in action or "从下" in action:
            return "low_angle"
        elif "鸟瞰" in action:
            return "bird_eye_view"
        else:
            # 默认平视
            return "eye_level"
    
    def _determine_camera_movement_professional(self, shot_type: str, action: str, 
                                               duration: float, shot_number: int) -> str:
        """确定专业摄影机运动"""
        
        # 短镜头通常静止
        if duration < 2.0:
            return "static"
        
        # 根据动作判断
        if "跟随" in action or "追踪" in action or "走" in action:
            return "tracking"  # 斯坦尼康跟踪
        elif "推进" in action or "靠近" in action or "逼近" in action:
            return "dolly_in"  # 轨道推进
        elif "拉远" in action or "后退" in action:
            return "dolly_out"  # 轨道拉远
        elif "摇" in action or "转向" in action:
            return "pan"  # 摇镜
        elif "升" in action or "降" in action:
            return "crane"  # 摇臂升降
        elif "环绕" in action or "旋转" in action:
            return "slow_pan"  # 缓慢环绕
        elif "对话" in action or "说话" in action:
            return "handheld"  # 手持增加真实感
        else:
            # 根据景别决定
            if shot_type in ["close_up", "extreme_close_up"]:
                return "static"  # 特写通常静止
            elif shot_type == "extreme_wide_shot":
                return "slow_pan"  # 大全景缓慢运动
            else:
                return "static" if duration < 4.0 else "slow_pan"
    
    def _determine_composition(self, shot_type: str, character_count: int) -> str:
        """确定构图方式"""
        
        # 根据景别和角色数量确定构图
        if character_count == 0:
            # 空镜头 - 环境构图
            return "establishing"
        elif character_count == 1:
            # 单人构图
            if shot_type in ["close_up", "extreme_close_up"]:
                return "centered"  # 特写居中
            else:
                return "rule_of_thirds"  # 三分法
        elif character_count == 2:
            # 双人构图
            return "two_shot"  # 对话构图
        else:
            # 多人构图
            return "group"  # 群像构图
    
    def _determine_transition_professional(self, shot_number: int, segment_index: int) -> str:
        """确定专业转场方式"""
        
        # 大部分使用硬切（HARD CUT）- 电影级标准
        return "cut"
    
    def _suggest_camera_equipment(self, shot_type: str, movement: str) -> str:
        """建议摄影机设备"""
        
        equipment_map = {
            "static": "三脚架固定机位",
            "tracking": "斯坦尼康（Steadicam）跟踪",
            "dolly_in": "轨道推车（Dolly）推进",
            "dolly_out": "轨道推车（Dolly）拉远",
            "crane": "摇臂（Crane）升降",
            "pan": "云台摇镜",
            "slow_pan": "稳定器（Gimbal）环绕",
            "handheld": "手持摄影（Handheld）"
        }
        
        return equipment_map.get(movement, "稳定器拍摄")
    
    def _validate_storyboard(self, storyboard: Dict, script: Dict) -> Dict:
        """验证分镜设计"""
        
        issues = []
        warnings = []
        suggestions = []
        
        shots = storyboard.get("shots", [])
        
        if not shots:
            issues.append("分镜为空")
            return {"valid": False, "issues": issues}
        
        # 检查时长
        total_duration = storyboard.get("total_duration", 0)
        target_duration = script.get("duration", 60)
        
        if abs(total_duration - target_duration) > 5:
            warnings.append(f"总时长({total_duration}s)与目标({target_duration}s)偏差较大")
        
        # 检查景别多样性
        shot_types = [shot.get("shot_type") for shot in shots]
        unique_types = set(shot_types)
        
        if len(unique_types) < 3:
            warnings.append(f"景别类型较少({len(unique_types)}种)，建议增加多样性")
            suggestions.append("增加更多景别变化，避免视觉单调")
        
        # 检查摄影机角度多样性
        angles = [shot.get("camera_angle") for shot in shots]
        unique_angles = set(angles)
        
        if len(unique_angles) < 2:
            suggestions.append("考虑使用更多摄影机角度增加视觉趣味")
        
        # 检查单个镜头时长
        for shot in shots:
            duration = shot.get("duration", 0)
            if duration > 8:
                warnings.append(f"镜头{shot['shot_number']}时长过长({duration}s)，可能影响节奏")
            elif duration < 1:
                warnings.append(f"镜头{shot['shot_number']}时长过短({duration}s)，观众可能看不清")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "suggestions": suggestions
        }
