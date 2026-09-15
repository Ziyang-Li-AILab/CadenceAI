# -*- coding: utf-8 -*-
"""
测试完整世界观生成（包含所有新增字段）
验证超时优化是否有效
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agents.specialists.world_builder import WorldBuilderAgent

# 使用实际配置
CONFIG = {
    "llm": {
        "endpoint": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "api_key": os.getenv("ARK_LLM_API_KEY") or os.getenv("VOLC_API_KEY", ""),
        "model": "doubao-seed-evolving",
        "temperature": 0.7,
        "max_tokens": 10000
    }
}

# 测试故事（简化版，但要求完整输出）
STORY_IDEA = """
《无名者》

风格：东方神话 × 近未来军事
主角：一个失忆的战士，代号"无名"
背景：哈夫克神权统治的阿萨拉，科技与神话交织
时长：60秒

核心场景：
1. 哈夫克尖塔 - 通天巨柱，金色符文，云海之上
2. 战场废墟 - 无名醒来的地方，破败、压抑
3. 机械玄武 - 巨型战争机器，象征哈夫克武力

主要角色：
- 无名：28岁，轮廓锐利，战袍破损，颈部有脑机接口
"""

def main():
    print("=" * 70)
    print("完整世界观生成测试")
    print("=" * 70)
    
    # 初始化Agent
    print("\n[1/3] 初始化WorldBuilderAgent...")
    agent = WorldBuilderAgent("world_builder", CONFIG)
    print("  ✓ 初始化成功")
    
    # 执行生成
    print("\n[2/3] 生成完整世界观...")
    print("  提示：这将调用LLM生成包含以下字段的完整JSON：")
    print("    - characters (含 personality, speech_pattern, actions)")
    print("    - locations (含 visual_elements, lighting_type, atmosphere)")
    print("    - props (道具列表)")
    print("    - visual_style (含 lighting_details 嵌套结构)")
    print("    - audio_style (含 ambience, sfx, dialogue)")
    print("    - shots (完整分镜数组)")
    print("    - pacing (时间轴)")
    print("    - technical_specs (技术规格)")
    print("    - style_references (风格参考)")
    print()
    
    context = {
        "story_idea": STORY_IDEA,
        "target_format": "史诗级电影震撼大片"
    }
    
    start_time = time.time()
    response = agent.execute(context)
    elapsed = time.time() - start_time
    
    # 显示结果
    print("\n[3/3] 结果分析")
    print("-" * 70)
    
    if response.success:
        print(f"  ✓ 生成成功！")
        print(f"  ✓ 耗时: {elapsed:.2f}秒 ({elapsed/60:.1f}分钟)")
        
        world = response.data
        
        # 检查各个字段
        print(f"\n  字段完整性检查:")
        print(f"    - title: {world.title}")
        print(f"    - genre: {world.genre}")
        print(f"    - characters: {len(world.characters)}个")
        print(f"    - locations: {len(world.locations)}个")
        print(f"    - props: {len(world.props)}个")
        print(f"    - shots: {len(world.shots)}个镜头")
        print(f"    - pacing: {'✓' if world.pacing else '✗'}")
        print(f"    - technical_specs: {'✓' if world.technical_specs else '✗'}")
        print(f"    - style_references: {'✓' if world.style_references else '✗'}")
        
        # 检查关键嵌套字段
        if world.characters:
            char = world.characters[0]
            print(f"\n  角色详细字段 ({char.name}):")
            print(f"    - personality: {char.personality if hasattr(char, 'personality') else '✗'}")
            print(f"    - speech_pattern: {char.speech_pattern if hasattr(char, 'speech_pattern') else '✗'}")
            print(f"    - actions: {char.actions if hasattr(char, 'actions') else '✗'}")
        
        if world.locations:
            loc = world.locations[0]
            print(f"\n  场景详细字段 ({loc.name}):")
            print(f"    - visual_elements: {loc.visual_elements if hasattr(loc, 'visual_elements') else '✗'}")
            print(f"    - lighting_type: {loc.lighting_type if hasattr(loc, 'lighting_type') else '✗'}")
            print(f"    - atmosphere: {loc.atmosphere if hasattr(loc, 'atmosphere') else '✗'}")
        
        if world.visual_style:
            print(f"\n  视觉风格嵌套:")
            print(f"    - lighting_details: {world.visual_style.get('lighting_details', '✗')}")
        
        if world.shots:
            shot = world.shots[0]
            print(f"\n  分镜详细字段 (Shot {shot.get('shot_id', 1)}):")
            print(f"    - camera_angle: {shot.get('camera_angle', '✗')}")
            print(f"    - camera_movement: {shot.get('camera_movement', '✗')}")
            print(f"    - visual_prompt: {shot.get('visual_prompt', '✗')[:50]}...")
            print(f"    - narration: {shot.get('narration', '✗')}")
        
        # 性能评估
        print(f"\n  性能评估:")
        if elapsed < 180:
            print(f"    ✓ 性能优秀 (< 3分钟)")
        elif elapsed < 270:
            print(f"    ✓ 性能良好 (3-4.5分钟)")
        elif elapsed < 300:
            print(f"    ⚠ 性能可接受 (4.5-5分钟)")
        else:
            print(f"    ✗ 性能不足 (> 5分钟，需优化)")
        
        # 保存测试结果
        import json
        test_output = Path("d:/cg_create/test_world_full_output.json")
        with open(test_output, 'w', encoding='utf-8') as f:
            json.dump(world.to_dict(), f, ensure_ascii=False, indent=2)
        print(f"\n  ✓ 完整输出已保存到: {test_output}")
        
    else:
        print(f"  ✗ 生成失败")
        print(f"  ✗ 错误: {response.error}")
        print(f"  ✗ 耗时: {elapsed:.2f}秒")
        
        if elapsed >= 300:
            print(f"\n  分析: 超时失败，建议:")
            print(f"    1. 检查网络连接")
            print(f"    2. 考虑启用流式输出")
            print(f"    3. 或分两阶段生成")
        else:
            print(f"\n  分析: 非超时失败，可能是:")
            print(f"    1. JSON解析问题")
            print(f"    2. 模型输出格式问题")
            print(f"    3. 检查日志中的详细错误")
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)

if __name__ == "__main__":
    main()
