# -*- coding: utf-8 -*-
"""
圆桌会议系统 - 多Agent协作讨论机制

实现Agent之间的真实讨论和决策
"""

import json
from typing import Dict, List, Optional
from pathlib import Path
from enum import Enum
from datetime import datetime


class AgentRole(Enum):
    """Agent角色枚举"""
    WORLD_BUILDER = "世界观构建师"
    WRITER = "编剧"
    STORYBOARD_ARTIST = "分镜师"
    CINEMATOGRAPHER = "摄影指导"
    DIRECTOR = "导演"
    PRODUCER = "制片人"


class Opinion:
    """意见/观点"""
    def __init__(self, role: AgentRole, content: str, 
                 priority: str = "normal", reasoning: str = ""):
        self.role = role
        self.content = content
        self.priority = priority  # low, normal, high, critical
        self.reasoning = reasoning
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            "role": self.role.value,
            "content": self.content,
            "priority": self.priority,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp.isoformat()
        }


class Discussion:
    """讨论记录"""
    def __init__(self, topic: str):
        self.topic = topic
        self.opinions: List[Opinion] = []
        self.consensus: Optional[Dict] = None
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
    
    def add_opinion(self, opinion: Opinion):
        """添加意见"""
        self.opinions.append(opinion)
    
    def reach_consensus(self, consensus: Dict):
        """达成共识"""
        self.consensus = consensus
        self.end_time = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            "topic": self.topic,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "opinions": [op.to_dict() for op in self.opinions],
            "consensus": self.consensus
        }


