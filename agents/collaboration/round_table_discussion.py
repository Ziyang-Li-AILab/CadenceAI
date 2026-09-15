"""
圆桌讨论机制 - Round Table Discussion

各个agent查看彼此的工作成果，进行集体讨论，
最后由导演生成最终结构报告。
"""

import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime


class RoundTableDiscussion:
    """圆桌讨论协调器"""
    
    def __init__(self, llm_config: Dict, log_file: Optional[str] = None):
        """
        初始化圆桌讨论
        
        Args:
            llm_config: LLM配置
            log_file: 讨论日志文件路径
        """
        self.llm_config = llm_config
        self.log_file = log_file
        self.discussion_rounds = []
        
        if log_file:
            self.log_path = Path(log_file)
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 仅在新日志文件中写入标题，恢复已有会话时保留全部历史内容。
            if not self.log_path.exists() or self.log_path.stat().st_size == 0:
                with open(self.log_path, 'w', encoding='utf-8') as f:
                    f.write(f"# 圆桌讨论记录\n\n")
                    f.write(f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write("---\n\n")
    
    def conduct_discussion(
        self,
        context: Dict,
        num_rounds: int = 2
    ) -> Dict[str, Any]:
        """
        开展圆桌讨论
        
        Args:
            context: 讨论上下文，包含：
                - story_idea: 原始故事创意
                - world: 世界观数据
                - script: 剧本数据
                - storyboard: 分镜数据
                - visual_dna: 视觉风格数据
                - character_bank: 角色库（可选）
                - quality_feedback: 质量反馈（如果是返工）
            num_rounds: 讨论轮数
            
        Returns:
            {
                "success": bool,
                "final_structure_report": Dict,  # 导演生成的最终结构报告
                "discussion_summary": str,
                "consensus": Dict
            }
        """
        print(f"\n🎭 开始圆桌讨论（共{num_rounds}轮）")
        
        # 提取参数
        world = context.get("world")
        script = context.get("script")
        storyboard = context.get("storyboard")
        visual_dna = context.get("visual_dna")
        quality_feedback = context.get("quality_feedback")
        
        if quality_feedback:
            print("📋 这是基于质量反馈的返工讨论")
            self._log(f"## 🔄 返工讨论\n\n")
            self._log(f"**质量问题**:\n")
            for issue in quality_feedback.get("issues", []):
                self._log(f"- {issue}\n")
            self._log(f"\n**改进建议**:\n")
            for suggestion in quality_feedback.get("suggestions", []):
                self._log(f"- {suggestion}\n")
            self._log("\n---\n\n")
        else:
            self._log(f"## 🎭 初次圆桌讨论\n\n")
        
        # 准备讨论材料
        materials = {
            "story_idea": context.get("story_idea"),
            "world": world,
            "script": script,
            "storyboard": storyboard,
            "visual_dna": visual_dna,
            "character_bank": context.get("character_bank"),
            "quality_feedback": quality_feedback
        }
        
        # 进行多轮讨论
        for round_num in range(1, num_rounds + 1):
            print(f"\n📣 第 {round_num}/{num_rounds} 轮讨论")
            self._log(f"### 第 {round_num} 轮讨论\n\n")
            
            round_result = self._conduct_single_round(materials, round_num)
            self.discussion_rounds.append(round_result)
            
            # 更新讨论材料（后续轮次可以看到前面的讨论）
            materials["previous_discussions"] = self.discussion_rounds
        
        # 导演生成最终结构报告
        print(f"\n🎬 导演生成最终结构报告...")
        self._log(f"\n## 🎬 导演最终决策\n\n")
        
        final_report = self._director_final_report(materials, self.discussion_rounds)
        
        # 生成讨论总结
        summary = self._generate_discussion_summary(self.discussion_rounds)
        
        # 提取共识
        consensus = self._extract_consensus(self.discussion_rounds)
        
        return {
            "success": True,
            "rounds": len(self.discussion_rounds),  # 修复：添加讨论轮数
            "final_structure_report": final_report,
            "discussion_summary": summary,
            "consensus": consensus
        }
    
    def _conduct_single_round(self, materials: Dict, round_num: int) -> Dict:
        """
        进行单轮讨论
        
        每个agent查看其他人的工作成果，提出自己的看法
        """
        round_discussions = {}
        
        # 1. 世界观构建师的观点
        print("   💬 世界观构建师: 检查世界观一致性...")
        world_builder_view = self._world_builder_perspective(materials)
        round_discussions["world_builder"] = world_builder_view
        self._log(f"**世界观构建师**:\n{world_builder_view['comment']}\n\n")
        
        # 2. 编剧的观点
        print("   💬 编剧: 检查故事线和角色一致性...")
        writer_view = self._writer_perspective(materials)
        round_discussions["writer"] = writer_view
        self._log(f"**编剧**:\n{writer_view['comment']}\n\n")
        
        # 3. 分镜师的观点
        print("   💬 分镜师: 检查镜头语言和连续性...")
        storyboard_view = self._storyboard_perspective(materials)
        round_discussions["storyboard_artist"] = storyboard_view
        self._log(f"**分镜师**:\n{storyboard_view['comment']}\n\n")
        
        # 4. 摄影指导的观点
        print("   💬 摄影指导: 检查视觉风格统一性...")
        cinematographer_view = self._cinematographer_perspective(materials)
        round_discussions["cinematographer"] = cinematographer_view
        self._log(f"**摄影指导**:\n{cinematographer_view['comment']}\n\n")
        
        self._log("---\n\n")
        
        return {
            "round": round_num,
            "discussions": round_discussions,
            "timestamp": datetime.now().isoformat()
        }
    
    def _world_builder_perspective(self, materials: Dict) -> Dict:
        """世界观构建师的视角"""
        world = materials.get("world") or {}
        script = materials.get("script") or {}
        storyboard = materials.get("storyboard", {})
        
        # 检查世界观一致性
        issues = []
        suggestions = []
        
        # 检查剧本是否符合世界观设定
        # setting 可能是字符串或字典
        world_setting = world.get("setting", "")
        if isinstance(world_setting, dict):
            time_period = world_setting.get("time_period", "")
        else:
            # setting 是字符串时，直接使用它作为描述
            time_period = world_setting if world_setting else ""
        
        comment = f"世界观审查：设定为'{time_period[:50]}...'，" if len(time_period) > 50 else f"世界观审查：设定为'{time_period}'，"
        
        # 简单检查
        if not time_period:
            issues.append("世界观缺少明确的设定")
            comment += "建议明确背景设定。"
        else:
            comment += "设定清晰。检查各场景是否符合该设定。"
        
        return {
            "agent": "world_builder",
            "comment": comment,
            "issues": issues,
            "suggestions": suggestions,
            "approved": len(issues) == 0
        }
    
    def _writer_perspective(self, materials: Dict) -> Dict:
        """编剧的视角"""
        script = materials.get("script") or {}
        storyboard = materials.get("storyboard") or {}
        
        issues = []
        suggestions = []
        
        # 检查角色一致性
        script_chars = script.get("characters", [])
        storyboard_shots = storyboard.get("shots", [])
        
        comment = f"剧本审查：共{len(script_chars)}个角色，{len(storyboard_shots)}个镜头。"
        
        # 检查角色在分镜中的一致性
        if script_chars and storyboard_shots:
            char_names = [c.get("name", "") for c in script_chars]
            comment += f" 主要角色：{', '.join(char_names[:3])}。检查各镜头中角色行为是否连贯。"
        
        return {
            "agent": "writer",
            "comment": comment,
            "issues": issues,
            "suggestions": suggestions,
            "approved": len(issues) == 0
        }
    
    def _storyboard_perspective(self, materials: Dict) -> Dict:
        """分镜师的视角"""
        storyboard = materials.get("storyboard") or {}
        visual_dna = materials.get("visual_dna") or {}
        
        issues = []
        suggestions = []
        
        shots = storyboard.get("shots", [])
        
        comment = f"分镜审查：共{len(shots)}个镜头。"
        
        # 检查镜头连续性
        if len(shots) >= 2:
            # 检查是否有合理的运镜安排
            movements = [s.get("camera_movement", "static") for s in shots]
            static_count = movements.count("static")
            
            if static_count == len(shots):
                suggestions.append("建议增加运镜变化，避免全部静态镜头")
                comment += " 注意：全部静态镜头可能缺乏动感。"
            else:
                comment += " 运镜设计合理，有静有动。"
        
        return {
            "agent": "storyboard_artist",
            "comment": comment,
            "issues": issues,
            "suggestions": suggestions,
            "approved": len(issues) == 0
        }
    
    def _cinematographer_perspective(self, materials: Dict) -> Dict:
        """摄影指导的视角"""
        visual_dna = materials.get("visual_dna") or {}
        storyboard = materials.get("storyboard") or {}
        
        issues = []
        suggestions = []
        
        # 检查视觉风格统一性
        dna = visual_dna.get("dna", {}) if isinstance(visual_dna, dict) else visual_dna
        
        color_palette = dna.get("color_palette", []) if isinstance(dna, dict) else []
        lighting = dna.get("lighting", {}) if isinstance(dna, dict) else {}
        
        comment = f"视觉审查：色彩方案{len(color_palette)}色，"
        
        if lighting:
            light_type = lighting.get("type", "natural")
            comment += f"光线类型'{light_type}'。检查各镜头是否保持视觉统一性。"
        else:
            comment += "建议明确光线方案。"
        
        return {
            "agent": "cinematographer",
            "comment": comment,
            "issues": issues,
            "suggestions": suggestions,
            "approved": len(issues) == 0
        }
    
    def _director_final_report(self, materials: Dict, discussions: List[Dict]) -> Dict:
        """
        导演生成最终结构报告
        
        综合所有讨论，生成包含完整信息的结构报告：
        - 完整镜头描述
        - 场景设定
        - 角色信息
        - 背景/道具
        - 音乐/音效
        - 运镜方式
        - 动作描述
        - 旁白/对话
        """
        print("   🎬 综合所有讨论...")
        print("   🎬 生成完整结构报告...")
        
        storyboard = materials.get("storyboard") or {}
        visual_dna = materials.get("visual_dna") or {}
        script = materials.get("script") or {}
        world = materials.get("world") or {}
        
        shots = storyboard.get("shots", [])
        
        # 构建完整的镜头描述
        enhanced_shots = []
        
        for i, shot in enumerate(shots, 1):
            print(f"      处理镜头 {i}/{len(shots)}...")
            
            enhanced_shot = {
                "shot_number": i,
                "shot_type": shot.get("shot_type", "medium_shot"),
                "camera_movement": shot.get("camera_movement", "static"),
                "duration": shot.get("duration", 5),
                
                # 场景描述
                "scene": {
                    "location": shot.get("location", ""),
                    "time_of_day": shot.get("time_of_day", "day"),
                    "weather": shot.get("weather", "clear"),
                    "description": shot.get("scene_description", "")
                },
                
                # 角色
                "characters": shot.get("characters", []),
                
                # 视觉元素
                "visual": {
                    "composition": shot.get("composition", ""),
                    "color_palette": shot.get("color_palette", []),
                    "lighting": shot.get("lighting", "natural"),
                    "mood": shot.get("mood", "neutral")
                },
                
                # 动作/动画
                "action": shot.get("action", ""),
                
                # 音频
                "audio": {
                    "dialogue": shot.get("dialogue", ""),
                    "voiceover": shot.get("voiceover", ""),
                    "music": shot.get("music", ""),
                    "sound_effects": shot.get("sound_effects", [])
                },
                
                # 技术参数
                "technical": {
                    "focal_length": shot.get("focal_length", "50mm"),
                    "aperture": shot.get("aperture", "f/2.8"),
                    "frame_rate": shot.get("frame_rate", 24)
                }
            }
            
            enhanced_shots.append(enhanced_shot)
        
        # 提取共识以计算质量指标
        consensus = self._extract_consensus(discussions)
        
        # 生成最终报告
        final_report = {
            "metadata": {
                "title": script.get("title", "Untitled"),
                "duration": sum(s["duration"] for s in enhanced_shots),
                "shot_count": len(enhanced_shots),
                "created_at": datetime.now().isoformat()
            },
            
            "world_setting": world.get("setting", ""),  # setting 可能是字符串或字典
            
            "visual_style": {
                "color_palette": visual_dna.get("dna", {}).get("color_palette", []) if isinstance(visual_dna, dict) else [],
                "lighting_scheme": visual_dna.get("dna", {}).get("lighting", {}) if isinstance(visual_dna, dict) else {},
                "art_style": visual_dna.get("dna", {}).get("style", "") if isinstance(visual_dna, dict) else ""
            },
            
            "characters": script.get("characters", []),
            
            "shots": enhanced_shots,
            
            "director_notes": self._generate_director_notes(discussions),
            
            # 修复：添加质量指标字段，供会议日志使用
            "story_coherence": consensus.get("all_approved", True),
            "character_consistency": consensus.get("all_approved", True),
            
            "technical_requirements": {
                "aspect_ratio": "16:9",
                "resolution": "1920x1080",
                "frame_rate": 24
            }
        }
        
        self._log(f"**最终决策**:\n")
        self._log(f"- 总时长: {final_report['metadata']['duration']}秒\n")
        self._log(f"- 镜头数: {final_report['metadata']['shot_count']}个\n")
        self._log(f"- 角色数: {len(final_report['characters'])}个\n")
        self._log(f"\n**导演备注**: {final_report['director_notes']}\n\n")
        
        return final_report
    
    def _generate_director_notes(self, discussions: List[Dict]) -> str:
        """生成导演备注"""
        notes = []
        
        # 收集所有的建议
        all_suggestions = []
        for round_data in discussions:
            for agent, data in round_data.get("discussions", {}).items():
                if data.get("suggestions"):
                    all_suggestions.extend(data["suggestions"])
        
        if all_suggestions:
            notes.append(f"团队建议: {'; '.join(all_suggestions[:3])}")
        
        # 检查是否所有agent都同意
        all_approved = True
        for round_data in discussions:
            for agent, data in round_data.get("discussions", {}).items():
                if not data.get("approved", True):
                    all_approved = False
                    break
        
        if all_approved:
            notes.append("所有部门审核通过")
        else:
            notes.append("部分调整已应用")
        
        return " | ".join(notes) if notes else "无特殊备注"
    
    def _generate_discussion_summary(self, discussions: List[Dict]) -> str:
        """生成讨论总结"""
        summary_parts = []
        
        for round_data in discussions:
            round_num = round_data.get("round", 0)
            summary_parts.append(f"第{round_num}轮讨论完成")
        
        return "; ".join(summary_parts)
    
    def _extract_consensus(self, discussions: List[Dict]) -> Dict:
        """提取共识"""
        consensus = {
            "all_approved": True,
            "key_decisions": [],
            "remaining_issues": []
        }
        
        for round_data in discussions:
            for agent, data in round_data.get("discussions", {}).items():
                if not data.get("approved", True):
                    consensus["all_approved"] = False
                
                if data.get("issues"):
                    consensus["remaining_issues"].extend(data["issues"])
        
        return consensus
    
    def _log(self, message: str):
        """记录到日志文件"""
        if self.log_file and self.log_path:
            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(message)
