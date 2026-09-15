# -*- coding: utf-8 -*-
"""测试 Post Production 模块"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from agents.specialists.post_production import PostProduction

def test_post_production():
    """测试后期制作功能"""
    
    print("=" * 60)
    print("测试 Post Production 模块")
    print("=" * 60)
    
    # 创建后期制作agent
    llm_config = {
        "provider": "openai",
        "model": "gpt-4",
        "temperature": 0.7
    }
    agent = PostProduction(llm_config=llm_config)
    
    # 测试数据
    test_data = {
        "shots": [
            {
                "shot_number": 1,
                "scene": "废墟",
                "camera_movement": "推进",
                "narration": "这是一个毁灭的世界",
                "dialogue": [
                    {
                        "character": "主角",
                        "content": "我必须活下去",
                        "emotion": "坚定"
                    }
                ]
            },
            {
                "shot_number": 2,
                "scene": "地下避难所",
                "camera_movement": "环绕",
                "dialogue": [
                    {
                        "character": "老人",
                        "content": "外面已经不安全了",
                        "emotion": "担忧"
                    },
                    {
                        "character": "主角",
                        "content": "我知道，但我别无选择",
                        "emotion": "冷静"
                    }
                ]
            }
        ],
        "video_files": [
            {"shot_number": 1, "path": "video_001.mp4"},
            {"shot_number": 2, "path": "video_002.mp4"}
        ],
        "music_style": "紧张悬疑",
        "reference_audio": "path/to/reference.wav"
    }
    
    print("\n[测试] 开始后期制作...")
    print(f"镜头数量: {len(test_data['shots'])}")
    print(f"视频文件: {len(test_data['video_files'])}")
    
    # 执行后期制作
    response = agent.execute(test_data)
    
    print("\n[结果]")
    print(f"状态: {'成功' if response.success else '失败'}")
    
    if response.error:
        print(f"错误: {response.error}")
    
    if response.data:
        print(f"\n生成的文件:")
        if isinstance(response.data, dict):
            for key, value in response.data.items():
                print(f"  - {key}: {value}")
        else:
            print(f"  {response.data}")
    
    if response.warnings:
        print(f"\n警告:")
        for warning in response.warnings:
            print(f"  - {warning}")
    
    if response.suggestions:
        print(f"\n建议:")
        for suggestion in response.suggestions:
            print(f"  - {suggestion}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    
    return response.success

if __name__ == "__main__":
    success = test_post_production()
    sys.exit(0 if success else 1)
