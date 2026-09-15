# -*- coding: utf-8 -*-
"""
视频生产多Agent系统

架构说明：
- Orchestrator: 总编排器，协调所有专业Agent
- Specialists: 专业Agent，执行具体任务

工作流程：
1. WorldBuilderAgent: 构建世界观（角色、场景、道具）
2. WriterAgent: 创作剧本（包含角色对话）
3. StoryboardArtist: 设计分镜
4. Cinematographer: 定义视觉风格
5. Director: 优化提示词
"""

# 不在这里导入，避免循环依赖
# 各模块自行导入所需的Agent

__all__ = []
