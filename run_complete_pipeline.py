# -*- coding: utf-8 -*-
"""
视频生产流水线 - 主入口脚本

【使用方法】
1. 直接运行: python run_complete_pipeline.py
2. 无需激活conda环境
3. 默认测试模式(skip_video_gen=True)，只运行前5个阶段

【主要参数】
修改CONFIG字典中的参数：
# - ARK_LLM_API_KEY (or VOLC_API_KEY): LLM API key
# - ARK_VIDEO_API_KEY (or ARK_API_KEY): video API key
# - AUDIO_API_KEY (or TTS_API_KEY): audio API key
- photos/: 按元素名称分目录存放的参考图片
- reference_audio: 参考音频路径
- story_idea: 故事想法文本
- target_duration: 目标时长(秒)

【输出目录】
pipeline_output/{session_id}/
- 01_world.json: 世界观
- 02_script.json: 剧本
- 03_storyboard.json: 分镜
- 04_visual_dna.json: 视觉DNA
- 05_prompts.json: 优化提示词
- 05_director_decisions.json: 导演决策
- round_table_meeting.md: 圆桌会议日志

【质量门控】
脚本会自动检查提示词质量，必须通过才会生成视频（避免浪费约20元/次）
"""

import json
import os
import sys
import io
from pathlib import Path

# 修复 Windows 终端编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from agents.orchestrator.video_production import VideoProductionOrchestrator


def _first_env(*names: str) -> str:
    """Return the first non-empty API key from the supplied environment variables."""
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


# ============== 配置 ==============
CONFIG = {
    # LLM配置（火山方舟/豆包）
    "llm": {
        "endpoint": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "api_key": _first_env("ARK_LLM_API_KEY", "VOLC_API_KEY"),
        "model": "doubao-seed-evolving",
        "temperature": 0.7,
        "max_tokens": 20000  # 增加到20000，确保完整剧本+世界观输出
    },
    
    # 视频生成配置（豆包Seedance via moyu.cn）
    "video_api": {
        "provider": "seedance",
        "api_key": _first_env("ARK_VIDEO_API_KEY", "ARK_API_KEY"),
        "base_url": "https://www.moyu.cn",
        # "model": "doubao-seedance-2-0-260128",
        "model": "doubao-seedance-2-0-mini-260615",
        "resolution": "720p",
        "duration": 5,
        "ratio": "16:9",
        "max_reference_images": 6,
        "reference_image_max_side": 768,
        "reference_image_jpeg_quality": 82,
        "max_request_body_bytes": 8 * 1024 * 1024,
    },
    
    # 音频生成配置
    "audio_api": {
        "endpoint": "https://openspeech.bytedance.com/api/v3/tts/create",
        "api_key": _first_env("AUDIO_API_KEY", "TTS_API_KEY"),
        "model": "seed-audio-1.0",
        "format": "mp3",
        "sample_rate": 48000
    },
    
    # 输出目录
    "output_dir": "D:/cg_create/pipeline_output"
}


def main():
    """主函数"""
    # RESUME_FROM = "20260914_114635"
    RESUME_FROM = None
    target_format = "中东废土风"
    reference_audio = "D:/cg_create/voice/wuming.m4a"
    target_duration = 30
    
    # ========== 配置结束 ==========
    
    # API keys are read from environment variables; see .env.video.example.
    missing_keys = []
    if not CONFIG["llm"]["api_key"]:
        missing_keys.append("ARK_LLM_API_KEY (or VOLC_API_KEY)")
    if not CONFIG["video_api"]["api_key"]:
        missing_keys.append("ARK_VIDEO_API_KEY (or ARK_API_KEY)")
    if not CONFIG["audio_api"]["api_key"]:
        missing_keys.append("AUDIO_API_KEY (or TTS_API_KEY)")
    if missing_keys:
        raise RuntimeError(
            "Missing API key environment variables: " + ", ".join(missing_keys)
        )

    print("=" * 80)
    print("视频生产流水线")
    print("=" * 80)
    print()
    print("配置:")
    print("   - 参考图片: 按 prompt 自动匹配 photos/{元素名称}/")
    print(f"   - 参考音频: {reference_audio}")
    print(f"   - 目标时长: {target_duration}秒")
    print()
    
    # 创建编排器
    story_idea = (Path(__file__).resolve().parent / "core" / "story_idea.txt").read_text(encoding="utf-8")

    orchestrator = VideoProductionOrchestrator(CONFIG)
    

    if RESUME_FROM:
        resume_session_dir = Path(CONFIG["output_dir"]) / str(RESUME_FROM)
        if not resume_session_dir.is_dir():
            raise FileNotFoundError(f"续跑会话目录不存在: {resume_session_dir}")
        print(f"[RESUME] 从会话继续: {RESUME_FROM}")
        print()
        result = orchestrator.resume(
            session_id=RESUME_FROM,
            story_idea=story_idea,
            target_duration=target_duration,
            reference_audio=reference_audio,
            skip_video_gen=False,
        )
    else:
        result = orchestrator.run(
            story_idea=story_idea,
            target_format=target_format,
            target_duration=target_duration,
            reference_audio=reference_audio,
            skip_video_gen=False    
        )
    
    # 打印结果
    if result["success"]:
        print()
        print("=" * 80)
        print("[SUCCESS] 流水线执行成功!")
        print("=" * 80)
        print(f"\n[OUTPUT] 输出目录: {result['output_dir']}")
        print()
        print("[FILES] 生成的文件:")
        print("   - round_table_meeting.md: 圆桌会议日志")
        print("   - 01_world.json: 世界观")
        print("   - 02_script.json: 剧本")
        print("   - 03_storyboard.json: 分镜")
        print("   - 05_prompts.json: 优化提示词")
        print("   - 05_director_decisions.json: 导演决策")
        print()
        
        if result.get("director_decisions"):
            decisions = result["director_decisions"]
            print("[DIRECTOR] 导演决策:")
            print(f"   - 帧继承镜头数: {sum(1 for v in decisions.get('frame_inheritance', {}).values() if v)}")
            print(f"   - 多角色参考图: {sum(1 for refs in decisions.get('multi_reference_images', {}).values() if len(refs) > 1)}个镜头")
            print()
        
        print("[TIP] 提示: 查看输出目录中的文件，了解流水线执行情况")
        print("[TIP] 提示: 测试满意后，设置 skip_video_gen=False 生成视频")
    else:
        print()
        print("=" * 80)
        print("[ERROR] 流水线执行失败!")
        print("=" * 80)
        print(f"\n错误: {result.get('error', '未知错误')}")
        print(f"阶段: {result.get('stage', '未知')}")
        print()


if __name__ == "__main__":
    main()
