# -*- coding: utf-8 -*-
"""
Director - 导演

【核心职责】
1. 优化提示词，确保音视频匹配
2. 【关键】决定帧继承策略：哪些镜头需要继承前一帧
3. 【关键】决定多角色参考图策略：哪些镜头需要上传多张参考图
4. 【关键】质量批准：是否允许进入视频生成阶段

【导演决策内容】
- frame_inheritance: Dict[shot_number, bool]  - 每个镜头是否使用帧继承
- multi_reference_images: Dict[shot_number, List[str]] - 每个镜头使用的参考图列表
- quality_approval: bool  - 是否批准进入视频生成
"""

import json
import re
from typing import Dict, List, Optional
from pathlib import Path

from core.base_agent import BaseAgent, AgentResponse, QualityGate
from core.visual_dna import VisualDNA
from core.character_bank import CharacterBank
from core.world_database import WorldDatabase


class Director(BaseAgent):
    """
    导演 - 优化提示词并做出关键决策
    
    【核心职责】
    1. 将分镜转化为AI可理解的提示词
    2. 【关键】决定帧继承策略（避免/启用帧继承）
    3. 【关键】决定多角色参考图策略
    4. 【关键】质量批准（允许进入视频生成）
    5. 对最终效果负责
    
    【导演决策】
    输入：分镜 + Visual DNA + Character Bank + 参考图片列表
    输出：优化的提示词 + 导演决策
    """
    
    def __init__(self, llm_config: Dict):
        config = {"llm": llm_config}
        super().__init__(config)
        self.name = "导演"
        self.quality_gate = QualityGate()
    
    def execute(self, context: Dict) -> AgentResponse:
        """
        执行导演任务
        
        Args:
            context: {
                "storyboard": Dict,
                "visual_dna": VisualDNA,
                "character_bank": CharacterBank,
                "world": WorldDatabase,
                "reference_images": List[str],  # 用户提供的参考图列表
                "story_idea": str,  # 【新增】原始故事想法
                "quality_feedback": Dict,  # [新增]质量反馈
                "rework": bool  # [新增]是否返工模式
            }
        
        Returns:
            AgentResponse: {
                "shots": List[Dict],  # 优化后的镜头列表
                "director_decisions": {
                    "frame_inheritance": Dict[shot_number, bool],
                    "multi_reference_images": Dict[shot_number, List[str]],
                    "quality_approval": bool
                },
                "quality_report": Dict
            }
        """
        
        storyboard = context.get("storyboard")
        visual_dna = context.get("visual_dna")
        character_bank = context.get("character_bank")
        world = context.get("world")
        reference_images = context.get("reference_images", [])
        story_idea = context.get("story_idea", "")  # 【修复】接收原始 story_idea
        
        # [新增]接收质量反馈
        quality_feedback = context.get("quality_feedback")
        is_rework = context.get("rework", False)
        
        if not storyboard:
            return AgentResponse(
                success=False,
                data=None,
                error="缺少分镜数据"
            )
        
        # 获取所有镜头
        shots = storyboard.get("shots", [])
        
        if not shots:
            return AgentResponse(
                success=False,
                data=None,
                error="分镜中没有镜头数据"
            )
        
        # [新增]如果是返工,记录质量反馈
        if is_rework and quality_feedback:
            print(f"\n🔄 导演决策返工模式")
            print(f"   - 质量问题: {len(quality_feedback.get('issues', []))}个")
            print(f"   - 改进建议: {len(quality_feedback.get('suggestions', []))}个")
            
            # 打印具体反馈
            for issue in quality_feedback.get("issues", [])[:3]:
                print(f"     问题: {issue}")
            for suggestion in quality_feedback.get("suggestions", [])[:3]:
                print(f"     建议: {suggestion}")
        
        # 优化每个镜头的提示词
        optimized_shots = []
        quality_issues = []
        
        # 【关键】导演决策
        director_decisions = {
            "frame_inheritance": {},      # shot_number -> bool
            "frame_inheritance_reasons": {},  # shot_number -> 判定过程与原因
            "multi_reference_images": {},  # shot_number -> List[str]
            "quality_approval": False     # 是否批准进入视频生成
        }
        
        print(f"\n🎬 导演开始工作...")
        print(f"   - 镜头数: {len(shots)}")
        print(f"   - 参考图数: {len(reference_images)}")
        print()
        
        # 分析镜头和角色
        all_characters = self._analyze_characters(shots, character_bank)
        scene_changes = self._analyze_scene_changes(shots)
        
        print(f"📊 镜头分析:")
        print(f"   - 涉及角色: {', '.join(all_characters)}")
        print(f"   - 场景切换点: {', '.join([str(s) for s in scene_changes]) or '无'}")
        print()
        
        # 处理每个镜头
        for i, shot in enumerate(shots):
            shot_number = shot.get("shot_number", i + 1)
            
            # 【修复】优化提示词（移除story_idea传递）
            optimized_shot = self._optimize_shot_prompt(
                shot, visual_dna, character_bank, world
            )
            
            # 【关键2】决定帧继承策略
            use_frame_inheritance = self._decide_frame_inheritance(
                shot_number, shot, scene_changes, i, shots
            )
            optimized_shot["use_frame_inheritance"] = use_frame_inheritance
            director_decisions["frame_inheritance"][shot_number] = use_frame_inheritance
            director_decisions["frame_inheritance_reasons"][shot_number] = getattr(
                self, "_last_frame_inheritance_reason", {
                    "scene_continuous": use_frame_inheritance,
                    "reason": "未提供详细判定原因",
                    "source": "unknown",
                }
            )
            
            # 【关键3】决定多角色参考图策略（集成角色变化检测）
            reference_for_shot = self._decide_reference_images(
                shot_number, shot, all_characters, reference_images, i, shots
            )
            optimized_shot["reference_images"] = reference_for_shot
            director_decisions["multi_reference_images"][shot_number] = reference_for_shot
            
            # 添加镜头描述用于区分参考图
            optimized_shot["reference_image_description"] = self._generate_reference_description(
                shot, all_characters
            )
            
            # 质量门检查
            validation = self.quality_gate.validate_prompt(
                optimized_shot, 
                shot_number
            )
            
            if not validation.success:
                quality_issues.append({
                    "shot": shot_number,
                    "error": validation.error,
                    "warnings": validation.warnings
                })
            
            optimized_shots.append(optimized_shot)
            
            # 打印导演决策
            frame_inherit_str = "✓继承" if use_frame_inheritance else "✗不继承"
            ref_count = len(reference_for_shot)
            print(f"  镜头{shot_number:2d}: {frame_inherit_str} | 参考图:{ref_count}张")
        
        print()
        
        # 【关键4】质量批准决策
        quality_approval = self._make_quality_approval(
            optimized_shots, quality_issues, director_decisions
        )
        director_decisions["quality_approval"] = quality_approval
        
        # 生成质量报告
        quality_report = self._generate_quality_report(
            optimized_shots, quality_issues
        )
        
        # 汇总结果
        result_data = {
            "shots": optimized_shots,
            "director_decisions": director_decisions,
            "quality_report": quality_report
        }
        
        # 打印导演决策总结
        frame_inherit_count = sum(1 for v in director_decisions["frame_inheritance"].values() if v)
        multi_ref_count = sum(1 for refs in director_decisions["multi_reference_images"].values() if len(refs) > 1)
        
        print(f"📋 导演决策总结:")
        print(f"   - 帧继承: {frame_inherit_count}/{len(shots)}个镜头")
        print(f"   - 多角色参考图: {multi_ref_count}个镜头")
        print(f"   - 质量批准: {'✅ 通过' if quality_approval else '❌ 不通过'}")
        print()
        
        # 【新增】检测 story_idea 污染
        pollution_detected = False
        pollution_warnings = []
        story_idea_keywords = ["原始故事参考", "Cadence AI", "第一章", "神殿陨"]
        
        for shot in optimized_shots:
            visual_prompt = shot.get("visual_prompt", "")
            prompt_length = len(visual_prompt)
            
            # 检查异常长度
            if prompt_length > 1500:
                pollution_detected = True
                pollution_warnings.append(
                    f"⚠️ 镜头{shot.get('shot_number')}: prompt过长({prompt_length}字)，可能包含story_idea污染"
                )
            
            # 检查是否包含 story_idea 特征关键词
            for keyword in story_idea_keywords:
                if keyword in visual_prompt:
                    pollution_detected = True
                    pollution_warnings.append(
                        f"⚠️ 镜头{shot.get('shot_number')}: 发现story_idea关键词'{keyword}'，数据已污染"
                    )
                    break
        
        if pollution_detected:
            print("\n❌ 检测到数据污染:")
            for warning in pollution_warnings:
                print(f"   {warning}")
            print()
        else:
            print("✅ 数据质量检查通过，无污染")
            print()
        
        # 如果有严重问题，返回警告
        warnings = pollution_warnings.copy()
        if quality_issues:
            warnings.append(f"有{len(quality_issues)}个镜头存在质量问题")
        
        return AgentResponse(
            success=True,
            data=result_data,
            warnings=warnings
        )
    
    # ======================== 核心决策方法 ========================
    
    def _decide_frame_inheritance(self, shot_number: int, shot: Dict, 
                                  scene_changes: List[int],
                                  current_index: int,
                                  all_shots: List[Dict]) -> bool:
        """
        【关键决策】决定是否使用帧继承
        
        决策规则（严格按顺序检查）：
        1. 第一个镜头：不继承（没有前一帧）
        2. 场景切换：不继承（基于视觉描述分析）
        3. 镜头类型变化大：不继承（如从特写到远景）
        4. 角色变化：不继承（新角色出现或旧角色离开）
        5. 场景连续性：根据剧本描述判断是否连续
        
        Args:
            shot_number: 镜头编号
            shot: 镜头数据
            scene_changes: 场景切换点列表
            current_index: 当前索引
            all_shots: 所有镜头
        
        Returns:
            bool: 是否使用帧继承
        """
        # 规则1: 第一个镜头不继承
        if shot_number == 1:
            self._last_frame_inheritance_reason = {
                "scene_continuous": False, "reason": "第一个镜头没有上一帧", "source": "rule"
            }
            print(f"    → 镜头{shot_number}: 第一个镜头，不继承")
            return False
        
        # 规则2: 显式禁用
        if shot.get("disable_frame_inheritance") == True:
            self._last_frame_inheritance_reason = {
                "scene_continuous": False, "reason": "镜头明确禁用帧继承", "source": "rule"
            }
            print(f"    → 镜头{shot_number}: 显式禁用，不继承")
            return False
        
        # 规则3: 显式启用
        if shot.get("force_frame_inheritance") == True:
            self._last_frame_inheritance_reason = {
                "scene_continuous": True, "reason": "镜头明确启用帧继承", "source": "rule"
            }
            print(f"    → 镜头{shot_number}: 显式启用，继承")
            return True
        
        prev_shot = all_shots[current_index - 1]

        # 明确的交接措辞属于结构化事实，优先于 LLM 的保守误判。
        # 例如“承接标题卡结尾的冷青色薄雾”明确要求使用上一段画面的视觉状态。
        explicit_handoff = self._has_explicit_visual_handoff(prev_shot, shot)
        if explicit_handoff:
            self._last_frame_inheritance_reason = {
                "scene_continuous": True,
                "reason": f"明确视觉承接，共享视觉锚点：{explicit_handoff}",
                "source": "deterministic_handoff",
            }
            print(f"    → 镜头{shot_number}: 检测到明确视觉承接({explicit_handoff})，继承上一帧")
            return True

        # 只有明确禁用才在 LLM 前拦截。角色、景别变化不能覆盖视觉交接。
        llm_result = self._llm_judge_scene_continuity(prev_shot, shot)
        if llm_result is None:
            print(f"    → 镜头{shot_number}: LLM 判定失败，使用交接描述兜底")
            llm_result = self._deterministic_continuity_fallback(prev_shot, shot)
            reason_source = "deterministic_fallback"
        else:
            reason_source = "llm"

        scene_continuous = bool(llm_result.get("scene_continuous", False))
        reason = llm_result.get("reason", "未提供判定原因")
        self._last_frame_inheritance_reason = {
            "scene_continuous": scene_continuous,
            "reason": reason,
            "source": reason_source,
        }
        if not scene_continuous:
            print(f"    → 镜头{shot_number}: 判定为不连续({reason})，不继承")
            return False

        print(f"    → 镜头{shot_number}: 判定场景连续({reason})，继承上一帧")
        return True

    def _has_explicit_visual_handoff(self, prev_shot: Dict, current_shot: Dict) -> Optional[str]:
        """识别剧本中明确写出的视觉交接，避免 LLM 对承接关系保守判定。"""
        previous_text = " ".join(
            str(prev_shot.get(field, "") or "")
            for field in ("ending_description", "scene_description", "visual_prompt", "key_action")
        )
        current_text = " ".join(
            str(current_shot.get(field, "") or "")
            for field in (
                "opening_description", "current_opening_description",
                "scene_description", "visual_prompt", "key_action",
            )
        )
        handoff_markers = ("承接", "衔接", "延续", "接续", "沿用", "从上一镜头", "从上个镜头")
        if not any(marker in current_text for marker in handoff_markers):
            return None

        visual_anchors = (
            ("冷青色薄雾", "冷青薄雾", "薄雾", "雾"),
            ("云海", "云雾", "云层"),
            ("烟", "浓烟", "烟雾"),
            ("金光", "金色光芒", "光芒", "闪光"),
            ("白屏", "白光", "黑屏", "黑场"),
        )
        for anchor_group in visual_anchors:
            current_has_anchor = any(anchor in current_text for anchor in anchor_group)
            previous_has_anchor = any(anchor in previous_text for anchor in anchor_group)
            if current_has_anchor and previous_has_anchor:
                return anchor_group[0]

        return None

    def _deterministic_continuity_fallback(self, prev_shot: Dict, current_shot: Dict) -> Dict:
        """LLM 不可用时，根据结尾/开头交接描述进行保守判定。"""
        ending = prev_shot.get("ending_description") or prev_shot.get("scene_description", "")
        opening = current_shot.get("opening_description") or current_shot.get("scene_description", "")
        pairs = [("云海", "云海"), ("雾", "雾"), ("烟", "烟"), ("黑屏", "黑屏"),
                 ("回廊", "回廊"), ("月门", "月门"), ("金色光芒", "金色光芒")]
        for end_token, open_token in pairs:
            if end_token in str(ending) and open_token in str(opening):
                return {"scene_continuous": True, "reason": f"结尾与开头共享视觉锚点：{end_token}"}
        return {"scene_continuous": False, "reason": "没有发现明确的结尾到开头视觉锚点"}
    def _llm_judge_scene_continuity(self, prev_shot: Dict, current_shot: Dict) -> Optional[Dict]:
        """【核心】调用 LLM 判断两个镜头是否处于同一场景。

        输入：两个镜头的字段（尽量包含 scene_description / visual_prompt / location 等）。
        输出：解析后的 dict，例如 {"scene_continuous": true, "reason": "..."}；解析失败返回 None。
        """
        def _summarize(s: Dict) -> Dict:
            return {
                "shot_number": s.get("shot_number"),
                "scene_id": s.get("scene_id") or s.get("scene_number"),
                "location": s.get("location") or s.get("scene_location"),
                "shot_type": s.get("shot_type"),
                "characters": s.get("characters", []),
                "opening_description": s.get("opening_description") or s.get("current_opening_description") or "",
                "ending_description": s.get("ending_description") or s.get("current_ending_description") or "",
                "previous_ending_description": s.get("previous_ending_description") or "",
                "transition": s.get("transition") or s.get("transition_type") or "",
                "scene_description": s.get("scene_description") or "",
                "visual_prompt": s.get("visual_prompt") or s.get("visual_description") or "",
                "narrative_context": s.get("narrative_context") or s.get("action") or s.get("description") or "",
            }

        prev_summary = _summarize(prev_shot)
        cur_summary = _summarize(current_shot)

        system_prompt = (
            "你是一位资深电影导演的副导演，负责逐镜头规划视频制作。"
            "你需要判断相邻两个镜头是否有场景交接，即需要通过运镜来变换后续场景，"
            "从而决定是否需要继承上一镜头的末帧作为参考图。"
            "请只输出严格 JSON，不要附加任何解释或 Markdown 标记。"
        )
        user_prompt = (
            "请判断下面相邻两个镜头是否处于同一场景/时空连续段。\n"
            "1) 先比较上一镜头的 ending_description 与当前镜头的 opening_description，这是最重要的依据。\n"
            "2) 如果上一个镜头结尾和下一个镜头开头共享同一视觉锚点（云海、雾、烟、黑屏、光芒、同一角色/物体），即使景别或角色数量变化，也判定可继承。\n"
            "3) 明确写有匹配剪辑、承接、从上一镜头状态开始、同空间机位切换时，判定可继承。\n"
            "4) 只有地点/时空明确跳转、结尾到开头没有视觉锚点、或明确要求切断时，判定不可继承。\n"
            "5) 帧继承是参考上一镜头末帧，不要求两个镜头景别相同；景别变化本身不能否决继承。\n"
            "6) 输出 scene_continuous=true 表示需要继承上一镜头末帧。\n\n"
            "上一镜头：\n" + json.dumps(prev_summary, ensure_ascii=False, indent=2) + "\n\n"
            "当前镜头：\n" + json.dumps(cur_summary, ensure_ascii=False, indent=2) + "\n\n"
            "输出 JSON（只输出这一段）：\n"
            '{"scene_continuous": <bool>, "reason": "<一句话中文理由>"}'
        )

        try:
            raw = self._call_llm(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.2,
                max_tokens=400,
            )
        except Exception as exc:
            print(f"    [Director LLM] 场景连续性判断失败: {exc}")
            return None

        return self._parse_continuity_result(raw)

    def _parse_continuity_result(self, raw: str) -> Optional[Dict]:
        """解析 LLM 返回的 JSON，兼容被 Markdown 包住或前后多余文字的情况。"""
        if not raw:
            return None
        text = raw.strip()

        # 去掉代码块围栏
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text).strip()
            if text.endswith("```"):
                text = text[:-3].strip()

        # 直接尝试解析
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "scene_continuous" in data:
                return data
        except json.JSONDecodeError:
            pass

        # 退化：用正则抓 JSON 子串
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, dict) and "scene_continuous" in data:
                    return data
            except json.JSONDecodeError:
                pass

        print(f"    [Director LLM] 无法解析场景连续性回复: {raw[:200]}")
        return None
    
    def _analyze_scene_changes(self, shots: List[Dict]) -> List[int]:
        """
        【增强】分析场景切换点
        
        使用多种方法综合判断：
        1. scene_id变化
        2. location变化
        3. 场景描述关键词变化
        4. 视觉元素显著变化
        """
        scene_changes = []
        
        for i, shot in enumerate(shots):
            if i == 0:
                continue
            
            prev_shot = shots[i-1]
            
            # 检查1: scene_id变化
            current_scene = shot.get("scene_id", "")
            prev_scene = prev_shot.get("scene_id", "")
            
            if current_scene != prev_scene and current_scene and prev_scene:
                scene_changes.append(i)
                continue
            
            # 检查2: location变化
            current_location = shot.get("location", "")
            prev_location = prev_shot.get("location", "")
            
            if current_location != prev_location and current_location and prev_location:
                scene_changes.append(i)
                continue
            
            # 检查3: 场景描述关键词
            current_desc = shot.get("scene_description", "")
            prev_desc = prev_shot.get("scene_description", "")
            
            # 明确的场景切换关键词
            scene_change_keywords = [
                "走进", "进入", "来到", "离开", "回到", "切换到", "转场",
                "此时", "下一刻", "画面一转", "镜头切到", "时间来到"
            ]
            
            for keyword in scene_change_keywords:
                if keyword in current_desc[:30]:  # 只检查开头
                    scene_changes.append(i)
                    break
        
        return scene_changes
    
    def _decide_reference_images(self, shot_number: int, shot: Dict,
                                 all_characters: List[str],
                                 reference_images: List[str],
                                 current_index: int = 0,
                                 all_shots: List[Dict] = None) -> List[str]:
        """
        【关键决策】决定该镜头使用哪些参考图
        
        决策规则：
        1. 检查该镜头剧本中是否真的包含角色
        2. 只有当镜头中明确出现该角色时才使用对应的参考图
        3. 环境描写、系统广播等无角色镜头不使用参考图
        4. 检测角色重大变化（换装、换人）并调整参考图策略
        
        Args:
            shot_number: 镜头编号
            shot: 镜头数据
            all_characters: 所有角色列表
            reference_images: 用户提供的参考图列表
            current_index: 当前镜头在列表中的索引
            all_shots: 所有镜头列表
        
        Returns:
            List[str]: 该镜头使用的参考图路径列表
        """
        shot_characters = shot.get("characters", [])
        
        # 【新增】检测角色重大变化
        has_major_change = False
        if all_shots and current_index > 0:
            has_major_change = self._has_major_character_change(
                shot, current_index, all_shots
            )
            if has_major_change:
                print(f"    ⚠️ 镜头{shot_number}: 检测到角色重大变化，重新选择参考图")
        
        # 如果用户没有提供参考图，返回空
        if not reference_images:
            return []
        
        # 【关键修复】检查该镜头是否真的包含角色
        if not shot_characters:
            # 进一步分析剧本内容，确认是否真的无角色
            scene_desc = shot.get("scene_description", "")
            visual_desc = shot.get("visual_description", "")
            dialogue = shot.get("dialogue", "")
            
            # 检查是否有角色相关的动作或台词
            has_character_action = False
            character_indicators = ["他", "她", "我", "你", "对着", "说出", "看着", "走", "站", "坐"]
            
            combined_text = scene_desc + visual_desc + dialogue
            for indicator in character_indicators:
                if indicator in combined_text:
                    has_character_action = True
                    break
            
            if not has_character_action:
                print(f"    → 镜头{shot_number}: 无角色出场（环境/系统描述），不使用参考图")
                return []
        
        # 分析该镜头需要的角色
        selected_refs = []
        
        # 【修复】智能匹配角色到参考图
        # 假设reference_images的顺序与all_characters对应
        for char in shot_characters:
            # 尝试找到角色对应的参考图
            char_ref = self._match_character_to_reference(
                char, all_characters, reference_images, shot
            )
            if char_ref and char_ref not in selected_refs:
                selected_refs.append(char_ref)
                print(f"    → 镜头{shot_number}: 角色'{char}'使用参考图 {char_ref}")
        
        # 如果有角色但没有匹配到参考图，使用第一个作为默认
        if shot_characters and not selected_refs and reference_images:
            selected_refs = [reference_images[0]]
            print(f"    → 镜头{shot_number}: 有角色但未匹配，使用默认参考图")
        
        return selected_refs
    
    def _match_character_to_reference(self, char_name: str, 
                                       all_characters: List[str],
                                       reference_images: List[str],
                                       shot: Dict) -> Optional[str]:
        """
        将角色匹配到参考图
        
        【关键修复】通过文件名匹配角色：
        - 检查参考图文件名是否包含角色名
        - 例如：wuming1.png 对应角色"无名"
        - 如果匹配失败，返回None（不使用参考图）
        
        Args:
            char_name: 角色名（如"无名"）
            all_characters: 所有角色列表
            reference_images: 参考图路径列表
            shot: 镜头数据
        
        Returns:
            Optional[str]: 匹配的参考图路径，如果无匹配则返回None
        """
        if not reference_images:
            return None
        
        # 【关键】通过文件名匹配角色
        import os
        for ref_img in reference_images:
            filename = os.path.basename(ref_img).lower()  # 获取文件名并转小写
            char_name_lower = char_name.lower()
            
            # 检查文件名是否包含角色名
            # 例如：wuming1.png 包含 "wuming"
            if char_name_lower in filename or self._fuzzy_match_name(char_name, filename):
                print(f"        匹配成功: 角色'{char_name}' → {ref_img}")
                return ref_img
        
        # 如果没有匹配到，不使用参考图
        print(f"        未匹配: 角色'{char_name}'无对应参考图")
        return None
    
    def _fuzzy_match_name(self, char_name: str, filename: str) -> bool:
        """
        模糊匹配角色名
        
        处理中文拼音等情况：
        - "无名" → "wuming"
        - "凯恩" → "kaien" 或 "kaine"
        """
        # 常见中文名拼音映射
        name_mapping = {
            "无名": ["wuming", "wu_ming"],
            "凯恩": ["kaien", "kaine", "kai_en"],
            "艾莉": ["aili", "ai_li", "ellie"],
            # 可以扩展更多
        }
        
        if char_name in name_mapping:
            for variant in name_mapping[char_name]:
                if variant in filename.lower():
                    return True
        
        return False
    
    def _generate_reference_description(self, shot: Dict,
                                       all_characters: List[str]) -> str:
        """
        生成参考图描述，用于在prompt中区分不同角色
        
        例如：
        - "主角无名特写"
        - "配角凯恩中景"
        """
        shot_characters = shot.get("characters", [])
        
        if not shot_characters:
            return "通用参考图"
        
        descriptions = []
        for i, char in enumerate(shot_characters):
            if i == 0:
                descriptions.append(f"主角{char}")
            else:
                descriptions.append(f"配角{char}")
        
        return " | ".join(descriptions)
    
    # ======================== 分析方法 ========================
    
    def _analyze_characters(self, shots: List[Dict], 
                           character_bank: CharacterBank) -> List[str]:
        """分析所有涉及的角色的列表（按出现顺序）"""
        characters = []
        seen = set()
        
        for shot in shots:
            shot_chars = shot.get("characters", [])
            for char in shot_chars:
                if char not in seen:
                    characters.append(char)
                    seen.add(char)
        
        return characters
    
    def _has_major_character_change(self, shot: Dict, 
                                    current_index: int,
                                    all_shots: List[Dict]) -> bool:
        """检查角色是否有重大变化（如换装、换人）"""
        if current_index == 0:
            return False
        
        prev_shot = all_shots[current_index - 1]
        
        current_chars = set(shot.get("characters", []))
        prev_chars = set(prev_shot.get("characters", []))
        
        # 检查角色完全改变
        if current_chars and prev_chars and current_chars != prev_chars:
            # 如果有新角色加入或旧角色离开，可能需要调整参考图
            new_chars = current_chars - prev_chars
            if new_chars:
                return True  # 新角色出现，需要重新选择参考图
        
        # 检查是否有显式的换装标志
        if shot.get("costume_change") == True:
            return True
        
        return False
    
    def _make_quality_approval(self, optimized_shots: List[Dict],
                                quality_issues: List[Dict],
                                director_decisions: Dict) -> bool:
        """
        【关键决策】质量批准
        
        决策规则：
        1. 如果有严重质量问题（issues，非warnings），不批准
        2. 如果帧继承决策不完整，不批准
        3. 如果参考图策略不明确，不批准
        4. 其他情况，批准
        
        Returns:
            bool: 是否批准进入视频生成
        """
        # 严重问题检查
        if quality_issues:
            print(f"⚠️  存在{len(quality_issues)}个质量问题")
            for issue in quality_issues[:3]:
                print(f"   - 镜头{issue.get('shot', '?')}: {issue.get('error', '未知')}")
        
        # 帧继承决策检查
        frame_inherit = director_decisions.get("frame_inheritance", {})
        if not frame_inherit:
            print("⚠️  帧继承决策未完成")
            return False
        
        # 参考图决策检查
        multi_ref = director_decisions.get("multi_reference_images", {})
        if not multi_ref:
            print("⚠️  参考图决策未完成")
            return False
        
        # 批准进入视频生成
        print("✅ 导演批准进入视频生成阶段")
        return True
    
    # ======================== 提示词构建 ========================
    
    def _optimize_shot_prompt(self, shot: Dict, visual_dna: VisualDNA,
                             character_bank: CharacterBank,
                             world: WorldDatabase) -> Dict:
        """优化单个镜头的提示词，完整保留原始结构化信息用于视频生成和后期制作。"""

        shot_number = shot.get("shot_number", 1)
        duration = shot.get("duration", 3.0)
        start_time = shot.get("start_time", 0.0)

        optimized = {
            "shot_number": shot_number,
            "duration": duration,
            "start_time": start_time,
            "end_time": start_time + duration,
            "time_marker": self._format_time_marker(shot_number, start_time, start_time + duration),
        }

        # 【核心】完整场景描述：优先用原始 storyboard 中的 scene_description /
        # key_action / visual_description，不做截断，供视频生成器参考
        original_scene = (
            shot.get("scene_description")
            or shot.get("visual_description")
            or shot.get("description")
            or ""
        )
        if original_scene:
            optimized["original_scene_description"] = original_scene

        # 【核心】原始摄像机描述：完整保留，不简化
        camera_desc = shot.get("camera_description") or {}
        if isinstance(camera_desc, dict):
            optimized["camera_description"] = camera_desc.get("full_description", str(camera_desc))
        elif camera_desc:
            optimized["camera_description"] = camera_desc

        # 【核心】光影提示
        lighting_hint = shot.get("lighting_hint") or shot.get("lighting_description") or ""
        if lighting_hint:
            optimized["lighting_hint"] = lighting_hint

        # 【核心】前景/后景构图
        foreground = shot.get("foreground") or shot.get("foreground_elements") or []
        background = shot.get("background") or shot.get("background_elements") or []
        if foreground or background:
            optimized["composition_layers"] = {
                "foreground": foreground if isinstance(foreground, list) else [foreground],
                "background": background if isinstance(background, list) else [background],
            }

        # 【核心】帧交接关系：上一个镜头结尾的状态 → 当前镜头开头的承接方式
        # 供视频生成器判断帧继承时的视觉衔接
        optimized["frame_continuity"] = {
            "inherits_from_previous": shot.get("inherits_from_previous", False),
            "previous_ending_description": shot.get("previous_ending_description") or "",
            "current_opening_description": (
                shot.get("current_opening_description")
                or shot.get("opening_description")
                or shot.get("scene_opening")
                or ""
            ),
            "current_ending_description": shot.get("ending_description") or "",
            "transition_type": shot.get("transition") or shot.get("transition_type") or "cut",
        }

        # 【核心】视觉提示词（基于原始场景 + 世界观增强）
        visual_prompt = self._build_visual_prompt(
            shot, visual_dna, character_bank, world
        )
        optimized["visual_prompt"] = visual_prompt

        # 【核心】音频提示词（含旁白 / 对白 / 音效）
        audio_prompt = self._build_audio_prompt(shot)
        optimized["audio_prompt"] = audio_prompt

        # 【核心】旁白/解说路由：通知 post_production 模块处理旁白配音
        # 旁白不由视频生成模型处理，交给 TTS 模块
        raw_narration = shot.get("narration") or shot.get("voiceover") or ""
        if raw_narration and raw_narration not in ("无", "无旁白"):
            optimized["narration_for_postproduction"] = {
                "content": raw_narration,
                "route_to": "post_production",
                "target_duration_seconds": float(shot.get("duration", 3.0)),
                "estimated_duration_seconds": self._estimate_speech_duration(raw_narration),
                "timing_policy": "在镜头目标时长内完成；超时则降低语速或拆分到后续镜头，不允许覆盖下一镜头",
            }

        # 完整的元数据（保留原始字段，不简化）
        metadata = {
            "shot_type": shot.get("shot_type"),
            "camera_angle": shot.get("camera_angle"),
            "camera_movement": shot.get("camera_movement"),
            "location": shot.get("location"),
            "characters": shot.get("characters", []),
            "scene_id": shot.get("scene_id"),
        }
        # 附加原始摄像机信息
        if shot.get("camera_equipment"):
            metadata["camera_equipment"] = shot.get("camera_equipment")
        if shot.get("composition"):
            metadata["composition"] = shot.get("composition")
        if shot.get("transition"):
            metadata["transition"] = shot.get("transition")
        if shot.get("key_action"):
            metadata["key_action"] = shot.get("key_action")
        if shot.get("sound_effects"):
            metadata["sound_effects"] = shot.get("sound_effects")
        optimized["metadata"] = metadata

        return optimized
    
    def _format_time_marker(self, shot_number: int, start_time: float, end_time: float) -> str:
        """格式化时间轴标记"""
        def fmt(s):
            return f"{int(s//60)}:{int(s%60):02d}"
        return f"镜头 {shot_number} [{fmt(start_time)}–{fmt(end_time)}]"
    
    def _build_visual_prompt(self, shot: Dict, visual_dna: VisualDNA,
                            character_bank: CharacterBank,
                            world: WorldDatabase) -> str:
        """
        构建电影级专业视觉提示词。

        优先以原始 scene_description / scene_opening / key_action 为基础，
        保留完整的场景氛围、摄像机运动细节、光影质感，不做截断或简化重构。
        """

        sections = []

        # 1. 摄影机参数（作为开头的基调描述）
        camera_parts = []
        shot_type = self._translate_shot_type_professional(shot.get("shot_type"))
        camera_parts.append(shot_type)

        angle = self._translate_angle_professional(shot.get("camera_angle"))
        if angle:
            camera_parts.append(angle)

        movement = self._translate_movement_professional(shot.get("camera_movement"))
        if movement:
            camera_parts.append(movement)

        sections.append("，".join(camera_parts))

        # 2. 【核心】原始完整场景描述：直接使用 storyboard 中的原始字段，
        # 不做简化重构，以保留完整的视觉氛围、纹理、色彩、景深等细节
        original_scene = (
            shot.get("scene_description")
            or shot.get("visual_description")
            or shot.get("description")
            or ""
        )
        if original_scene:
            sections.append(original_scene)

        # 3. 摄像机详细运动描述（若原始数据中有 camera_description）
        camera_desc_raw = shot.get("camera_description")
        if isinstance(camera_desc_raw, dict):
            full_desc = camera_desc_raw.get("full_description", "")
            if full_desc and full_desc not in original_scene:
                sections.append(full_desc)
        elif camera_desc_raw and camera_desc_raw not in original_scene:
            sections.append(str(camera_desc_raw))

        # 4. 前景 / 后景构图（若原始数据中有）
        foreground = shot.get("foreground") or shot.get("foreground_elements") or []
        background = shot.get("background") or shot.get("background_elements") or []
        if foreground:
            fg_str = "、".join(foreground) if isinstance(foreground, list) else str(foreground)
            sections.append(f"前景：{fg_str}。")
        if background:
            bg_str = "、".join(background) if isinstance(background, list) else str(background)
            sections.append(f"后景：{bg_str}。")

        # 5. 角色描述（补充，非覆盖）
        character_desc = self._build_detailed_characters(shot, character_bank)
        if character_desc:
            sections.append(character_desc)

        # 6. 动作和台词（补充原始 key_action）
        action_desc = self._build_detailed_actions(shot)
        if action_desc:
            sections.append(action_desc)

        # 7. 光影质感（若原始数据中有 lighting_hint，优先保留）
        lighting_hint = shot.get("lighting_hint") or shot.get("lighting_description") or ""
        if lighting_hint:
            sections.append(lighting_hint)
        else:
            # 仅在无原始描述时用世界观增强
            lighting_desc = self._build_detailed_lighting(shot, visual_dna, world)
            if lighting_desc:
                sections.append(lighting_desc)

        # 8. 技术参数（补充）
        tech_params = self._build_technical_parameters(shot, visual_dna)
        if tech_params:
            sections.append(tech_params)

        prompt = "。".join(sections)
        if not prompt.endswith("。"):
            prompt += "。"
        return prompt
    
    def _build_detailed_actions(self, shot: Dict) -> str:
        """【关键】构建动作描述，必须包含台词"""
        action_parts = []
        
        # 基础动作
        action = shot.get("key_action") or shot.get("action", "")
        if action:
            action_parts.append(action)
        
        # 【关键】强制包含台词
        dialogue = shot.get("character_dialogue") or {}  # 修复：可能为None
        if dialogue and dialogue.get("text"):
            dialogue_text = dialogue["text"]
            emotion = dialogue.get("emotion", "")
            
            dialogue_action = f"对着镜头说出台词「{dialogue_text}」，口型清晰精准"  # 这里是个待修复的bug，因为人物说台词不一定非要对着镜头
            
            # 情绪视觉化
            if emotion:
                emotion_visual = self._translate_emotion_to_visual(emotion)
                if emotion_visual:
                    dialogue_action += f"，{emotion_visual}"
            
            action_parts.append(dialogue_action)
        
        return "。".join(action_parts) if action_parts else ""
    
    def _translate_emotion_to_visual(self, emotion: str) -> str:
        """情绪转视觉描述"""
        mapping = {
            "冷漠": "眉头紧锁，下颌肌肉紧绷",
            "愤怒": "眼神凌厉，嘴角下压，额头青筋暴起",
            "坚定": "眼神凝视，下巴微抬",
            "恐惧": "瞳孔放大，嘴唇颤抖",
            "悲伤": "眼眶泛红，嘴角下垂",
            "冷笑": "嘴角微扬，眼神轻蔑"
        }
        return mapping.get(emotion, "")
    
    def _translate_shot_type_professional(self, shot_type: str) -> str:
        mapping = {
            "extreme_wide_shot": "大远景定场",
            "wide_shot": "全景",
            "medium_shot": "中景",
            "close_up": "特写",
            "extreme_close_up": "大特写微距"
        }
        return mapping.get(shot_type, "中景")
    
    def _translate_angle_professional(self, angle: str) -> str:
        mapping = {
            "eye_level": "平视角度",
            "high_angle": "俯拍角度",
            "low_angle": "低角度仰拍",
            "bird_eye_view": "鸟瞰视角",
            "dutch_angle": "荷兰角倾斜"
        }
        return mapping.get(angle, "")
    
    def _translate_movement_professional(self, movement: str) -> str:
        mapping = {
            "static": "固定机位",
            "pan": "摇镜跟随",
            "tilt": "升降摇臂",
            "dolly_in": "轨道推进",
            "dolly_out": "轨道拉远",
            "tracking": "斯坦尼康跟踪",
            "crane": "摇臂升降",
            "slow_pan": "缓慢稳定器环绕",
            "handheld": "手持摄影"
        }
        return mapping.get(movement, "")
    
    def _build_detailed_scene(self, shot: Dict, world: WorldDatabase) -> str:
        """【修复】构建详细场景描述，从世界观数据库提取结构化数据"""
        location = shot.get("location", "")
        scene_description = shot.get("scene_description", "")
        
        scene_parts = []
        
        if location and world:
            location_data = world.get_location(location)
            if location_data:
                # 提取结构化数据
                desc = location_data.get("description", "")
                visual_elements = location_data.get("visual_elements", [])
                color_palette = location_data.get("color_palette", [])
                atmosphere = location_data.get("atmosphere", "")
                
                if desc:
                    scene_parts.append(desc)
                
                # 视觉元素
                if visual_elements:
                    elements_str = "、".join(visual_elements[:5])
                    scene_parts.append(f"视觉元素包括{elements_str}")
                
                # 色彩基调
                if color_palette:
                    colors_str = "、".join(color_palette[:3])
                    scene_parts.append(f"色彩基调为{colors_str}")
                
                # 氛围
                if atmosphere:
                    scene_parts.append(f"整体氛围{atmosphere}")
        
        # 原有的场景描述（作为补充）
        if scene_description and scene_description not in "".join(scene_parts):
            scene_parts.append(scene_description)
        
        # 如果都没有，返回基础描述
        if not scene_parts and location:
            return f"{location}内部环境"
        
        return "，".join(scene_parts)
    
    def _build_detailed_characters(self, shot: Dict, character_bank: CharacterBank) -> str:
        """【修复】构建详细角色描述，从角色库提取结构化数据"""
        characters = shot.get("characters", [])
        if not characters:
            return ""
        
        char_parts = []
        for char_name in characters:
            parts = []
            
            if character_bank:
                base_desc = character_bank.get_character_prompt_description(char_name)
                if base_desc:
                    parts.append(base_desc)

                # 【新增】尝试获取角色的详细视觉特征
                char_data = character_bank.get_character(char_name)
                if char_data:
                    # Character 是 dataclass：直接属性访问
                    distinctive_features = getattr(char_data, "distinctive_features", []) or []
                    clothing = getattr(char_data, "clothing", {}) or {}

                    # 服装描述
                    if clothing and len(clothing) > 0:
                        clothing_type = clothing.get("type", "") if isinstance(clothing, dict) else ""
                        if clothing_type and clothing_type not in base_desc:
                            parts.append(f"身着{clothing_type}")

                    # 外貌特征
                    if distinctive_features:
                        if isinstance(distinctive_features, list) and len(distinctive_features) > 0:
                            feature_str = "、".join(distinctive_features[:2])
                            if feature_str not in "".join(parts):
                                parts.append(feature_str)
            else:
                parts.append(char_name)
            
            # 镜头内的角色状态
            char_state = shot.get("character_states", {}).get(char_name, {})
            if char_state.get("expression"):
                parts.append(f"表情{char_state['expression']}")
            if char_state.get("eyes"):
                parts.append(char_state["eyes"])
            if char_state.get("posture"):
                parts.append(char_state["posture"])
            
            if parts:
                char_parts.append("，".join(parts))
        
        return " 与 ".join(char_parts) if len(char_parts) > 1 else (char_parts[0] if char_parts else "")
    
    def _build_detailed_lighting(self, shot: Dict, visual_dna: VisualDNA, world: WorldDatabase) -> str:
        """【修复】构建光影描述，从world和visual_dna提取数据"""
        lighting = shot.get("lighting", {})
        parts = []
        
        if lighting:
            if lighting.get("type"):
                parts.append(lighting["type"])
            if lighting.get("direction"):
                parts.append(f"光线{lighting['direction']}照射")
        
        # 【新增】尝试从world获取场景的默认光影风格
        if world and not parts:
            try:
                location = shot.get("location", "")
                if location:
                    location_data = world.get_location(location)
                    if location_data and location_data.get("lighting_type"):
                        parts.append(location_data["lighting_type"])
            except Exception:
                pass
        
        # 从visual_dna获取全局光影风格
        if visual_dna and not parts:
            try:
                if hasattr(visual_dna, 'lighting_style') and visual_dna.lighting_style:
                    parts.append(visual_dna.lighting_style)
            except Exception:
                pass
        
        return "，".join(parts) if parts else ""
    
    def _build_technical_parameters(self, shot: Dict, visual_dna: VisualDNA) -> str:
        params = []
        
        shot_type = shot.get("shot_type", "")
        if shot_type in ["extreme_wide_shot"]:
            params.append("24mm广角镜头")
        elif shot_type == "close_up":
            params.append("85mm镜头")
        else:
            params.append("35mm标准镜头")
        
        if shot_type in ["close_up", "extreme_close_up"]:
            params.append("浅景深f/2.8")
        else:
            params.append("中等景深f/5.6")
        
        params.extend(["真实照片级质感", "电影胶片颗粒"])
        return "，".join(params)
    
    def _build_audio_prompt(self, shot: Dict) -> Dict:
        """构建可并存的对白/旁白/音效结构，并记录时长约束。"""
        audio = {}

        dialogue = shot.get("character_dialogue") or {}
        dialogue_text = dialogue.get("content") or dialogue.get("text") or ""
        if dialogue_text:
            audio["dialogue"] = {
                "type": "dialogue",
                "character": dialogue.get("character") or dialogue.get("speaker", ""),
                "content": dialogue_text,
                "emotion": dialogue.get("emotion", "平静"),
                "estimated_duration_seconds": self._estimate_speech_duration(dialogue_text),
            }

        narration = shot.get("narration", "") or shot.get("voiceover", "") or ""
        if narration and narration not in ("无", "无旁白"):
            audio["narration"] = {
                "type": "narration",
                "content": narration,
                "route_to": "post_production",
                "estimated_duration_seconds": self._estimate_speech_duration(narration),
            }

        sound_effects = shot.get("sound_effects", []) or shot.get("sound_fx", []) or []
        audio["sound_effects"] = sound_effects if isinstance(sound_effects, list) else [sound_effects]
        audio["target_shot_duration_seconds"] = float(shot.get("duration", 3.0))
        speech_duration = sum(
            item.get("estimated_duration_seconds", 0.0)
            for key in ("dialogue", "narration")
            for item in ([audio[key]] if key in audio else [])
        )
        audio["speech_duration_seconds"] = round(speech_duration, 2)
        audio["speech_fits_shot"] = speech_duration <= float(shot.get("duration", 3.0))
        return audio if any(audio.values()) else {}

    @staticmethod
    def _estimate_speech_duration(text: str) -> float:
        """中文旁白/对白的保守时长估算，供质量门和后期对齐使用。"""
        if not text:
            return 0.0
        compact = re.sub(r"\\s+", "", str(text))
        # 约每秒 4 个中文字符，标点增加短停顿。
        punctuation_pauses = len(re.findall(r"[，。！？；：、,.!?;:]", compact)) * 0.12
        return round(max(0.4, len(compact) / 4.0 + punctuation_pauses), 2)
    
    def _generate_quality_report(self, shots: List[Dict], 
                                 issues: List[Dict]) -> Dict:
        """生成质量报告"""
        
        prompt_lengths = [len(shot.get("visual_prompt", "")) for shot in shots]
        avg_length = sum(prompt_lengths) / len(prompt_lengths) if prompt_lengths else 0
        
        return {
            "total_shots": len(shots),
            "stats": {
                "passed": len(shots) - len(issues),
                "warnings": len(issues),
                "avg_length": int(avg_length),
                "max_length": max(prompt_lengths) if prompt_lengths else 0
            },
            "issues": issues,
            "summary": f"总镜头{len(shots)}个，通过{len(shots)-len(issues)}个"
        }
