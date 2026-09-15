"""
增强的质量检查员 - Enhanced Quality Inspector

对最终结构报告进行全面评审，包括：
- 故事线连续性
- 逻辑一致性
- 角色定义一致性
- 视觉风格统一性
- 镜头语言合理性
- 技术规范完整性
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime


class EnhancedQualityInspector:
    """增强的质量检查员"""
    
    # 评审维度权重
    DIMENSION_WEIGHTS = {
        "story_continuity": 0.25,      # 故事线连续性
        "logical_consistency": 0.20,    # 逻辑一致性
        "character_consistency": 0.20,  # 角色定义一致性
        "visual_unity": 0.15,           # 视觉风格统一性
        "shot_language": 0.10,          # 镜头语言合理性
        "technical_completeness": 0.10  # 技术规范完整性
    }
    
    # 及格分数线
    PASS_THRESHOLD = 0.70
    
    def __init__(self, llm_config: Optional[Dict] = None):
        """
        初始化增强的质量检查员
        
        Args:
            llm_config: LLM配置（预留，当前使用规则检查）
        """
        self.llm_config = llm_config or {}
    
    def inspect(self, stage: str, data: Any, context: Dict = None) -> Dict[str, Any]:
        """
        通用检查接口，支持不同阶段
        
        Args:
            stage: 检查阶段 ("prompts", "final_report", etc.)
            data: 待检查的数据
            context: 上下文信息
            
        Returns:
            统一格式的检查结果
        """
        if stage == "prompts":
            return self._inspect_prompts(data, context or {})
        elif stage == "final_report":
            return self.inspect_final_report(data)
        else:
            raise ValueError(f"不支持的检查阶段: {stage}")
    
    def _inspect_prompts(self, optimized_shots: Dict, context: Dict) -> Dict[str, Any]:
        """
        检查优化后的提示词阶段
        
        Args:
            optimized_shots: 优化后的镜头数据
            context: 包含 world, script, storyboard 等上下文
            
        Returns:
            {
                "pass": bool,
                "score": float,
                "threshold": float,
                "dimension_scores": Dict[str, float],
                "issues": List[str],
                "suggestions": List[str],
                "detailed_review": str,
                "approval_reason": str
            }
        """
        print("\n🔍 质量检查员：检查提示词质量...")
        
        issues = []
        suggestions = []
        dimension_scores = {}
        
        shots = optimized_shots.get("shots", [])
        if not shots:
            return {
                "pass": False,
                "score": 0.0,
                "threshold": self.PASS_THRESHOLD,
                "dimension_scores": {},
                "issues": ["没有可用的镜头数据"],
                "suggestions": [],
                "detailed_review": "缺少镜头数据",
                "approval_reason": ""
            }
        
        # 1. 视觉统一性检查 (15%)
        visual_unity_score = self._check_prompt_visual_unity(shots, context)
        dimension_scores["visual_unity"] = visual_unity_score
        if visual_unity_score < 0.7:
            issues.append(f"视觉统一性不足({visual_unity_score:.2f})，风格描述不一致")
        
        # 2. 镜头语言检查 (10%)
        shot_language_score = self._check_prompt_shot_language(shots)
        dimension_scores["shot_language"] = shot_language_score
        if shot_language_score < 0.7:
            issues.append(f"镜头语言质量不足({shot_language_score:.2f})，缺少运镜或构图描述")
        
        # 3. 技术完整性检查 (10%)
        technical_score = self._check_prompt_technical_completeness(shots)
        dimension_scores["technical_completeness"] = technical_score
        if technical_score < 0.7:
            issues.append(f"技术完整性不足({technical_score:.2f})，缺少必要的技术参数")
        
        # 4. 角色一致性检查 (20%)
        character_score = self._check_prompt_character_consistency(shots, context)
        dimension_scores["character_consistency"] = character_score
        if character_score < 0.7:
            issues.append(f"角色一致性不足({character_score:.2f})，角色描述不统一")
        
        # 5. 逻辑一致性检查 (20%)
        logical_score = self._check_prompt_logical_consistency(shots, context)
        dimension_scores["logical_consistency"] = logical_score
        if logical_score < 0.7:
            issues.append(f"逻辑一致性不足({logical_score:.2f})，镜头间衔接有问题")
        
        # 6. 故事连续性检查 (25%)
        story_score = self._check_prompt_story_continuity(shots, context)
        dimension_scores["story_continuity"] = story_score
        if story_score < 0.7:
            issues.append(f"故事连续性不足({story_score:.2f})，叙事不流畅")
        
        # 计算加权总分
        overall_score = (
            dimension_scores["visual_unity"] * 0.15 +
            dimension_scores["shot_language"] * 0.10 +
            dimension_scores["technical_completeness"] * 0.10 +
            dimension_scores["character_consistency"] * 0.20 +
            dimension_scores["logical_consistency"] * 0.20 +
            dimension_scores["story_continuity"] * 0.25
        )
        
        # 严格判定：总分达标且无严重问题
        passed = overall_score >= self.PASS_THRESHOLD and len(issues) == 0
        
        # 生成建议
        if not passed:
            if dimension_scores["visual_unity"] < 0.7:
                suggestions.append("统一视觉风格描述，确保色调、光线、氛围一致")
            if dimension_scores["shot_language"] < 0.7:
                suggestions.append("补充运镜、景别、构图等镜头语言描述")
            if dimension_scores["technical_completeness"] < 0.7:
                suggestions.append("补充技术参数：分辨率、帧率、运动幅度等")
            if dimension_scores["character_consistency"] < 0.7:
                suggestions.append("统一角色外观描述，确保特征一致")
            if dimension_scores["logical_consistency"] < 0.7:
                suggestions.append("检查镜头间的空间和时间逻辑")
            if dimension_scores["story_continuity"] < 0.7:
                suggestions.append("确保每个镜头都推进故事发展")
        
        detailed_review = f"""提示词质量评审报告
        
