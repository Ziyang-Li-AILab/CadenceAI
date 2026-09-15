# -*- coding: utf-8 -*-
"""
Visual DNA - 视觉基因系统

为整个项目定义统一的视觉风格，确保所有镜头的视觉一致性
类似于电影的"视觉设计圣经"
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class VisualDNA:
    """
    视觉DNA - 定义项目的整体视觉风格
    
    包含：
    - 整体风格定义
    - 色彩方案
    - 光线风格
    - 摄影机风格
    - 氛围设定
    - 视觉主题元素
    """
    
    def __init__(self):
        self.dna = {
            "overall_style": {
                "style": "",
                "references": [],
                "keywords": []
            },
            "color_palette": {
                "primary": [],
                "secondary": [],
                "accent": [],
                "mood": ""
            },
            "lighting": {
                "type": "",
                "direction": "",
                "quality": "",
                "mood": "",
                "color_temperature": ""
            },
            "camera_style": {
                "preferred_angles": [],
                "movement_style": "",
                "focal_range": "",
                "depth_of_field": ""
            },
            "atmosphere": {
                "weather": "",
                "time_of_day": "",
                "effects": [],
                "mood": ""
            },
            "visual_motifs": []
        }
    
    def set_overall_style(self, style: str, references: List[str] = None,
                         keywords: List[str] = None):
        """设置整体风格"""
        self.dna["overall_style"]["style"] = style
        if references:
            self.dna["overall_style"]["references"] = references
        if keywords:
            self.dna["overall_style"]["keywords"] = keywords
    
    def set_color_palette(self, primary: List[str], secondary: List[str] = None,
                         accent: List[str] = None, mood: str = ""):
        """设置色彩方案"""
        self.dna["color_palette"]["primary"] = primary
        if secondary:
            self.dna["color_palette"]["secondary"] = secondary
        if accent:
            self.dna["color_palette"]["accent"] = accent
        if mood:
            self.dna["color_palette"]["mood"] = mood
    
    def set_lighting(self, lighting_type: str, direction: str = "",
                    quality: str = "", mood: str = "", color_temp: str = ""):
        """设置光线风格"""
        self.dna["lighting"]["type"] = lighting_type
        self.dna["lighting"]["direction"] = direction
        self.dna["lighting"]["quality"] = quality
        self.dna["lighting"]["mood"] = mood
        self.dna["lighting"]["color_temperature"] = color_temp
    
    def set_camera_style(self, angles: List[str] = None, movement: str = "",
                        focal_range: str = "", dof: str = ""):
        """设置摄影机风格"""
        if angles:
            self.dna["camera_style"]["preferred_angles"] = angles
        if movement:
            self.dna["camera_style"]["movement_style"] = movement
        if focal_range:
            self.dna["camera_style"]["focal_range"] = focal_range
        if dof:
            self.dna["camera_style"]["depth_of_field"] = dof
    
    def set_atmosphere(self, weather: str = "", time_of_day: str = "",
                      effects: List[str] = None, mood: str = ""):
        """设置氛围"""
        if weather:
            self.dna["atmosphere"]["weather"] = weather
        if time_of_day:
            self.dna["atmosphere"]["time_of_day"] = time_of_day
        if effects:
            self.dna["atmosphere"]["effects"] = effects
        if mood:
            self.dna["atmosphere"]["mood"] = mood
    
    def add_visual_motif(self, name: str, description: str):
        """添加视觉主题元素"""
        self.dna["visual_motifs"].append({
            "name": name,
            "description": description
        })
    
    def get_prompt_guidelines(self) -> str:
        """
        生成提示词指南
        
        返回可以直接用于提示词的视觉风格描述
        """
        parts = []
        
        # 整体风格
        style = self.dna["overall_style"]["style"]
        if style:
            parts.append(f"整体风格：{style}")
        
        # 色彩
        colors = self.dna["color_palette"]["primary"]
        if colors:
            parts.append(f"主色调：{', '.join(colors[:3])}")
        
        # 光线
        lighting = self.dna["lighting"]
        if lighting["type"]:
            light_desc = f"{lighting['type']}"
            if lighting["quality"]:
                light_desc += f"，{lighting['quality']}"
            parts.append(f"光线：{light_desc}")
        
        # 氛围
        atmosphere = self.dna["atmosphere"]
        if atmosphere["mood"]:
            parts.append(f"氛围：{atmosphere['mood']}")
        
        return "；".join(parts)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return self.dna.copy()
    
    def from_dict(self, data: Dict):
        """从字典加载"""
        self.dna = data.copy()
    
    def validate(self) -> Dict:
        """验证Visual DNA的完整性"""
        issues = []
        warnings = []
        
        # 检查必要字段
        if not self.dna["overall_style"]["style"]:
            warnings.append("未设置整体风格")
        
        if not self.dna["color_palette"]["primary"]:
            warnings.append("未设置主色调")
        
        if not self.dna["lighting"]["type"]:
            warnings.append("未设置光线类型")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings
        }
