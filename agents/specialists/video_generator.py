# -*- coding: utf-8 -*-
"""
Video Generator - 视频生成器

负责调用视频生成API生成视频片段
支持参考帧继承，确保镜头间的连贯性
"""

import json
import base64
import time
import re
import cv2
import numpy as np
from typing import Dict, List, Optional
from pathlib import Path

from core.base_agent import BaseAgent, AgentResponse


class SeedanceTaskSubmittedError(RuntimeError):
    """任务已提交，但客户端无法确认最终结果；禁止自动重新提交。"""

    def __init__(self, message: str, task_id: str):
        super().__init__(message)
        self.task_id = task_id


class SeedanceSubmissionRejectedError(RuntimeError):
    """Seedance 在创建阶段明确拒绝请求；禁止盲目重复提交。"""


class VideoGenerator(BaseAgent):
    """
    视频生成器 - 调用API生成视频
    
    核心职责：
    1. 将优化的提示词发送给视频生成API
    2. 管理生成队列和重试
    3. 保存生成的视频文件
    4. 处理失败情况
    5. 使用参考帧继承确保镜头连贯性
    
    输入：优化的提示词列表
    输出：视频文件列表
    
    参考帧继承机制：
    - 提取前一个镜头的最后一帧
    - 作为下一个镜头的参考图
    - 确保角色外貌、场景元素的延续性
    """
    
    def __init__(self, llm_config: Dict, video_api_config: Dict = None):
        config = {"llm": llm_config}
        super().__init__(config)
        self.name = "视频生成器"
        self.video_api_config = video_api_config or {"provider": "mock"}
        # 【重要】帧继承决策完全由Director控制，不再从配置读取
        # 每个shot的use_frame_inheritance字段由Director的智能决策系统决定
        # 这里不再设置默认值，避免覆盖Director的决策
        self.use_frame_inheritance = None  # 废弃，仅用于向后兼容
    
    def execute(self, context: Dict) -> AgentResponse:
        """
        执行视频生成
        
        【关键修复】根据 skip_video_gen 决定是否实际生成：
        - skip_video_gen=False: 实际生成视频（调用API）
        - skip_video_gen=True: Mock模式（不调用API）
        """
        
        # 保留 context 供断点续传、导演帧继承决策等生成控制使用。
        self.context = context
        # 缓存当前会话的输出根目录，便于参考图查找等辅助逻辑从 session/assets 读取。
        self.output_dir = Path(context.get("output_dir", "videos"))

        shots = context.get("shots", [])
        output_dir = self.output_dir
        parallel = context.get("parallel", False)
        skip_video_gen = context.get("skip_video_gen", False)  # 【新增】从上下文获取
        
        if not shots:
            return AgentResponse(
                success=False,
                data=None,
                error="没有镜头需要生成"
            )
        
        # 创建输出目录
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 【关键修复】根据 skip_video_gen 决定模式
        if skip_video_gen:
            # Mock模式：不实际生成，只保存提示词
            print("\n[视频生成器] Mock模式：跳过实际视频生成")
            result = self._mock_generation(shots, output_dir)
        else:
            # 实际生成模式
            provider = self.video_api_config.get("provider", "mock")

            if provider == "mock":
                print("\n[视频生成器] Mock模式：provider设为mock")
                result = self._mock_generation(shots, output_dir)
            else:
                print(f"\n[视频生成器] 实际生成模式：provider={provider}")
                result = self._real_generation(
                    shots,
                    output_dir,
                    parallel,
                    start_shot=self.context.get("start_shot"),
                )
        
        return AgentResponse(
            success=True,
            data=result,
            warnings=result.get("warnings", [])
        )
    
    def _mock_generation(self, shots: List[Dict], output_dir: Path) -> Dict:
        """Mock模式：不实际生成，仅用于测试"""
        
        # 保存所有提示词到文件
        prompts_file = output_dir / "all_prompts.json"
        with open(prompts_file, 'w', encoding='utf-8') as f:
            json.dump(shots, f, ensure_ascii=False, indent=2)
        
        # 为每个镜头创建占位符信息
        videos = []
        for shot in shots:
            video_info = {
                "shot_number": shot.get("shot_number"),
                "file": str(output_dir / f"shot_{shot.get('shot_number'):03d}.mp4"),
                "status": "mock",
                "prompt": shot.get("visual_prompt", "")  # 【修复】完整提示词，不截断
            }
            videos.append(video_info)
        
        return {
            "mode": "mock",
            "total": len(shots),
            "succeeded": len(shots),
            "failed": 0,
            "videos": videos,
            "prompts_file": str(prompts_file),
            "warnings": ["运行在Mock模式，未实际生成视频"],
            "all_generated": True  # Mock模式视为全部生成成功
        }
    
    def _real_generation(self, shots: List[Dict], output_dir: Path,
                        parallel: bool, start_shot: Optional[int] = None) -> Dict:
        """
        实际生成视频（支持参考帧继承）

        【关键修复】根据 provider 选择实际的生成方法
        【重要】parallel 参数被强制设为 False，因为帧继承需要顺序生成
        【断点续传】start_shot>1 时，只提交该镜头及之后的镜头；之前已存在的视频会在
        各 provider 的具体方法里被识别并复用为前置帧。
        """

        provider = self.video_api_config.get("provider", "kling")

        print(f"\n[视频生成器] 实际生成模式")
        print(f"  - 提供商: {provider}")
        print(f"  - 镜头数: {len(shots)}")
        print(f"  - 并行: False (帧继承需要顺序生成)")
        print(f"  - 提交完整prompt: 是")
        print(f"  - 帧继承机制: 完全由Director决策，逐镜头判断")
        if start_shot and start_shot > 1:
            print(f"  - 断点续传: 从镜头 {start_shot} 开始提交，之前的镜头复用本地视频")

        # 【关键修复】强制顺序生成，因为帧继承需要前一个镜头的最后帧
        parallel = False

        # 根据提供商选择生成方法，使用带重试机制的生成
        # 你的流程规则是每个镜头最多重试一次；重试仍失败时立即终止进程，
        # 防止部分视频结果继续流入后期制作。
        max_retries = 1
        retry_delay = self.video_api_config.get("retry_delay", 60)

        if provider == "kling":
            generation_func = lambda s, o, p: self._generate_with_kling(s, o, p)
        elif provider == "runway":
            generation_func = lambda s, o, p: self._generate_with_runway(s, o, p)
        elif provider == "pika":
            generation_func = lambda s, o, p: self._generate_with_pika(s, o, p)
        elif provider == "seedance":
            generation_func = lambda s, o, p: self._generate_with_seedance(s, o, p)
        else:
            raise ValueError(f"不支持的视频生成提供商: {provider}")

        # 【断点续传】仅提交 start_shot 及之后的镜头；之前镜头视为已完成
        if start_shot and start_shot > 1:
            pending_shots = [
                shot for shot in shots
                if int(shot.get("shot_number", 0)) >= int(start_shot)
            ]
            print(f"[视频生成器] 断点续传：原 {len(shots)} 个镜头，本次提交 {len(pending_shots)} 个")
            shots_to_run = pending_shots
        else:
            shots_to_run = shots

        # 使用带重试机制的生成
        return self._generate_with_retry(
            generation_func, shots_to_run, output_dir, parallel, max_retries, retry_delay
        )
    
    def _generate_with_retry(self, generation_func, shots: List[Dict], 
                            output_dir: Path, parallel: bool,
                            max_retries: int, retry_delay: int) -> Dict:
        """
        【关键】带重试机制的视频生成
        
        确保所有镜头都成功生成后才返回结果。
        如果某个镜头失败，会重试直到成功或达到最大重试次数。
        
        Args:
            generation_func: 实际的生成函数
            shots: 镜头列表
            output_dir: 输出目录
            parallel: 是否并行生成
            max_retries: 每个镜头的最大重试次数
            retry_delay: 重试间隔（秒）
        
        Returns:
            包含所有视频结果的字典
        """
        all_videos = []
        # 每个镜头严格执行：首次生成失败后只重试一次。
        max_retries = 1
        failed_shots = []
        retry_counts = {}
        all_warnings = []
        all_continuity_scores = []
        
        # 第一轮生成
        print(f"\n[视频生成器] 开始第1轮生成，共 {len(shots)} 个镜头")

        result = generation_func(shots, output_dir, parallel)
        
        all_videos = result.get("videos", [])
        all_warnings.extend(result.get("warnings", []))
        all_continuity_scores.extend(result.get("continuity_scores", []))
        
        for video in all_videos:
            if video.get("status") != "success":
                shot_num = video.get("shot_number")
                failed_shots.append(shot_num)
                retry_counts[shot_num] = 0
                print(f"  [视频生成器] ⚠️ 镜头 {shot_num} 生成失败: {video.get('error', '未知错误')}")
        
        # 重试失败的镜头
        retry_round = 1
        while failed_shots:
            retry_round += 1
            exhausted_shots = [
                shot_num for shot_num in failed_shots
                if retry_counts.get(shot_num, 0) >= max_retries
            ]
            if exhausted_shots:
                failed_numbers = ", ".join(map(str, exhausted_shots))
                print(
                    f"\n[视频生成器] ❌ 镜头 {failed_numbers} 首次生成失败，"
                    "重试后仍失败；视频流水线已终止。"
                )
                raise SystemExit(1)
            print(f"\n[视频生成器] 开始第{retry_round}轮重试，失败镜头: {failed_shots}")
            
            # 等待后重试
            print(f"  [视频生成器] 等待 {retry_delay} 秒后重试...")
            import time
            time.sleep(retry_delay)
            
            # 获取失败的镜头数据
            failed_shot_data = [shot for shot in shots if shot.get("shot_number") in failed_shots]

            # 失败镜头前面可能已经有成功的视频。恢复这个前置视频，
            # 这样重试成功后仍能保持帧继承链，而不是从空上下文重新开始。
            preceding_success = next(
                (
                    video for video in reversed(all_videos)
                    if video.get("status") == "success"
                    and video.get("file")
                    and video.get("shot_number", 0) < min(failed_shots)
                ),
                None,
            )
            if preceding_success and hasattr(self, "context"):
                self.context["previous_video_path"] = preceding_success["file"]

            # 重新生成失败的镜头
            retry_result = generation_func(failed_shot_data, output_dir, parallel)
            retry_videos = retry_result.get("videos", [])
            all_warnings.extend(retry_result.get("warnings", []))
            all_continuity_scores.extend(retry_result.get("continuity_scores", []))
            
            new_failed_shots = []
            for i, video in enumerate(retry_videos):
                shot_num = video.get("shot_number")
                if video.get("status") == "success":
                    # 替换原来失败的记录
                    for j, v in enumerate(all_videos):
                        if v.get("shot_number") == shot_num:
                            all_videos[j] = video
                            break
                    print(f"  [视频生成器] ✓ 镜头 {shot_num} 重试成功")
                elif video.get("status") != "success":
                    new_failed_shots.append(shot_num)
                    retry_counts[shot_num] = retry_counts.get(shot_num, 0) + 1
                    # 更新错误信息
                    for j, v in enumerate(all_videos):
                        if v.get("shot_number") == shot_num:
                            all_videos[j] = video
                            break
                    print(f"  [视频生成器] ✗ 镜头 {shot_num} 重试失败 ({retry_counts[shot_num]}/{max_retries}): {video.get('error', '未知错误')}")

            failed_shots = new_failed_shots

            # 生成函数遇到失败镜头会停止当前批次。该镜头重试成功后，
            # 必须继续提交它之后尚未处理的镜头，不能把当前批次误认为已完成。
            if not failed_shots:
                successful_shots = {
                    video.get("shot_number")
                    for video in all_videos
                    if video.get("status") == "success"
                }
                remaining_shots = [
                    shot for shot in shots
                    if shot.get("shot_number") not in successful_shots
                ]

                if remaining_shots:
                    last_successful_video = next(
                        (
                            video for video in reversed(all_videos)
                            if video.get("status") == "success"
                            and video.get("file")
                        ),
                        None,
                    )
                    if last_successful_video and hasattr(self, "context"):
                        # Seedance 的生成器从 context 读取断点前置视频；其他提供商
                        # 会忽略该字段，因此这里统一更新不会改变其行为。
                        self.context["previous_video_path"] = last_successful_video["file"]

                    print(
                        "  [视频生成器] 重试成功，继续生成后续镜头: "
                        f"{[shot.get('shot_number') for shot in remaining_shots]}"
                    )
                    continuation_result = generation_func(
                        remaining_shots, output_dir, parallel
                    )
                    continuation_videos = continuation_result.get("videos", [])
                    all_videos.extend(continuation_videos)
                    all_warnings.extend(continuation_result.get("warnings", []))
                    all_continuity_scores.extend(
                        continuation_result.get("continuity_scores", [])
                    )
                    failed_shots = [
                        video.get("shot_number")
                        for video in continuation_videos
                        if video.get("status") != "success"
                    ]
                    for shot_num in failed_shots:
                        retry_counts.setdefault(shot_num, 0)

        # 最终统计
        succeeded = sum(1 for v in all_videos if v.get("status") == "success")
        failed = len(all_videos) - succeeded
        
        # 按镜头号排序
        all_videos.sort(key=lambda x: x.get("shot_number", 0))
        
        # 计算平均连续性
        avg_continuity = 0.0
        if all_continuity_scores:
            avg_continuity = sum(s["similarity"] for s in all_continuity_scores) / len(all_continuity_scores)
        
        print(f"\n[视频生成器] 生成完成:")
        print(f"  - 成功: {succeeded}/{len(shots)}")
        print(f"  - 失败: {failed}/{len(shots)}")
        if avg_continuity > 0:
            print(f"  - 平均连续性: {avg_continuity:.2f}")
        
        # 【关键】如果有镜头仍然失败，发出警告
        if failed > 0:
            failed_numbers = [
                v.get("shot_number") for v in all_videos
                if v.get("status") != "success"
            ]
            error_message = (
                f"镜头 {failed_numbers} 首次生成失败，重试后仍失败；"
                "视频流水线已终止。"
            )
            print(f"\n[视频生成器] ❌ {error_message}")
            raise SystemExit(1)

        return {
            "total": len(shots),
            "succeeded": succeeded,
            "failed": failed,
            "videos": all_videos,
            "warnings": all_warnings,
            "continuity_scores": all_continuity_scores,
            "average_continuity": avg_continuity,
            "all_generated": succeeded == len(shots),
            "stopped_after_failure": succeeded < len(shots)
        }
    
    def extract_last_frame(self, video_path: Path) -> Optional[Path]:
        """
        从视频中提取最后一帧
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            最后一帧图片的路径，失败返回None
        """
        if not video_path.exists():
            print(f"  [视频生成器] 视频文件不存在: {video_path}")
            return None
        
        try:
            # 打开视频
            cap = cv2.VideoCapture(str(video_path))
            
            if not cap.isOpened():
                print(f"  [视频生成器] 无法打开视频: {video_path}")
                return None
            
            # 获取总帧数
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if total_frames == 0:
                print(f"  [视频生成器] 视频没有帧: {video_path}")
                cap.release()
                return None
            
            # 跳到最后一帧
            cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)
            
            # 读取最后一帧
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                print(f"  [视频生成器] 无法读取最后一帧")
                return None
            
            # 保存最后一帧
            frame_path = video_path.parent / f"{video_path.stem}_last_frame.jpg"
            cv2.imwrite(str(frame_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            print(f"  [视频生成器] 提取最后一帧: {frame_path}")
            return frame_path
            
        except Exception as e:
            print(f"  [视频生成器] 提取最后一帧失败: {e}")
            return None
    
    def extract_multiple_frames(self, video_path: Path, num_frames: int = 3) -> List[Path]:
        """
        【新增】从视频中提取多帧
        
        当最后一帧画面不好时（如只漏半个人脸），提取多帧作为参考
        选择策略：最后一帧 + 倒数第二帧 + 中间帧
        
        Args:
            video_path: 视频文件路径
            num_frames: 提取的帧数（默认3帧）
            
        Returns:
            多个帧图片的路径列表
        """
        if not video_path.exists():
            print(f"  [视频生成器] 视频文件不存在: {video_path}")
            return []
        
        try:
            cap = cv2.VideoCapture(str(video_path))
            
            if not cap.isOpened():
                print(f"  [视频生成器] 无法打开视频: {video_path}")
                return []
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if total_frames == 0:
                cap.release()
                return []
            
            frame_paths = []
            
            # 选择要提取的帧位置
            if total_frames <= num_frames:
                # 视频太短，提取所有帧
                frame_positions = list(range(total_frames))
            else:
                # 最后一帧，倒数第二帧，和中间帧
                frame_positions = [total_frames - 1, total_frames - 2]
                middle = total_frames // 2
                if middle not in frame_positions:
                    frame_positions.append(middle)
                frame_positions = frame_positions[:num_frames]
            
            for i, pos in enumerate(frame_positions):
                cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
                ret, frame = cap.read()
                
                if ret:
                    # 保存帧
                    frame_path = video_path.parent / f"{video_path.stem}_frame_{i}.jpg"
                    cv2.imwrite(str(frame_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    frame_paths.append(frame_path)
            
            cap.release()
            
            print(f"  [视频生成器] 提取 {len(frame_paths)} 帧作为参考: {frame_paths}")
            return frame_paths
            
        except Exception as e:
            print(f"  [视频生成器] 提取多帧失败: {e}")
            return []
    
    def get_reference_images_with_fallback(self, video_path: Path, 
                                         default_ref: Path = None) -> List[Path]:
        """
        【新增】获取参考图列表（带降级策略）
        
        策略：
        1. 优先提取最后一帧
        2. 如果最后一帧不好（检测到人脸不完整），提取多帧
        3. 如果有默认参考图，也一并返回
        4. 确保至少有一个可用的参考图
        
        Args:
            video_path: 视频文件路径
            default_ref: 默认参考图路径
            
        Returns:
            参考图路径列表
        """
        ref_images = []
        
        # 尝试提取最后一帧
        last_frame = self.extract_last_frame(video_path)
        if last_frame:
            ref_images.append(last_frame)
        
        # 检查是否需要提取多帧
        if last_frame and self._is_frame_problematic(last_frame):
            print(f"  [视频生成器] 最后一帧可能不完整，提取额外帧...")
            extra_frames = self.extract_multiple_frames(video_path, num_frames=3)
            ref_images.extend(extra_frames)
        
        # 添加默认参考图
        if default_ref and default_ref.exists():
            ref_images.append(default_ref)
            print(f"  [视频生成器] 添加默认参考图: {default_ref}")
        
        return ref_images
    
    def _is_frame_problematic(self, frame_path: Path) -> bool:
        """
        【新增】检测帧是否有问题（如人脸不完整）
        
        简化版：检查帧文件大小，如果太小可能说明画面不完整
        
        Returns:
            True 如果帧可能有问题
        """
        if not frame_path.exists():
            return True
        
        # 检查文件大小
        file_size = frame_path.stat().st_size
        # 如果文件小于10KB，可能画面有问题
        if file_size < 10000:
            print(f"  [视频生成器] 帧文件过小 ({file_size} bytes)，可能画面不完整")
            return True
        
        return False
    
    def extract_first_frame(self, video_path: Path) -> Optional[Path]:
        """
        从视频中提取第一帧（用于后期分析）
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            第一帧图片的路径，失败返回None
        """
        if not video_path.exists():
            return None
        
        try:
            cap = cv2.VideoCapture(str(video_path))
            
            if not cap.isOpened():
                return None
            
            # 读取第一帧
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                return None
            
            # 保存第一帧
            frame_path = video_path.parent / f"{video_path.stem}_first_frame.jpg"
            cv2.imwrite(str(frame_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            return frame_path
            
        except Exception as e:
            print(f"  [视频生成器] 提取第一帧失败: {e}")
            return None
    
    def calculate_frame_similarity(self, frame1_path: Path, frame2_path: Path) -> float:
        """
        计算两帧之间的相似度（用于质量检查）
        
        Args:
            frame1_path: 第一帧路径
            frame2_path: 第二帧路径
            
        Returns:
            相似度分数 (0-1)，1表示完全相同
        """
        try:
            img1 = cv2.imread(str(frame1_path))
            img2 = cv2.imread(str(frame2_path))
            
            if img1 is None or img2 is None:
                return 0.0
            
            # 调整大小到相同尺寸
            h, w = 256, 256
            img1 = cv2.resize(img1, (w, h))
            img2 = cv2.resize(img2, (w, h))
            
            # 转换为灰度图
            gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
            
            # 计算结构相似性
            from skimage.metrics import structural_similarity as ssim
            similarity = ssim(gray1, gray2)
            
            return float(similarity)
            
        except ImportError:
            # 如果没有skimage，使用简单的MSE
            try:
                img1 = cv2.imread(str(frame1_path))
                img2 = cv2.imread(str(frame2_path))
                
                h, w = 256, 256
                img1 = cv2.resize(img1, (w, h))
                img2 = cv2.resize(img2, (w, h))
                
                mse = np.mean((img1.astype(float) - img2.astype(float)) ** 2)
                max_mse = 255.0 ** 2
                similarity = 1 - (mse / max_mse)
                
                return float(similarity)
            except Exception as e:
                print(f"  [视频生成器] 计算相似度失败: {e}")
                return 0.0
        except Exception as e:
            print(f"  [视频生成器] 计算相似度失败: {e}")
            return 0.0
    
    def _find_character_references(self, characters: List[str], reference_images: List[str]) -> List[Path]:
        """
        根据角色名称查找本地参考图片
        
        Args:
            characters: 镜头中出现的角色名称列表（如 ["无名", "守卫"]）
            reference_images: 用户提供的参考图片路径列表
            
        Returns:
            匹配的参考图片路径列表
        """
        matched_refs = []
        
        if not characters or not reference_images:
            return matched_refs
        
        # 遍历每个角色
        for character in characters:
            # 标准化角色名（去空格，转小写）
            char_normalized = character.strip().lower().replace(" ", "")
            
            # 遍历所有参考图，查找文件名包含角色名的
            for ref_path_str in reference_images:
                ref_path = Path(ref_path_str)
                
                # 检查文件是否存在
                if not ref_path.exists():
                    continue
                
                # 获取文件名（不含扩展名）
                filename = ref_path.stem.lower().replace(" ", "")
                
                # 检查文件名是否包含角色名
                # 例如：wuming.png 匹配角色 "无名" 或 "wuming"
                # 例如：wuming1.png 也匹配
                if char_normalized in filename or character.lower() in filename:
                    if ref_path not in matched_refs:
                        matched_refs.append(ref_path)
                        print(f"  [参考图匹配] 角色 '{character}' → {ref_path.name}")
        
        return matched_refs

    def _get_shot_reference_text(self, shot: Dict) -> str:
        """合并镜头所有文本字段，避免生成后的 prompt 丢失元素名称。"""
        text_parts = []

        def collect(value):
            if isinstance(value, dict):
                for nested_value in value.values():
                    collect(nested_value)
            elif isinstance(value, (list, tuple)):
                for nested_value in value:
                    collect(nested_value)
            elif value is not None:
                text_parts.append(str(value))

        collect(shot)
        return " ".join(text_parts)

    def _find_element_references(self, prompt: str) -> List[Path]:
        """
        从 prompt 中检测元素名称，查找当前 session 资产目录下的参考图。

        新结构（取代旧的 D:/cg_create/photos/{元素名}/）：
            {session_dir}/assets/characters/{角色名}.png
            {session_dir}/assets/locations/{场景名}.png

        匹配策略（按顺序尝试，任一命中即收录）：
            1. 文件名 stem 完整出现在 prompt 中
            2. 把 stem 中的下划线/连字符去掉再匹配（覆盖 X-7_大流士 → X-7大流士 / 大流士）
            3. 去掉形如 "X-7_" 这类前缀后再匹配
            4. 找到 stem 中长度 ≥ 2 的最长连续中文字符子串做包含匹配
               （避免把"切卡"误匹配到"切卡机/卡卡"等场景）
        """
        if not self.output_dir:
            return []

        # session 目录 = videos/ 的父目录；assets/ 与之并列
        session_dir = self.output_dir.parent
        assets_root = session_dir / "assets"
        if not assets_root.is_dir():
            return []

        matched: List[Path] = []
        prompt_str = prompt or ""

        # 候选资产目录
        candidate_dirs = [
            assets_root / "characters",
            assets_root / "locations",
            assets_root / "props",
        ]

        # 中文字符判断
        def _has_cjk(s: str) -> bool:
            return any("\u4e00" <= ch <= "\u9fff" for ch in s)

        def _longest_cjk_run(stem: str) -> str:
            best = ""
            cur = []
            for ch in stem:
                if "\u4e00" <= ch <= "\u9fff":
                    cur.append(ch)
                else:
                    if len(cur) > len(best):
                        best = "".join(cur)
                    cur = []
            if len(cur) > len(best):
                best = "".join(cur)
            return best

        def _all_cjk_runs(stem: str, min_len: int = 2) -> List[str]:
            """所有长度 ≥ min_len 的连续中文字符串（按出现顺序），保留重复。"""
            runs = []
            cur = []
            for ch in stem:
                if "\u4e00" <= ch <= "\u9fff":
                    cur.append(ch)
                else:
                    if len(cur) >= min_len:
                        runs.append("".join(cur))
                    cur = []
            if len(cur) >= min_len:
                runs.append("".join(cur))
            return runs

        def _strip_prefix_token(stem: str) -> str:
            """去掉类似 'X-7_' 的前缀（字母/数字+下划线/连字符）。"""
            parts = re.split(r"[_\-]+", stem)
            if len(parts) >= 2 and all(
                p and (p.isascii() and not _has_cjk(p)) for p in parts[:-1]
            ):
                return parts[-1]
            return stem

        seen: set = set()
        for asset_dir in candidate_dirs:
            if not asset_dir.is_dir():
                continue
            for img_file in asset_dir.iterdir():
                if not img_file.is_file():
                    continue
                if img_file.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
                    continue
                if img_file in seen:
                    continue

                stem = img_file.stem  # 例如 "X-7_大流士"
                # 策略 1：完整 stem
                hit = stem and stem in prompt_str
                # 策略 2：去掉下划线/连字符
                if not hit:
                    cleaned = re.sub(r"[_\-]+", "", stem)
                    if cleaned and cleaned in prompt_str:
                        hit = True
                # 策略 3：去掉前缀 token
                if not hit:
                    stripped = _strip_prefix_token(stem)
                    if stripped and stripped != stem and stripped in prompt_str:
                        hit = True
                # 策略 4：把 CJK run 按位置切分成若干片段，任一 ≥ 2 字符片段命中即认为匹配。
                # 解决 "熄焰炼油厂" → "熄焰的炼油厂" 这种被"的"打断的场景。
                if not hit:
                    runs = _all_cjk_runs(stem)
                    for run in runs:
                        n = len(run)
                        # 从长到短尝试切分（前缀 / 后缀 / 子串），任一 ≥ 2 字符命中即收
                        candidates = set()
                        for i in range(n):
                            for j in range(i + 2, n + 1):
                                piece = run[i:j]
                                if len(piece) >= 2:
                                    candidates.add(piece)
                        for piece in sorted(candidates, key=len, reverse=True):
                            if piece in prompt_str:
                                hit = True
                                break
                        if hit:
                            break

                if hit:
                    seen.add(img_file)
                    matched.append(img_file)
                    print(f"  [参考图匹配] '{img_file.parent.name}/{img_file.name}'")

        return matched

    def _detect_scene_change(self, current_shot: Dict, previous_shot: Optional[Dict]) -> bool:
        """
        检测场景是否发生转换
        
        Args:
            current_shot: 当前镜头
            previous_shot: 上一个镜头
            
        Returns:
            True 表示场景转换，False 表示场景连续
        """
        if not previous_shot:
            return True
        
        # 方法1：检查 scene_id 或 scene_number
        current_scene = current_shot.get("scene_id") or current_shot.get("scene_number")
        previous_scene = previous_shot.get("scene_id") or previous_shot.get("scene_number")
        
        if current_scene and previous_scene:
            return current_scene != previous_scene
        
        # 方法2：检查 location（场景地点）
        current_location = current_shot.get("location", "").lower()
        previous_location = previous_shot.get("location", "").lower()
        
        if current_location and previous_location:
            # 如果地点明显不同，判断为场景转换
            if current_location != previous_location:
                return True
        
        # 方法3：检查视觉风格的剧烈变化
        current_style = current_shot.get("visual_style", {})
        previous_style = previous_shot.get("visual_style", {})
        
        # 检查色调变化
        current_tone = current_style.get("color_tone", "")
        previous_tone = previous_style.get("color_tone", "")
        
        if current_tone and previous_tone and current_tone != previous_tone:
            # 色调变化可能表示场景转换
            return True
        
        # 方法4：检查时间跳跃（通过对话或动作描述判断）
        current_action = current_shot.get("action", "").lower()
        
        # 关键词检测（表示明显的场景切换）
        scene_change_keywords = [
            "切换到", "转场", "新场景", "另一处", "同时", "此时", 
            "meanwhile", "later", "elsewhere", "next scene"
        ]
        
        for keyword in scene_change_keywords:
            if keyword in current_action:
                return True
        
        # 默认：场景连续
        return False
    
    def _generate_with_kling(self, shots: List[Dict], output_dir: Path,
                            parallel: bool) -> Dict:
        """使用Kling API生成（支持参考帧继承）"""
        
        videos = []
        succeeded = 0
        failed = 0
        
        previous_video_path = None
        continuity_scores = []  # 记录连续性分数
        
        # 【新增】创建shots子目录，保存每个镜头的详细信息
        shots_detail_dir = output_dir / "shots_detail"
        shots_detail_dir.mkdir(parents=True, exist_ok=True)
        
        for i, shot in enumerate(shots):
            shot_num = shot.get('shot_number', i+1)
            shot_dir = shots_detail_dir / f"shot_{shot_num:03d}"
            shot_dir.mkdir(parents=True, exist_ok=True)

            try:
                should_inherit = shot.get("use_frame_inheritance", False)
                reference_frames = []
                element_references = []
                last_frame_reference = None

                # 第1步：从 prompt 中检测元素，查找 D:/cg_create/photos 下对应子目录的图片
                prompt_text = self._get_shot_reference_text(shot)
                if prompt_text:
                    element_references = self._find_element_references(prompt_text)

                # 第2步：根据Director决策决定是否使用帧继承
                if should_inherit and previous_video_path:
                    if not shot.get("disable_frame_inheritance"):
                        last_frame_reference = self.extract_last_frame(previous_video_path)
                        if last_frame_reference:
                            reference_frames = [last_frame_reference] + element_references
                        else:
                            reference_frames = element_references
                    else:
                        reference_frames = element_references
                else:
                    reference_frames = element_references

                primary_reference = reference_frames[0] if reference_frames else None
                if primary_reference:
                    print(f"  [视频生成器] 镜头 {shot_num}: 参考图 {len(reference_frames)}张（首位: {primary_reference.name}）")
                
                # 保存由 prompt 元素匹配和帧继承产生的参考图。
                all_reference_images = list(reference_frames)
                character_references = []

                # 保存所有参考图到镜头目录
                saved_references = []
                for idx, ref_path in enumerate(all_reference_images):
                    import shutil
                    if ref_path.exists():
                        # 区分帧继承和角色参考
                        if ref_path in reference_frames:
                            ref_name = f"frame_inheritance_{idx:02d}{ref_path.suffix}"
                        else:
                            ref_name = f"character_ref_{idx:02d}{ref_path.suffix}"
                        
                        dest_path = shot_dir / ref_name
                        shutil.copy2(ref_path, dest_path)
                        saved_references.append(str(dest_path))
                        print(f"  [视频生成器] 保存参考图: {ref_name}")
                
                # 【新增】保存prompt到文件
                prompt = shot.get("visual_prompt", "")
                prompt_file = shot_dir / "prompt.txt"
                with open(prompt_file, 'w', encoding='utf-8') as f:
                    f.write(f"=== 镜头 {shot_num} 提示词 ===\n\n")
                    f.write(prompt)
                    f.write(f"\n\n=== 参数信息 ===\n")
                    f.write(f"时长: {shot.get('duration', 3.0)}秒\n")
                    f.write(f"宽高比: {shot.get('aspect_ratio', '16:9')}\n")
                    f.write(f"FPS: {shot.get('fps', 24)}\n")
                    f.write(f"CFG Scale: {shot.get('cfg_scale', 7.5)}\n")
                    f.write(f"使用帧继承: {'是' if should_inherit else '否'}\n")
                    f.write(f"角色参考图数量: {len(character_references)}\n")
                
                print(f"  [视频生成器] 已保存prompt到: {prompt_file}")
                
                # 调用API生成
                video_path = self._call_kling_api(
                    shot=shot,
                    output_dir=output_dir,
                    reference_image=primary_reference,
                    reference_images=reference_frames if len(reference_frames) > 1 else None,
                    shot_detail_dir=shot_dir  # 【新增】传递镜头详细目录
                )
                
                # 如果使用了参考帧，计算连续性
                if primary_reference and video_path.exists():
                    first_frame = self.extract_first_frame(video_path)
                    if first_frame:
                        similarity = self.calculate_frame_similarity(primary_reference, first_frame)
                        continuity_scores.append({
                            "shot_number": shot.get("shot_number"),
                            "similarity": similarity
                        })
                        print(f"  [视频生成器] 连续性分数: {similarity:.2f}")
                
                # 【新增】保存生成记录
                record = {
                    "shot_number": shot.get("shot_number"),
                    "file": str(video_path),
                    "status": "success",
                    "prompt": prompt,  # 【修复】完整提示词，不截断
                    "prompt_file": str(prompt_file),
                    "used_reference": primary_reference is not None,
                    "reference_frame": str(primary_reference) if primary_reference else None,
                    "reference_frames": [str(f) for f in reference_frames],
                    "character_references": [str(f) for f in character_references],
                    "saved_references": saved_references,
                    "director_decision": should_inherit,
                    "detail_dir": str(shot_dir)
                }
                
                # 保存JSON记录
                record_file = shot_dir / "generation_record.json"
                with open(record_file, 'w', encoding='utf-8') as f:
                    json.dump(record, f, ensure_ascii=False, indent=2)
                
                videos.append(record)
                succeeded += 1
                previous_video_path = video_path
                
            except Exception as e:
                print(f"  [视频生成器] ✗ 镜头 {shot_num} 生成失败: {e}")
                
                # 【新增】保存失败记录
                error_record = {
                    "shot_number": shot.get("shot_number"),
                    "file": None,
                    "status": "failed",
                    "error": str(e),
                    "detail_dir": str(shot_dir)
                }
                
                error_file = shot_dir / "generation_error.json"
                with open(error_file, 'w', encoding='utf-8') as f:
                    json.dump(error_record, f, ensure_ascii=False, indent=2)
                
                videos.append(error_record)
                failed += 1
                previous_video_path = None
                print(f"  [视频生成器] 已停止：镜头 {shot_num} 生成失败，后续镜头不再提交")
                break
        
        # 计算平均连续性
        avg_continuity = 0.0
        if continuity_scores:
            avg_continuity = sum(s["similarity"] for s in continuity_scores) / len(continuity_scores)
        
        return {
            "mode": "kling",
            "total": len(shots),
            "succeeded": succeeded,
            "failed": failed,
            "videos": videos,
            "frame_inheritance_enabled": "Director决策（逐镜头）",  # 不再使用全局配置
            "continuity_scores": continuity_scores,
            "average_continuity": avg_continuity,
            "all_generated": failed == 0,  # 关键标志：所有镜头是否都生成成功
            "shots_detail_dir": str(shots_detail_dir)
        }
    
    def _generate_with_runway(self, shots: List[Dict], output_dir: Path,
                             parallel: bool) -> Dict:
        """使用Runway API生成（支持参考帧继承）"""
        
        videos = []
        succeeded = 0
        failed = 0
        
        previous_video_path = None
        continuity_scores = []
        
        for i, shot in enumerate(shots):
            try:
                should_inherit = shot.get("use_frame_inheritance", False)
                reference_frames = []
                element_references = []
                last_frame_reference = None
                shot_num = shot.get('shot_number', i+1)

                # 第1步：从 prompt 中检测元素
                prompt_text = self._get_shot_reference_text(shot)
                if prompt_text:
                    element_references = self._find_element_references(prompt_text)

                # 第2步：根据Director决策决定是否使用帧继承
                if should_inherit and previous_video_path:
                    if not shot.get("disable_frame_inheritance"):
                        last_frame_reference = self.extract_last_frame(previous_video_path)
                        if last_frame_reference:
                            reference_frames = [last_frame_reference] + element_references
                        else:
                            reference_frames = element_references
                    else:
                        reference_frames = element_references
                else:
                    reference_frames = element_references

                primary_reference = reference_frames[0] if reference_frames else None
                if primary_reference:
                    print(f"  [视频生成器] 镜头 {shot_num}: 参考图 {len(reference_frames)}张（首位: {primary_reference.name}）")

                # 调用API生成
                video_path = self._call_runway_api(
                    shot=shot,
                    output_dir=output_dir,
                    reference_image=primary_reference,
                    reference_images=reference_frames if len(reference_frames) > 1 else None
                )
                
                # 计算连续性
                if primary_reference and video_path.exists():
                    first_frame = self.extract_first_frame(video_path)
                    if first_frame:
                        similarity = self.calculate_frame_similarity(primary_reference, first_frame)
                        continuity_scores.append({
                            "shot_number": shot.get("shot_number"),
                            "similarity": similarity
                        })
                        print(f"  [视频生成器] 连续性分数: {similarity:.2f}")
                
                videos.append({
                    "shot_number": shot.get("shot_number"),
                    "file": str(video_path),
                    "status": "success",
                    "prompt": shot.get("visual_prompt", ""),  # 【修复】完整提示词，不截断
                    "used_reference": primary_reference is not None,
                    "reference_frame": str(primary_reference) if primary_reference else None,
                    "reference_frames": [str(f) for f in reference_frames],
                    "director_decision": should_inherit,
                    "inheritance_requested": bool(should_inherit),
                    "previous_video_available": previous_video_path is not None,
                    "inheritance_applied": bool(last_frame_reference and last_frame_reference.exists()),
                })
                succeeded += 1
                previous_video_path = video_path
                
            except Exception as e:
                videos.append({
                    "shot_number": shot.get("shot_number"),
                    "file": None,
                    "status": "failed",
                    "task_id": getattr(e, "task_id", None),
                    "retryable": not isinstance(e, (SeedanceTaskSubmittedError, SeedanceSubmissionRejectedError)),
                    "error": str(e)
                })
                failed += 1
                previous_video_path = None
                print(f"  [视频生成器] 已停止：镜头 {shot_num} 生成失败，后续镜头不再提交")
                break
        
        avg_continuity = 0.0
        if continuity_scores:
            avg_continuity = sum(s["similarity"] for s in continuity_scores) / len(continuity_scores)
        
        return {
            "mode": "runway",
            "total": len(shots),
            "succeeded": succeeded,
            "failed": failed,
            "videos": videos,
            "frame_inheritance_enabled": "Director决策（逐镜头）",  # 不再使用全局配置
            "continuity_scores": continuity_scores,
            "average_continuity": avg_continuity,
            "all_generated": succeeded == len(shots),
            "stopped_after_failure": succeeded < len(shots)
        }
    
    def _generate_with_pika(self, shots: List[Dict], output_dir: Path,
                           parallel: bool) -> Dict:
        """使用Pika API生成（支持参考帧继承）"""
        
        videos = []
        succeeded = 0
        failed = 0
        
        previous_video_path = None
        continuity_scores = []
        
        for i, shot in enumerate(shots):
            try:
                should_inherit = shot.get("use_frame_inheritance", False)
                reference_frames = []
                element_references = []
                last_frame_reference = None
                shot_num = shot.get('shot_number', i+1)

                # 第1步：从 prompt 中检测元素
                prompt_text = self._get_shot_reference_text(shot)
                if prompt_text:
                    element_references = self._find_element_references(prompt_text)

                # 第2步：根据Director决策决定是否使用帧继承
                if should_inherit and previous_video_path:
                    if not shot.get("disable_frame_inheritance"):
                        last_frame_reference = self.extract_last_frame(previous_video_path)
                        if last_frame_reference:
                            reference_frames = [last_frame_reference] + element_references
                        else:
                            reference_frames = element_references
                    else:
                        reference_frames = element_references
                else:
                    reference_frames = element_references

                primary_reference = reference_frames[0] if reference_frames else None
                if primary_reference:
                    print(f"  [视频生成器] 镜头 {shot_num}: 参考图 {len(reference_frames)}张（首位: {primary_reference.name}）")

                # 调用API生成
                video_path = self._call_pika_api(
                    shot=shot,
                    output_dir=output_dir,
                    reference_image=primary_reference,
                    reference_images=reference_frames if len(reference_frames) > 1 else None
                )
                
                # 计算连续性
                if primary_reference and video_path.exists():
                    first_frame = self.extract_first_frame(video_path)
                    if first_frame:
                        similarity = self.calculate_frame_similarity(primary_reference, first_frame)
                        continuity_scores.append({
                            "shot_number": shot.get("shot_number"),
                            "similarity": similarity
                        })
                        print(f"  [视频生成器] 连续性分数: {similarity:.2f}")
                
                videos.append({
                    "shot_number": shot.get("shot_number"),
                    "file": str(video_path),
                    "status": "success",
                    "prompt": shot.get("visual_prompt", ""),  # 【修复】完整提示词，不截断
                    "used_reference": primary_reference is not None,
                    "reference_frame": str(primary_reference) if primary_reference else None,
                    "reference_frames": [str(f) for f in reference_frames],
                    "director_decision": should_inherit,
                    "inheritance_requested": bool(should_inherit),
                    "previous_video_available": previous_video_path is not None,
                    "inheritance_applied": bool(last_frame_reference and last_frame_reference.exists()),
                })
                succeeded += 1
                previous_video_path = video_path
                
            except Exception as e:
                videos.append({
                    "shot_number": shot.get("shot_number"),
                    "file": None,
                    "status": "failed",
                    "task_id": getattr(e, "task_id", None),
                    "retryable": not isinstance(e, (SeedanceTaskSubmittedError, SeedanceSubmissionRejectedError)),
                    "error": str(e)
                })
                failed += 1
                previous_video_path = None
                print(f"  [视频生成器] 已停止：镜头 {shot_num} 生成失败，后续镜头不再提交")
                break
        
        avg_continuity = 0.0
        if continuity_scores:
            avg_continuity = sum(s["similarity"] for s in continuity_scores) / len(continuity_scores)
        
        return {
            "mode": "pika",
            "total": len(shots),
            "succeeded": succeeded,
            "failed": failed,
            "videos": videos,
            "frame_inheritance_enabled": "Director决策（逐镜头）",  # 不再使用全局配置
            "continuity_scores": continuity_scores,
            "average_continuity": avg_continuity,
            "all_generated": succeeded == len(shots),
            "stopped_after_failure": succeeded < len(shots)
        }
    
    def _call_kling_api(self, shot: Dict, output_dir: Path, 
                       reference_image: Optional[Path] = None,
                       reference_images: Optional[List[Path]] = None,
                       shot_detail_dir: Optional[Path] = None) -> Path:
        """
        调用Kling API生成视频
        
        Args:
            shot: 镜头数据
            output_dir: 输出目录
            reference_image: 主要参考图片（用于帧继承）
            reference_images: 多张参考图片列表
            shot_detail_dir: 镜头详细信息目录（用于保存请求记录）
            
        Returns:
            生成的视频文件路径
        """
        
        prompt = shot.get("visual_prompt", "")
        duration = shot.get("duration", 3.0)
        shot_number = shot.get("shot_number", 0)
        
        print(f"  [Kling API] 生成镜头 {shot_number}")
        print(f"  [Kling API] 提示词: {prompt}")  # 【修复】完整提示词，不截断
        print(f"  [Kling API] 时长: {duration}秒")
        
        # 【改进】记录参考图信息
        if reference_images and len(reference_images) > 1:
            print(f"  [Kling API] 使用多参考图 ({len(reference_images)}张): {reference_images}")
        elif reference_image:
            print(f"  [Kling API] 使用参考图: {reference_image}")
        
        # 【新增】记录API调用信息
        api_call_record = {
            "shot_number": shot_number,
            "timestamp": str(Path.cwd()),  # 临时占位
            "prompt": prompt,
            "duration": duration,
            "parameters": {
                "aspect_ratio": shot.get("aspect_ratio", "16:9"),
                "fps": shot.get("fps", 24),
                "cfg_scale": shot.get("cfg_scale", 7.5),
                "seed": shot.get("seed", -1)
            }
        }
        
        try:
            import requests
            import time
            from datetime import datetime
            
            api_call_record["timestamp"] = datetime.now().isoformat()
            
            # 构造API请求
            api_endpoint = self.video_api_config.get("endpoint", "")
            api_key = self.video_api_config.get("api_key", "")
            
            if not api_endpoint or not api_key:
                raise ValueError("Kling API配置不完整：缺少endpoint或api_key")
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # 【修复】构造请求体 - 使用完整 prompt，不截断
            request_body = {
                "prompt": prompt,  # 【关键】完整提示词
                "duration": duration,
                "aspect_ratio": shot.get("aspect_ratio", "16:9"),
                "fps": shot.get("fps", 24),
                "cfg_scale": shot.get("cfg_scale", 7.5),
                "seed": shot.get("seed", -1)
            }
            
            # 【修复】如果有参考图，添加到请求中（完整路径）
            if reference_image and reference_image.exists():
                # 方式1：如果API支持图片URL
                # 需要先上传图片或使用base64编码
                import base64
                with open(reference_image, 'rb') as f:
                    img_data = base64.b64encode(f.read()).decode('utf-8')
                request_body["reference_image"] = img_data
                request_body["image_strength"] = shot.get("reference_strength", 0.7)
                api_call_record["frame_inheritance_image"] = str(reference_image)
                print(f"  [Kling API] 已添加帧继承参考图: {reference_image}")
            
            # 参考图统一由上层传入：帧继承图在首位，元素参考图随后。
            # 不再读取 shot["reference_images"] 或上传旧的角色参考图字段。
            
            # 【新增】保存请求体（不包含base64数据）
            if shot_detail_dir:
                request_record = request_body.copy()
                # 移除base64数据，只保留标记
                if "reference_image" in request_record:
                    request_record["reference_image"] = "<base64_data_removed>"
                if "character_references" in request_record:
                    request_record["character_references"] = f"<{len(request_body['character_references'])} images>"
                
                api_call_record["request_body"] = request_record
                api_call_record["api_endpoint"] = api_endpoint
                
                request_file = shot_detail_dir / "api_request.json"
                with open(request_file, 'w', encoding='utf-8') as f:
                    json.dump(api_call_record, f, ensure_ascii=False, indent=2)
                print(f"  [Kling API] 已保存请求记录: {request_file}")
            
            # 发送请求
            print(f"  [Kling API] 发送请求到: {api_endpoint}")
            start_time = time.time()
            
            response = requests.post(
                api_endpoint,
                headers=headers,
                json=request_body,
                timeout=300
            )
            
            elapsed_time = time.time() - start_time
            api_call_record["request_time_seconds"] = elapsed_time
            
            if response.status_code != 200:
                api_call_record["error"] = f"HTTP {response.status_code}: {response.text}"
                if shot_detail_dir:
                    error_file = shot_detail_dir / "api_error.json"
                    with open(error_file, 'w', encoding='utf-8') as f:
                        json.dump(api_call_record, f, ensure_ascii=False, indent=2)
                raise Exception(f"API返回错误: {response.status_code} - {response.text}")
            
            result = response.json()
            api_call_record["response"] = result
            
            # 获取任务ID（异步模式）
            task_id = result.get("task_id") or result.get("id")
            
            if not task_id:
                # 同步模式：直接返回视频URL
                video_url = result.get("video_url") or result.get("url")
                if not video_url:
                    raise Exception("API响应中没有视频URL或任务ID")
            else:
                # 异步模式：轮询结果
                print(f"  [Kling API] 任务ID: {task_id}，开始轮询...")
                api_call_record["task_id"] = task_id
                video_url = self._poll_kling_task(task_id, headers, shot_detail_dir)
            
            api_call_record["video_url"] = video_url
            
            # 下载视频
            video_path = output_dir / f"shot_{shot_number:03d}.mp4"
            print(f"  [Kling API] 下载视频到: {video_path}")
            
            download_start = time.time()
            video_response = requests.get(video_url, timeout=300)
            download_time = time.time() - download_start
            
            with open(video_path, 'wb') as f:
                f.write(video_response.content)
            
            api_call_record["download_time_seconds"] = download_time
            api_call_record["video_file"] = str(video_path)
            api_call_record["video_size_bytes"] = video_path.stat().st_size
            api_call_record["status"] = "success"
            
            # 【新增】保存成功记录
            if shot_detail_dir:
                success_file = shot_detail_dir / "api_success.json"
                with open(success_file, 'w', encoding='utf-8') as f:
                    json.dump(api_call_record, f, ensure_ascii=False, indent=2)
            
            print(f"  [Kling API] ✓ 生成成功 (请求: {elapsed_time:.1f}s, 下载: {download_time:.1f}s)")
            return video_path
            
        except Exception as e:
            api_call_record["status"] = "failed"
            api_call_record["error"] = str(e)
            
            # 【新增】保存失败记录
            if shot_detail_dir:
                error_file = shot_detail_dir / "api_error.json"
                with open(error_file, 'w', encoding='utf-8') as f:
                    json.dump(api_call_record, f, ensure_ascii=False, indent=2)
            
            print(f"  [Kling API] ✗ 生成失败: {e}")
            raise
    
    def _poll_kling_task(self, task_id: str, headers: Dict, 
                        shot_detail_dir: Optional[Path] = None,
                        max_attempts: int = 60, interval: int = 10) -> str:
        """
        轮询Kling任务状态，等待视频生成完成
        
        Args:
            task_id: 任务ID
            headers: 请求头
            shot_detail_dir: 镜头详细信息目录（用于保存轮询记录）
            max_attempts: 最大尝试次数
            interval: 轮询间隔（秒）
            
        Returns:
            视频URL
        """
        import requests
        import time
        from datetime import datetime
        
        status_endpoint = self.video_api_config.get("status_endpoint", "")
        poll_record = {
            "task_id": task_id,
            "start_time": datetime.now().isoformat(),
            "attempts": []
        }
        
        for attempt in range(max_attempts):
            try:
                attempt_start = time.time()
                response = requests.get(
                    f"{status_endpoint}/{task_id}",
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    status = result.get("status", "unknown")
                    
                    attempt_record = {
                        "attempt": attempt + 1,
                        "timestamp": datetime.now().isoformat(),
                        "status": status,
                        "response": result
                    }
                    poll_record["attempts"].append(attempt_record)
                    
                    print(f"  [Kling API] 轮询 {attempt+1}/{max_attempts}: {status}")
                    
                    if status == "completed" or status == "success":
                        video_url = result.get("video_url") or result.get("url")
                        if video_url:
                            poll_record["end_time"] = datetime.now().isoformat()
                            poll_record["final_status"] = "success"
                            poll_record["video_url"] = video_url
                            
                            # 【新增】保存轮询记录
                            if shot_detail_dir:
                                poll_file = shot_detail_dir / "api_polling.json"
                                with open(poll_file, 'w', encoding='utf-8') as f:
                                    json.dump(poll_record, f, ensure_ascii=False, indent=2)
                            
                            return video_url
                        else:
                            raise Exception("任务已完成但没有返回视频URL")
                    
                    elif status == "failed" or status == "error":
                        error_msg = result.get("error", "未知错误")
                        poll_record["end_time"] = datetime.now().isoformat()
                        poll_record["final_status"] = "failed"
                        poll_record["error"] = error_msg
                        
                        if shot_detail_dir:
                            poll_file = shot_detail_dir / "api_polling_failed.json"
                            with open(poll_file, 'w', encoding='utf-8') as f:
                                json.dump(poll_record, f, ensure_ascii=False, indent=2)
                        
                        raise Exception(f"任务失败: {error_msg}")
                    
                    # 任务仍在处理中，等待后继续
                    time.sleep(interval)
                else:
                    attempt_record = {
                        "attempt": attempt + 1,
                        "timestamp": datetime.now().isoformat(),
                        "status": "http_error",
                        "error": f"HTTP {response.status_code}: {response.text}"
                    }
                    poll_record["attempts"].append(attempt_record)
                    print(f"  [Kling API] 轮询出错: HTTP {response.status_code}")
                    time.sleep(interval)
                    
            except Exception as e:
                attempt_record = {
                    "attempt": attempt + 1,
                    "timestamp": datetime.now().isoformat(),
                    "status": "exception",
                    "error": str(e)
                }
                poll_record["attempts"].append(attempt_record)
                print(f"  [Kling API] 轮询异常: {e}")
                time.sleep(interval)
        
        # 超时
        poll_record["end_time"] = datetime.now().isoformat()
        poll_record["final_status"] = "timeout"
        poll_record["error"] = f"轮询超时（{max_attempts * interval}秒）"
        
        if shot_detail_dir:
            poll_file = shot_detail_dir / "api_polling_timeout.json"
            with open(poll_file, 'w', encoding='utf-8') as f:
                json.dump(poll_record, f, ensure_ascii=False, indent=2)
        
        raise Exception(f"轮询超时：任务在{max_attempts * interval}秒内未完成")
    
    def _call_runway_api(self, shot: Dict, output_dir: Path,
                        reference_image: Optional[Path] = None,
                        reference_images: Optional[List[Path]] = None) -> Path:
        """调用Runway API（类似Kling实现）"""
        
        # TODO: 根据Runway API文档实现
        # 结构类似_call_kling_api，但使用Runway的API规范
        
        prompt = shot.get("visual_prompt", "")  # 【修复】完整提示词
        duration = shot.get("duration", 3.0)
        shot_number = shot.get("shot_number", 0)
        
        print(f"  [Runway API] 生成镜头 {shot_number}")
        print(f"  [Runway API] 提示词: {prompt}")
        
        # 临时返回占位符
        video_path = output_dir / f"shot_{shot_number:03d}.mp4"
        raise NotImplementedError("Runway API尚未实现，请配置API信息后使用")
    
    def _call_pika_api(self, shot: Dict, output_dir: Path,
                      reference_image: Optional[Path] = None,
                      reference_images: Optional[List[Path]] = None) -> Path:
        """调用Pika API（类似Kling实现）"""
        
        # TODO: 根据Pika API文档实现
        # 结构类似_call_kling_api，但使用Pika的API规范
        
        prompt = shot.get("visual_prompt", "")  # 【修复】完整提示词
        duration = shot.get("duration", 3.0)
        shot_number = shot.get("shot_number", 0)
        
        print(f"  [Pika API] 生成镜头 {shot_number}")
        print(f"  [Pika API] 提示词: {prompt}")
        
        # 临时返回占位符
        video_path = output_dir / f"shot_{shot_number:03d}.mp4"
        raise NotImplementedError("Pika API尚未实现，请配置API信息后使用")
    
    def _generate_with_seedance(self, shots: List[Dict], output_dir: Path,
                               parallel: bool) -> Dict:
        """使用Seedance生成视频（支持参考帧继承）

        支持断点续传：当本地已存在 `shot_XXX.mp4` 时，直接复用，不再调用 API 提交，
        避免对同一镜头重复扣费。
        """

        videos = []
        succeeded = 0
        failed = 0
        previous_video_path = self.context.get("previous_video_path")
        if previous_video_path:
            previous_video_path = Path(previous_video_path)
            if not previous_video_path.exists():
                print(f"  [视频生成器] ⚠️ 前置帧视频不存在: {previous_video_path}，回退到无前置帧")
                previous_video_path = None
            else:
                print(f"  [视频生成器] 注入断点前置帧: {previous_video_path.name}")
        continuity_scores = []
        skipped_resume = 0

        # 参考图只来自 prompt 元素匹配和上一镜头最后一帧；不读取旧全局列表。

        director_decisions = self.context.get("director_decisions") or {}
        decision_map = {}
        raw_inherit = director_decisions.get("frame_inheritance", {}) or {}
        for k, v in raw_inherit.items():
            try:
                decision_map[int(k)] = bool(v)
            except (TypeError, ValueError):
                continue
        if decision_map:
            print(f"\n[视频生成器] 导演决策（帧继承）快照: {decision_map}")
            for shot in shots:
                sn = shot.get("shot_number")
                if sn is not None and int(sn) in decision_map:
                    # 决策快照是唯一权威来源，避免旧 prompts 中残留值覆盖新导演决策。
                    shot["use_frame_inheritance"] = decision_map[int(sn)]

        for i, shot in enumerate(shots):
            try:
                shot_num = shot.get('shot_number', i+1)
                print(f"\n[视频生成器] 处理镜头 {shot_num}/{len(shots)}")

                # 【断点续传】如果本地已有视频文件，直接复用，不再提交任务。
                existing_video = output_dir / f"shot_{int(shot_num):03d}.mp4"
                if existing_video.exists() and existing_video.stat().st_size > 0:
                    videos.append({
                        "shot_number": shot_num,
                        "file": str(existing_video),
                        "status": "success",
                        "resumed": True,
                        "prompt": shot.get("visual_prompt", ""),
                        "used_reference": False,
                        "reference_frame": None,
                        "reference_frames": [],
                        "director_decision": shot.get("use_frame_inheritance", False),
                    "inheritance_requested": bool(shot.get("use_frame_inheritance", False)),
                    "previous_video_available": previous_video_path is not None,
                    "inheritance_applied": False,
                    })
                    succeeded += 1
                    skipped_resume += 1
                    previous_video_path = existing_video
                    print(f"  [视频生成器] ✓ 镜头 {shot_num} 已存在本地视频，复用为前置帧: {existing_video.name}")
                    continue

                should_inherit = shot.get("use_frame_inheritance", False)
                reference_frames = []
                element_references = []
                last_frame_reference = None

                # 第1步：从 prompt 中检测元素，查找 D:/cg_create/photos 下对应子目录的图片
                prompt_text = self._get_shot_reference_text(shot)
                if prompt_text:
                    element_references = self._find_element_references(prompt_text)
                    if element_references:
                        print(f"  [视频生成器] 镜头 {shot_num}: 从prompt检测到元素，找到参考图 {len(element_references)}张")

                # 第2步：根据Director决策决定是否使用帧继承
                if should_inherit and previous_video_path and previous_video_path.exists():
                    if not shot.get("disable_frame_inheritance"):
                        print(f"  [视频生成器] 镜头 {shot_num}: 帧继承，提取上一镜头最后帧")
                        last_frame_reference = self.extract_last_frame(previous_video_path)

                        if last_frame_reference:
                            # 帧继承时：上一帧优先作为主参考，然后追加元素图
                            reference_frames = [last_frame_reference] + element_references
                            print(f"  [视频生成器] ✓ 参考图顺序: 上一帧(首位) + {len(element_references)}张元素图")
                        else:
                            # 无法提取最后帧，只用元素图
                            reference_frames = element_references
                            print(f"  [视频生成器] ✗ 无法提取最后帧，使用元素图")
                    else:
                        print(f"  [视频生成器] 镜头 {shot_num}: 显式禁用帧继承，仅使用元素图")
                        reference_frames = element_references
                else:
                    # 不走帧继承：只用元素图
                    reference_frames = element_references
                    if not should_inherit:
                        print(f"  [视频生成器] 镜头 {shot_num}: 不继承帧，使用元素图")
                    else:
                        print(f"  [视频生成器] 镜头 {shot_num}: 需要继承但上一帧不可用，使用元素图")

                # 第3步：如果没有任何参考图，纯文本生成
                if not reference_frames:
                    print(f"  [视频生成器] 镜头 {shot_num}: 无匹配参考图，使用纯文本生成")

                # 【改进】使用主参考帧
                primary_reference = reference_frames[0] if reference_frames else None

                # 【调试】输出最终参考决策，便于核对与Director决策是否一致
                inherit_final = bool(last_frame_reference and last_frame_reference.exists())
                decision_str = (
                    f"  [视频生成器] 镜头 {shot_num} 决策: "
                    f"Director.use_frame_inheritance={should_inherit}, "
                    f"上一帧可用={bool(previous_video_path and previous_video_path.exists())}, "
                    f"最终使用帧继承={inherit_final}, 参考图数={len(reference_frames)}"
                )
                print(decision_str)

                # 调用API生成
                
                video_path = self._call_seedance_api(
                    shot=shot,
                    output_dir=output_dir,
                    reference_image=primary_reference,
                    reference_images=reference_frames,  # 传递完整的参考图列表
                    first_frame_reference=last_frame_reference,
                )

                # 计算连续性
                if primary_reference and video_path.exists():
                    first_frame = self.extract_first_frame(video_path)
                    if first_frame:
                        similarity = self.calculate_frame_similarity(primary_reference, first_frame)
                        continuity_scores.append({
                            "shot_number": shot.get("shot_number"),
                            "similarity": similarity
                        })
                        print(f"  [视频生成器] 连续性分数: {similarity:.2f}")

                videos.append({
                    "shot_number": shot.get("shot_number"),
                    "file": str(video_path),
                    "status": "success",
                    "prompt": shot.get("visual_prompt", ""),  # 【修复】完整提示词，不截断
                    "used_reference": primary_reference is not None,
                    "reference_frame": str(primary_reference) if primary_reference else None,
                    "reference_frames": [str(f) for f in reference_frames],
                    "director_decision": should_inherit,
                    "inheritance_requested": bool(should_inherit),
                    "previous_video_available": previous_video_path is not None,
                    "inheritance_applied": bool(last_frame_reference and last_frame_reference.exists()),
                })
                succeeded += 1
                previous_video_path = video_path

            except Exception as e:
                videos.append({
                    "shot_number": shot.get("shot_number"),
                    "file": None,
                    "status": "failed",
                    "task_id": getattr(e, "task_id", None),
                    "retryable": not isinstance(e, (SeedanceTaskSubmittedError, SeedanceSubmissionRejectedError)),
                    "error": str(e)
                })
                failed += 1
                previous_video_path = None
                print(f"  [视频生成器] 已停止：镜头 {shot_num} 生成失败，后续镜头不再提交")
                break
        
        avg_continuity = 0.0
        if continuity_scores:
            avg_continuity = sum(s["similarity"] for s in continuity_scores) / len(continuity_scores)
        
        return {
            "mode": "seedance",
            "total": len(shots),
            "succeeded": succeeded,
            "failed": failed,
            "videos": videos,
            "frame_inheritance_enabled": "Director决策（逐镜头）",  # 不再使用全局配置
            "continuity_scores": continuity_scores,
            "average_continuity": avg_continuity,
            "all_generated": succeeded == len(shots),
            "stopped_after_failure": succeeded < len(shots)
        }
    
    def _poll_seedance_task(self, status_url: str, headers: Dict[str, str],
                            task_id: str, requests) -> Dict:
        """查询已提交任务；查询失败时保留 task_id，禁止重新创建。"""
        max_wait_time = self.video_api_config.get("status_timeout", 600)
        poll_interval = self.video_api_config.get("poll_interval", 5)
        deadline = time.monotonic() + max_wait_time
        pending_states = {
            "pending", "queued", "processing", "not_start", "not_started",
            "in_progress", "inprogress", "running", "generating",
        }
        success_states = {"completed", "success", "succeeded", "done"}
        failure_states = {"failed", "failure", "error", "canceled", "cancelled"}
        first_request = True

        while time.monotonic() < deadline:
            if not first_request:
                time.sleep(poll_interval)
            first_request = False

            try:
                response = requests.get(status_url, headers=headers, timeout=30)
            except requests.exceptions.RequestException as exc:
                raise SeedanceTaskSubmittedError(
                    f"任务已提交，但状态查询网络失败: {exc}", task_id
                ) from exc

            if response.status_code == 501:
                raise SeedanceTaskSubmittedError(
                    "任务已提交，但服务商未实现当前状态查询接口（HTTP 501）",
                    task_id,
                )

            try:
                data = response.json()
            except ValueError as exc:
                raise SeedanceTaskSubmittedError(
                    f"任务已提交，但状态查询返回了无效JSON（HTTP {response.status_code}）",
                    task_id,
                ) from exc

            if response.status_code != 200:
                code = str(data.get("code", ""))
                message = data.get("message", response.text[:300])
                if response.status_code == 403 and "concurrency_limit" in code:
                    print(f"  [Seedance API] 并发限制，继续查询任务 {task_id}")
                    continue
                raise SeedanceTaskSubmittedError(
                    f"任务已提交，但查询失败 HTTP {response.status_code}: {message}",
                    task_id,
                )

            task = data.get("data", data)
            if not isinstance(task, dict):
                raise SeedanceTaskSubmittedError(
                    f"任务已提交，但状态查询返回格式异常: {data}", task_id
                )

            status = str(task.get("status", "")).strip().lower().replace("-", "_").replace(" ", "_")
            elapsed = int(max_wait_time - max(0, deadline - time.monotonic()))
            print(f"  [Seedance API] 状态: {status} (已等待 {elapsed}秒)")

            if status in success_states:
                return task
            if status in failure_states:
                error_msg = (
                    task.get("fail_reason")
                    or task.get("error")
                    or task.get("message")
                    or "未知错误"
                )
                raise ValueError(f"视频生成失败: {error_msg}")
            if status not in pending_states:
                raise SeedanceTaskSubmittedError(
                    f"任务已提交，但返回未知状态: {status}", task_id
                )

        raise SeedanceTaskSubmittedError(
            f"任务已提交，但状态查询超时（{max_wait_time}秒），禁止重新提交",
            task_id,
        )

    def _download_seedance_video(self, video_url: str, video_path: Path, requests) -> Path:
        """流式下载已完成的视频，不重新创建任务。"""
        with requests.get(video_url, stream=True, timeout=(10, 300)) as response:
            response.raise_for_status()
            with open(video_path, "wb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        output.write(chunk)
        return video_path

    def _encode_seedance_reference_image(self, ref_file: Path):
        """压缩本地参考图，避免 Base64 JSON 请求超过平台代理限制。"""
        raw_bytes = ref_file.read_bytes()
        image = cv2.imdecode(
            np.frombuffer(raw_bytes, dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )
        if image is None:
            raise ValueError(f"无法读取参考图: {ref_file}")

        max_side = int(self.video_api_config.get("reference_image_max_side", 768))
        quality = int(self.video_api_config.get("reference_image_jpeg_quality", 82))
        quality = max(50, min(95, quality))
        height, width = image.shape[:2]
        scale = min(1.0, max_side / max(height, width))
        if scale < 1.0:
            image = cv2.resize(
                image,
                (max(1, round(width * scale)), max(1, round(height * scale))),
                interpolation=cv2.INTER_AREA,
            )

        success, encoded = cv2.imencode(
            ".jpg",
            image,
            [
                cv2.IMWRITE_JPEG_QUALITY, quality,
                cv2.IMWRITE_JPEG_OPTIMIZE, 1,
            ],
        )
        if not success:
            raise ValueError(f"无法压缩参考图: {ref_file}")

        encoded_bytes = encoded.tobytes()
        data_url = "data:image/jpeg;base64," + base64.b64encode(encoded_bytes).decode("ascii")
        return data_url, len(encoded_bytes)

    def _call_seedance_api(self, shot: Dict, output_dir: Path, 
                          reference_image: Optional[Path] = None,
                          reference_images: Optional[List[Path]] = None,
                          first_frame_reference: Optional[Path] = None) -> Path:
        """
        调用Seedance API生成视频（OpenAI兼容接口）
        
        Args:
            shot: 镜头数据
            output_dir: 输出目录
            reference_image: 主要参考图片（用于帧继承）
            reference_images: 多张参考图片列表
            
        Returns:
            生成的视频文件路径
        """
        
        prompt = shot.get("visual_prompt", "")
        duration = shot.get("duration", 5.0)
        shot_number = shot.get("shot_number", 0)
        
        print(f"  [Seedance API] 生成镜头 {shot_number}")
        print(f"  [Seedance API] 提示词: {prompt}")  # 【修复】完整提示词，不截断
        print(f"  [Seedance API] 时长: {duration}秒")
        
        # 【改进】记录参考图信息
        if reference_images and len(reference_images) > 1:
            print(f"  [Seedance API] 使用多参考图 ({len(reference_images)}张): {reference_images}")
        elif reference_image:
            print(f"  [Seedance API] 使用参考图: {reference_image}")
        
        import requests

        
        # 获取API配置
        base_url = self.video_api_config.get("base_url", "https://www.moyu.cn")
        api_key = self.video_api_config.get("api_key", "")
        model = self.video_api_config.get("model", "doubao-seedance-2-0-mini-260615")
        
        # 【修复】解析分辨率和比例
        # 从 "720p" 和 "16:9" 转换为实际尺寸
        resolution = self.video_api_config.get("resolution", "720p")
        ratio = self.video_api_config.get("ratio", "16:9")
        
        # 【关键】分辨率映射表（根据Seedance API文档）
        size_map = {
            "480p": {
                "16:9": "854x480",
                "4:3": "752x560",
                "1:1": "640x640",
                "3:4": "560x752",
                "9:16": "480x854",
                "21:9": "992x432"
            },
            "720p": {
                "16:9": "1280x720",
                "4:3": "1112x834",
                "1:1": "960x960",
                "3:4": "834x1112",
                "9:16": "720x1280",
                "21:9": "1470x630"
            }
        }
        
        size = size_map.get(resolution, {}).get(ratio, "1280x720")
        
        if not api_key:
            raise ValueError("Seedance API配置不完整：缺少api_key")
        
        # 【修复】使用正确的视频生成端点（moyu.cn 图生视频标准端点）
        api_endpoint = f"{base_url}/v1/video/generations"

        print(f"  [Seedance API] 端点: {api_endpoint}")
        print(f"  [Seedance API] 模型: {model}")
        print(f"  [Seedance API] 尺寸: {size}")

        # 【修复】按 moyu.cn 多图生视频接口构造 JSON 请求体。
        # 首帧和元素参考图可以在同一个请求中提交：上一镜头末帧使用
        # first_frame，其余元素图使用 reference_image。
        first_frame_path = Path(first_frame_reference) if first_frame_reference else None
        has_first_frame = bool(first_frame_path and first_frame_path.exists())
        raw_reference_candidates = [Path(path) for path in (reference_images or [])]

        # 确保首帧始终排在第一位，并避免首帧文件被重复提交。
        if has_first_frame:
            reference_candidates = [first_frame_path]
            reference_candidates.extend(
                path for path in raw_reference_candidates
                if path.resolve() != first_frame_path.resolve()
            )
        else:
            reference_candidates = raw_reference_candidates

        max_reference_images = max(
            1, int(self.video_api_config.get("max_reference_images", 6))
        )
        if len(reference_candidates) > max_reference_images:
            reference_candidates = reference_candidates[:max_reference_images]
            print(
                f"  [Seedance API] 参考图超过上限，仅保留前 {max_reference_images} 张"
            )


        content = [{"type": "text", "text": prompt}]
        

        # 构造 metadata。注：当前 doubao-seedance-2-0-mini 在 r2v（图生视频）
        # 模式下不支持自定义 duration 参数，传了会被 API 400 拒绝：
        #   "the parameter duration specified in the request is not valid for
        #    model doubao-seedance-2-0-mini in r2v"
        # 该模型在 r2v 模式下使用固定时长（约 5 秒），由模型自身决定。
        # 因此这里不再向 Seedance 透传 shot.duration；其它视频 API（Kling、
        # Runway、Pika）走各自的分支，原有 duration 透传逻辑保持不变。
        seedance_metadata = {
            "content": content,
            "resolution": resolution,
            "ratio": ratio,
            "generate_audio": self.video_api_config.get("generate_audio", True),
        }
        # 仅在显式开启 "seedance_supports_duration" 时才透传 duration，
        # 以便未来支持自定义时长的 Seedance 模型（如 pro 版）能直接受益。
        if self.video_api_config.get("seedance_supports_duration", False):
            seedance_metadata["duration"] = duration

        request_body = {
            "model": model,
            "prompt": "首帧生视频",
            "metadata": seedance_metadata,
        }

        max_request_body_bytes = max(
            512 * 1024,
            int(self.video_api_config.get("max_request_body_bytes", 8 * 1024 * 1024)),
        )

        # 先压缩候选图片，确定是否属于“单独首帧”场景。
        encoded_references = []
        for ref_path in reference_candidates:
            ref_file = Path(ref_path)
            if not ref_file.exists():
                print(f"    文件不存在，跳过: {ref_file}")
                continue

            try:
                image_url, compressed_size = self._encode_seedance_reference_image(ref_file)
            except Exception as exc:
                print(f"    参考图压缩失败，跳过 {ref_file.name}: {exc}")
                continue

            is_previous_frame = (
                first_frame_path is not None
                and ref_file.resolve() == first_frame_path.resolve()
            )
            encoded_references.append(
                (ref_file, image_url, compressed_size, is_previous_frame)
            )

        skipped_for_size = []
        image_index = 0
        for ref_file, image_url, compressed_size, is_previous_frame in encoded_references:
            role = "first_frame" if has_first_frame and is_previous_frame else "reference_image"
            image_item = {
                "type": "image_url",
                "image_url": {"url": image_url},
                # "role": role,
            }
            content.append(image_item)
            estimated_body_size = len(
                json.dumps(request_body, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
            )
            if estimated_body_size > max_request_body_bytes:
                content.pop()
                skipped_for_size.append(ref_file.name)
                continue

            image_index += 1
            print(
                f"    [{image_index}] {role}: {ref_file.name} "
                f"(压缩后 {compressed_size / 1024:.1f} KB)"
            )

        if skipped_for_size:
            print(
                "  [Seedance API] 请求体预算不足，跳过参考图: "
                + ", ".join(skipped_for_size)
            )
        if not encoded_references:
            print(f"  [Seedance API] 无可用参考图，使用纯文本生成")
        elif image_index == 0:
            print(f"  [Seedance API] 参考图均超出请求体预算，使用纯文本生成")

        estimated_body_size = len(
            json.dumps(request_body, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        )
        print(
            f"  [Seedance API] 请求体估算: {estimated_body_size / 1024 / 1024:.2f} MiB "
            f"(上限 {max_request_body_bytes / 1024 / 1024:.2f} MiB)"
        )
        print(f"  [Seedance API] 调用API...")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        response = requests.post(
            api_endpoint,
            headers=headers,
            json=request_body,
            timeout=800
        )

        # 检查响应状态
        if response.status_code != 200:
            error_detail = response.text[:500]
            raise SeedanceSubmissionRejectedError(
                f"API拒绝创建任务 {response.status_code}: {error_detail}"
            )
        
        # 解析响应
        result = response.json()
        
        # 【关键】获取任务ID（异步生成）
        # 【修复】Seedance可能返回 "task_id" 或 "id"
        task_id = result.get("task_id") or result.get("id")
        if not task_id:
            raise ValueError(f"API响应缺少任务ID: {result}")
        
        print(f"  [Seedance API] 任务ID: {task_id}")
        print(f"  [Seedance API] 等待生成完成...")
        
        # 创建、查询、下载分为独立阶段。拿到 task_id 后，任何查询异常
        # 都不能回到外层重新提交，否则可能产生重复任务和重复扣费。
        status_data = self._poll_seedance_task(
            status_url=f"{base_url}/v1/video/generations/{task_id}",
            headers=headers,
            task_id=str(task_id),
            requests=requests,
        )
        video_url = (
            status_data.get("result_url")
            or status_data.get("video_url")
            or status_data.get("url")
        )
        if not video_url:
            raise SeedanceTaskSubmittedError(
                f"任务已完成但响应缺少视频URL: {status_data}", str(task_id)
            )

        video_path = output_dir / f"shot_{shot_number:03d}.mp4"
        try:
            self._download_seedance_video(video_url, video_path, requests)
        except Exception as exc:
            raise SeedanceTaskSubmittedError(
                f"任务已完成但视频下载失败: {exc}", str(task_id)
            ) from exc
        print(f"  [Seedance API] ✓ 视频已保存: {video_path}")
        return video_path