总体评分: {overall_score:.2f}/{self.PASS_THRESHOLD}
评审结果: {'✅ 通过' if passed else '❌ 不通过'}

维度评分:
- 视觉统一性: {dimension_scores['visual_unity']:.2f} (15%)
- 镜头语言: {dimension_scores['shot_language']:.2f} (10%)
- 技术完整性: {dimension_scores['technical_completeness']:.2f} (10%)
- 角色一致性: {dimension_scores['character_consistency']:.2f} (20%)
- 逻辑一致性: {dimension_scores['logical_consistency']:.2f} (20%)
- 故事连续性: {dimension_scores['story_continuity']:.2f} (25%)

问题数: {len(issues)}
建议数: {len(suggestions)}
"""
        
        approval_reason = "所有维度均达标，提示词质量优秀" if passed else ""
        
        return {
            "pass": passed,
            "score": overall_score,
            "threshold": self.PASS_THRESHOLD,
            "dimension_scores": dimension_scores,
            "issues": issues,
            "suggestions": suggestions,
            "detailed_review": detailed_review,
            "approval_reason": approval_reason
        }
    
    def _check_prompt_visual_unity(self, shots: List[Dict], context: Dict) -> float:
        """检查提示词的视觉统一性"""
        score = 1.0
        visual_dna = context.get("visual_dna", )
        
        if not visual_dna:
            return 0.8  # 没有visual_dna，给基础分
        
        # 检查每个镜头是否体现了visual_dna的核心风格
        style_keywords = ["电影", "cinematic", "风格", "色调", "光线", "氛围"]
        style_mentioned_count = 0
        
        for shot in shots:
            prompt = shot.get("visual_prompt", "").lower()
            if any(kw in prompt for kw in style_keywords):
                style_mentioned_count += 1
        
        style_ratio = style_mentioned_count / len(shots) if shots else 0
        if style_ratio < 0.5:
            score -= 0.3
        
        return max(0.0, score)
    
    def _check_prompt_shot_language(self, shots: List[Dict]) -> float:
        """检查镜头语言质量"""
        score = 1.0
        shot_keywords = ["特写", "全景", "中景", "运镜", "推镜", "拉镜", "摇镜", "构图", "景别"]
        
        shots_with_language = 0
        for shot in shots:
            prompt = shot.get("visual_prompt", "")
            if any(kw in prompt for kw in shot_keywords):
                shots_with_language += 1
        
        language_ratio = shots_with_language / len(shots) if shots else 0
        if language_ratio < 0.7:
            score -= 0.3
        elif language_ratio < 0.5:
            score -= 0.5
        
        return max(0.0, score)
    
    def _check_prompt_technical_completeness(self, shots: List[Dict]) -> float:
        """检查技术完整性"""
        score = 1.0
        # negative_prompt 是可选的，只检查必需字段
        required_fields = ["visual_prompt", "duration"]
        
        complete_shots = 0
        for shot in shots:
            if all(shot.get(field) for field in required_fields):
                complete_shots += 1
        
        completeness_ratio = complete_shots / len(shots) if shots else 0
        if completeness_ratio < 1.0:
            score -= (1.0 - completeness_ratio) * 0.5
        
        return max(0.0, score)
    
    def _check_prompt_character_consistency(self, shots: List[Dict], context: Dict) -> float:
        """检查角色一致性"""
        score = 1.0
        character_bank = context.get("character_bank", {})
        
        if not character_bank:
            return 0.9  # 没有角色，给高分
        
        # 检查是否使用了参考图
        shots_with_ref = sum(1 for shot in shots if shot.get("reference_image"))
        ref_ratio = shots_with_ref / len(shots) if shots else 0
        
        if ref_ratio < 0.3:
            score -= 0.2  # 参考图使用率低
        
        return max(0.0, score)
    
    def _check_prompt_logical_consistency(self, shots: List[Dict], context: Dict) -> float:
        """检查逻辑一致性"""
        score = 1.0
        
        # 检查镜头间的帧继承逻辑
        director_decisions = context.get("director_decisions", {})
        frame_inherit = director_decisions.get("frame_inheritance", {})
        
        if frame_inherit:
            inherit_ratio = sum(1 for v in frame_inherit.values() if v) / len(frame_inherit)
            if inherit_ratio < 0.2 or inherit_ratio > 0.9:
                score -= 0.2  # 继承比例异常
        
        return max(0.0, score)
    
    def _check_prompt_story_continuity(self, shots: List[Dict], context: Dict) -> float:
        """检查故事连续性"""
        score = 1.0
        script = context.get("script", )
        
        if not script:
            return 0.8
        
        # 检查每个镜头是否有场景描述
        shots_with_scene = sum(1 for shot in shots if shot.get("scene_description"))
        scene_ratio = shots_with_scene / len(shots) if shots else 0
        
        if scene_ratio < 0.8:
            score -= 0.3
        
        return max(0.0, score)
    
    def inspect_final_report(self, final_report: Dict) -> Dict[str, Any]:
        """
        检查最终结构报告
        
        Args:
            final_report: 导演生成的最终结构报告
            
        Returns:
            {
                "passed": bool,
                "overall_score": float,
                "dimension_scores": Dict[str, float],
                "issues": List[str],
                "suggestions": List[str],
                "warnings": List[str],
                "detailed_feedback": Dict
            }
        """
        print("\n🔍 开始全面质量检查...")
        print("   评审维度：")
        print("   1. 故事线连续性 (25%)")
        print("   2. 逻辑一致性 (20%)")
        print("   3. 角色定义一致性 (20%)")
        print("   4. 视觉风格统一性 (15%)")
        print("   5. 镜头语言合理性 (10%)")
        print("   6. 技术规范完整性 (10%)")
        print()
        
        # 各维度评分
        dimension_scores = {}
        dimension_feedback = {}
        
        # 1. 故事线连续性
        print("   ✓ 检查故事线连续性...")
        story_result = self._check_story_continuity(final_report)
        dimension_scores["story_continuity"] = story_result["score"]
        dimension_feedback["story_continuity"] = story_result
        
        # 2. 逻辑一致性
        print("   ✓ 检查逻辑一致性...")
        logic_result = self._check_logical_consistency(final_report)
        dimension_scores["logical_consistency"] = logic_result["score"]
        dimension_feedback["logical_consistency"] = logic_result
        
        # 3. 角色定义一致性
        print("   ✓ 检查角色定义一致性...")
        character_result = self._check_character_consistency(final_report)
        dimension_scores["character_consistency"] = character_result["score"]
        dimension_feedback["character_consistency"] = character_result
        
        # 4. 视觉风格统一性
        print("   ✓ 检查视觉风格统一性...")
        visual_result = self._check_visual_unity(final_report)
        dimension_scores["visual_unity"] = visual_result["score"]
        dimension_feedback["visual_unity"] = visual_result
        
        # 5. 镜头语言合理性
        print("   ✓ 检查镜头语言合理性...")
        shot_result = self._check_shot_language(final_report)
        dimension_scores["shot_language"] = shot_result["score"]
        dimension_feedback["shot_language"] = shot_result
        
        # 6. 技术规范完整性
        print("   ✓ 检查技术规范完整性...")
        tech_result = self._check_technical_completeness(final_report)
        dimension_scores["technical_completeness"] = tech_result["score"]
        dimension_feedback["technical_completeness"] = tech_result
        
        # 计算总分
        overall_score = sum(
            dimension_scores[dim] * self.DIMENSION_WEIGHTS[dim]
            for dim in dimension_scores
        )
        
        # 收集所有问题和建议
        issues = []
        suggestions = []
        warnings = []
        
        for dim, feedback in dimension_feedback.items():
            issues.extend(feedback.get("issues", []))
            suggestions.extend(feedback.get("suggestions", []))
            warnings.extend(feedback.get("warnings", []))
        
        # 严格判定：总分达标且无严重问题
        passed = overall_score >= self.PASS_THRESHOLD and len(issues) == 0
        
        print(f"\n📊 质量评分: {overall_score:.2%}")
        print(f"   及格线: {self.PASS_THRESHOLD:.2%}")
        print(f"   结果: {'✅ 通过' if passed else '❌ 不通过'}")
        
        return {
            "passed": passed,
            "overall_score": overall_score,
            "dimension_scores": dimension_scores,
            "issues": issues,
            "suggestions": suggestions,
            "warnings": warnings,
            "detailed_feedback": dimension_feedback,
            "timestamp": datetime.now().isoformat()
        }
    
    def _check_story_continuity(self, report: Dict) -> Dict:
        """检查故事线连续性"""
        issues = []
        suggestions = []
        warnings = []
        score = 1.0
        
        shots = report.get("shots", [])
        
        if not shots:
            issues.append("没有镜头数据")
            return {"score": 0.0, "issues": issues, "suggestions": suggestions, "warnings": warnings}
        
        # 检查镜头编号是否连续
        shot_numbers = [s.get("shot_number", 0) for s in shots]
        expected_numbers = list(range(1, len(shots) + 1))
        
        if shot_numbers != expected_numbers:
            issues.append("镜头编号不连续")
            score -= 0.2
        
        # 检查时间流是否合理
        prev_time = None
        for i, shot in enumerate(shots, 1):
            scene = shot.get("scene", {})
            time_of_day = scene.get("time_of_day", "")
            
            if prev_time and time_of_day:
                # 简单检查：如果从夜晚突然跳到白天，给出警告
                if prev_time == "night" and time_of_day == "day" and i > 1:
                    warnings.append(f"镜头{i}时间跳跃：从夜晚到白天，建议添加过渡")
            
            prev_time = time_of_day
        
        # 检查场景转换是否合理
        prev_location = None
        for i, shot in enumerate(shots, 1):
            scene = shot.get("scene", {})
            location = scene.get("location", "")
            
            if prev_location and location and location != prev_location:
                # 场景切换，检查是否有必要说明
                if i < len(shots):
                    suggestions.append(f"镜头{i}场景切换：从'{prev_location}'到'{location}'，确保转换自然")
            
            prev_location = location
        
        # 检查动作连贯性
        for i, shot in enumerate(shots, 1):
            action = shot.get("action", "")
            if not action or len(action) < 10:
                warnings.append(f"镜头{i}缺少详细的动作描述")
                score -= 0.05
        
        score = max(0.0, min(1.0, score))
        
        return {
            "score": score,
            "issues": issues,
            "suggestions": suggestions,
            "warnings": warnings
        }
    
    def _check_logical_consistency(self, report: Dict) -> Dict:
        """检查逻辑一致性"""
        issues = []
        suggestions = []
        warnings = []
        score = 1.0
        
        shots = report.get("shots", [])
        world_setting = report.get("world_setting", {})
        
        # 检查世界观设定
        if not world_setting:
            issues.append("缺少世界观设定")
            score -= 0.3
        else:
            time_period = world_setting.get("time_period", "")
            if not time_period:
                warnings.append("世界观缺少时代设定")
                score -= 0.1
        
        # 检查角色行为逻辑
        characters = report.get("characters", [])
        character_shots = {}
        
        for shot in shots:
            shot_chars = shot.get("characters", [])
            for char in shot_chars:
                char_name = char.get("name", "") if isinstance(char, dict) else char
                if char_name:
                    if char_name not in character_shots:
                        character_shots[char_name] = []
                    character_shots[char_name].append(shot.get("shot_number", 0))
        
        # 检查角色出现是否合理
        for char_name, shot_nums in character_shots.items():
            if len(shot_nums) == 1:
                warnings.append(f"角色'{char_name}'只出现在1个镜头中，考虑是否需要增加戏份")
        
        # 检查对话逻辑
        for i, shot in enumerate(shots, 1):
            audio = shot.get("audio", {})
            dialogue = audio.get("dialogue", "")
            chars_in_shot = shot.get("characters", [])
            
            if dialogue and not chars_in_shot:
                issues.append(f"镜头{i}有对话但没有角色")
                score -= 0.1
        
        score = max(0.0, min(1.0, score))
        
        return {
            "score": score,
            "issues": issues,
            "suggestions": suggestions,
            "warnings": warnings
        }
    
    def _check_character_consistency(self, report: Dict) -> Dict:
        """检查角色定义一致性"""
        issues = []
        suggestions = []
        warnings = []
        score = 1.0
        
        characters = report.get("characters", [])
        shots = report.get("shots", [])
        
        if not characters:
            warnings.append("没有定义角色")
            return {"score": 0.8, "issues": issues, "suggestions": suggestions, "warnings": warnings}
        
        # 提取角色名称
        char_names = set()
        for char in characters:
            if isinstance(char, dict):
                name = char.get("name", "")
            else:
                name = char
            if name:
                char_names.add(name)
        
        # 检查镜头中的角色是否都在角色表中
        for i, shot in enumerate(shots, 1):
            shot_chars = shot.get("characters", [])
            for char in shot_chars:
                char_name = char.get("name", "") if isinstance(char, dict) else char
                if char_name and char_name not in char_names:
                    issues.append(f"镜头{i}中的角色'{char_name}'未在角色表中定义")
                    score -= 0.1
        
        # 检查角色描述一致性
        for char in characters:
            if isinstance(char, dict):
                name = char.get("name", "")
                description = char.get("description", "")
                
                if not description or len(description) < 10:
                    warnings.append(f"角色'{name}'缺少详细描述")
                    score -= 0.05
        
        score = max(0.0, min(1.0, score))
        
        return {
            "score": score,
            "issues": issues,
            "suggestions": suggestions,
            "warnings": warnings
        }
    
    def _check_visual_unity(self, report: Dict) -> Dict:
        """检查视觉风格统一性"""
        issues = []
        suggestions = []
        warnings = []
        score = 1.0
        
        visual_style = report.get("visual_style", {})
        shots = report.get("shots", [])
        
        # 检查是否有视觉风格定义
        if not visual_style:
            issues.append("缺少视觉风格定义")
            return {"score": 0.5, "issues": issues, "suggestions": suggestions, "warnings": warnings}
        
        # 检查色彩方案
        global_palette = visual_style.get("color_palette", [])
        if not global_palette:
            warnings.append("缺少全局色彩方案")
            score -= 0.1
        elif len(global_palette) > 5:
            suggestions.append(f"色彩方案包含{len(global_palette)}种颜色，建议控制在3-5种以内")
            score -= 0.05
        
        # 检查光线方案
        lighting_scheme = visual_style.get("lighting_scheme", {})
        if not lighting_scheme:
            warnings.append("缺少光线方案")
            score -= 0.1
        
        # 检查各镜头是否遵循视觉风格
        for i, shot in enumerate(shots, 1):
            visual = shot.get("visual", {})
            shot_palette = visual.get("color_palette", [])
            
            # 如果镜头有自己的色彩，检查是否与全局一致
            if shot_palette and global_palette:
                # 检查镜头色彩是否是全局色彩的子集
                for color in shot_palette:
                    if color not in global_palette:
                        warnings.append(f"镜头{i}使用了非全局色彩方案中的颜色：{color}")
                        score -= 0.02
        
        score = max(0.0, min(1.0, score))
        
        return {
            "score": score,
            "issues": issues,
            "suggestions": suggestions,
            "warnings": warnings
        }
    
    def _check_shot_language(self, report: Dict) -> Dict:
        """检查镜头语言合理性"""
        issues = []
        suggestions = []
        warnings = []
        score = 1.0
        
        shots = report.get("shots", [])
        
        if not shots:
            return {"score": 0.0, "issues": ["没有镜头"], "suggestions": suggestions, "warnings": warnings}
        
        # 检查景别分布
        shot_types = [s.get("shot_type", "") for s in shots]
        shot_type_counts = {}
        for st in shot_types:
            shot_type_counts[st] = shot_type_counts.get(st, 0) + 1
        
        # 如果全部是同一种景别，给出建议
        if len(shot_type_counts) == 1:
            suggestions.append(f"所有镜头都是'{list(shot_type_counts.keys())[0]}'，建议增加景别变化")
            score -= 0.1
        
        # 检查运镜方式
        movements = [s.get("camera_movement", "") for s in shots]
        static_count = movements.count("static")
        
        if static_count == len(shots):
            suggestions.append("所有镜头都是静态，建议增加运镜变化")
            score -= 0.1
        elif static_count == 0:
            warnings.append("没有静态镜头，可能过于动感")
        
        # 检查镜头时长
        for i, shot in enumerate(shots, 1):
            duration = shot.get("duration", 0)
            if duration <= 0:
                issues.append(f"镜头{i}时长无效：{duration}秒")
                score -= 0.1
            elif duration > 30:
                warnings.append(f"镜头{i}时长过长：{duration}秒，可能需要分割")
        
        # 检查场景描述
        for i, shot in enumerate(shots, 1):
            scene = shot.get("scene", {})
            description = scene.get("description", "")
            
            if not description or len(description) < 20:
                warnings.append(f"镜头{i}场景描述过于简单")
                score -= 0.05
        
        score = max(0.0, min(1.0, score))
        
        return {
            "score": score,
            "issues": issues,
            "suggestions": suggestions,
            "warnings": warnings
        }
    
    def _check_technical_completeness(self, report: Dict) -> Dict:
        """检查技术规范完整性"""
        issues = []
        suggestions = []
        warnings = []
        score = 1.0
        
        # 检查元数据
        metadata = report.get("metadata", {})
        if not metadata:
            issues.append("缺少元数据")
            score -= 0.3
        else:
            required_fields = ["title", "duration", "shot_count"]
            for field in required_fields:
                if field not in metadata:
                    warnings.append(f"元数据缺少字段：{field}")
                    score -= 0.1
        
        # 检查技术要求
        tech_req = report.get("technical_requirements", {})
        if not tech_req:
            warnings.append("缺少技术要求定义")
            score -= 0.2
        else:
            if "aspect_ratio" not in tech_req:
                warnings.append("未定义画面比例")
            if "resolution" not in tech_req:
                warnings.append("未定义分辨率")
            if "frame_rate" not in tech_req:
                warnings.append("未定义帧率")
        
        # 检查每个镜头的技术参数
        shots = report.get("shots", [])
        for i, shot in enumerate(shots, 1):
            technical = shot.get("technical", {})
            
            if not technical:
                suggestions.append(f"镜头{i}缺少技术参数")
                score -= 0.02
        
        score = max(0.0, min(1.0, score))
        
        return {
            "score": score,
            "issues": issues,
            "suggestions": suggestions,
            "warnings": warnings
        }
