"""
Creative Session - 创意会议系统

实现多Agent之间的真实协作：提案、评审、修订、达成共识。
"""

import json
from typing import Dict, Any, List, Optional
from enum import Enum


class SessionPhase(Enum):
    """会议阶段"""
    PROPOSAL = "proposal"      # 提案阶段
    REVIEW = "review"          # 评审阶段
    REVISION = "revision"      # 修订阶段
    CONSENSUS = "consensus"    # 达成共识


class CreativeSession:
    """创意会议系统"""
    
    def __init__(self, session_name: str, participants: List[str]):
        """
        初始化创意会议
        
        Args:
            session_name: 会议名称
            participants: 参与者角色列表
        """
        self.session_name = session_name
        self.participants = participants
        self.phase = SessionPhase.PROPOSAL
        
        # 会议记录
        self.proposals: Dict[str, Dict[str, Any]] = {}  # {participant: proposal}
        self.reviews: List[Dict[str, Any]] = []          # 评审意见
        self.revisions: Dict[str, Dict[str, Any]] = {}   # {participant: revision}
        self.consensus: Optional[Dict[str, Any]] = None  # 最终共识
        
        # 会议历史
        self.transcript: List[Dict[str, Any]] = []
    
    def add_proposal(self, participant: str, proposal: Dict[str, Any]):
        """
        添加提案
        
        Args:
            participant: 参与者角色
            proposal: 提案内容
        """
        if self.phase != SessionPhase.PROPOSAL:
            print(f"⚠️  当前不在提案阶段，无法添加提案")
            return
        
        self.proposals[participant] = proposal
        
        self.transcript.append({
            "phase": "proposal",
            "participant": participant,
            "content": proposal,
            "timestamp": self._get_timestamp()
        })
        
        print(f"✓ {participant} 提交提案")
    
    def add_review(self, 
                   reviewer: str, 
                   target_participant: str,
                   comments: str,
                   suggestions: List[str],
                   rating: Optional[float] = None):
        """
        添加评审意见
        
        Args:
            reviewer: 评审者
            target_participant: 被评审的参与者
            comments: 评审意见
            suggestions: 修改建议列表
            rating: 评分 (0-1)
        """
        if self.phase != SessionPhase.REVIEW:
            print(f"⚠️  当前不在评审阶段，无法添加评审")
            return
        
        review = {
            "reviewer": reviewer,
            "target": target_participant,
            "comments": comments,
            "suggestions": suggestions,
            "rating": rating
        }
        
        self.reviews.append(review)
        
        self.transcript.append({
            "phase": "review",
            "reviewer": reviewer,
            "target": target_participant,
            "content": review,
            "timestamp": self._get_timestamp()
        })
        
        print(f"✓ {reviewer} → {target_participant}: 评审完成")
    
    def add_revision(self, participant: str, revision: Dict[str, Any]):
        """
        添加修订版本
        
        Args:
            participant: 参与者
            revision: 修订内容
        """
        if self.phase != SessionPhase.REVISION:
            print(f"⚠️  当前不在修订阶段，无法添加修订")
            return
        
        self.revisions[participant] = revision
        
        self.transcript.append({
            "phase": "revision",
            "participant": participant,
            "content": revision,
            "timestamp": self._get_timestamp()
        })
        
        print(f"✓ {participant} 提交修订")
    
    def reach_consensus(self, consensus: Dict[str, Any]):
        """
        达成共识
        
        Args:
            consensus: 最终共识内容
        """
        if self.phase != SessionPhase.CONSENSUS:
            print(f"⚠️  当前不在共识阶段")
            return
        
        self.consensus = consensus
        
        self.transcript.append({
            "phase": "consensus",
            "content": consensus,
            "timestamp": self._get_timestamp()
        })
        
        print(f"✓ 会议达成共识")
    
    def advance_phase(self):
        """推进到下一阶段"""
        phase_order = [
            SessionPhase.PROPOSAL,
            SessionPhase.REVIEW,
            SessionPhase.REVISION,
            SessionPhase.CONSENSUS
        ]
        
        current_idx = phase_order.index(self.phase)
        if current_idx < len(phase_order) - 1:
            self.phase = phase_order[current_idx + 1]
            print(f"→ 会议进入 {self.phase.value} 阶段")
        else:
            print(f"✓ 会议已完成")
    
    def get_proposal_summary(self) -> str:
        """获取提案摘要"""
        if not self.proposals:
            return "无提案"
        
        summary = "# 提案摘要\n\n"
        for participant, proposal in self.proposals.items():
            summary += f"## {participant}\n"
            summary += f"{self._format_dict(proposal)}\n\n"
        
        return summary
    
    def get_review_summary(self) -> str:
        """获取评审摘要"""
        if not self.reviews:
            return "无评审"
        
        summary = "# 评审摘要\n\n"
        for review in self.reviews:
            summary += f"## {review['reviewer']} → {review['target']}\n"
            summary += f"**意见**: {review['comments']}\n"
            if review['suggestions']:
                summary += f"**建议**:\n"
                for suggestion in review['suggestions']:
                    summary += f"- {suggestion}\n"
            if review['rating'] is not None:
                summary += f"**评分**: {review['rating']:.2f}\n"
            summary += "\n"
        
        return summary
    
    def get_revision_summary(self) -> str:
        """获取修订摘要"""
        if not self.revisions:
            return "无修订"
        
        summary = "# 修订摘要\n\n"
        for participant, revision in self.revisions.items():
            summary += f"## {participant}\n"
            summary += f"{self._format_dict(revision)}\n\n"
        
        return summary
    
    def get_consensus_result(self) -> Optional[Dict[str, Any]]:
        """获取共识结果"""
        return self.consensus
    
    def get_full_transcript(self) -> str:
        """获取完整会议记录"""
        transcript = f"# 创意会议记录: {self.session_name}\n\n"
        transcript += f"**参与者**: {', '.join(self.participants)}\n\n"
        
        for entry in self.transcript:
            transcript += f"## [{entry['phase'].upper()}] "
            
            if 'participant' in entry:
                transcript += f"{entry['participant']}\n"
            elif 'reviewer' in entry:
                transcript += f"{entry['reviewer']} → {entry['target']}\n"
            else:
                transcript += "\n"
            
            transcript += f"{self._format_dict(entry['content'])}\n\n"
        
        return transcript
    
    def validate_session_completion(self) -> tuple[bool, List[str]]:
        """
        验证会议是否完整
        
        Returns:
            (是否完整, 缺失项列表)
        """
        issues = []
        
        if not self.proposals:
            issues.append("缺少提案")
        
        if len(self.reviews) < len(self.participants) - 1:
            issues.append("评审不足（建议每人至少评审一次）")
        
        if not self.consensus:
            issues.append("未达成共识")
        
        return (len(issues) == 0, issues)
    
    def merge_proposals(self) -> Dict[str, Any]:
        """
        合并所有提案（用于快速整合）
        
        Returns:
            合并后的提案
        """
        merged = {}
        
        for participant, proposal in self.proposals.items():
            for key, value in proposal.items():
                if key not in merged:
                    merged[key] = value
                elif isinstance(value, list):
                    # 列表类型：合并
                    if isinstance(merged[key], list):
                        merged[key].extend(value)
                    else:
                        merged[key] = [merged[key], value]
                elif isinstance(value, dict):
                    # 字典类型：更新
                    if isinstance(merged[key], dict):
                        merged[key].update(value)
                    else:
                        merged[key] = value
        
        return merged
    
    def get_best_proposal(self, criterion: str = "rating") -> Optional[tuple[str, Dict[str, Any]]]:
        """
        获取最佳提案
        
        Args:
            criterion: 评选标准，"rating" 或 "consensus"
            
        Returns:
            (参与者, 提案) 或 None
        """
        if criterion == "rating" and self.reviews:
            # 基于评分
            scores = {}
            for review in self.reviews:
                target = review['target']
                rating = review.get('rating', 0.5)
                if target not in scores:
                    scores[target] = []
                scores[target].append(rating)
            
            # 计算平均分
            avg_scores = {k: sum(v)/len(v) for k, v in scores.items()}
            best = max(avg_scores.items(), key=lambda x: x[1])
            
            return (best[0], self.proposals.get(best[0]))
        
        return None
    
    def _format_dict(self, data: Any, indent: int = 0) -> str:
        """格式化字典为可读文本"""
        if isinstance(data, dict):
            lines = []
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    lines.append(f"{'  ' * indent}**{key}**:")
                    lines.append(self._format_dict(value, indent + 1))
                else:
                    lines.append(f"{'  ' * indent}**{key}**: {value}")
            return "\n".join(lines)
        elif isinstance(data, list):
            lines = []
            for item in data:
                if isinstance(item, dict):
                    lines.append(self._format_dict(item, indent))
                else:
                    lines.append(f"{'  ' * indent}- {item}")
            return "\n".join(lines)
        else:
            return str(data)
    
    def _get_timestamp(self) -> str:
        """获取时间戳"""
        import time
        return time.strftime("%Y-%m-%d %H:%M:%S")
    
    def save(self, filepath: str):
        """保存会议记录"""
        data = {
            "session_name": self.session_name,
            "participants": self.participants,
            "phase": self.phase.value,
            "proposals": self.proposals,
            "reviews": self.reviews,
            "revisions": self.revisions,
            "consensus": self.consensus,
            "transcript": self.transcript
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Session saved to {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> 'CreativeSession':
        """从文件加载"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        instance = cls(data["session_name"], data["participants"])
        instance.phase = SessionPhase(data["phase"])
        instance.proposals = data["proposals"]
        instance.reviews = data["reviews"]
        instance.revisions = data["revisions"]
        instance.consensus = data["consensus"]
        instance.transcript = data["transcript"]
        
        print(f"✓ Session loaded from {filepath}")
        return instance
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"CreativeSession(name={self.session_name}, " \
               f"phase={self.phase.value}, " \
               f"participants={len(self.participants)})"
