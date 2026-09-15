# -*- coding: utf-8 -*-
"""
Cinematographer - 摄影指导

负责定义整体视觉风格和角色视觉一致性
"""

import json
from typing import Dict, List, Optional
from pathlib import Path

from core.base_agent import BaseAgent, AgentResponse
from core.visual_dna import VisualDNA
from core.character_bank import CharacterBank
from core.world_database import WorldDatabase


class Cinematographer(BaseAgent):
    """
    摄影指导 - 定义视觉风格
    
    核心职责：
    1. 创建Visual DNA（统一视觉风格）
    2. 构建Character Bank（角色一致性）
    3. 为分镜增加视觉细节
    4. 确保整体视觉连贯性
    
    输入：世界观 + 分镜
    输出：Visual DNA + Character Bank + 增强分镜
    """
    
    def __init__(self, llm_config: Dict):
        config = {"llm": llm_config}
        super().__init__(config)
        self.name = "摄影指导"
    
    def execute(self, context: Dict) -> AgentResponse:
        """执行视觉风格定义"""
        
        world = context.get("world")
        storyboard = context.get("storyboard")
        
        if not world:
            return AgentResponse(
                success=False,
                data=None,
                error="缺少世界观数据"
            )
        
        if not storyboard:
            return AgentResponse(
                success=False,
                data=None,
                error="缺少分镜数据"
            )
        
        # 创建Visual DNA
        visual_dna = self._create_visual_dna(world)
        
        # 构建Character Bank
        character_bank = self._build_character_bank(world)
        
        # 增强分镜（添加视觉细节）
        enhanced_storyboard = self._enhance_storyboard(
            storyboard, visual_dna, character_bank
        )
        
        # 验证
        validation = self._validate_visual_consistency(
            visual_dna, character_bank, enhanced_storyboard
        )
        
        result_data = {
            "visual_dna": visual_dna,
            "character_bank": character_bank,
            "enhanced_storyboard": enhanced_storyboard
        }
        
        return AgentResponse(
            success=True,
            data=result_data,
            warnings=validation.get("warnings", []),
            suggestions=validation.get("suggestions", [])
        )
    
    def _create_visual_dna(self, world: WorldDatabase) -> VisualDNA:
        """创建Visual DNA"""
        
        dna = VisualDNA()
        
        # 根据类型确定风格（支持列表和字符串）
        if isinstance(world.genre, list):
            genre = " ".join(world.genre).lower() if world.genre else ""
        else:
            genre = world.genre.lower() if world.genre else ""
            
        tone = world.tone.lower() if world.tone else ""
        
        # 整体风格
        if "战争" in genre:
            style = "写实战争片，强调真实质感和历史感"
            references = ["拯救大兵瑞恩", "1917", "敦刻尔克"]
            keywords = ["写实", "粗粝", "历史", "纪实"]
        elif "科幻" in genre:
            style = "未来科幻，强调科技感和视觉冲击"
            references = ["银翼杀手2049", "星际穿越"]
            keywords = ["科技", "未来", "冷峻", "磅礴"]
        elif "悬疑" in genre or "惊悚" in genre:
            style = "悬疑惊悚，强调氛围和紧张感"
            references = ["七宗罪", "沉默的羔羊"]
            keywords = ["阴暗", "神秘", "压抑", "紧张"]
        else:
            style = "现实主义，注重情感表达"
            references = ["三块广告牌", "海边的曼彻斯特"]
            keywords = ["自然", "真实", "情感", "人文"]
        
        dna.set_overall_style(style, references, keywords)
        
        # 色彩方案
        if "战争" in genre:
            primary = ["灰褐色", "暗绿色", "土黄色"]
            secondary = ["钢铁灰", "烟雾白"]
            accent = ["血红色", "火光橙"]
            mood = "压抑、严峻"
        elif "科幻" in genre:
            primary = ["深蓝色", "银灰色", "黑色"]
            secondary = ["钴蓝", "冷白"]
            accent = ["霓虹蓝", "电光紫"]
            mood = "冷峻、未来感"
        elif "悬疑" in genre:
            primary = ["暗灰色", "深蓝色", "黑色"]
            secondary = ["阴影灰"]
            accent = ["暗红色"]
            mood = "神秘、不安"
        else:
            primary = ["自然色调", "暖灰色"]
            secondary = ["米白色", "浅褐色"]
            accent = ["暖橙色", "天空蓝"]
            mood = "温暖、真实"
        
        dna.set_color_palette(primary, secondary, accent, mood)
        
        # 光线风格
        if "阴郁" in tone or "黑暗" in tone or "悲壮" in tone:
            lighting_type = "低调照明，硬光为主"
            direction = "侧光、逆光"
            quality = "硬光、强对比"
            light_mood = "戏剧性、紧张"
            color_temp = "冷色调"
        elif "明快" in tone or "欢乐" in tone:
            lighting_type = "高调照明，柔光为主"
            direction = "顺光、侧光"
            quality = "柔光、低对比"
            light_mood = "轻松、愉快"
            color_temp = "暖色调"
        else:
            lighting_type = "自然光为主"
            direction = "侧光"
            quality = "中等硬度"
            light_mood = "真实、自然"
            color_temp = "中性偏暖"
        
        dna.set_lighting(lighting_type, direction, quality, light_mood, color_temp)
        
        # 摄影机风格
        if "战争" in genre:
            angles = ["平视为主", "适度低角度增强英雄感"]
            movement = "手持摄影营造真实感"
            focal_range = "中长焦为主"
            dof = "中等景深"
        elif "悬疑" in genre:
            angles = ["多角度", "荷兰角增加不安感"]
            movement = "稳定器慢推营造紧张感"
            focal_range = "广角与长焦对比"
            dof = "浅景深突出主体"
        else:
            angles = ["平视为主"]
            movement = "稳定、少运动"
            focal_range = "标准焦段"
            dof = "中等景深"
        
        dna.set_camera_style(angles, movement, focal_range, dof)
        
        # 氛围 - 从世界观的setting字符串中推断
        weather = ""
        time_of_day = ""
        
        # 简单的关键词匹配
        setting_text = world.setting.lower() if world.setting else ""
        if "雨" in setting_text or "阴" in setting_text:
            weather = "阴雨"
        elif "雪" in setting_text:
            weather = "下雪"
        elif "晴" in setting_text:
            weather = "晴朗"
        
        if "夜" in setting_text or "晚" in setting_text:
            time_of_day = "夜晚"
        elif "晨" in setting_text or "早" in setting_text:
            time_of_day = "清晨"
        elif "午" in setting_text:
            time_of_day = "正午"
        else:
            time_of_day = "日间"
        
        atmosphere_effects = []
        if "战争" in genre:
            atmosphere_effects = ["硝烟", "尘埃", "火光"]
        elif "科幻" in genre:
            atmosphere_effects = ["雾气", "光束", "全息投影"]
        
        dna.set_atmosphere(weather, time_of_day, atmosphere_effects, tone)
        
        # 视觉主题元素
        if "战争" in genre:
            dna.add_visual_motif("战争遗迹", "废墟、弹坑、烧毁的建筑")
            dna.add_visual_motif("军事符号", "军装、武器、军用物资")
        
        return dna
    
    def _build_character_bank(self, world: WorldDatabase) -> CharacterBank:
        """构建Character Bank"""
        
        bank = CharacterBank()
        
        # 从世界观中提取角色
        for name, char in world.characters.items():
            # 提取关键信息
            role = char.role if char.role else "supporting"
            age = str(char.age) if char.age else "未知"
            
            # 从visual_features推断gender
            gender = "未知"
            if char.visual_features:
                gender_hint = char.visual_features.get("gender", "")
                if gender_hint:
                    gender = gender_hint
            
            # 外貌特征
            distinctive_features = []
            
            # 从visual_features中提取
            if char.visual_features:
                # 身材
                if char.visual_features.get("body"):
                    distinctive_features.append(char.visual_features["body"])
                
                # 面部
                if char.visual_features.get("face"):
                    distinctive_features.append(char.visual_features["face"])
            
            # 限制特征数量
            distinctive_features = distinctive_features[:3]
            
            # 服装 - 从visual_features或clothing字段提取
            clothing = {}
            if char.visual_features and char.visual_features.get("clothing"):
                clothing_desc = char.visual_features["clothing"]
                if isinstance(clothing_desc, str):
                    clothing = {"main": clothing_desc}
                elif isinstance(clothing_desc, dict):
                    clothing = clothing_desc
            elif char.clothing:
                # clothing是列表
                clothing = {"items": char.clothing}
            
            # 性格特征
            personality = char.personality if char.personality else []
            
            # 背景故事 - 从world.setting生成简单的背景
            backstory = f"{name}是{world.title}中的{role}角色"
            
            # 添加到Character Bank
            bank.add_character(
                name=name,
                role=role,
                age_range=age,
                gender=gender,
                distinctive_features=distinctive_features,
                clothing=clothing,
                personality_traits=personality,
                backstory=backstory
            )
        
        return bank
    
    def _enhance_storyboard(self, storyboard: Dict, visual_dna: VisualDNA,
                           character_bank: CharacterBank) -> Dict:
        """增强分镜，添加视觉细节"""
        
        enhanced = storyboard.copy()
        enhanced_shots = []
        
        for shot in storyboard.get("shots", []):
            enhanced_shot = shot.copy()
            
            # 添加光线描述
            lighting = visual_dna.dna["lighting"]
            enhanced_shot["lighting"] = {
                "type": lighting["type"],
                "direction": lighting["direction"],
                "mood": lighting["mood"]
            }
            
            # 添加色彩方案
            colors = visual_dna.dna["color_palette"]
            enhanced_shot["color_palette"] = {
                "primary": colors["primary"][:2],  # 最多2个主色
                "accent": colors["accent"][:1] if colors["accent"] else []
            }
            
            # 添加氛围效果
            atmosphere = visual_dna.dna["atmosphere"]
            if atmosphere["effects"]:
                enhanced_shot["atmosphere_effects"] = atmosphere["effects"][:2]
            
            # 增强角色描述（使用Character Bank）
            if shot.get("characters"):
                enhanced_characters = []
                for char_name in shot["characters"]:
                    char_desc = character_bank.get_character_prompt_description(char_name)
                    enhanced_characters.append({
                        "name": char_name,
                        "description": char_desc
                    })
                    
                    # 标记出现
                    character_bank.mark_appearance(
                        char_name,
                        shot.get("shot_number", 0),
                        shot.get("duration", 0)
                    )
                
                enhanced_shot["enhanced_characters"] = enhanced_characters
            
            enhanced_shots.append(enhanced_shot)
        
        enhanced["shots"] = enhanced_shots
        
        return enhanced
    
    def _validate_visual_consistency(self, visual_dna: VisualDNA,
                                    character_bank: CharacterBank,
                                    storyboard: Dict) -> Dict:
        """验证视觉一致性"""
        
        warnings = []
        suggestions = []
        
        # 验证Visual DNA
        dna_validation = visual_dna.validate()
        if dna_validation["warnings"]:
            warnings.extend(dna_validation["warnings"])
        
        # 验证Character Bank
        char_validation = character_bank.validate_consistency()
        if char_validation["warnings"]:
            warnings.extend(char_validation["warnings"])
        
        # 检查角色出现频率
        stats = character_bank.get_all_stats()
        if stats:
            main_char = stats[0]
            if main_char["appearances"] < 3:
                suggestions.append(f"主角{main_char['name']}出现次数较少，建议增加")
        
        return {
            "warnings": warnings,
            "suggestions": suggestions
        }
