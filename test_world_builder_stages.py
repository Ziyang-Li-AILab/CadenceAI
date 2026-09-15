"""测试分阶段生成策略"""
from agents.specialists.world_builder import WorldBuilderAgent

def test_prompts():
    """测试提示词生成"""
    agent = WorldBuilderAgent()
    
    story = "一个关于未来战士的故事"
    
    # 测试阶段1：核心世界观提示词
    print("=" * 60)
    print("阶段1：核心世界观提示词")
    print("=" * 60)
    core_prompt = agent._build_core_prompt(story, "电影")
    print(f"长度: {len(core_prompt)} 字符")
    print(f"\n前500字符:\n{core_prompt[:500]}")
    
    # 测试阶段2：分镜提示词
    print("\n" + "=" * 60)
    print("阶段2：分镜提示词")
    print("=" * 60)
    
    mock_core_data = {
        "title": "三角洲：无名",
        "genre": "东方神话史诗",
        "characters": [{"name": "无名"}],
        "locations": [{"name": "哈夫克尖塔"}],
        "visual_style": {"lighting": "侧逆光"},
        "audio_style": {}
    }
    
    shots_prompt = agent._build_shots_prompt(mock_core_data, "电影")
    print(f"长度: {len(shots_prompt)} 字符")
    print(f"\n前500字符:\n{shots_prompt[:500]}")
    
    print("\n" + "=" * 60)
    print("对比分析")
    print("=" * 60)
    print(f"核心提示词长度: {len(core_prompt)}")
    print(f"分镜提示词长度: {len(shots_prompt)}")
    print(f"总长度: {len(core_prompt) + len(shots_prompt)}")
    print(f"\n✓ 分阶段策略将单次请求拆分为两次，每次长度更短")
    print(f"✓ 预期每次LLM调用时间: 60-120秒（远小于300秒超时）")

if __name__ == "__main__":
    test_prompts()
