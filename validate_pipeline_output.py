#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
流水线输出验证工具

用途: 验证流水线输出数据的质量，检测污染和异常
使用: python validate_pipeline_output.py <session_id>
示例: python validate_pipeline_output.py 20260913_014648
"""

import json
import sys
import io
from pathlib import Path
from typing import Dict, List, Tuple

# 设置标准输出为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class PipelineValidator:
    """流水线输出验证器"""
    
    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.issues = []
        self.warnings = []
        
        # 污染检测关键词
        self.pollution_keywords = [
            "原始故事参考",
            "Cadence AI",
            "第一章",
            "神殿陨",
            "【原始",
            "风格：东方神话"
        ]
        
        # 长度阈值
        self.thresholds = {
            "prompt_min": 50,
            "prompt_normal_max": 1000,
            "prompt_critical_max": 1500
        }
    
    def validate_all(self) -> bool:
        """执行完整验证"""
        print("=" * 80)
        print("流水线输出验证")
        print("=" * 80)
        print(f"会话目录: {self.session_dir}")
        print()
        
        # 检查目录存在
        if not self.session_dir.exists():
            print(f"❌ 错误: 目录不存在: {self.session_dir}")
            return False
        
        # 验证各个文件
        self._validate_world()
        self._validate_script()
        self._validate_storyboard()
        self._validate_visual_dna()
        self._validate_prompts()  # 最关键
        
        # 打印结果
        self._print_results()
        
        return len(self.issues) == 0
    
    def _validate_world(self):
        """验证世界观文件"""
        print("[1/5] 验证世界观...")
        
        file_path = self.session_dir / "01_world.json"
        if not file_path.exists():
            self.issues.append("缺少文件: 01_world.json")
            return
        
        with open(file_path, encoding='utf-8') as f:
            data = json.load(f)
        
        # 检查必要字段
        required_fields = ["characters", "locations", "themes", "visual_style"]
        for field in required_fields:
            if field not in data:
                self.issues.append(f"01_world.json 缺少字段: {field}")
        
        # 检查字符数
        content_size = len(json.dumps(data, ensure_ascii=False))
        if content_size > 5000:
            self.warnings.append(
                f"01_world.json 过大({content_size}字)，可能包含冗余数据"
            )
        
        print(f"  ✓ 字符数: {content_size}")
        print(f"  ✓ 角色数: {len(data.get('characters', []))}")
        print(f"  ✓ 场景数: {len(data.get('locations', []))}")
        print()
    
    def _validate_script(self):
        """验证剧本文件"""
        print("[2/5] 验证剧本...")
        
        file_path = self.session_dir / "02_script.json"
        if not file_path.exists():
            self.issues.append("缺少文件: 02_script.json")
            return
        
        with open(file_path, encoding='utf-8') as f:
            data = json.load(f)
        
        # 检查必要字段
        if "scenes" not in data:
            self.issues.append("02_script.json 缺少字段: scenes")
            return
        
        # 统计镜头数
        shot_count = sum(len(scene.get("shots", [])) for scene in data["scenes"])
        print(f"  ✓ 场景数: {len(data['scenes'])}")
        print(f"  ✓ 镜头数: {shot_count}")
        
        # 检查是否保留了 original_story_idea（合理）
        if "original_story_idea" in data:
            print(f"  ℹ 保留了 original_story_idea (溯源用，正常)")
        
        print()
    
    def _validate_storyboard(self):
        """验证分镜文件"""
        print("[3/5] 验证分镜...")
        
        file_path = self.session_dir / "03_storyboard.json"
        if not file_path.exists():
            self.issues.append("缺少文件: 03_storyboard.json")
            return
        
        with open(file_path, encoding='utf-8') as f:
            data = json.load(f)
        
        if "shots" not in data:
            self.issues.append("03_storyboard.json 缺少字段: shots")
            return
        
        shots = data["shots"]
        print(f"  ✓ 镜头数: {len(shots)}")
        print()
    
    def _validate_visual_dna(self):
        """验证视觉DNA文件"""
        print("[4/5] 验证视觉DNA...")
        
        file_path = self.session_dir / "04_visual_dna.json"
        if not file_path.exists():
            self.issues.append("缺少文件: 04_visual_dna.json")
            return
        
        with open(file_path, encoding='utf-8') as f:
            data = json.load(f)
        
        required_fields = ["color_grading", "lighting", "camera"]
        for field in required_fields:
            if field not in data:
                self.issues.append(f"04_visual_dna.json 缺少字段: {field}")
        
        print(f"  ✓ 视觉参数完整")
        print()
    
    def _validate_prompts(self):
        """验证提示词文件（最关键）"""
        print("[5/5] 验证提示词（核心检查）...")
        
        file_path = self.session_dir / "05_prompts.json"
        if not file_path.exists():
            self.issues.append("缺少文件: 05_prompts.json")
            return
        
        with open(file_path, encoding='utf-8') as f:
            data = json.load(f)
        
        if "shots" not in data:
            self.issues.append("05_prompts.json 缺少字段: shots")
            return
        
        shots = data["shots"]
        print(f"  📊 总镜头数: {len(shots)}")
        print()
        
        # 详细检查每个镜头
        prompt_lengths = []
        polluted_shots = []
        
        for shot in shots:
            shot_number = shot.get("shot_number", "?")
            visual_prompt = shot.get("visual_prompt", "")
            prompt_length = len(visual_prompt)
            prompt_lengths.append(prompt_length)
            
            # 长度检查
            status = "✓"
            if prompt_length < self.thresholds["prompt_min"]:
                status = "⚠️"
                self.warnings.append(
                    f"镜头{shot_number}: prompt过短({prompt_length}字)"
                )
            elif prompt_length > self.thresholds["prompt_critical_max"]:
                status = "❌"
                self.issues.append(
                    f"镜头{shot_number}: prompt过长({prompt_length}字)，疑似污染"
                )
                polluted_shots.append(shot_number)
            elif prompt_length > self.thresholds["prompt_normal_max"]:
                status = "⚠️"
                self.warnings.append(
                    f"镜头{shot_number}: prompt较长({prompt_length}字)"
                )
            
            # 污染关键词检查
            found_keywords = []
            for keyword in self.pollution_keywords:
                if keyword in visual_prompt:
                    found_keywords.append(keyword)
                    if shot_number not in polluted_shots:
                        polluted_shots.append(shot_number)
            
            if found_keywords:
                status = "❌"
                self.issues.append(
                    f"镜头{shot_number}: 发现污染关键词 {found_keywords}"
                )
            
            # 打印单个镜头状态
            print(f"  {status} 镜头{shot_number:2d}: {prompt_length:4d} 字", end="")
            if found_keywords:
                print(f" (包含: {', '.join(found_keywords)})")
            else:
                print()
        
        # 统计摘要
        print()
        print(f"  📈 统计:")
        print(f"     - 平均长度: {sum(prompt_lengths) / len(prompt_lengths):.0f} 字")
        print(f"     - 最短: {min(prompt_lengths)} 字")
        print(f"     - 最长: {max(prompt_lengths)} 字")
        
        if polluted_shots:
            print(f"     - 污染镜头: {len(polluted_shots)}个 {polluted_shots}")
        else:
            print(f"     - 污染镜头: 0 个 ✅")
        
        print()
    
    def _print_results(self):
        """打印验证结果"""
        print("=" * 80)
        print("验证结果")
        print("=" * 80)
        
        if self.issues:
            print(f"❌ 发现 {len(self.issues)} 个问题:")
            for issue in self.issues:
                print(f"   - {issue}")
            print()
        
        if self.warnings:
            print(f"⚠️  发现 {len(self.warnings)} 个警告:")
            for warning in self.warnings:
                print(f"   - {warning}")
            print()
        
        if not self.issues and not self.warnings:
            print("✅ 所有检查通过，数据质量优秀！")
            print()
        elif not self.issues:
            print("✅ 主要检查通过，但存在一些警告")
            print()
        else:
            print("❌ 验证失败，请检查上述问题")
            print()
        
        print("=" * 80)


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python validate_pipeline_output.py <session_id>")
        print("示例: python validate_pipeline_output.py 20260913_014648")
        sys.exit(1)
    
    session_id = sys.argv[1]
    session_dir = Path("pipeline_output") / session_id
    
    validator = PipelineValidator(session_dir)
    success = validator.validate_all()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
