# -*- coding: utf-8 -*-
"""
世界观数据库 - 共享上下文
确保角色、场景、道具在所有Agent之间保持一致性
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class Character:
    """角色数据"""
    name: str
    role: str  # protagonist, antagonist, supporting
    age: Optional[int] = None
    visual_features: Dict[str, str] = field(default_factory=dict)
    clothing: List[str] = field(default_factory=list)
    personality: List[str] = field(default_factory=list)
    speech_pattern: str = ""
    appearance_changes: List[Dict] = field(default_factory=list)
    
    def get_consistency_prompt(self) -> str:
        """生成角色一致性提示词片段"""
        features = []
        if self.visual_features:
            for key, value in self.visual_features.items():
                features.append(f"{key}: {value}")
        return f"角色保持一致: {', '.join(features)}"


@dataclass  
class Location:
    """场景数据"""
    name: str
    description: str
    type: str = "场景"  # 新增：场景类型
    visual_elements: List[str] = field(default_factory=list)
    color_palette: List[str] = field(default_factory=list)
    lighting_type: str = ""
    atmosphere: str = ""
    
    def get_setting_prompt(self) -> str:
        """生成场景设置提示词"""
        elements = ", ".join(self.visual_elements)
        colors = ", ".join(self.color_palette)
        return f"场景: {self.name} | 元素: {elements} | 色调: {colors} | 氛围: {self.atmosphere}"


@dataclass
class Prop:
    """道具数据 - 故事中具有视觉识别度、需保持镜头间一致性的关键物品

    与 Character / Location 的字段尽量对齐，便于上层 Agent 在统一模型上做提示词工程。
    """
    name: str
    description: str = ""            # 道具的文字描述
    significance: str = ""           # 故事意义（剧情作用、为何重要）
    visual_key: str = ""             # 视觉识别关键词（用于镜头中检索）
    type: str = "道具"               # 道具类型：武器 / 载具 / 徽记 / 容器 / 法器 等
    visual_elements: List[str] = field(default_factory=list)  # 关键视觉元素（材质、磨损、铭文等）
    color_palette: List[str] = field(default_factory=list)
    owner: str = ""                  # 所属角色 / 阵营；空表示公共
    era: str = ""                    # 时代锚定
    atmosphere: str = ""             # 携带的氛围（沉重、诡异、温暖等）

    def get_setting_prompt(self) -> str:
        """生成道具描述提示词片段（用于镜头参考图匹配/补充）。"""
        elements = ", ".join(self.visual_elements)
        colors = ", ".join(self.color_palette)
        parts = [f"道具[{self.name}] | 识别关键: {self.visual_key}"]
        if elements:
            parts.append(f"元素: {elements}")
        if colors:
            parts.append(f"色调: {colors}")
        if self.atmosphere:
            parts.append(f"氛围: {self.atmosphere}")
        return " | ".join(parts)


class WorldDatabase:
    """世界观数据库 - 所有Agent共享的上下文"""
    
    def __init__(self):
        self.title: str = ""
        self.genre: str = ""
        self.setting: str = ""
        self.themes: List[str] = []
        self.tone: str = ""
        self.target_audience: str = ""
        
        self.characters: Dict[str, Character] = {}
        self.locations: Dict[str, Location] = {}
        self.props: Dict[str, Prop] = {}
        
        self.timeline: List[Dict] = []
        self.relationships: Dict[str, List[str]] = {}
        
        self.visual_style: Dict[str, Any] = {
            "color_palette": [],
            "lighting_style": "",
            "camera_movement": "",
            "lens_style": "",
            "grain": "",
            "aspect_ratio": "9:16"
        }
        
        self.audio_style: Dict[str, Any] = {
            "music_genre": "",
            "sound_effects": [],
            "voice_type": ""
        }
        
        # 新增：分镜相关
        self.shots: List[Dict] = []
        self.pacing: Dict[str, str] = {}
        self.technical_specs: Dict[str, Any] = {}
        self.style_references: List[str] = []
        # 新版世界观 JSON 的完整分层结构，兼容保留于稳定数据模型之外。
        self.structured_data: Dict[str, Any] = {}
        
        self.metadata = {
            "created_at": datetime.now().isoformat(),
            "version": "1.0"
        }
    
    def add_character(self, character: Character) -> None:
        """添加角色"""
        self.characters[character.name] = character
    
    def get_character(self, name: str) -> Optional[Character]:
        """获取角色"""
        return self.characters.get(name)
    
    def add_location(self, location: Location) -> None:
        """添加场景"""
        self.locations[location.name] = location
    
    def get_location(self, name: str) -> Optional[Location]:
        """获取场景"""
        return self.locations.get(name)
    
    def add_prop(self, prop: Prop) -> None:
        """添加道具"""
        self.props[prop.name] = prop

    def get_prop(self, name: str) -> Optional["Prop"]:
        """获取道具（与 get_character / get_location 同形 API）"""
        return self.props.get(name)
    
    def set_visual_style(self, **kwargs) -> None:
        """设置视觉风格"""
        self.visual_style.update(kwargs)
    
    def get_visual_context_for_shot(self, shot_number: int,
                                     location_name: str = None,
                                     character_names: List[str] = None,
                                     prop_names: List[str] = None) -> str:
        """为某个镜头生成视觉上下文"""
        context_parts = []

        if self.visual_style.get("color_palette"):
            colors = ", ".join(self.visual_style["color_palette"])
            context_parts.append(f"整体色调: {colors}")

        if self.visual_style.get("lighting_style"):
            context_parts.append(f"灯光风格: {self.visual_style['lighting_style']}")

        if location_name:
            loc = self.get_location(location_name)
            if loc:
                context_parts.append(loc.get_setting_prompt())

        if character_names:
            for name in character_names:
                char = self.get_character(name)
                if char:
                    context_parts.append(f"角色[{name}]: {char.get_consistency_prompt()}")

        if prop_names:
            for name in prop_names:
                prop = self.get_prop(name)
                if prop:
                    context_parts.append(prop.get_setting_prompt())

        return " | ".join(context_parts)
    
    def to_dict(self) -> Dict:
        """导出为字典"""
        return {
            "title": self.title,
            "genre": self.genre,
            "setting": self.setting,
            "themes": self.themes,
            "tone": self.tone,
            "target_audience": self.target_audience,
            "characters": {k: asdict(v) for k, v in self.characters.items()},
            "locations": {k: asdict(v) for k, v in self.locations.items()},
            "props": {k: asdict(v) for k, v in self.props.items()},
            "timeline": self.timeline,
            "relationships": self.relationships,
            "visual_style": self.visual_style,
            "audio_style": self.audio_style,
            "shots": self.shots,
            "pacing": self.pacing,
            "technical_specs": self.technical_specs,
            "style_references": self.style_references,
            "structured_data": self.structured_data,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'WorldDatabase':
        """从字典加载"""
        db = cls()
        db.title = data.get("title", "")
        db.genre = data.get("genre", "")
        db.setting = data.get("setting", "")
        db.themes = data.get("themes", [])
        db.tone = data.get("tone", "")
        db.target_audience = data.get("target_audience", "")
        
        for name, char_data in data.get("characters", {}).items():
            db.characters[name] = Character(**char_data)
        
        for name, loc_data in data.get("locations", {}).items():
            db.locations[name] = Location(**loc_data)
        
        for name, prop_data in data.get("props", {}).items():
            # 兼容旧版本只有 4 字段的 Prop 记录
            db.props[name] = Prop(**{
                "name": name,
                "description": prop_data.get("description", ""),
                "significance": prop_data.get("significance", ""),
                "visual_key": prop_data.get("visual_key", ""),
                "type": prop_data.get("type", "道具"),
                "visual_elements": prop_data.get("visual_elements", []) or [],
                "color_palette": prop_data.get("color_palette", []) or [],
                "owner": prop_data.get("owner", ""),
                "era": prop_data.get("era", ""),
                "atmosphere": prop_data.get("atmosphere", ""),
            })
        
        db.timeline = data.get("timeline", [])
        db.relationships = data.get("relationships", {})
        db.visual_style = data.get("visual_style", {})
        db.audio_style = data.get("audio_style", {})
        db.shots = data.get("shots", [])
        db.pacing = data.get("pacing", {})
        db.technical_specs = data.get("technical_specs", {})
        db.style_references = data.get("style_references", [])
        db.structured_data = data.get("structured_data", {})
        db.metadata = data.get("metadata", {})
        
        return db
    
    def save(self, path: Path) -> None:
        """保存到文件"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load(cls, path: Path) -> 'WorldDatabase':
        """从文件加载"""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)
