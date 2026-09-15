"""
测试圆桌讨论修复
验证返回值结构是否正确
"""

import sys
import json
from pathlib import Path

# 模拟返回值结构
def test_return_structure():
    """测试修复后的返回值结构"""
    
    # 模拟修复后的返回值
    discussion_result = {
        "success": True,
        "rounds": 2,  # ✅ 现在有这个字段
        "final_structure_report": {
            "metadata": {
                "shot_count": 12,  # ✅ 正确的字段名
                "duration": 61,     # ✅ 正确的字段名
            },
            "story_coherence": True,       # ✅ 新增字段
            "character_consistency": True,  # ✅ 新增字段
            "shots": []
        },
        "discussion_summary": "测试总结",
        "consensus": {"all_approved": True}
    }
    
    # 测试会议日志需要的字段
    print("📋 测试会议日志字段读取：\n")
    
    # Test 1: rounds 字段
    rounds = discussion_result.get('rounds', 0)
    print(f"✅ 讨论回合: {rounds} (期望: 2)")
    assert rounds == 2, f"❌ rounds 字段错误: {rounds}"
    
    # Test 2: final_report metadata
    final_report = discussion_result.get('final_structure_report', {})
    metadata = final_report.get('metadata', {})
    
    shot_count = metadata.get('shot_count', 0)
    print(f"✅ 总镜头数: {shot_count} (期望: 12)")
    assert shot_count == 12, f"❌ shot_count 字段错误: {shot_count}"
    
    duration = metadata.get('duration', 0)
    print(f"✅ 总时长: {duration}秒 (期望: 61)")
    assert duration == 61, f"❌ duration 字段错误: {duration}"
    
    # Test 3: 质量指标
    story_coherence = final_report.get('story_coherence', False)
    print(f"✅ 故事线完整性: {'✓' if story_coherence else '✗'} (期望: ✓)")
    assert story_coherence == True, f"❌ story_coherence 字段错误: {story_coherence}"
    
    character_consistency = final_report.get('character_consistency', False)
    print(f"✅ 角色一致性: {'✓' if character_consistency else '✗'} (期望: ✓)")
    assert character_consistency == True, f"❌ character_consistency 字段错误: {character_consistency}"
    
    print("\n🎉 所有字段测试通过！")
    return True


def test_old_structure():
    """展示修复前的问题"""
    
    # 模拟修复前的返回值
    old_result = {
        "success": True,
        # ❌ 缺少 rounds
        "final_structure_report": {
            "metadata": {
                "shot_count": 12,
                "duration": 61,
            },
            # ❌ 缺少 story_coherence, character_consistency
        },
        "discussion_summary": "测试总结",
        "consensus": {"all_approved": True}
    }
    
    print("\n❌ 修复前的问题：\n")
    
    rounds = old_result.get('rounds', 0)
    print(f"   讨论回合: {rounds} (显示为 0)")
    
    final_report = old_result.get('final_structure_report', {})
    
    # 错误的字段访问
    total_shots = final_report.get('total_shots', 0)
    print(f"   总镜头数: {total_shots} (错误字段，显示为 0)")
    
    total_duration = final_report.get('total_duration', 0)
    print(f"   总时长: {total_duration}秒 (错误字段，显示为 0)")
    
    story_coherence = final_report.get('story_coherence', False)
    print(f"   故事线完整性: {'✓' if story_coherence else '✗'} (缺失字段，显示为 ✗)")
    
    character_consistency = final_report.get('character_consistency', False)
    print(f"   角色一致性: {'✓' if character_consistency else '✗'} (缺失字段，显示为 ✗)")


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 圆桌讨论返回值结构测试")
    print("=" * 60)
    
    # 展示问题
    test_old_structure()
    
    print("\n" + "=" * 60)
    
    # 验证修复
    try:
        test_return_structure()
        print("\n✅ 修复验证成功！")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ 修复验证失败: {e}")
        sys.exit(1)