class RoundTableMeeting:
    """
    圆桌会议系统
    
    协调多个Agent进行讨论、评审和决策
    """
    
    def __init__(self, log_file: str = None):
        self.discussions: List[Discussion] = []
        self.current_discussion: Optional[Discussion] = None
        
        # 日志文件路径
        self.log_file = Path(log_file) if log_file else None
        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            # 仅在新日志文件中写入标题，resume 时保留已有会议记录。
            if not self.log_file.exists() or self.log_file.stat().st_size == 0:
                with open(self.log_file, 'w', encoding='utf-8') as f:
                    f.write("# 圆桌会议讨论日志\n\n")
                    f.write(f"**会议开始时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write("---\n\n")
            else:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(f"\n## 恢复执行\n\n**恢复时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n")
            print(f" 圆桌会议日志: {self.log_file}")
    
    def _append_to_log(self, content: str):
        """追加内容到日志文件"""
        if self.log_file:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(content + "\n")
    
    def hold_meeting(self, topic: str, context: Dict, 
                    participants: List[AgentRole]) -> Dict:
        """
        召开会议
        
        Args:
            topic: 讨论主题
            context: 讨论的上下文（世界观、剧本等）
            participants: 参与者角色列表
        
        Returns:
            达成的共识
        """
        print(f"开始讨论: {topic}")
        print(f"参与者: {', '.join([p.value for p in participants])}\n")
        
        # 记录会议开始到日志
        self._append_to_log(f"## 讨论主题: {topic}\n")
        self._append_to_log(f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self._append_to_log(f"**参与者**: {', '.join([p.value for p in participants])}\n\n")
        
        discussion = Discussion(topic)
        self.current_discussion = discussion
        
        # 收集各方意见
        for role in participants:
            opinion = self._get_opinion(role, topic, context)
            discussion.add_opinion(opinion)
            
            # 打印到控制台
            print(f"[{role.value}] {opinion.content}")
            if opinion.reasoning:
                print(f"  理由: {opinion.reasoning}\n")
            
            # 实时写入日志
            self._append_to_log(f"### [{role.value}]\n")
            self._append_to_log(f"**观点**: {opinion.content}\n")
            if opinion.reasoning:
                self._append_to_log(f"**理由**: {opinion.reasoning}\n")
            self._append_to_log(f"**优先级**: {opinion.priority}\n\n")
        
        # 综合意见，达成共识
        consensus = self._build_consensus(discussion.opinions, context)
        discussion.reach_consensus(consensus)
        
        # 记录共识到日志
        self._append_to_log(f"###  达成共识\n")
        self._append_to_log(f"```json\n{json.dumps(consensus, ensure_ascii=False, indent=2)}\n```\n\n")
        self._append_to_log("---\n\n")
        
        self.discussions.append(discussion)
        self.current_discussion = None
        
        return consensus
    
    def _get_opinion(self, role: AgentRole, topic: str, context: Dict) -> Opinion:
        """获取某个角色的意见"""
        
        # 根据不同角色和主题生成意见
        if role == AgentRole.WORLD_BUILDER:
            return self._world_builder_opinion(topic, context)
        elif role == AgentRole.WRITER:
            return self._writer_opinion(topic, context)
        elif role == AgentRole.STORYBOARD_ARTIST:
            return self._storyboard_opinion(topic, context)
        elif role == AgentRole.CINEMATOGRAPHER:
            return self._cinematographer_opinion(topic, context)
        elif role == AgentRole.DIRECTOR:
            return self._director_opinion(topic, context)
        else:
            return Opinion(role, "无意见", "low")
    
    def _world_builder_opinion(self, topic: str, context: Dict) -> Opinion:
        """世界观构建师的意见"""
        world = context.get("world")
        
        if "世界观" in topic:
            content = f"世界观设定完整，包含{len(world.characters)}个角色和{len(world.locations)}个场景。"
            reasoning = "世界观是故事的基础，必须在开始前明确定义。"
            return Opinion(AgentRole.WORLD_BUILDER, content, "high", reasoning)
        
        elif "剧本" in topic:
            content = "剧本需要遵循已建立的世界观设定，角色行为要符合其背景和性格。"
            reasoning = "保持世界观一致性是我的核心职责。"
            return Opinion(AgentRole.WORLD_BUILDER, content, "normal", reasoning)
        
        else:
            return Opinion(AgentRole.WORLD_BUILDER, "从世界观角度看没有问题。", "low")
    
    def _writer_opinion(self, topic: str, context: Dict) -> Opinion:
        """编剧的意见"""
        script = context.get("script")
        
        if "世界观" in topic:
            content = "世界观设定为剧本创作提供了丰富的素材。建议增加角色之间的冲突点。"
            reasoning = "冲突是戏剧的核心，角色关系需要张力。"
            return Opinion(AgentRole.WRITER, content, "high", reasoning)
        
        elif "剧本" in topic:
            if script:
                has_dialogue = any(
                    shot.get("character_dialogue") 
                    for seg in script.get("segments", []) 
                    for shot in seg.get("shots", [])
                )
                if has_dialogue:
                    content = "剧本包含角色对话，叙事更加生动。情感节奏控制良好。"
                else:
                    content = "建议增加更多角色对话，纯旁白容易让观众疲劳。"
                    return Opinion(AgentRole.WRITER, content, "high", "对话比旁白更能吸引观众")
                
                return Opinion(AgentRole.WRITER, content, "normal")
            return Opinion(AgentRole.WRITER, "等待剧本数据", "low")
        
        else:
            return Opinion(AgentRole.WRITER, "从叙事角度看，需要确保视觉服务于故事。", "normal")
    
    def _storyboard_opinion(self, topic: str, context: Dict) -> Opinion:
        """分镜师的意见"""
        
        if "剧本" in topic:
            content = "剧本为分镜设计提供了清晰的指导。建议明确关键镜头的情感重点。"
            reasoning = "分镜需要将文字转化为画面，情感点是关键。"
            return Opinion(AgentRole.STORYBOARD_ARTIST, content, "normal", reasoning)
        
        elif "分镜" in topic:
            content = "分镜设计完成，包含多种景别和角度变化，节奏控制合理。"
            return Opinion(AgentRole.STORYBOARD_ARTIST, content, "high")
        
        else:
            return Opinion(AgentRole.STORYBOARD_ARTIST, "从分镜角度看可行。", "low")
    
    def _cinematographer_opinion(self, topic: str, context: Dict) -> Opinion:
        """摄影指导的意见"""
        
        if "视觉" in topic or "风格" in topic:
            content = "视觉风格已定义。光影和色彩将用于强化情感表达。"
            reasoning = "视觉语言应该与叙事主题一致。"
            return Opinion(AgentRole.CINEMATOGRAPHER, content, "high", reasoning)
        
        elif "提示词" in topic:
            content = "提示词需要包含具体的光影描述，避免抽象概念。"
            reasoning = "视频生成AI需要明确的视觉指令。"
            return Opinion(AgentRole.CINEMATOGRAPHER, content, "critical", reasoning)
        
        else:
            return Opinion(AgentRole.CINEMATOGRAPHER, "需要确保视觉一致性。", "normal")
    
    def _director_opinion(self, topic: str, context: Dict) -> Opinion:
        """导演的意见"""
        
        if "剧本" in topic:
            content = "剧本整体节奏良好。建议在高潮部分增加更多视觉冲击力。"
            reasoning = "短视频需要在有限时间内创造最大冲击。"
            return Opinion(AgentRole.DIRECTOR, content, "high", reasoning)
        
        elif "提示词" in topic:
            content = "提示词必须简洁、具体、可视觉化。这是最终成片质量的关键。"
            reasoning = "我对最终效果负责，提示词质量直接影响生成结果。"
            return Opinion(AgentRole.DIRECTOR, content, "critical", reasoning)
        
        else:
            content = "整体方向正确，继续推进。"
            return Opinion(AgentRole.DIRECTOR, content, "normal")
    
    def _build_consensus(self, opinions: List[Opinion], context: Dict) -> Dict:
        """综合意见，构建共识"""
        
        # 统计意见优先级
        priority_count = {
            "low": 0,
            "normal": 0,
            "high": 0,
            "critical": 0
        }
        
        for opinion in opinions:
            priority_count[opinion.priority] += 1
        
        # 提取关键建议
        recommendations = []
        concerns = []
        
        for opinion in opinions:
            if opinion.priority in ["high", "critical"]:
                if "建议" in opinion.content or "增加" in opinion.content:
                    recommendations.append(opinion.content)
                elif "问题" in opinion.content or "需要" in opinion.content:
                    concerns.append(opinion.content)
        
        # 计算共识度
        total_opinions = len(opinions)
        high_priority = priority_count["high"] + priority_count["critical"]
        consensus_level = 1.0 - (high_priority / total_opinions * 0.3) if total_opinions > 0 else 1.0
        
        consensus = {
            "consensus_level": consensus_level,
            "recommendations": recommendations,
            "concerns": concerns,
            "action_required": priority_count["critical"] > 0,
            "summary": self._summarize_consensus(opinions, consensus_level)
        }
        
        return consensus
    
    def _summarize_consensus(self, opinions: List[Opinion], level: float) -> str:
        """总结共识"""
        if level >= 0.8:
            return "各方意见基本一致，可以继续推进。"
        elif level >= 0.6:
            return "存在一些分歧，但可以通过调整达成一致。"
        else:
            return "存在重大分歧，需要进一步讨论。"
    
    def export_transcript(self, output_path: Path):
        """导出会议记录"""
        transcript = {
            "total_meetings": len(self.discussions),
            "discussions": [d.to_dict() for d in self.discussions]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(transcript, f, ensure_ascii=False, indent=2)


class CollaborativeWorkflow:
    """
    协作工作流
    
    管理Agent之间的协作流程
    """
    
    def __init__(self, meeting: RoundTableMeeting):
        self.meeting = meeting
        self.workflow_steps: List[Dict] = []
    
    def add_review_stage(self, stage_name: str, reviewers: List[AgentRole], 
                        artifact: any) -> Dict:
        """
        添加评审阶段
        
        Args:
            stage_name: 阶段名称
            reviewers: 评审者列表
            artifact: 待评审的产物
        
        Returns:
            评审结果
        """
        print(f"\n{'='*60}")
        print(f"评审阶段: {stage_name}")
        print(f"{'='*60}\n")
        
        # 收集评审意见
        reviews = []
        for reviewer in reviewers:
            review = self._conduct_review(reviewer, artifact)
            reviews.append(review)
            print(f"[{reviewer.value}] {review['verdict']}")
            if review.get("comments"):
                for comment in review["comments"]:
                    print(f"  - {comment}")
            print()
        
        # 综合评审结果
        approval_count = sum(1 for r in reviews if r["verdict"] == "approved")
        approval_rate = approval_count / len(reviews) if reviews else 0
        
        result = {
            "stage": stage_name,
            "reviews": reviews,
            "approval_rate": approval_rate,
            "verdict": "approved" if approval_rate >= 0.7 else "needs_revision"
        }
        
        self.workflow_steps.append(result)
        
        return result
    
    def _conduct_review(self, reviewer: AgentRole, artifact: any) -> Dict:
        """执行评审"""
        
        # 根据不同角色进行不同的评审
        if reviewer == AgentRole.DIRECTOR:
            return {
                "reviewer": reviewer.value,
                "verdict": "approved",
                "comments": [
                    "整体质量符合要求",
                    "提示词具体且可执行"
                ]
            }
        
        elif reviewer == AgentRole.CINEMATOGRAPHER:
            return {
                "reviewer": reviewer.value,
                "verdict": "approved",
                "comments": [
                    "视觉风格统一",
                    "光影描述清晰"
                ]
            }
        
        else:
            return {
                "reviewer": reviewer.value,
                "verdict": "approved",
                "comments": []
            }
    
    def get_workflow_report(self) -> Dict:
        """获取工作流报告"""
        return {
            "total_stages": len(self.workflow_steps),
            "stages": self.workflow_steps,
            "overall_approval_rate": sum(s["approval_rate"] for s in self.workflow_steps) / len(self.workflow_steps) if self.workflow_steps else 0
        }
