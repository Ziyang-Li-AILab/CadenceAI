# -*- coding: utf-8 -*-
"""
视频生产流水线总编排器
实现Orchestrator模式,协调所有专业Agent的工作

[核心流程]质量门控驱动
1. 世界观构建 -> 圆桌会议评审
2. 剧本创作 -> 圆桌会议评审
3. 分镜设计 -> 圆桌会议评审
4. 视觉风格定义 -> 圆桌会议评审
5. 导演优化 -> 导演决策(帧继承, 多角色参考图)
6. [质量门控]-> 必须通过才能进入视频生成
7. 视频生成(严格按导演决策执行)
8. 后期制作

[关键原则]
- 圆桌会议必须开启
- 质量门控不通过则打回重走
- 导演决定帧继承策略
- 导演决定多角色参考图策略
- 所有决策敲定后才生成视频(避免资源浪费)
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent))

from core.world_database import WorldDatabase
from core.base_agent import BaseAgent, AgentResponse, QualityGate
from core.visual_dna import VisualDNA
from core.character_bank import CharacterBank
from core.round_table import RoundTableMeeting, CollaborativeWorkflow, AgentRole
from agents.specialists.world_builder import WorldBuilderAgent
from agents.specialists.writer import WriterAgent
from agents.specialists.storyboard_artist import StoryboardArtist
from agents.specialists.cinematographer import Cinematographer
from agents.specialists.director import Director
from agents.specialists.video_generator import VideoGenerator
from agents.specialists.post_production import PostProduction
from agents.collaboration.round_table_discussion import RoundTableDiscussion
from agents.quality.enhanced_quality_inspector import EnhancedQualityInspector



class VideoProductionOrchestrator:
    """
    视频生产总编排器 - 电影的"制片人"角色
    
    [核心职责]
    1. 协调各个专业Agent的工作
    2. 管理质量门控流程
    3. 确保所有决策敲定后才生成视频
    4. 避免资源浪费(视频生成一次约20元)
    
    [流程控制]
    - 圆桌会议:必须开启,记录所有讨论
    - 质量门控:每个阶段评审,不通过打回重走
    - 导演决策:帧继承策略, 多角色参考图策略
    - 视频生成:质量门控通过后才能执行
    
    [开幕式优化]
    - 当用户输入包含"开幕式"等关键词时,第一个镜头将尽全力优化
    - 开幕式相关prompt需要更详细的视觉描述
    - 相关会议讨论需要特别关注质量
    """
    
    # [新增]开幕式关键词列表
    OPENING_CEREMONY_KEYWORDS = [
        "开幕式", "开幕", "典礼", "仪式", "首发", "首映", 
        "启动仪式", "上线仪式", "发布仪式", "开业典礼"
    ]
    
    # ======================== 初始化 ========================
    
    def __init__(self, config: Dict = None):
        # 优先使用传入的完整配置（包含真实 API key），同时合并 pipeline_config.json 中的默认值
        # 确保 pipeline_config.json 的默认值填充不会覆盖调用方传入的显式 key
        base_config = self._load_default_config()
        if config:
            # 深度合并：config（调用方提供）优先于 base_config（文件默认值）
            self.config = self._deep_merge_config(base_config, config)
        else:
            self.config = base_config
        
        # 初始化所有专业Agent
        self.world_builder = WorldBuilderAgent(self.config)
        self.writer = WriterAgent(self.config)
        self.storyboard_artist = StoryboardArtist(self.config)
        self.cinematographer = Cinematographer(self.config)
        self.director = Director(self.config)
        # 【修复】正确传递llm_config和video_api_config
        self.video_generator = VideoGenerator(
            llm_config=self.config.get('llm', {}),
            video_api_config=self.config.get('video_api', {})
        )
        # 【修复】正确传递llm_config和tts_config
        self.post_production = PostProduction(
            llm_config=self.config.get('llm', {}),
            tts_config=self.config.get('audio_api', {})
        )
        
        # 质量门控
        self.quality_gate = QualityGate()
        
        # 增强的质量检查员
        self.quality_inspector = EnhancedQualityInspector()
        
        # 圆桌讨论协调器
        self.round_table: Optional[RoundTableDiscussion] = None
        
        # 旧的圆桌会议(保留兼容性)
        self.meeting: Optional[RoundTableMeeting] = None
        self.workflow: Optional[CollaborativeWorkflow] = None
        
        # 共享上下文
        self.world: Optional[WorldDatabase] = None
        self.script: Optional[Dict] = None
        self.storyboard: Optional[Dict] = None
        self.visual_dna: Optional[VisualDNA] = None
        self.character_bank: Optional[CharacterBank] = None
        self.optimized_shots: Optional[Dict] = None
        self.video_files: Optional[list] = None
        
        # 导演决策记录
        self.director_decisions: Dict[str, Any] = {
            "frame_inheritance": {},      # 每个镜头的帧继承决策
            "multi_reference_images": {},  # 每个镜头的多角色参考图策略
            "quality_approval": False      # 质量门控是否通过
        }
        
        # 输出目录
        self.output_dir = Path(self.config.get("output_dir", "pipeline_output"))
        self.session_dir: Optional[Path] = None
        
        # 流程状态
        self.pipeline_state = {
            "phase": "idle",
            "quality_check_passed": False,
            "video_generation_allowed": False,
            "errors": [],
            "retry_count": {}
        }
    
    # ======================== 主入口 ========================
    
    def resume(self, session_id: str, story_idea: str, target_duration: int = 60,
               reference_images: List[str] = None,
               reference_audio: str = None,
               skip_video_gen: bool = True) -> Dict[str, Any]:
        """断点续传入口

        Args:
            session_id: 要继续的会话ID
            story_idea: 故事想法
            target_duration: 目标时长
            reference_images: 参考图片列表
            reference_audio: 参考音频
            skip_video_gen: 是否跳过视频生成（默认True，安全优先）

        Returns:
            执行结果
        """
        return self._resume_from_checkpoint(
            session_id, story_idea, target_duration,
            reference_images, reference_audio, skip_video_gen,
        )
    
    def run(self, story_idea: str, target_format: str, target_duration: int = 60,
            reference_images: List[str] = None, 
            reference_audio: str = None,
            skip_video_gen: bool = True) -> Dict[str, Any]:
        """Run the video production pipeline."""
        print("=" * 80)
        print("Video Production Pipeline Started")
        print("=" * 80)
        print("Quality gate mode: all decisions confirmed before video generation")
        print()
        
        # Record input parameters
        self._log_input_params(story_idea, target_duration, reference_images, reference_audio)
        
        self.story_idea = story_idea
        self.skip_video_gen = skip_video_gen
        
        # 创建会话目录
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = str(session_id)
        self.session_dir = self.output_dir / session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[INFO] 会话ID: {session_id}")
        print(f"[INFO] 输出目录: {self.session_dir}")
        print(f"[INFO] 参考图片: {reference_images or '无'}")
        print(f"[INFO] 参考音频: {reference_audio or '无'}")
        print()
        
        # [新增]检测是否包含开幕式关键词
        is_opening_ceremony = self._detect_opening_ceremony(story_idea)
        self.pipeline_state["is_opening_ceremony"] = is_opening_ceremony
        
        if is_opening_ceremony:
            print("[SPECIAL] 检测到开幕式/典礼相关主题,启动强化优化模式")
            print("   第一个镜头将尽全力优化,所有相关讨论将特别记录")
            print()
        
        # 初始化圆桌会议(必须开启)
        log_file = self.session_dir / "round_table_meeting.md"
        self.meeting = RoundTableMeeting(log_file=str(log_file))
        self.workflow = CollaborativeWorkflow(self.meeting)
        print("[OK] 圆桌会议已开启(所有讨论将实时记录)")
        print()
        
        # ==================== 阶段1: 世界观构建 ====================
        print("\n" + "="*80)
        print("[STAGE 1/8] 世界观构建")
        print("="*80)
        print("📌 story_idea 传入: 世界观构建师")
        
        world_result = self._build_world(story_idea, target_format, target_duration)
        if not world_result["success"]:
            return self._handle_failure("世界观构建失败", world_result)

        import sys;sys.exit(1)
        
        # ==================== 阶段2: 剧本创作 ====================
        print("\n" + "="*80)
        print("[STAGE 2/8] 剧本创作")
        print("="*80)
        print("📌 story_idea 传入: 编剧")
        
        script_result = self._write_script(target_duration)
        if not script_result["success"]:
            return self._handle_failure("剧本创作失败", script_result)
        
        # ==================== 阶段3: 分镜设计 ====================
        print("\n" + "="*80)
        print("[STAGE 3/8] 分镜设计")
        print("="*80)
        print("📌 不传入 story_idea，仅传入 script + world")
        
        storyboard_result = self._design_storyboard()
        if not storyboard_result["success"]:
            return self._handle_failure("分镜设计失败", storyboard_result)
        
        # ==================== 阶段4: 视觉风格 ====================
        print("\n" + "="*80)
        print("[STAGE 4/8] 视觉风格定义")
        print("="*80)
        print("📌 不传入 story_idea，仅传入 storyboard + world")
        
        visual_result = self._define_visual_style()
        if not visual_result["success"]:
            return self._handle_failure("视觉风格定义失败", visual_result)
        
        # ==================== 阶段5: 圆桌讨论 ====================
        print("\n" + "="*80)
        print("[STAGE 5/8] 圆桌讨论")
        print("="*80)
        print("🎭 各个agent查看彼此工作成果，集体讨论")
        print("🎭 导演生成最终结构报告")
        
        discussion_result = self._conduct_round_table_discussion()
        if not discussion_result["success"]:
            return self._handle_failure("圆桌讨论失败", discussion_result)
        
        # 保存最终结构报告
        final_report = discussion_result["final_structure_report"]
        report_path = self.session_dir / "05_final_structure_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(final_report, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 最终结构报告已生成")
        print(f"   保存位置: {report_path}")
        
        # ==================== 阶段5.5: 提示词优化 ====================
        print("\n" + "="*80)
        print("[STAGE 5.5/8] 提示词优化（导演）")
        print("="*80)
        print("🎬 导演根据最终结构报告优化所有镜头提示词")
        
        prompts_result = self._optimize_prompts()
        if not prompts_result["success"]:
            return self._handle_failure("提示词优化失败", prompts_result)
        
        print(f"\n✅ 提示词优化完成")
        print(f"   - 镜头数: {len(self.optimized_shots.get('shots', []))}")
        
        # ==================== 阶段6: [质量门控] ====================
        max_quality_retries = 3
        quality_retry_count = 0
        
        while quality_retry_count < max_quality_retries:
            print("\n" + "="*80)
            if quality_retry_count == 0:
                print(f"[STAGE 6/8] 质量门控检查 (全流水线唯一评审)")
            else:
                print(f"[STAGE 6/8] 质量门控检查 (重试第 {quality_retry_count} 次)")
            print("="*80)
            print("📋 评审内容: 优化后的提示词")
            print("📋 评审维度: 视觉质量、一致性、技术规范等")
            
            quality_result = self._quality_gate_check()
            
            if quality_result["passed"]:
                print("\n✅ 质量门控检查通过")
                print("[OK] 允许进入视频生成阶段")
                self.pipeline_state["quality_check_passed"] = True
                self.pipeline_state["video_generation_allowed"] = True
                break
            else:
                print("\n❌ 质量门控检查未通过")
                print("📋 问题列表:")
                for issue in quality_result["issues"]:
                    print(f"   - {issue}")
                
                print("\n💡 建议:")
                for suggestion in quality_result["suggestions"]:
                    print(f"   - {suggestion}")
                
                quality_retry_count += 1
                
                if quality_retry_count >= max_quality_retries:
                    return self._handle_failure("质量门控检查失败(已达最大重试次数)", {
                        "error": "质量检查未通过",
                        "issues": quality_result["issues"]
                    })
                
                # 【关键】根据问题类型决定返工策略
                print(f"\n🔄 打回重新工作 ({quality_retry_count}/{max_quality_retries})...")
                
                # 分析问题，决定返工目标
                rework_decision = self._determine_rework_target(quality_result)
                target_stage = rework_decision["target_stage"]
                reason = rework_decision["reason"]
                
                print(f"   返工目标: {target_stage}")
                print(f"   原因: {reason}")
                
                self.pipeline_state["retry_count"]["quality_gate"] = quality_retry_count
                
                # 根据目标阶段执行返工
                if target_stage == "prompt_optimization":
                    # 只重新优化提示词
                    print("   执行提示词重新优化...")
                    rework_result = self._rework_prompt_optimization(quality_result)
                    
                elif target_stage == "round_table":
                    # 重新圆桌讨论 + 提示词优化
                    print("   执行圆桌讨论返工...")
                    discussion_result = self._conduct_round_table_discussion(quality_feedback=quality_result)
                    
                    if not discussion_result.get("success"):
                        return self._handle_failure(f"返工失败: {discussion_result.get('error')}", discussion_result)
                    
                    # 更新最终结构报告
                    final_report = discussion_result["final_structure_report"]
                    report_path = self.session_dir / "05_final_structure_report.json"
                    with open(report_path, 'w', encoding='utf-8') as f:
                        json.dump(final_report, f, ensure_ascii=False, indent=2)
                    
                    # 重新优化提示词
                    print("   重新优化提示词...")
                    prompts_result = self._optimize_prompts()
                    if not prompts_result["success"]:
                        return self._handle_failure("提示词重新优化失败", prompts_result)
                    
                    rework_result = {"success": True}
                    
                else:
                    # 无法确定，默认全流程返工
                    print("   ⚠️ 无法确定具体问题，执行全流程返工...")
                    discussion_result = self._conduct_round_table_discussion(quality_feedback=quality_result)
                    
                    if not discussion_result.get("success"):
                        return self._handle_failure(f"返工失败: {discussion_result.get('error')}", discussion_result)
                    
                    final_report = discussion_result["final_structure_report"]
                    report_path = self.session_dir / "05_final_structure_report.json"
                    with open(report_path, 'w', encoding='utf-8') as f:
                        json.dump(final_report, f, ensure_ascii=False, indent=2)
                    
                    prompts_result = self._optimize_prompts()
                    if not prompts_result["success"]:
                        return self._handle_failure("提示词重新优化失败", prompts_result)
                    
                    rework_result = {"success": True}
                
                if not rework_result.get("success"):
                    return self._handle_failure(f"返工失败: {rework_result.get('error')}", rework_result)
                
                print("\n✅ 返工完成，准备重新进行质量检查...")
                continue
        
        # ==================== 阶段7: 视频生成 ====================
        if not skip_video_gen:
            print("\n" + "="*80)
            print(" 阶段7/8: 视频生成")
            print("="*80)
            print("  视频生成费用: 约20元/次")
            print(" 质量门控已通过,开始生成...")
            
            # [严格]按导演决策执行视频生成
            video_result = self._generate_videos_with_director_decisions(reference_images)
            if not video_result["success"]:
                return self._handle_failure("视频生成失败", video_result)
            
            # ==================== 阶段8: 后期制作 ====================
            print("\n" + "="*80)
            print(" 阶段8/8: 后期制作")
            print("="*80)
            
            post_result = self._post_production(reference_audio)
            if not post_result["success"]:
                return self._handle_failure("后期制作失败", post_result)
        else:
            print("\n" + "="*80)
            print("  阶段7-8: 视频生成和后期制作")
            print("="*80)
            print("  已跳过(测试模式)")
            print()
            print("💡 如需生成视频,请设置 skip_video_gen=False")
        
        # ==================== 完成 ====================
        summary = self._generate_summary()
        
        # 导出所有记录
        self._export_records()
        
        print("\n" + "="*80)
        print(" 流水线完成")
        print("="*80)
        self._print_summary(summary)
        
        return {
            "success": True,
            "session_id": session_id,
            "output_dir": str(self.session_dir),
            "quality_check_passed": self.pipeline_state["quality_check_passed"],
            "director_decisions": self.director_decisions,
            "world": self.world.to_dict() if self.world else None,
            "script": self.script,
            "storyboard": self.storyboard,
            "optimized_shots": self.optimized_shots,
            "summary": summary
        }
    
    # ======================== 阶段实现 ========================
    
    def _build_world(self, story_idea: str, target_format: str, target_duration: int = 60) -> Dict:
        """阶段1: 构建世界观（接收story_idea和目标时长）"""
        context = {
            "story_idea": story_idea,
            "target_format": target_format,
            "target_duration": target_duration,
        }
        
        response = self.world_builder.execute(context)
        
        if response.success:
            self.world = response.data
            world_path = self.session_dir / "01_world.json"
            self.world.save(world_path)
            
            print(f" 世界观构建完成")
            print(f"   - 标题: {self.world.title}")
            genre_str = ", ".join(self.world.genre) if isinstance(self.world.genre, list) else self.world.genre
            print(f"   - 类型: {genre_str}")
            print(f"   - 角色数: {len(self.world.characters)}")
            print(f"   - 场景数: {len(self.world.locations)}")
            
            # 保存到圆桌会议日志
            self.meeting._append_to_log(f"**世界观构建结果**: {self.world.title}")
            self.meeting._append_to_log(f"**角色数**: {len(self.world.characters)}")
            self.meeting._append_to_log(f"**场景数**: {len(self.world.locations)}\n")
            
            return {"success": True}
        else:
            print(f" {response.error}")
            return {"success": False, "error": response.error}
    
    def _write_script(self, target_duration: int) -> Dict:
        """阶段2: 创作剧本（接收story_idea）"""
        context = {
            "world": self.world,
            "target_duration": target_duration,
            "story_idea": self.story_idea  # 传递原始 story_idea
        }
        
        response = self.writer.execute(context)
        
        if response.success:
            self.script = response.data
            script_path = self.session_dir / "02_script.json"
            with open(script_path, 'w', encoding='utf-8') as f:
                json.dump(self.script, f, ensure_ascii=False, indent=2)
            
            # 统计
            total_shots = sum(len(seg.get("shots", [])) for seg in self.script.get("segments", []))
            has_dialogue = False
            for segment in self.script.get("segments", []):
                for shot in segment.get("shots", []):
                    if shot.get("character_dialogue"):
                        has_dialogue = True
                        break
            
            print(f" 剧本创作完成")
            print(f"   - 标题: {self.script.get('title', '未命名')}")
            print(f"   - 时长: {self.script.get('duration', 0)}秒")
            print(f"   - 镜头数: {total_shots}")
            print(f"   - 包含角色对话: {'是' if has_dialogue else '否'}")
            
            if response.warnings:
                print(f"\n  警告:")
                for warning in response.warnings:
                    print(f"   - {warning}")
            
            # 保存到圆桌会议日志
            self.meeting._append_to_log(f"**剧本创作结果**: {self.script.get('title', '未命名')}")
            self.meeting._append_to_log(f"**镜头数**: {total_shots}")
            self.meeting._append_to_log(f"**包含对话**: {'是' if has_dialogue else '否'}\n")
            
            return {"success": True}
        else:
            print(f" {response.error}")
            if response.suggestions:
                print(f"\n💡 建议:")
                for suggestion in response.suggestions:
                    print(f"   - {suggestion}")
            return {"success": False, "error": response.error}
    
    def _design_storyboard(self) -> Dict:
        """阶段3: 设计分镜"""
        context = {
            "script": self.script,
            "world": self.world,
            "visual_style": {},
            "story_idea": self.story_idea  # 【修复】传递story_idea
        }
        
        response = self.storyboard_artist.execute(context)
        
        if response.success:
            self.storyboard = response.data
            storyboard_path = self.session_dir / "03_storyboard.json"
            with open(storyboard_path, 'w', encoding='utf-8') as f:
                json.dump(self.storyboard, f, ensure_ascii=False, indent=2)
            
            print(f" 分镜设计完成")
            print(f"   - 总镜头数: {len(self.storyboard.get('shots', []))}")
            print(f"   - 总时长: {self.storyboard.get('total_duration', 0)}秒")
            
            if response.warnings:
                print(f"\n  警告:")
                for warning in response.warnings:
                    print(f"   - {warning}")
            
            # 保存到圆桌会议日志
            self.meeting._append_to_log(f"**分镜设计结果**: {len(self.storyboard.get('shots', []))}个镜头")
            self.meeting._append_to_log(f"**总时长**: {self.storyboard.get('total_duration', 0)}秒\n")
            
            return {"success": True}
        else:
            print(f" {response.error}")
            return {"success": False, "error": response.error}
    
    def _define_visual_style(self) -> Dict:
        """阶段4: 定义视觉风格"""
        context = {
            "world": self.world,
            "storyboard": self.storyboard,
            "story_idea": self.story_idea  # 【修复】传递story_idea
        }
        
        response = self.cinematographer.execute(context)
        
        if response.success:
            result_data = response.data
            self.visual_dna = result_data.get("visual_dna")
            self.character_bank = result_data.get("character_bank")
            
            if result_data.get("enhanced_storyboard"):
                self.storyboard = result_data["enhanced_storyboard"]
            
            # 保存Visual DNA
            visual_path = self.session_dir / "04_visual_dna.json"
            with open(visual_path, 'w', encoding='utf-8') as f:
                json.dump(self.visual_dna.to_dict(), f, ensure_ascii=False, indent=2)
            
            # 保存Character Bank
            char_path = self.session_dir / "04_character_bank.json"
            with open(char_path, 'w', encoding='utf-8') as f:
                json.dump(self.character_bank.to_dict(), f, ensure_ascii=False, indent=2)
            
            print(f" 视觉风格定义完成")
            print(f"   - VisualDNA: 已保存")
            print(f"   - CharacterBank: 已保存")
            
            # 保存到圆桌会议日志
            self.meeting._append_to_log(f"**视觉风格定义完成**")
            self.meeting._append_to_log(f"**色调**: {', '.join(self.visual_dna.dna.get('color_palette', []))}")
            self.meeting._append_to_log(f"**灯光**: {self.visual_dna.dna.get('lighting', {}).get('type', 'N/A')}\n")
            
            return {"success": True}
        else:
            print(f" {response.error}")
            return {"success": False, "error": response.error}
    
    def _optimize_prompts(self, reference_images: List[str] = None) -> Dict:
        """阶段5: 导演优化提示词(含决策)"""
        context = {
            "storyboard": self.storyboard,
            "visual_dna": self.visual_dna,
            "character_bank": self.character_bank,
            "world": self.world,
            "reference_images": reference_images or [],
            "story_idea": self.story_idea  # 【修复】传递story_idea
        }
        
        response = self.director.execute(context)
        
        if response.success:
            result_data = response.data
            
            # [新增]应用开幕式特殊优化
            if self.pipeline_state.get("is_opening_ceremony"):
                print("\n 检测到开幕式主题,应用特殊优化...")
                shots = result_data.get("shots", [])
                optimized_shots = self._apply_opening_ceremony_optimization(shots)
                result_data["shots"] = optimized_shots
            
            self.optimized_shots = result_data
            
            # [关键]提取导演决策
            self.director_decisions = result_data.get("director_decisions", {
                "frame_inheritance": {},
                "multi_reference_images": {},
                "quality_approval": False
            })
            
            # 保存优化后的提示词
            prompts_path = self.session_dir / "05_prompts.json"
            with open(prompts_path, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            
            # 保存导演决策
            decisions_path = self.session_dir / "05_director_decisions.json"
            with open(decisions_path, 'w', encoding='utf-8') as f:
                json.dump(self.director_decisions, f, ensure_ascii=False, indent=2)
            
            # 统计
            shots = result_data.get("shots", [])
            frame_inherit_count = sum(1 for d in self.director_decisions.get("frame_inheritance", {}).values() if d)
            multi_ref_count = sum(1 for refs in self.director_decisions.get("multi_reference_images", {}).values() if len(refs) > 1)
            
            print(f" 导演提示词优化完成")
            print(f"   - 镜头数: {len(shots)}")
            print(f"   - 帧继承镜头: {frame_inherit_count}个")
            print(f"   - 多角色参考图: {multi_ref_count}个")
            
            # [新增]如果开幕式优化成功,标记日志
            if self.pipeline_state.get("is_opening_ceremony"):
                opening_optimized = any(s.get("opening_ceremony_optimized") for s in shots)
                if opening_optimized:
                    print(f"   - 开幕式优化: ✓ 已应用到第一个镜头")
            
            # 保存到圆桌会议日志
            self.meeting._append_to_log(f"**导演优化结果**: {len(shots)}个镜头")
            self.meeting._append_to_log(f"**帧继承决策**: {frame_inherit_count}个镜头需要继承")
            self.meeting._append_to_log(f"**多角色参考图**: {multi_ref_count}个镜头使用多参考图")
            self.meeting._append_to_log(f"\n**导演决策详情**:\n```json\n{json.dumps(self.director_decisions, ensure_ascii=False, indent=2)}\n```\n")
            
            return {"success": True}
        else:
            print(f" {response.error}")
            return {"success": False, "error": response.error}
    
    def _quality_gate_check(self) -> Dict:
        """
        阶段6: [关键]质量门控检查
        
        使用独立的QualityInspector进行专业评审
        
        检查内容:
        1. 所有镜头的提示词质量（使用专业评审员）
        2. 导演决策完整性
        3. 帧继承策略合理性
        4. 摄影决策语言检查（避免物体清单）
        5. 运镜六要素检查
        6. 负向提示词翻译检查
        7. 色彩策略限制检查（3-5色原则）
        8. 台词匹配检查
        
        Returns:
            {
                "passed": bool,
                "score": float,
                "issues": List[str],
                "suggestions": List[str],
                "warnings": List[str],
                "detailed_review": str
            }
        """
        issues = []
        suggestions = []
        warnings = []
        
        print("\n 开始质量门控检查...")
        print("   使用专业质量检查员进行评审...")
        
        # 1. 基础检查：镜头数量
        shots = self.optimized_shots.get("shots", []) if self.optimized_shots else []
        if not shots:
            issues.append("没有可用的镜头数据")
            return {
                "passed": False,
                "score": 0.0,
                "issues": issues,
                "suggestions": ["请确保前序阶段正确完成"],
                "warnings": [],
                "detailed_review": "缺少镜头数据，无法进行质量评审"
            }
        
        print(f"   ✓ 镜头数量: {len(shots)}")
        
        # 2. 使用QualityInspector进行专业评审（必须成功，不使用try-except）
        # 构建完整上下文
        full_context = {
            "world": self.world.to_dict() if self.world else None,
            "script": self.script,
            "storyboard": self.storyboard,
            "visual_dna": self.visual_dna.to_dict() if self.visual_dna else None,
            "character_bank": self.character_bank.to_dict() if self.character_bank else None,
            "director_decisions": self.director_decisions,
            "optimized_shots": self.optimized_shots
        }
        
        # 调用质量检查员对prompts阶段进行评审（不捕获异常，让错误向上传播）
        print("   📋 调用质量检查员进行评审...")
        inspection_result = self.quality_inspector.inspect(
            stage="prompts",
            data=self.optimized_shots,
            context=full_context
        )
        
        passed = inspection_result.get("pass", False)
        score = inspection_result.get("score", 0.0)
        threshold = inspection_result.get("threshold", 0.75)
        detailed_review = inspection_result.get("detailed_review", "")
        dimension_scores = inspection_result.get("dimension_scores", {})
        inspector_issues = inspection_result.get("issues", [])
        inspector_suggestions = inspection_result.get("suggestions", [])
        approval_reason = inspection_result.get("approval_reason", "")
        
        # 合并质量检查员的发现
        issues.extend(inspector_issues)
        suggestions.extend(inspector_suggestions)
        
        print(f"   ✓ 质量检查员评审完成")
        print(f"     - 综合评分: {score:.2f}/{threshold}")
        print(f"     - 评审结果: {'✅ 通过' if passed else '❌ 不通过'}")
        
        # 显示各维度得分
        if dimension_scores:
            print(f"     - 维度评分:")
            for dim_name, dim_score in dimension_scores.items():
                status = '✅' if dim_score >= 0.65 else '⚠️' if dim_score >= 0.5 else '❌'
                print(f"       • {dim_name}: {dim_score:.2f} {status}")
        
        # 3. 基础结构检查（补充）
        for shot in shots:
            shot_num = shot.get("shot_number", "?")
            visual_prompt = shot.get("visual_prompt", "")
            
            # 检查提示词长度
            if len(visual_prompt) < 50:
                warnings.append(f"镜头{shot_num}: 提示词过短({len(visual_prompt)}字符)")
            
            # 检查台词匹配
            dialogue = shot.get("character_dialogue") or {}  # 修复：可能为None
            if dialogue.get("text"):
                if not any(keyword in visual_prompt for keyword in ["台词", "口型", "说话", "对话"]):
                    warnings.append(f"镜头{shot_num}: 有对话但提示词中未包含台词描述")
        
        # 4. 检查导演决策完整性
        if not self.director_decisions:
            issues.append("缺少导演决策数据")
        else:
            print(f"   ✓ 导演决策数据完整")
            
            # 检查帧继承决策
            frame_inherit = self.director_decisions.get("frame_inheritance", {})
            if frame_inherit:
                inherit_count = sum(1 for v in frame_inherit.values() if v)
                inherit_ratio = inherit_count / len(frame_inherit) if frame_inherit else 0
                print(f"   ✓ 帧继承策略: {inherit_count}/{len(frame_inherit)}个镜头 ({inherit_ratio:.1%})")
                
                # 检查帧继承比例是否合理
                if inherit_ratio < 0.2:
                    warnings.append(f"帧继承比例较低({inherit_ratio:.1%})，可能影响角色一致性")
                elif inherit_ratio > 0.9:
                    warnings.append(f"帧继承比例过高({inherit_ratio:.1%})，可能存在误判")
            else:
                suggestions.append("建议为每个镜头明确设置帧继承策略")
            
            # 检查多角色参考图决策
            multi_ref = self.director_decisions.get("multi_reference_images", {})
            if multi_ref:
                multi_count = sum(1 for refs in multi_ref.values() if len(refs) > 1)
                print(f"   ✓ 多角色参考图: {multi_count}个镜头使用")
        
        # 5. 最终判定 - 基于质量检查员的严格评审
        # 保持严格：总分达标且无严重问题才通过
        final_passed = passed
        
        result = {
            "passed": final_passed,
            "score": score,
            "issues": issues,
            "suggestions": suggestions,
            "warnings": warnings,
            "detailed_review": detailed_review,
            "dimension_scores": dimension_scores,
            "approval_reason": approval_reason if final_passed else "质量检查未通过，需要返工"
        }
        
        # 保存到会议日志
        self.meeting._append_to_log(f"##  质量门控最终检查\n\n")
        self.meeting._append_to_log(f"**评审结果**: {' 通过' if final_passed else ' 不通过'}\n")
        self.meeting._append_to_log(f"**综合评分**: {score:.2f}\n")
        
        if dimension_scores:
            self.meeting._append_to_log(f"\n**各维度评分**:\n")
            for dim_name, dim_score in dimension_scores.items():
                status = '' if dim_score >= 0.6 else ''
                self.meeting._append_to_log(f"- {dim_name}: {dim_score:.2f} {status}\n")
        
        if detailed_review:
            self.meeting._append_to_log(f"\n**详细评审**:\n{detailed_review}\n")
        
        if issues:
            self.meeting._append_to_log(f"\n**严重问题**:\n")
            for i, issue in enumerate(issues, 1):
                self.meeting._append_to_log(f"{i}. {issue}\n")
        
        if warnings:
            self.meeting._append_to_log(f"\n**警告**:\n")
            for i, w in enumerate(warnings, 1):
                self.meeting._append_to_log(f"{i}. {w}\n")
        
        if suggestions:
            self.meeting._append_to_log(f"\n**改进建议**:\n")
            for i, s in enumerate(suggestions, 1):
                self.meeting._append_to_log(f"{i}. {s}\n")
        
        if final_passed:
            self.meeting._append_to_log(f"\n**通过理由**: {approval_reason}\n")
            self.meeting._append_to_log(f"\n **质量门控通过，允许进入视频生成阶段**\n")
        else:
            self.meeting._append_to_log(f"\n **质量门控不通过，需要返工修改**\n")
        
        self.meeting._append_to_log("\n---\n\n")
        
        return result
    
    def _generate_videos_with_director_decisions(self, reference_images: List[str] = None) -> Dict:
        """
        阶段7: [严格]按导演决策生成视频
        
        严格按导演的决策执行:
        1. 帧继承策略
        2. 多角色参考图策略
        3. 每个镜头的具体参数
        4. 【关键】检查all_generated标志，确保所有视频生成完毕
        """
        print("\n 开始视频生成(严格按导演决策执行)...")
        print(f"  当前余额: 请确保余额充足(约20元/镜头)")
        print()
        
        # 验证质量门控
        if not self.pipeline_state.get("video_generation_allowed"):
            print(" 错误: 质量门控未通过,禁止生成视频")
            return {"success": False, "error": "质量门控未通过"}
        
        # 构建上下文,严格包含导演决策
        context = {
            "shots": self.optimized_shots.get("shots", []) if self.optimized_shots else [],
            "director_decisions": self.director_decisions,
            "reference_images": reference_images or [],
            "output_dir": str(self.session_dir / "videos"),
            "skip_video_gen": self.skip_video_gen,  # 【关键修复】传递skip_video_gen参数
            "start_shot": self.pipeline_state.get("video_start_shot", 1),
            "previous_video_path": self.pipeline_state.get("previous_video_path"),
        }
        # 构建完成后直接进入视频生成，不在生产流程中暂停调试。
        # 保存导演决策到日志
        self.meeting._append_to_log(f"## 视频生成开始\n")
        self.meeting._append_to_log(f"**严格按导演决策执行**:\n")
        self.meeting._append_to_log(f"- 帧继承策略: {self.director_decisions.get('frame_inheritance', {})}\n")
        self.meeting._append_to_log(f"- 多角色参考图: {self.director_decisions.get('multi_reference_images', {})}\n")
        self.meeting._append_to_log(f"- skip_video_gen: {self.skip_video_gen} (False=实际生成, True=Mock模式)\n")
        self.meeting._append_to_log("---\n\n")
        
        response = self.video_generator.execute(context)
        
        if response.success:
            result_data = response.data
            
            # 【关键】检查是否所有视频都生成完毕
            all_generated = result_data.get("all_generated", False)
            videos = result_data.get("videos", [])
            succeeded = result_data.get("succeeded", 0)
            failed = result_data.get("failed", 0)
            total = result_data.get("total", 0)
            
            print(f"\n 视频生成完成")
            print(f"   - 成功: {succeeded}/{total}")
            print(f"   - 失败: {failed}/{total}")
            
            # 【关键】如果有视频生成失败，阻止进入下一环节
            if not all_generated:
                warning_msg = f" 警告: 有 {failed} 个镜头未能成功生成，已达最大重试次数"
                print(f"\n{warning_msg}")
                print(" 视频生成未完全完成，阻止进入后期制作环节")
                
                # 记录到日志
                self.meeting._append_to_log(f"##  视频生成未完全完成\n\n")
                self.meeting._append_to_log(f"**失败镜头**: {[v.get('shot_number') for v in videos if v.get('status') != 'success']}\n")
                self.meeting._append_to_log(f"**原因**: 已达最大重试次数\n")
                self.meeting._append_to_log("---\n\n")
                
                return {
                    "success": False,
                    "error": f"视频生成未完全完成: {failed}/{total} 个镜头失败",
                    "data": result_data,
                    "incomplete": True
                }
            
            # 保存视频结果
            video_path = self.session_dir / "06_video_results.json"
            with open(video_path, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            
            self.video_files = videos
            
            # 保存到日志
            self.meeting._append_to_log(f"## 视频生成结果\n")
            self.meeting._append_to_log(f"**成功**: {succeeded}/{total}\n")
            self.meeting._append_to_log(f"**所有镜头已完成**: \n")
            self.meeting._append_to_log("---\n\n")
            
            return {"success": True, "data": result_data}
        else:
            print(f" {response.error}")
            return {"success": False, "error": response.error}
    
    def _post_production(self, reference_audio: str = None) -> Dict:
        """阶段8: 后期制作"""
        print("\n 开始后期制作...")
        
        # 从optimized_shots中提取shots列表
        shots = self.optimized_shots.get("shots", []) if self.optimized_shots else []
        
        context = {
            "video_files": self.video_files,
            "shots": shots,  # 【修复】传递shots而不是optimized_shots
            "optimized_shots": self.optimized_shots,
            "reference_audio": reference_audio,
            "output_dir": str(self.session_dir)
        }
        
        response = self.post_production.execute(context)
        
        if response.success:
            result_data = response.data
            
            # 保存后期结果
            post_path = self.session_dir / "07_post_production.json"
            with open(post_path, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            
            print(f" 后期制作完成")
            print(f"   - 最终视频: {result_data.get('final_video', 'N/A')}")
            
            return {"success": True, "data": result_data}
        else:
            print(f" {response.error}")
            return {"success": False, "error": response.error}
    
    # ======================== 辅助方法 ========================
    
    def _conduct_meeting(self, topic: str, context: Dict):
        """召开圆桌会议 - 使用独立质量检查员进行评审"""
        if not self.meeting:
            return
        
        # 记录会议开始
        self.meeting._append_to_log(f"## [{topic}]\n")
        self.meeting._append_to_log(f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # 收集各方意见和评审
        opinions = []
        
        # WorldBuilder意见
        if context.get("world"):
            self.meeting._append_to_log("### [世界观构建师]\n")
            if isinstance(context["world"], dict):
                characters = context["world"].get("characters", {})
                locations = context["world"].get("locations", {})
                self.meeting._append_to_log(f"- 角色数: {len(characters)}\n")
                self.meeting._append_to_log(f"- 场景数: {len(locations)}\n")
            self.meeting._append_to_log(f"**初步意见**: 世界观设定完整,角色关系清晰\n")
            self.meeting._append_to_log(f"**状态**:  已完成\n\n")
        
        # Writer意见
        if context.get("script"):
            self.meeting._append_to_log("### [编剧]\n")
            shots = []
            for seg in context["script"].get("segments", []):
                shots.extend(seg.get("shots", []))
            dialogues = sum(1 for s in shots if s.get("character_dialogue"))
            self.meeting._append_to_log(f"- 镜头数: {len(shots)}\n")
            self.meeting._append_to_log(f"- 有对话镜头: {dialogues}\n")
            self.meeting._append_to_log(f"**初步意见**: 剧本叙事流畅,情感节奏控制良好\n")
            self.meeting._append_to_log(f"**状态**:  已完成\n\n")
        
        # Cinematographer意见
        if context.get("visual_dna") or context.get("character_bank"):
            self.meeting._append_to_log("### [摄影指导]\n")
            self.meeting._append_to_log(f"**初步意见**: 视觉风格统一,光影设计服务于叙事\n")
            self.meeting._append_to_log(f"**状态**:  已完成\n\n")
        
        # Director意见(关键)
        if context.get("director_decisions"):
            self.meeting._append_to_log("### [导演]\n")
            decisions = context["director_decisions"]
            
            # 详细记录帧继承决策的理由
            frame_inherit = decisions.get('frame_inheritance', {})
            inherit_count = sum(1 for v in frame_inherit.values() if v)
            total_shots = len(frame_inherit)
            
            self.meeting._append_to_log(f"**帧继承决策分析**:\n")
            self.meeting._append_to_log(f"- 启用帧继承: {inherit_count}/{total_shots}个镜头\n")
            self.meeting._append_to_log(f"- 决策依据: 基于场景切换分析, 角色一致性评估\n")
            
            frame_reasons = decisions.get('frame_inheritance_reasons', {})
            for shot_num, use_inherit in frame_inherit.items():
                decision_detail = frame_reasons.get(str(shot_num), frame_reasons.get(shot_num, {}))
                if isinstance(decision_detail, dict):
                    reason = decision_detail.get("reason", "未提供判定原因")
                    source = decision_detail.get("source", "unknown")
                    continuity = decision_detail.get("scene_continuous", use_inherit)
                    reason_text = f"{reason}（连续性={str(bool(continuity)).lower()}，来源={source}）"
                else:
                    reason_text = str(decision_detail)
                self.meeting._append_to_log(
                    f"  - 镜头{shot_num}: {'继承' if use_inherit else '不继承'} - {reason_text}\n"
                )
            
            self.meeting._append_to_log(f"**质量批准**: {'是' if decisions.get('quality_approval') else '否'}\n")
            self.meeting._append_to_log(f"**状态**:  已完成\n\n")
        
        # [关键]调用独立质量检查员进行专业评审
        self.meeting._append_to_log("###  质量门控检查员评审\n\n")
        
        # 确定当前评审阶段
        stage_map = {
            "世界观构建": "world_building",
            "剧本创作": "script",
            "分镜设计": "storyboard",
            "导演决策和提示词优化": "director_decisions",
            "视频生成质量门控": "prompts"
        }
        stage = stage_map.get(topic, "unknown")
        
        # 构建评审数据
        if stage == "world_building":
            review_data = context.get("world", {})
        elif stage == "script":
            review_data = context.get("script", {})
        elif stage == "storyboard":
            review_data = context.get("storyboard", {})
        elif stage == "director_decisions":
            review_data = context.get("director_decisions", {})
        elif stage == "prompts":
            review_data = context.get("prompts", {})
        else:
            review_data = {}
        
        # 调用质量检查员
        # 【关键修复】质量检查必须成功，不可回退到基础模式
        max_retry_attempts = 3
        inspection_result = None
        last_error = None
        
        for attempt in range(max_retry_attempts):
            try:
                print(f"[质量检查] 尝试第 {attempt + 1}/{max_retry_attempts} 次...")
                inspection_result = self.quality_inspector.inspect(
                    stage=stage,
                    data=review_data,
                    context=context
                )
                
                # 【关键】检查是否所有评分都为1.0（异常情况）
                dimension_scores = inspection_result.get('dimension_scores', {})
                if dimension_scores:
                    all_ones = all(score == 1.0 for score in dimension_scores.values())
                    if all_ones and len(dimension_scores) > 0:
                        raise ValueError("检测到异常评分：所有维度评分均为1.0，评审无效")
                
                # 成功获取评审结果
                print(f"[质量检查] 第 {attempt + 1} 次尝试成功")
                break
                
            except Exception as e:
                last_error = e
                print(f"⚠️ [质量检查] 第 {attempt + 1} 次尝试失败: {e}")
                if attempt < max_retry_attempts - 1:
                    import time
                    time.sleep(2)  # 等待2秒后重试
                continue
        
        # 【关键】如果所有重试都失败，必须中断流程
        if inspection_result is None:
            error_msg = f"质量检查失败：已重试{max_retry_attempts}次，最后错误：{last_error}"
            print(f"\n❌ {error_msg}")
            self.meeting._append_to_log(f"**评审失败**: {error_msg}\n")
            self.meeting._append_to_log("**流程中断**: 质量检查系统不可用，无法继续\n\n")
            raise RuntimeError(error_msg)
        
        # 记录评审结果
        passed = inspection_result.get('pass', False)
        score = inspection_result.get('score', 0)
        threshold = inspection_result.get('threshold', 0.7)
        detailed_review = inspection_result.get('detailed_review', '')
        issues = inspection_result.get('issues', [])
        suggestions = inspection_result.get('suggestions', [])
        
        decision_symbol = '✓' if passed else '✗'
        self.meeting._append_to_log(f"**评审结果**: {decision_symbol} {'通过' if passed else '不通过'}\n")
        self.meeting._append_to_log(f"**综合评分**: {score:.2f} (阈值: {threshold})\n\n")
        
        # 记录各维度得分
        dimension_scores = inspection_result.get('dimension_scores', {})
        if dimension_scores:
            self.meeting._append_to_log("**各维度评分**:\n")
            for dim_name, dim_score in dimension_scores.items():
                status = '✓' if dim_score >= 0.6 else '✗'
                self.meeting._append_to_log(f"- {dim_name}: {dim_score:.2f} {status}\n")
            self.meeting._append_to_log("\n")
        
        # 记录详细评审意见
        if detailed_review:
            self.meeting._append_to_log("**详细评审**:\n")
            self.meeting._append_to_log(f"{detailed_review}\n\n")
        
        # 记录发现的问题
        if issues:
            self.meeting._append_to_log("**发现的问题**:\n")
            for i, issue in enumerate(issues, 1):
                self.meeting._append_to_log(f"{i}. {issue}\n")
            self.meeting._append_to_log("\n")
        
        # 记录改进建议
        if suggestions:
            self.meeting._append_to_log("**改进建议**:\n")
            for i, suggestion in enumerate(suggestions, 1):
                self.meeting._append_to_log(f"{i}. {suggestion}\n")
            self.meeting._append_to_log("\n")
        
        # 生成通过理由（如果通过）
        if passed:
            approval_reason = self._generate_approval_reason(topic, context)
            self.meeting._append_to_log(f"**通过理由**: {approval_reason}\n\n")
            self.meeting._append_to_log("**评审有效性**: ✓ 质量检查员进行了详细的多维度评审，评审过程有意义\n\n")
        else:
            self.meeting._append_to_log("**不通过原因**: 未达到质量标准，需要重新制作\n\n")
        
        print(f"\n[MEETING] {topic} - {decision_symbol} {'通过' if passed else '不通过'} (评分: {score:.2f}/{threshold})")
        
        self.meeting._append_to_log("\n---\n\n")
    

    def _generate_approval_reason(self, topic: str, context: Dict) -> str:
        """生成通过理由"""
        
        reasons = []
        
        if "世界观" in topic:
            reasons.append("世界观设定完整,角色和场景设计清晰")
            reasons.append("符合目标平台的风格要求")
        elif "剧本" in topic:
            reasons.append("剧本叙事结构完整,情感节奏控制良好")
            reasons.append("包含足够的对话和动作描写")
        elif "分镜" in topic:
            reasons.append("分镜设计专业,景别变化丰富")
            reasons.append("运镜方式合理服务于叙事")
        elif "视觉" in topic:
            reasons.append("视觉风格统一,色彩和光影设计服务于叙事主题")
            reasons.append("角色一致性机制完善")
        elif "导演决策" in topic:
            decisions = context.get("director_decisions", {})
            frame_inherit = decisions.get('frame_inheritance', {})
            inherit_count = sum(1 for v in frame_inherit.values() if v)
            total = len(frame_inherit)
            
            reasons.append(f"帧继承策略合理:{inherit_count}/{total}个镜头启用继承")
            reasons.append("导演对场景切换和角色变化进行了认真分析")
            reasons.append("提示词优化专业,兼顾视觉描述和叙事意图")
        
        return ";".join(reasons)
    
    def _log_input_params(self, story_idea: str, target_duration: int, 
                          reference_images: List[str], reference_audio: str):
        """记录输入参数到日志"""
        if not self.meeting:
            return
        
        self.meeting._append_to_log("# 圆桌会议讨论日志\n")
        self.meeting._append_to_log(f"**流水线启动时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.meeting._append_to_log(f"**目标时长**: {target_duration}秒\n")
        self.meeting._append_to_log(f"**参考图片**: {reference_images or '无'}\n")
        self.meeting._append_to_log(f"**参考音频**: {reference_audio or '无'}\n")
        self.meeting._append_to_log(f"\n**故事想法**:\n{story_idea[:200]}...\n")
        self.meeting._append_to_log("---\n\n")
    
    def _export_records(self):
        """导出所有记录"""
        if not self.meeting:
            return
        
        # 导出JSON格式的会议记录
        meeting_transcript = self.session_dir / "meeting_transcript.json"
        self.meeting.export_transcript(meeting_transcript)
        
        # 导出工作流报告
        if self.workflow:
            workflow_report = self.session_dir / "workflow_report.json"
            with open(workflow_report, 'w', encoding='utf-8') as f:
                json.dump(self.workflow.get_workflow_report(), f, ensure_ascii=False, indent=2)
    
    def _handle_failure(self, stage: str, result: Dict) -> Dict:
        """处理失败情况"""
        print(f"\n {stage}")
        print(f"错误: {result.get('error', '未知错误')}")
        
        self.pipeline_state["errors"].append({
            "stage": stage,
            "error": result.get("error")
        })
        
        return {
            "success": False,
            "stage": stage,
            "error": result.get("error"),
            "output_dir": str(self.session_dir) if self.session_dir else None
        }
    
    def _handle_quality_failure(self, quality_result: Dict) -> Dict:
        """
        【关键】处理质量检查失败 - 形成闭环反馈
        
        将质量问题反馈给相关Agent，触发返工机制
        """
        print("\n🔄 质量检查失败，启动返工机制...")
        
        # 根据问题类型决定重试策略
        issues = quality_result.get("issues", [])
        suggestions = quality_result.get("suggestions", [])
        dimension_scores = quality_result.get("dimension_scores", {})
        
        # 记录到会议日志
        self.meeting._append_to_log(f"\n##  质量门控失败 - 第{self.pipeline_state['retry_count'].get('quality_gate', 0) + 1}次\n\n")
        self.meeting._append_to_log(f"**发现的问题**:\n")
        for issue in issues:
            self.meeting._append_to_log(f"- {issue}\n")
        self.meeting._append_to_log(f"\n**改进建议**:\n")
        for suggestion in suggestions:
            self.meeting._append_to_log(f"- {suggestion}\n")
        self.meeting._append_to_log("\n---\n\n")
        
        # 分析问题类型，决定返工策略
        rework_strategy = self._analyze_quality_issues(issues, dimension_scores)
        
        print(f"\n📋 返工策略: {rework_strategy['target_stage']}")
        print(f"   原因: {rework_strategy['reason']}")
        
        # 根据策略执行返工
        if rework_strategy['target_stage'] == 'prompt_optimization':
            print("\n🔄 重新执行提示词优化...")
            return self._rework_prompt_optimization(quality_result)
        elif rework_strategy['target_stage'] == 'storyboard':
            print("\n🔄 重新执行分镜设计...")
            return self._rework_storyboard(quality_result)
        elif rework_strategy['target_stage'] == 'script':
            print("\n🔄 重新执行剧本创作...")
            return self._rework_script(quality_result)
        elif rework_strategy['target_stage'] == 'round_table':
            print("\n🔄 重新启动圆桌讨论...")
            return self._rework_round_table(quality_result)
        else:
            # 不应该到这里，但作为保险
            print("\n⚠️ 未知的返工策略，回退到圆桌讨论...")
            return self._rework_round_table(quality_result)
    
    def _determine_rework_target(self, quality_result: Dict) -> Dict:
        """
        根据质量检查结果决定返工目标
        
        Args:
            quality_result: 质量检查结果
            
        Returns:
            {
                "target_stage": "prompt_optimization" | "round_table",
                "reason": "原因说明"
            }
        """
        issues = quality_result.get("issues", [])
        dimension_scores = quality_result.get("dimension_scores", {})
        return self._analyze_quality_issues(issues, dimension_scores)
    
    def _analyze_quality_issues(self, issues: List[str], dimension_scores: Dict) -> Dict:
        """
        分析质量问题，决定返工策略
        
        Returns:
            {
                "target_stage": "prompt_optimization" | "storyboard" | "script" | "round_table",
                "reason": "原因说明"
            }
        """
        # 优先检查维度评分（更精确的指标）
        # 注意：使用QualityInspector实际返回的维度名称
        # 阈值设置为0.70，与QualityInspector的PASS_THRESHOLD一致
        DIMENSION_THRESHOLD = 0.70
        
        print(f"\n🔍 分析返工目标...")
        print(f"   维度评分: {dimension_scores}")
        print(f"   问题列表: {issues}")
        
        if dimension_scores:
            # 找出所有低于阈值的维度
            low_dimensions = {}
            for dim_name, dim_score in dimension_scores.items():
                if dim_score < DIMENSION_THRESHOLD:
                    low_dimensions[dim_name] = dim_score
            
            print(f"   低于阈值的维度: {low_dimensions}")
            
            # 策略1: 如果只有提示词相关维度问题，只返工提示词
            prompt_only_dims = ["visual_unity", "shot_language", "technical_completeness"]
            prompt_issues = {k: v for k, v in low_dimensions.items() if k in prompt_only_dims}
            other_issues = {k: v for k, v in low_dimensions.items() if k not in prompt_only_dims}
            
            if prompt_issues and not other_issues:
                # 只有提示词问题
                dim_desc = ", ".join([f"{k}({v:.2f})" for k, v in prompt_issues.items()])
                return {
                    "target_stage": "prompt_optimization",
                    "reason": f"{dim_desc} 低于阈值，只需重新优化提示词"
                }
            
            # 策略2: 如果有故事连续性问题，需要全流程返工
            if "story_continuity" in low_dimensions:
                return {
                    "target_stage": "round_table",
                    "reason": f"故事连续性({low_dimensions['story_continuity']:.2f})不足，需要重新圆桌讨论"
                }
            
            # 策略3: 如果有角色/逻辑一致性问题，可能需要重新分镜或圆桌
            consistency_dims = ["character_consistency", "logical_consistency"]
            consistency_issues = {k: v for k, v in low_dimensions.items() if k in consistency_dims}
            
            if consistency_issues:
                # 检查分数是否非常低（<0.5），如果是则需要圆桌讨论
                min_consistency = min(consistency_issues.values())
                if min_consistency < 0.5:
                    dim_desc = ", ".join([f"{k}({v:.2f})" for k, v in consistency_issues.items()])
                    return {
                        "target_stage": "round_table",
                        "reason": f"{dim_desc} 严重不足(< 0.5)，需要重新圆桌讨论"
                    }
                else:
                    # 分数在0.5-0.7之间，可能是分镜问题，也可能是提示词问题
                    # 如果同时有提示词问题，优先认为是提示词导致的
                    if prompt_issues:
                        all_dims = ", ".join([f"{k}({v:.2f})" for k, v in low_dimensions.items()])
                        return {
                            "target_stage": "prompt_optimization",
                            "reason": f"{all_dims} 不足，优先优化提示词"
                        }
                    else:
                        dim_desc = ", ".join([f"{k}({v:.2f})" for k, v in consistency_issues.items()])
                        return {
                            "target_stage": "round_table",
                            "reason": f"{dim_desc} 不足，需要重新讨论分镜和角色设计"
                        }
        
        # 检查具体问题描述中的关键词（作为补充判断）
        if issues:
            issues_text = " ".join(issues)
            print(f"   问题文本: {issues_text}")
            
            # 提示词问题关键词
            prompt_keywords = ["提示词", "视觉描述", "负向提示", "prompt", "描述不足", "画面质量", "visual_unity", "shot_language", "technical_completeness"]
            
            # 一致性问题关键词
            consistency_keywords = ["一致性", "角色", "逻辑", "衔接", "连续", "character_consistency", "logical_consistency", "story_continuity"]
            
            has_prompt_keywords = any(kw in issues_text for kw in prompt_keywords)
            has_consistency_keywords = any(kw in issues_text for kw in consistency_keywords)
            
            if has_prompt_keywords and not has_consistency_keywords:
                return {
                    "target_stage": "prompt_optimization",
                    "reason": "问题主要集中在提示词质量"
                }
            elif has_consistency_keywords:
                return {
                    "target_stage": "round_table",
                    "reason": "涉及一致性问题，需要重新圆桌讨论"
                }
        
        # 如果有问题但无法精确定位，默认重新优化提示词（最轻量的返工）
        if issues:
            return {
                "target_stage": "prompt_optimization",
                "reason": "问题不明确，尝试重新优化提示词"
            }
        
        # 没有问题但评分不够，回退到圆桌讨论
        return {
            "target_stage": "round_table",
            "reason": "评分不达标但无具体问题，需要全面审查"
        }
    
    def _rework_prompt_optimization(self, quality_result: Dict) -> Dict:
        """
        返工：重新执行提示词优化
        
        将质量反馈作为上下文传递给Prompt优化Agent
        """
        print("\n🔄 返工阶段: 提示词优化")
        print(" 质量反馈已传递给Prompt优化Agent...")
        
        # 构建包含质量反馈的上下文
        context = {
            "storyboard": self.storyboard,
            "visual_dna": self.visual_dna,
            "character_bank": self.character_bank.to_dict() if self.character_bank else None,
            "quality_feedback": {
                "issues": quality_result.get("issues", []),
                "suggestions": quality_result.get("suggestions", []),
                "dimension_scores": quality_result.get("dimension_scores", {}),
                "detailed_review": quality_result.get("detailed_review", "")
            },
            "rework": True,
            "retry_count": self.pipeline_state["retry_count"].get("quality_gate", 0)
        }
        
        # 重新执行提示词优化（使用Director）
        response = self.director.execute(context)
        
        if response.success:
            result_data = response.data
            self.optimized_shots = result_data
            
            # 提取导演决策（和_optimize_prompts保持一致）
            self.director_decisions = result_data.get("director_decisions", {
                "frame_inheritance": {},
                "multi_reference_images": {},
                "quality_approval": False
            })
            
            # 保存优化结果
            prompts_path = self.session_dir / "05_prompts.json"
            with open(prompts_path, 'w', encoding='utf-8') as f:
                json.dump(self.optimized_shots, f, ensure_ascii=False, indent=2)
            
            print(" 提示词优化完成（返工）")
            print(f"   - 导演决策已提取: {len(self.director_decisions.get('frame_inheritance', {}))} 个镜头")
            
            # 继续执行质量门控（递归检查）
            return {"success": True, "continue_to_quality_gate": True}
        else:
            return {"success": False, "error": f"提示词优化返工失败: {response.error}"}
    
    def _rework_storyboard(self, quality_result: Dict) -> Dict:
        """
        返工：重新执行分镜设计
        
        将质量反馈传递给分镜设计Agent
        """
        print("\n🔄 返工阶段: 分镜设计")
        print(" 质量反馈已传递给分镜设计Agent...")
        
        # 构建包含质量反馈的上下文
        context = {
            "script": self.script,
            "world": self.world,
            "quality_feedback": {
                "issues": quality_result.get("issues", []),
                "suggestions": quality_result.get("suggestions", []),
                "dimension_scores": quality_result.get("dimension_scores", {})
            },
            "rework": True
        }
        
        # 重新执行分镜设计
        response = self.storyboard_artist.execute(context)
        
        if response.success:
            self.storyboard = response.data
            
            # 保存分镜
            storyboard_path = self.session_dir / "03_storyboard.json"
            with open(storyboard_path, 'w', encoding='utf-8') as f:
                json.dump(self.storyboard, f, ensure_ascii=False, indent=2)
            
            print(" 分镜设计完成（返工）")
            
            # 需要重新执行后续所有阶段
            print("\n 阶段4(续): 视觉DNA和角色库")
            visual_dna_result = self._visual_dna_and_character_bank()
            if not visual_dna_result["success"]:
                return visual_dna_result
            
            print("\n 阶段5(续): 提示词优化")
            prompt_result = self._optimize_prompts()
            if not prompt_result["success"]:
                return prompt_result
            
            # 导演决策已经在_optimize_prompts中完成
            print(f"   - 导演决策已提取: {len(self.director_decisions.get('frame_inheritance', {}))} 个镜头")
            
            # 继续执行质量门控（递归检查）
            return {"success": True, "continue_to_quality_gate": True}
        else:
            return {"success": False, "error": f"分镜设计返工失败: {response.error}"}
    
    def _rework_script(self, quality_result: Dict) -> Dict:
        """
        返工：重新执行剧本创作
        
        将质量反馈传递给编剧Agent
        """
        print("\n🔄 返工阶段: 剧本创作")
        print("   质量反馈已传递给编剧Agent...")
        
        # 构建包含质量反馈的上下文
        context = {
            "world": self.world,
            "story_idea": self.story_idea,
            "quality_feedback": {
                "issues": quality_result.get("issues", []),
                "suggestions": quality_result.get("suggestions", []),
                "dimension_scores": quality_result.get("dimension_scores", {})
            },
            "rework": True
        }
        
        # 重新执行剧本创作
        response = self.writer.execute(context)
        
        if response.success:
            self.script = response.data
            
            # 保存剧本
            script_path = self.session_dir / "02_script.json"
            with open(script_path, 'w', encoding='utf-8') as f:
                json.dump(self.script, f, ensure_ascii=False, indent=2)
            
            print("   ✓ 剧本创作完成（返工）")
            
            # 需要重新执行后续所有阶段
            print("\n📋 阶段3(续): 分镜设计")
            storyboard_result = self._storyboard_design()
            if not storyboard_result["success"]:
                return storyboard_result
            
            print("\n🎨 阶段4(续): 视觉DNA和角色库")
            visual_dna_result = self._visual_dna_and_character_bank()
            if not visual_dna_result["success"]:
                return visual_dna_result
            
            print("\n✨ 阶段5(续): 提示词优化")
            prompt_result = self._optimize_prompts()
            if not prompt_result["success"]:
                return prompt_result
            
            # 导演决策已经在_optimize_prompts中完成
            print(f"   - 导演决策已提取: {len(self.director_decisions.get('frame_inheritance', {}))} 个镜头")
            
            # 继续执行质量门控（递归检查）
            return {"success": True, "continue_to_quality_gate": True}
        else:
            return {"success": False, "error": f"剧本创作返工失败: {response.error}"}
    
    def _rework_round_table(self, quality_result: Dict) -> Dict:
        """
        返工：重新启动圆桌讨论
        
        将质量反馈作为新一轮讨论的输入
        """
        print("\n🔄 返工阶段: 圆桌讨论")
        print("   将质量反馈引入新一轮圆桌讨论...")
        
        # 构建包含质量反馈的讨论上下文
        discussion_context = {
            "world": self.world,
            "script": self.script,
            "storyboard": self.storyboard,
            "optimized_shots": self.optimized_shots,
            "quality_feedback": {
                "issues": quality_result.get("issues", []),
                "suggestions": quality_result.get("suggestions", []),
                "dimension_scores": quality_result.get("dimension_scores", {}),
                "detailed_review": quality_result.get("detailed_review", "")
            },
            "rework": True
        }
        
        # 重新启动圆桌讨论
        response = self.meeting.execute(discussion_context)
        
        if response.success:
            meeting_result = response.data
            
            # 提取改进建议
            improvements = meeting_result.get("improvements", {})
            
            print(f"   ✓ 圆桌讨论完成，获得 {len(improvements)} 项改进建议")
            
            # 根据改进建议重新执行相应阶段
            if improvements.get("script_improvements"):
                print("\n📝 应用剧本改进...")
                script_result = self._rework_script(quality_result)
                if not script_result["success"]:
                    return script_result
            
            elif improvements.get("storyboard_improvements"):
                print("\n📋 应用分镜改进...")
                storyboard_result = self._rework_storyboard(quality_result)
                if not storyboard_result["success"]:
                    return storyboard_result
            
            elif improvements.get("prompt_improvements"):
                print("\n✨ 应用提示词改进...")
                prompt_result = self._rework_prompt_optimization(quality_result)
                if not prompt_result["success"]:
                    return prompt_result
            
            else:
                # 没有具体改进建议，重新执行提示词优化
                print("\n✨ 未获得具体改进方向，重新优化提示词...")
                prompt_result = self._rework_prompt_optimization(quality_result)
                if not prompt_result["success"]:
                    return prompt_result
            
            # 继续执行质量门控（递归检查）
            return {"success": True, "continue_to_quality_gate": True}
        else:
            return {"success": False, "error": f"圆桌讨论返工失败: {response.error}"}
    
    def _generate_summary(self) -> Dict:
        """生成执行总结"""
        summary = {
            "phases_completed": 8,
            "quality_check_passed": self.pipeline_state.get("quality_check_passed", False),
            "video_generation_allowed": self.pipeline_state.get("video_generation_allowed", False),
            "director_decisions": {
                "frame_inheritance_count": len([v for v in self.director_decisions.get("frame_inheritance", {}).values() if v]),
                "multi_reference_images_count": sum(len(refs) for refs in self.director_decisions.get("multi_reference_images", {}).values())
            }
        }
        
        # 保存总结
        if self.session_dir:
            summary_path = self.session_dir / "summary.json"
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
        
        return summary
    
    def _print_summary(self, summary: Dict):
        """打印总结"""
        print(f"\n📊 执行总结:")
        print(f"   - 质量门控: {'通过' if summary.get('quality_check_passed') else '未通过'}")
        print(f"   - 视频生成授权: {'是' if summary.get('video_generation_allowed') else '否'}")
        
        decisions = summary.get("director_decisions", {})
        print(f"   - 帧继承镜头数: {decisions.get('frame_inheritance_count', 0)}")
        print(f"   - 多角色参考图: {decisions.get('multi_reference_images_count', 0)}个参考图")
    
    def _deep_merge_config(self, base: Dict, override: Dict) -> Dict:
        """深度合并配置：override 的值优先，base 填充缺失字段。"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge_config(result[key], value)
            else:
                result[key] = value
        return result

    def _load_default_config(self) -> Dict:
        """加载默认配置"""
        config_path = Path("pipeline_config.json")
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        return {
            "llm": {
                "endpoint": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
                "api_key": "",
                "model": "doubao-seed-evolving"
            },
            "output_dir": "pipeline_output"
        }
    
    def _detect_opening_ceremony(self, story_idea: str) -> bool:
        """
        [新增]检测故事想法是否包含开幕式相关关键词
        
        当检测到开幕式主题时,第一个镜头将尽全力优化
        """
        if not story_idea:
            return False
        
        story_lower = story_idea.lower()
        for keyword in self.OPENING_CEREMONY_KEYWORDS:
            if keyword in story_lower:
                print(f"   匹配关键词: '{keyword}'")
                return True
        
        return False
    
    def _apply_opening_ceremony_optimization(self, shots: List[Dict]) -> List[Dict]:
        """
        Apply special optimization for opening ceremony first shot.
        
        The first shot of an opening ceremony needs:
        1. Most grand shot type
        2. Most detailed scene description
        3. Strongest visual impact
        """
        if not shots or not self.pipeline_state.get("is_opening_ceremony"):
            return shots
        
        first_shot = shots[0]
        shot_number = first_shot.get("shot_number", 1)
        
        print(f"\n 开幕式优化:强化镜头 {shot_number} 的视觉描述")
        
        # 强化景别
        if first_shot.get("shot_type") not in ["extreme_wide_shot"]:
            print(f"   - 景别升级: {first_shot.get('shot_type')} -> extreme_wide_shot")
            first_shot["shot_type"] = "extreme_wide_shot"
        
        # 强化场景描述
        scene_desc = first_shot.get("scene_description", "")
        if scene_desc and len(scene_desc) < 100:
            enhanced_desc = scene_desc + " 宏大气势,精细细节,视觉震撼"
            print(f"   - 场景描述增强: {len(scene_desc)} -> {len(enhanced_desc)} 字符")
            first_shot["scene_description"] = enhanced_desc
        
        # 强化运镜描述
        if first_shot.get("camera_movement") == "static":
            print(f"   - 运镜优化: static -> slow_pan (增加开场气势)")
            first_shot["camera_movement"] = "slow_pan"
        
        # 添加开场特殊标记
        first_shot["opening_ceremony_optimized"] = True
        first_shot["optimization_level"] = "maximum"
        
        # 记录到日志
        if self.meeting:
            self.meeting._append_to_log(f"\n##  开幕式特殊优化\n")
            self.meeting._append_to_log(f"**主题**: 检测到开幕式相关关键词\n")
            self.meeting._append_to_log(f"**优化镜头**: 镜头 {shot_number}\n")
            self.meeting._append_to_log(f"**优化措施**:\n")
            self.meeting._append_to_log(f"- 景别: extreme_wide_shot(大全景)\n")
            self.meeting._append_to_log(f"- 场景描述: 增强至 {len(first_shot.get('scene_description', ''))} 字符\n")
            self.meeting._append_to_log(f"- 运镜: slow_pan(缓慢环绕)\n")
            self.meeting._append_to_log("---\n\n")
        
        return shots
    
    def _conduct_round_table_discussion(self, quality_feedback: Dict = None) -> Dict:
        """
        阶段5: 圆桌讨论
        
        所有Agent查看彼此的工作成果，进行集体讨论，导演生成最终结构报告
        
        Args:
            quality_feedback: 质量反馈（如果是返工）
        
        Returns:
            {
                "success": bool,
                "final_structure_report": Dict,
                "error": str (如果失败)
            }
        """
        print("\n🎭 开始圆桌讨论...")
        
        try:
            # 初始化圆桌讨论协调器（如果尚未初始化）
            if not self.round_table:
                self.round_table = RoundTableDiscussion(
                    self.config,
                    log_file=str(self.session_dir / "round_table_meeting.md")
                )
            
            # 构建讨论上下文
            discussion_context = {
                "story_idea": self.story_idea,  # 【关键】传递原始 story_idea
                "world": self.world.to_dict() if self.world else None,
                "script": self.script,
                "storyboard": self.storyboard,
                "visual_dna": self.visual_dna.to_dict() if self.visual_dna else None,
                "character_bank": self.character_bank.to_dict() if self.character_bank else None,
                "quality_feedback": quality_feedback  # 如果是返工，包含质量反馈
            }
            
            # 调用圆桌讨论
            discussion_result = self.round_table.conduct_discussion(discussion_context)
            
            if not discussion_result.get("success"):
                return {
                    "success": False,
                    "error": discussion_result.get("error", "圆桌讨论失败")
                }
            
            # 获取最终结构报告
            final_report = discussion_result.get("final_structure_report", {})
            
            print(f"\n✅ 圆桌讨论完成")
            print(f"   - 参与Agent: 世界观构建师、编剧、分镜艺术家、摄影指导、导演")
            print(f"   - 讨论回合: {discussion_result.get('rounds', 0)}")
            print(f"   - 最终报告生成: {'是' if final_report else '否'}")
            
            # 保存讨论记录到会议日志
            if self.meeting:
                self.meeting._append_to_log(f"\n## 🎭 圆桌讨论\n\n")
                self.meeting._append_to_log(f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                self.meeting._append_to_log(f"**参与Agent**: 世界观构建师、编剧、分镜艺术家、摄影指导、导演\n")
                self.meeting._append_to_log(f"**讨论回合**: {discussion_result.get('rounds', 0)}\n\n")
                
                # 记录讨论要点
                discussion_summary = discussion_result.get("summary", "")
                if discussion_summary:
                    self.meeting._append_to_log(f"**讨论要点**:\n{discussion_summary}\n\n")
                
                # 记录最终报告摘要
                if final_report:
                    metadata = final_report.get('metadata', {})
                    self.meeting._append_to_log(f"**最终结构报告**:\n")
                    self.meeting._append_to_log(f"- 总镜头数: {metadata.get('shot_count', 0)}\n")
                    self.meeting._append_to_log(f"- 总时长: {metadata.get('duration', 0)}秒\n")
                    self.meeting._append_to_log(f"- 故事线完整性: {'✓' if final_report.get('story_coherence') else '✗'}\n")
                    self.meeting._append_to_log(f"- 角色一致性: {'✓' if final_report.get('character_consistency') else '✗'}\n")
                
                self.meeting._append_to_log("\n---\n\n")
            
            return {
                "success": True,
                "final_structure_report": final_report,
                "discussion_summary": discussion_result.get("summary", "")
            }
            
        except Exception as e:
            print(f"\n❌ 圆桌讨论异常: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": f"圆桌讨论异常: {str(e)}"
            }
    
    def _quality_gate_check_final_report(self, final_report: Dict) -> Dict:
        """
        质量门控：检查最终结构报告
        
        使用增强的质量检查员对最终结构报告进行评审
        
        Args:
            final_report: 最终结构报告
        
        Returns:
            {
                "passed": bool,
                "score": float,
                "issues": List[str],
                "suggestions": List[str],
                "detailed_review": str
            }
        """
        print("\n🔍 质量门控：检查最终结构报告...")
        
        try:
            # 构建完整上下文
            full_context = {
                "story_idea": self.story_idea,  # 【关键】传递原始 story_idea
                "world": self.world.to_dict() if self.world else None,
                "script": self.script,
                "storyboard": self.storyboard,
                "visual_dna": self.visual_dna.to_dict() if self.visual_dna else None,
                "character_bank": self.character_bank.to_dict() if self.character_bank else None,
                "final_report": final_report
            }
            
            # 调用增强质量检查员
            inspection_result = self.quality_inspector.inspect(
                stage="final_report",
                data=final_report,
                context=full_context
            )
            
            passed = inspection_result.get("pass", False)
            score = inspection_result.get("score", 0.0)
            threshold = inspection_result.get("threshold", 0.75)
            issues = inspection_result.get("issues", [])
            suggestions = inspection_result.get("suggestions", [])
            detailed_review = inspection_result.get("detailed_review", "")
            dimension_scores = inspection_result.get("dimension_scores", {})
            
            print(f"\n📊 质量检查结果:")
            print(f"   - 综合评分: {score:.2f}/{threshold}")
            print(f"   - 评审结果: {'✅ 通过' if passed else '❌ 不通过'}")
            
            # 显示各维度得分
            if dimension_scores:
                print(f"   - 维度评分:")
                for dim_name, dim_score in dimension_scores.items():
                    status = '✓' if dim_score >= 0.6 else '✗'
                    print(f"     • {dim_name}: {dim_score:.2f} {status}")
            
            # 显示问题和建议
            if issues:
                print(f"\n   📋 发现的问题:")
                for i, issue in enumerate(issues, 1):
                    print(f"      {i}. {issue}")
            
            if suggestions:
                print(f"\n   💡 改进建议:")
                for i, suggestion in enumerate(suggestions, 1):
                    print(f"      {i}. {suggestion}")
            
            return {
                "passed": passed,
                "score": score,
                "threshold": threshold,
                "issues": issues,
                "suggestions": suggestions,
                "detailed_review": detailed_review,
                "dimension_scores": dimension_scores
            }
            
        except Exception as e:
            print(f"\n❌ 质量检查异常: {e}")
            import traceback
            traceback.print_exc()
            
            # 返回失败结果
            return {
                "passed": False,
                "score": 0.0,
                "threshold": 0.75,
                "issues": [f"质量检查异常: {str(e)}"],
                "suggestions": ["请检查质量检查员配置", "人工复核最终报告"],
                "detailed_review": f"质量检查过程中发生异常: {str(e)}"
            }
    
    # ======================== 断点续传功能 ========================
    
    def _resume_from_checkpoint(self, session_id: str, story_idea: str,
                                target_duration: int, reference_images: List[str],
                                reference_audio: str, skip_video_gen: bool) -> Dict[str, Any]:
        """从检查点恢复执行

        检测已完成的阶段，从失败或未完成的阶段继续
        """
        session_id = str(session_id)
        self.session_dir = self.output_dir / session_id
        self.story_idea = story_idea
        self.skip_video_gen = skip_video_gen
        
        print(f"\n[RESUME] 会话目录: {self.session_dir}")
        
        # 检测已完成的阶段
        completed_stages = self._detect_completed_stages()
        
        print(f"[RESUME] 已完成的阶段:")
        for stage in completed_stages:
            print(f"   ✓ {stage}")
        
        # 初始化圆桌会议
        log_file = self.session_dir / "round_table_meeting.md"
        self.meeting = RoundTableMeeting(log_file=str(log_file))
        self.workflow = CollaborativeWorkflow(self.meeting)
        
        # 加载已有数据
        self._load_checkpoint_data(completed_stages)
        
        # 确定从哪个阶段继续
        next_stage = self._determine_next_stage(completed_stages)
        
        print(f"\n[RESUME] 从阶段继续: {next_stage}")
        print()
        
        # 根据下一个阶段执行
        if next_stage == "world":
            return self._run_from_world(story_idea, target_duration, reference_images, 
                                        reference_audio, skip_video_gen)
        elif next_stage == "script":
            return self._run_from_script(target_duration, reference_images, 
                                         reference_audio, skip_video_gen)
        elif next_stage == "storyboard":
            return self._run_from_storyboard(reference_images, reference_audio, skip_video_gen)
        elif next_stage == "visual":
            return self._run_from_visual(reference_images, reference_audio, skip_video_gen)
        elif next_stage == "round_table":
            return self._run_from_round_table(reference_images, reference_audio, skip_video_gen)
        elif next_stage == "prompts":
            return self._run_from_prompts(reference_images, reference_audio, skip_video_gen)
        elif next_stage == "quality_gate":
            return self._run_from_quality_gate(reference_images, reference_audio, skip_video_gen)
        elif next_stage == "video_generation":
            return self._run_from_video_generation(reference_images, reference_audio, skip_video_gen)
        elif next_stage == "post_production":
            return self._run_from_post_production(reference_audio)
        else:
            # 已全部完成
            print("[RESUME] 所有阶段已完成")
            return self._build_success_result()
    
    def _detect_completed_stages(self) -> List[str]:
        """检测已完成的阶段"""
        stages = []
        
        if (self.session_dir / "01_world.json").exists():
            stages.append("world")
        if (self.session_dir / "02_script.json").exists():
            stages.append("script")
        if (self.session_dir / "03_storyboard.json").exists():
            stages.append("storyboard")
        if (self.session_dir / "04_visual_dna.json").exists():
            stages.append("visual")
        if (self.session_dir / "05_final_structure_report.json").exists():
            stages.append("round_table")
        if (self.session_dir / "05_prompts.json").exists():
            stages.append("prompts")
        if (self.session_dir / "quality_gate_passed.flag").exists():
            stages.append("quality_gate")
        if (self.session_dir / "06_videos").exists() and len(list((self.session_dir / "06_videos").glob("*.mp4"))) > 0:
            stages.append("video_generation")
        if (self.session_dir / "final_video.mp4").exists():
            stages.append("post_production")
        
        return stages
    
    def _load_checkpoint_data(self, completed_stages: List[str]):
        """加载检查点数据"""
        if "world" in completed_stages:
            with open(self.session_dir / "01_world.json", 'r', encoding='utf-8') as f:
                world_data = json.load(f)
                # 尝试加载为 WorldDatabase，失败则保持原始数据
                try:
                    if "characters" in world_data and isinstance(world_data["characters"], dict):
                        self.world = WorldDatabase.from_dict(world_data)
                    else:
                        self.world = world_data
                except Exception as e:
                    print(f"[WARN] WorldDatabase 加载失败，使用原始数据: {e}")
                    self.world = world_data
                print(f"[RESUME] 已加载: 世界观")
        
        if "script" in completed_stages:
            with open(self.session_dir / "02_script.json", 'r', encoding='utf-8') as f:
                self.script = json.load(f)
                print(f"[RESUME] 已加载: 剧本")
        
        if "storyboard" in completed_stages:
            with open(self.session_dir / "03_storyboard.json", 'r', encoding='utf-8') as f:
                self.storyboard = json.load(f)
                print(f"[RESUME] 已加载: 分镜")
        
        if "visual" in completed_stages:
            with open(self.session_dir / "04_visual_dna.json", 'r', encoding='utf-8') as f:
                visual_data = json.load(f)
                self.visual_dna = VisualDNA()
                self.visual_dna.from_dict(visual_data)
                print(f"[RESUME] 已加载: 视觉DNA")
        
        if "round_table" in completed_stages:
            with open(self.session_dir / "05_final_structure_report.json", 'r', encoding='utf-8') as f:
                self.final_structure_report = json.load(f)
                print(f"[RESUME] 已加载: 最终结构报告")
        
        if "prompts" in completed_stages:
            with open(self.session_dir / "05_prompts.json", 'r', encoding='utf-8') as f:
                self.optimized_shots = json.load(f)
                print(f"[RESUME] 已加载: 优化提示词")
        
        # 🔥 关键修复: 如果质量门控已通过，恢复pipeline_state
        if "quality_gate" in completed_stages:
            flag_file = self.session_dir / "quality_gate_passed.flag"
            if flag_file.exists():
                self.pipeline_state["quality_check_passed"] = True
                self.pipeline_state["video_generation_allowed"] = True
                print(f"[RESUME] 已恢复: 质量门控通过状态")
    
    def _determine_next_stage(self, completed_stages: List[str]) -> str:
        """确定下一个要执行的阶段"""
        all_stages = [
            "world", "script", "storyboard", "visual", 
            "round_table", "prompts", "quality_gate",
            "video_generation", "post_production"
        ]
        
        for stage in all_stages:
            if stage not in completed_stages:
                return stage
        
        return "completed"
    
    def _run_from_round_table(self, reference_images, reference_audio, skip_video_gen):
        """从圆桌讨论阶段继续"""
        print("\n" + "="*80)
        print("[STAGE 5/8] 圆桌讨论 (续)")
        print("="*80)
        
        discussion_result = self._conduct_round_table_discussion()
        if not discussion_result["success"]:
            return self._handle_failure("圆桌讨论失败", discussion_result)
        
        final_report = discussion_result["final_structure_report"]
        report_path = self.session_dir / "05_final_structure_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(final_report, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 最终结构报告已生成")
        
        return self._run_from_prompts(reference_images, reference_audio, skip_video_gen)
    
    def _run_from_prompts(self, reference_images, reference_audio, skip_video_gen):
        """从提示词优化阶段继续"""
        print("\n" + "="*80)
        print("[STAGE 5.5/8] 提示词优化 (续)")
        print("="*80)
        
        prompts_result = self._optimize_prompts()
        if not prompts_result["success"]:
            return self._handle_failure("提示词优化失败", prompts_result)
        
        print(f"\n✅ 提示词优化完成")
        
        return self._run_from_quality_gate(reference_images, reference_audio, skip_video_gen)
    
    def _run_from_quality_gate(self, reference_images, reference_audio, skip_video_gen):
        """从质量门控阶段继续"""
        max_quality_retries = 3
        quality_retry_count = 0
        
        while quality_retry_count < max_quality_retries:
            print("\n" + "="*80)
            if quality_retry_count == 0:
                print(f"[STAGE 6/8] 质量门控检查 (续)")
            else:
                print(f"[STAGE 6/8] 质量门控检查 (重试第 {quality_retry_count} 次)")
            print("="*80)
            
            quality_result = self._quality_gate_check()
            
            if quality_result["passed"]:
                print("\n✅ 质量门控检查通过")
                
                # 创建通过标记文件
                flag_file = self.session_dir / "quality_gate_passed.flag"
                flag_file.write_text(json.dumps({
                    "passed": True,
                    "timestamp": datetime.now().isoformat(),
                    "score": quality_result.get("score", 0)
                }, ensure_ascii=False, indent=2))
                
                self.pipeline_state["quality_check_passed"] = True
                self.pipeline_state["video_generation_allowed"] = True
                break
            else:
                print("\n❌ 质量门控检查未通过")
                quality_retry_count += 1
                
                if quality_retry_count >= max_quality_retries:
                    return self._handle_failure("质量门控检查失败", quality_result)
                
                # 返工
                rework_decision = self._determine_rework_target(quality_result)
                target_stage = rework_decision["target_stage"]
                
                if target_stage == "prompt_optimization":
                    rework_result = self._rework_prompt_optimization(quality_result)
                    if not rework_result.get("success"):
                        return self._handle_failure("提示词优化返工失败", rework_result)
                elif target_stage == "round_table":
                    discussion_result = self._conduct_round_table_discussion(quality_feedback=quality_result)
                    if not discussion_result.get("success"):
                        return self._handle_failure("返工失败", discussion_result)
                    
                    final_report = discussion_result["final_structure_report"]
                    report_path = self.session_dir / "05_final_structure_report.json"
                    with open(report_path, 'w', encoding='utf-8') as f:
                        json.dump(final_report, f, ensure_ascii=False, indent=2)
                    
                    prompts_result = self._optimize_prompts()
                    if not prompts_result["success"]:
                        return self._handle_failure("提示词重新优化失败", prompts_result)
        
        if skip_video_gen:
            print("\n[INFO] 跳过视频生成(测试模式)")
            return self._build_success_result()
        
        return self._run_from_video_generation(reference_images, reference_audio, skip_video_gen)
    
    def _run_from_video_generation(self, reference_images, reference_audio, skip_video_gen):
        """从视频生成阶段继续"""
        if skip_video_gen:
            print("\n[INFO] 跳过视频生成(测试模式)")
            return self._build_success_result()

        print("\n" + "="*80)
        print("[STAGE 7/8] 视频生成 (续)")
        print("="*80)

        # Resume position is derived only from files in this session.
        existing_summary = self._prepare_video_resume()

        if existing_summary:
            self.pipeline_state["video_start_shot"] = existing_summary["start_shot"]
            self.pipeline_state["previous_video_path"] = existing_summary["previous_video_path"]
            print(f"[RESUME] Existing shots detected: {existing_summary['existing_shots']}")
            print(f"[RESUME] Submitting from shot {existing_summary['start_shot']}")
            if existing_summary["previous_video_path"]:
                print(f"[RESUME] Previous video: {existing_summary['previous_video_path']}")
        else:
            self.pipeline_state["video_start_shot"] = 1
            self.pipeline_state["previous_video_path"] = None

        video_result = self._generate_videos_with_director_decisions(reference_images)
        if not video_result["success"]:
            return self._handle_failure("视频生成失败", video_result)

        print(f"\n✅ 视频生成完成")

        return self._run_from_post_production(reference_audio)

    def _prepare_video_resume(self) -> Optional[Dict]:
        """扫描本地已有视频，返回用于断点续传的起点信息。

        返回 None 表示没有任何本地视频，需从镜头 1 开始。
        返回字典时，包含:
            - existing_shots: 已存在本地视频的镜头号列表（升序）
            - start_shot:    第一个缺失的镜头号
            - previous_video_path: 起点之前最近的本地视频，供生成器作为前置帧
        """
        videos_dir = self.session_dir / "videos"
        if not videos_dir.exists():
            return None

        existing = sorted(
            int(p.stem.replace("shot_", ""))
            for p in videos_dir.glob("shot_*.mp4")
            if p.is_file() and p.stat().st_size > 0
        )
        if not existing:
            return None

        # Use the first missing shot, rather than max(existing) + 1, so a gap
        # in the local files can never be skipped accidentally.
        total_shots = len((self.optimized_shots or {}).get("shots", []))
        if total_shots > 0:
            start_shot = next(
                (shot_number for shot_number in range(1, total_shots + 1)
                 if shot_number not in existing),
                total_shots + 1,
            )
        else:
            start_shot = existing[-1] + 1

        previous_shot = max(
            (shot_number for shot_number in existing if shot_number < start_shot),
            default=0,
        )
        previous_path = (
            videos_dir / f"shot_{previous_shot:03d}.mp4"
            if previous_shot else None
        )
        return {
            "existing_shots": existing,
            "start_shot": start_shot,
            "previous_video_path": str(previous_path) if previous_path else None,
        }
    
    def _run_from_post_production(self, reference_audio):
        """从后期制作阶段继续"""
        print("\n" + "="*80)
        print("[STAGE 8/8] 后期制作 (续)")
        print("="*80)
        
        post_result = self._post_production(reference_audio)
        if not post_result["success"]:
            return self._handle_failure("后期制作失败", post_result)
        
        print(f"\n✅ 后期制作完成")
        
        return self._build_success_result()
    
    def _run_from_world(self, story_idea, target_duration, reference_images, reference_audio, skip_video_gen):
        """从世界观构建阶段重新开始"""
        # 重置session_id
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = str(session_id)
        self.session_dir = self.output_dir / session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
        # 调用正常流程
        return self._run_normal_pipeline(story_idea, target_duration, reference_images, 
                                        reference_audio, skip_video_gen)
    
    def _run_from_script(self, target_duration, reference_images, reference_audio, skip_video_gen):
        """从剧本创作阶段继续（世界观已完成）"""
        print("\n" + "="*80)
        print("[STAGE 2/8] 剧本创作 (续)")
        print("="*80)
        
        script_result = self._write_script(target_duration)
        if not script_result["success"]:
            return self._handle_failure("剧本创作失败", script_result)
        
        return self._run_from_storyboard(reference_images, reference_audio, skip_video_gen)
    
    def _run_from_storyboard(self, reference_images, reference_audio, skip_video_gen):
        """从分镜设计阶段继续"""
        print("\n" + "="*80)
        print("[STAGE 3/8] 分镜设计 (续)")
        print("="*80)
        
        storyboard_result = self._design_storyboard()
        if not storyboard_result["success"]:
            return self._handle_failure("分镜设计失败", storyboard_result)
        
        return self._run_from_visual(reference_images, reference_audio, skip_video_gen)
    
    def _run_from_visual(self, reference_images, reference_audio, skip_video_gen):
        """从视觉风格定义阶段继续"""
        print("\n" + "="*80)
        print("[STAGE 4/8] 视觉风格定义 (续)")
        print("="*80)
        
        visual_result = self._define_visual_style()
        if not visual_result["success"]:
            return self._handle_failure("视觉风格定义失败", visual_result)
        
        return self._run_from_round_table(reference_images, reference_audio, skip_video_gen)
    
    def _run_normal_pipeline(self, story_idea: str, target_duration: int,
                            reference_images: List[str], reference_audio: str,
                            skip_video_gen: bool) -> Dict[str, Any]:
        """执行正常流程（从头开始）
        
        这是完整的视频制作流水线入口，包含以下阶段：
        1. 世界观构建
        2. 剧本创作
        3. 分镜设计
        4. 视觉风格定义
        5. 圆桌讨论
        5.5. 提示词优化
        6. 质量门控检查（可能触发返工）
        7. 视频生成（可选）
        8. 后期制作（可选）
        
        Args:
            story_idea: 故事创意描述
            target_duration: 目标时长（秒）
            reference_images: 参考图片列表
            reference_audio: 参考音频路径
            skip_video_gen: 是否跳过视频生成
            
        Returns:
            包含成功状态、输出目录、会话ID等信息的字典
        """
        return self.run(
            story_idea=story_idea,
            target_duration=target_duration,
            reference_images=reference_images,
            reference_audio=reference_audio,
            skip_video_gen=skip_video_gen
        )
    
    def _build_success_result(self) -> Dict[str, Any]:
        """构建成功结果"""
        return {
            "success": True,
            "output_dir": str(self.session_dir),
            "session_id": self.session_dir.name,
            "director_decisions": getattr(self, 'director_decisions', {}),
            "video_files": getattr(self, 'video_files', [])
        }
