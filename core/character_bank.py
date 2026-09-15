# -*- coding: utf-8 -*-
"""
Character Bank - 角色银行系统

维护所有角色的统一描述，确保角色在不同镜头中的视觉一致性
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class AgentRole(Enum):
    """Agent角色枚举"""
    WORLD_BUILDER = "世界观构建师"
    WRITER = "编剧"
    STORYBOARD_ARTIST = "分镜师"
    CINEMATOGRAPHER = "摄影指导"
    DIRECTOR = "导演"
    VIDEO_GENERATOR = "视频生成器"
    POST_PRODUCTION = "后期制作"


@dataclass
class Character:
    """角色数据"""
    name: str
    role: str
    age_range: str
    gender: str
    distinctive_features: List[str] = field(default_factory=list)
    clothing: Dict = field(default_factory=dict)
    personality_traits: List[str] = field(default_factory=list)
    backstory: str = ""
    
    # 统计信息
    appearances: List[int] = field(default_factory=list)  # 出现在哪些镜头中
    total_screen_time: float = 0.0


class CharacterBank:
    """
    角色银行 - 管理所有角色的统一描述
    
    功能：
    1. 存储角色的标准化描述
    2. 生成一致的角色提示词
    3. 跟踪角色出现情况
    4. 确保视觉一致性
    """
    
    def __init__(self):
        self.characters: Dict[str, Character] = {}
        self._prompt_cache: Dict[str, str] = {}
    
    def add_character(self, name: str, role: str, age_range: str = "",
                     gender: str = "", distinctive_features: List[str] = None,
                     clothing: Dict = None, personality_traits: List[str] = None,
                     backstory: str = ""):
        """添加角色"""
        
        character = Character(
            name=name,
            role=role,
            age_range=age_range,
            gender=gender,
            distinctive_features=distinctive_features or [],
            clothing=clothing or {},
            personality_traits=personality_traits or [],
            backstory=backstory
        )
        
        self.characters[name] = character
        
        # 清除缓存
        if name in self._prompt_cache:
            del self._prompt_cache[name]
    
    def get_character(self, name: str) -> Optional[Character]:
        """获取角色"""
        return self.characters.get(name)
    
    def get_character_prompt_description(self, name: str) -> str:
        """
        获取角色的提示词描述
        
        这是最重要的功能 - 为每个镜头生成统一的角色描述
        """
        
        # 检查缓存
        if name in self._prompt_cache:
            return self._prompt_cache[name]
        
        character = self.characters.get(name)
        if not character:
            return name
        
        # 构建简洁的角色描述
        parts = []
        
        # 1. 基本信息（名字+性别+年龄）
        basic = name
        if character.gender:
            basic += f"（{character.gender}"
            if character.age_range:
                basic += f"，{character.age_range}"
            basic += "）"
        elif character.age_range:
            basic += f"（{character.age_range}）"
        
        parts.append(basic)
        
        # 2. 显著特征（最多2个）
        if character.distinctive_features:
            features = character.distinctive_features[:2]
            parts.append("、".join(features))
        
        # 3. 服装（简要）
        if character.clothing:
            clothing_type = character.clothing.get("type", "")
            if clothing_type:
                parts.append(clothing_type)
        
        # 组合成最终描述（控制长度）
        description = "，".join(parts)
        
        # 缓存
        self._prompt_cache[name] = description
        
        return description
    
    def mark_appearance(self, name: str, shot_number: int, duration: float = 0.0):
        """标记角色出现"""
        character = self.characters.get(name)
        if character:
            if shot_number not in character.appearances:
                character.appearances.append(shot_number)
            character.total_screen_time += duration
    
    def get_appearance_stats(self, name: str) -> Dict:
        """获取角色出现统计"""
        character = self.characters.get(name)
        if not character:
            return {}
        
        return {
            "name": name,
            "appearances": len(character.appearances),
            "shots": character.appearances,
            "total_screen_time": character.total_screen_time
        }
    
    def get_all_stats(self) -> List[Dict]:
        """获取所有角色统计"""
        stats = []
        for name in self.characters:
            stats.append(self.get_appearance_stats(name))
        
        # 按出现次数排序
        stats.sort(key=lambda x: x.get("appearances", 0), reverse=True)
        
        return stats
    
    def validate_consistency(self) -> Dict:
        """验证角色一致性"""
        issues = []
        warnings = []
        
        for name, character in self.characters.items():
            # 检查必要信息
            if not character.gender:
                warnings.append(f"{name}: 未指定性别")
            
            if not character.age_range:
                warnings.append(f"{name}: 未指定年龄段")
            
            if not character.distinctive_features:
                warnings.append(f"{name}: 没有显著特征，可能影响识别度")
            
            # 检查描述长度
            prompt_desc = self.get_character_prompt_description(name)
            if len(prompt_desc) > 50:
                warnings.append(f"{name}: 描述过长({len(prompt_desc)}字)，建议简化")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings
        }
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            name: {
                "name": char.name,
                "role": char.role,
                "age_range": char.age_range,
                "gender": char.gender,
                "distinctive_features": char.distinctive_features,
                "clothing": char.clothing,
                "personality_traits": char.personality_traits,
                "backstory": char.backstory,
                "appearances": char.appearances,
                "total_screen_time": char.total_screen_time,
                "prompt_description": self.get_character_prompt_description(name)
            }
            for name, char in self.characters.items()
        }
    
    def from_dict(self, data: Dict):
        """从字典加载"""
        self.characters.clear()
        self._prompt_cache.clear()
        
        for name, char_data in data.items():
            character = Character(
                name=char_data.get("name", name),
                role=char_data.get("role", ""),
                age_range=char_data.get("age_range", ""),
                gender=char_data.get("gender", ""),
                distinctive_features=char_data.get("distinctive_features", []),
                clothing=char_data.get("clothing", {}),
                personality_traits=char_data.get("personality_traits", []),
                backstory=char_data.get("backstory", "")
            )
            character.appearances = char_data.get("appearances", [])
            character.total_screen_time = char_data.get("total_screen_time", 0.0)
            
            self.characters[name] = character
    
    def __len__(self):
        """返回角色数量"""
        return len(self.characters)
    
    def __contains__(self, name: str):
        """检查角色是否存在"""
        return name in self.characters
    
    def __iter__(self):
        """迭代角色"""
        return iter(self.characters.items())
