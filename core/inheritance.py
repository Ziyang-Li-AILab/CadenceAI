# -*- coding: utf-8 -*-
"""
帧继承系统 - 简化版

核心功能：从已生成的视频中提取最后一帧，作为下一个镜头的参考图。

【简化说明】
- 只保留核心功能：提取帧、获取参考图
- 删除复杂的权重计算、链追踪、报告生成
- 遵循"简化实现"原则
"""

import json
from typing import Dict, List, Optional
from pathlib import Path


class ShotInheritance:
    """
    简化版帧继承系统
    
    核心职责：
    1. 从视频提取最后一帧
    2. 提供参考图路径给VideoGenerator
    
    【使用流程】
    1. 初始化时指定输出目录
    2. 每个镜头生成后，调用extract_last_frame保存最后一帧
    3. 生成下一镜头时，调用get_reference_image获取上一帧路径
    """
    
    def __init__(self, output_dir: str):
        """
        初始化帧继承系统
        
        Args:
            output_dir: 输出目录，用于保存提取的帧图片
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 存储已提取的帧: {shot_number: frame_path}
        self.last_frames: Dict[int, str] = {}
    
    def extract_last_frame(self, video_path: str, shot_number: int) -> Optional[str]:
        """
        从视频中提取最后一帧
        
        Args:
            video_path: 视频文件路径
            shot_number: 镜头编号
        
        Returns:
            提取的帧图片路径，失败返回None
        """
        try:
            import cv2
            
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                print(f"⚠️  无法打开视频: {video_path}")
                return None
            
            # 跳到最后一帧
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)
            
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                print(f"⚠️  无法读取最后一帧")
                return None
            
            # 保存帧
            frame_path = self.output_dir / f"frame_{shot_number:03d}_last.jpg"
            cv2.imwrite(str(frame_path), frame)
            
            self.last_frames[shot_number] = str(frame_path)
            
            print(f"  ✓ 提取最后一帧: 镜头{shot_number} -> {frame_path.name}")
            return str(frame_path)
            
        except ImportError:
            print("⚠️  OpenCV未安装，无法提取帧")
            print("   请运行: pip install opencv-python")
            return None
        except Exception as e:
            print(f"⚠️  提取帧失败: {e}")
            return None
    
    def get_reference_image(self, current_shot: int) -> Optional[str]:
        """
        获取当前镜头的参考图（上一镜头的最后一帧）
        
        Args:
            current_shot: 当前镜头编号
        
        Returns:
            参考图路径，如果没有则返回None
        """
        previous_shot = current_shot - 1
        return self.last_frames.get(previous_shot)
    
    def get_reference_images_for_shot(self, shot_number: int) -> List[str]:
        """
        获取某个镜头的所有参考图
        
        包含：
        1. 帧继承参考图（上一镜头最后一帧）
        2. 用户提供的角色参考图（在VideoGenerator中处理）
        
        Args:
            shot_number: 镜头编号
        
        Returns:
            参考图路径列表
        """
        refs = []
        
        # 添加帧继承参考图
        frame_ref = self.get_reference_image(shot_number)
        if frame_ref:
            refs.append(frame_ref)
        
        return refs
    
    def clear(self):
        """清空所有已保存的帧"""
        self.last_frames.clear()
        print("✓ 已清空帧继承缓存")


def create_inheritance(output_dir: str) -> ShotInheritance:
    """
    工厂函数：创建帧继承系统实例
    
    Args:
        output_dir: 输出目录
    
    Returns:
        ShotInheritance实例
    """
    return ShotInheritance(output_dir)
