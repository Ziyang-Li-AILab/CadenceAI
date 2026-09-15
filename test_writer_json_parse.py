# -*- coding: utf-8 -*-
"""
测试Writer Agent的JSON解析问题
"""

import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from core.base_agent import BaseAgent
from agents.specialists.world_builder import WorldBuilderAgent
from agents.specialists.writer import WriterAgent

# 配置
CONFIG = {
    "llm": {
        "endpoint": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "model": "doubao-1.5-pro-32k-250115",
        "api_key": os.getenv("ARK_LLM_API_KEY") or os.getenv("VOLC_API_KEY", ""),
        "max_tokens": 10000
    }
}

# 简短的story_idea用于测试
story_idea = "一个未来战士在废墟中寻找希望"

print("=" * 80)
print("测试Writer Agent JSON解析")
print("=" * 80)

# Step 1: 先生成世界观
print("\n[1/2] 生成世界观...")
world_builder = WorldBuilderAgent(CONFIG)
world_response = world_builder.execute({
    "story_idea": story_idea,
    "target_format": "60秒短片"
})

if not world_response.success:
    print(f"❌ 世界观生成失败: {world_response.error}")
    sys.exit(1)

print("✓ 世界观生成成功")

# Step 2: 生成剧本，并捕获原始响应
print("\n[2/2] 生成剧本并检查JSON...")
writer = WriterAgent(CONFIG)

# 保存原始_call_llm方法
original_call_llm = writer._call_llm

# 包装_call_llm来捕获响应
captured_response = None

def wrapped_call_llm(*args, **kwargs):
    global captured_response
    captured_response = original_call_llm(*args, **kwargs)
    return captured_response

writer._call_llm = wrapped_call_llm

# 执行
script_response = writer.execute({
    "world": world_response.data,
    "target_duration": 60,
    "story_idea": story_idea
})

# 分析结果
print("\n" + "=" * 80)
print("分析结果")
print("=" * 80)

if script_response.success:
    print("✓ 剧本生成成功")
else:
    print(f"❌ 剧本生成失败: {script_response.error}")
    
    if captured_response:
        print("\n[原始LLM响应] (前2000字符):")
        print("-" * 80)
        print(captured_response[:2000])
        print("-" * 80)
        
        # 保存完整响应
        debug_file = Path("writer_debug_response.txt")
        debug_file.write_text(captured_response, encoding='utf-8')
        print(f"\n完整响应已保存到: {debug_file.absolute()}")
        
        # 尝试手动解析
        print("\n[诊断] 尝试手动解析JSON...")
        import json
        import re
        
        # 检查是否包含JSON
        if '{' in captured_response and '}' in captured_response:
            print("  ✓ 响应包含花括号")
            
            # 尝试提取JSON
            start = captured_response.find('{')
            end = captured_response.rfind('}')
            json_str = captured_response[start:end+1]
            
            print(f"  提取的JSON长度: {len(json_str)}字符")
            print(f"  JSON起始: {json_str[:100]}")
            print(f"  JSON结尾: {json_str[-100:]}")
            
            try:
                parsed = json.loads(json_str)
                print("  ✓ JSON可以解析!")
                print(f"  包含的键: {list(parsed.keys())}")
            except json.JSONDecodeError as e:
                print(f"  ✗ JSON解析失败: {e}")
                print(f"  错误位置: 行{e.lineno} 列{e.colno}")
        else:
            print("  ✗ 响应不包含完整的JSON结构")
            print(f"  响应开头: {captured_response[:200]}")
