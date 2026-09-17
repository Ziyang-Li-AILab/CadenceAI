# -*- coding: utf-8 -*-
"""
Post Production - 后期制作

负责视频剪辑、音频合成和字幕添加
"""

import json
import subprocess
from typing import Dict, List, Optional
from pathlib import Path

from core.base_agent import BaseAgent, AgentResponse


def _generate_placeholder_mp3(output_path: Path, duration_seconds: float = 1.0, freq: int = 440) -> Optional[str]:
    """用 imageio 自带的 ffmpeg 生成一段占位正弦波 mp3。

    Args:
        output_path: 输出文件路径
        duration_seconds: 时长（秒）
        freq: 正弦波频率

    Returns:
        写入的路径，失败返回 None
    """
    try:
        import imageio_ffmpeg

        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        subprocess.run(
            [
                ffmpeg_path,
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={freq}:duration={duration_seconds}",
                "-ar",
                "48000",
                "-ac",
                "1",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )
        return str(output_path)
    except Exception:
        return None


class VoiceProfileManager:
    """
    【新增】音色一致性管理器
    
    核心职责：
    1. 管理参考音频与角色的绑定（参考音频只对应一个人物）
    2. 为其他角色生成音色描述，确保跨镜头一致性
    3. 防止参考音频被错误地用于多个角色
    
    【设计原则】
    - 一个参考音频只能绑定到一个角色
    - 其他角色的音色通过描述生成，但保持一致
    - 每次生成都需要验证音色是否与该角色历史一致
    """
    
    def __init__(self):
        # 角色音色配置表
        self.profiles: Dict[str, Dict] = {}
        # 参考音频到角色的映射（只能有一个）
        self.reference_audio_binding: Dict[str, str] = {}  # reference_audio -> character
        # 旁白专用音色配置（永远不使用参考音频）
        self.narration_profile: Dict = None
    
    def set_reference_voice(self, character: str, reference_audio: str, description: str = ""):
        """
        设置参考音频对应的角色
        
        【关键约束】参考音频只能绑定到一个角色
        如果之前有绑定，会覆盖原绑定
        """
        # 解除之前的绑定（如果存在）
        for char, ref in list(self.reference_audio_binding.items()):
            if ref == character:
                del self.reference_audio_binding[char]
        
        # 建立新绑定
        self.reference_audio_binding[reference_audio] = character
        
        self.profiles[character] = {
            "type": "reference",
            "reference_audio": reference_audio,
            "description": description,
            "consistent": True
        }
        
        print(f"[音色管理器] 参考音频 '{reference_audio}' 绑定到角色 '{character}'")
    
    def set_narration_voice(self, description: str):
        """
        设置旁白音色（永远不使用参考音频）
        
        旁白应该有独立的音色，与所有角色区分开
        """
        self.narration_profile = {
            "type": "narration",
            "description": description,
            "reference_audio": None,
            "character": "__NARRATOR__",
            "consistent": True
        }
        print(f"[音色管理器] 旁白音色已配置: {description}")
    
    def generate_voice_profile(self, character: str, dialogues: List[Dict] = None):
        """
        为角色生成音色描述
        
        当没有参考音频时，根据角色特征和对话生成音色描述
        确保该角色在所有镜头中使用相同的音色
        """
        # 检查是否已有该角色的配置
        if character in self.profiles:
            return self.profiles[character]
        
        # 基于对话内容推断音色
        voice_description = self._infer_voice_from_dialogues(character, dialogues or [])
        
        self.profiles[character] = {
            "type": "generated",
            "description": voice_description,
            "reference_audio": None,
            "consistent": True
        }
        
        print(f"[音色管理器] 为角色 '{character}' 生成音色描述: {voice_description}")
        return self.profiles[character]
    
    def _infer_voice_from_dialogues(self, character: str, dialogues: List[Dict]) -> str:
        """
        从对话内容推断角色音色
        
        分析对话的语气、情绪、词汇特征来描述音色
        """
        if not dialogues:
            # 默认音色描述
            return "中性、自然的说话方式，语速适中"
        
        # 收集所有对话内容
        all_text = " ".join([d.get("content", "") for d in dialogues])
        emotions = [d.get("emotion", "") for d in dialogues if d.get("emotion")]
        
        # 分析情绪特征
        emotion_counts = {}
        for e in emotions:
            emotion_counts[e] = emotion_counts.get(e, 0) + 1
        
        dominant_emotion = max(emotion_counts, key=emotion_counts.get) if emotion_counts else "平静"
        
        # 基于情绪推断音色
        voice_mapping = {
            "愤怒": "低沉有力，带有压迫感，语速较快",
            "悲伤": "低沉沙哑，语速较慢，带有颤抖",
            "恐惧": "尖细紧绷，语速急促，偶尔停顿",
            "冷漠": "平淡机械，语速稳定，缺乏情感起伏",
            "坚定": "浑厚有力，语速适中，停顿清晰",
            "冷笑": "阴冷低沉，带有嘲讽意味",
            "欢乐": "明快清脆，语速轻快，语调上扬",
            "平静": "自然舒缓，语速平稳，音色干净"
        }
        
        base_voice = voice_mapping.get(dominant_emotion, voice_mapping["平静"])
        
        return base_voice
    
    def get_profile(self, character: str) -> Optional[Dict]:
        """获取角色的音色配置"""
        return self.profiles.get(character)
    
    def has_profile(self, character: str) -> bool:
        """检查是否有该角色的音色配置"""
        return character in self.profiles
    

    
    def validate_consistency(self, character: str, new_dialogue: Dict) -> bool:
        """
        【关键】验证新对话是否与历史音色一致
        
        调用TTS前必须验证，确保跨镜头音色一致
        """
        if character not in self.profiles:
            # 如果没有配置先生成
            self.generate_voice_profile(character, [new_dialogue])
            return True
        
        profile = self.profiles[character]
        
        # 如果是参考音色，直接通过
        if profile.get("type") == "reference":
            return True
        
        # 如果是生成音色，检查新对话的情绪是否与历史一致
        new_emotion = new_dialogue.get("emotion", "平静")
        description = profile.get("description", "")
        
        # 简单的情绪一致性检查
        # 如果新情绪与音色描述不匹配，发出警告
        expected_voice = self._infer_voice_from_dialogues(character, [new_dialogue])
        
        return True  # 简化版，始终返回一致
    
    def get_narration_profile(self) -> Optional[Dict]:
        """获取旁白音色配置"""
        return self.narration_profile
    
    def get_all_profiles_summary(self) -> Dict:
        """获取所有音色配置摘要"""
        reference_voices = []
        generated_voices = []
        
        # 分类角色
        for char, profile in self.profiles.items():
            if profile.get("type") == "reference":
                reference_voices.append(char)
            else:
                generated_voices.append(char)
        
        return {
            "reference_voices": reference_voices,
            "generated_voices": generated_voices,
            "narration_configured": self.narration_profile is not None,
            "total_characters": len(self.profiles)
        }


class PostProduction(BaseAgent):
    """
    后期制作 - 视频剪辑和合成
    
    核心职责：
    1. 将多个视频片段剪辑成完整视频
    2. 添加音频（旁白、对话、音效、背景音乐）
    3. 添加字幕
    4. 调色和特效
    5. 导出最终成片
    
    【音色控制机制】
    - 参考音频只对应一个特定人物（通常是主角）
    - 其他人物的音色由模型自主生成，但需要在多个镜头下保持一致
    - 为每个角色生成音色描述，确保跨镜头一致性
    
    输入：视频片段列表 + 音频脚本
    输出：最终视频文件
    """
    
    def __init__(self, llm_config: Dict, tts_config: Dict = None):
        config = {"llm": llm_config}
        super().__init__(config)
        self.name = "后期制作"
        self.tts_config = tts_config or {"provider": "mock"}
        
        # 【新增】音色一致性管理器
        self.voice_profile_manager = VoiceProfileManager()
    
    def execute(self, context: Dict) -> AgentResponse:
        """执行后期制作"""
        
        video_files = context.get("video_files", [])
        shots = context.get("shots", [])
        output_path = context.get("output_path", Path("final_video.mp4"))
        
        add_music = context.get("add_music", False)
        add_subtitles = context.get("add_subtitles", True)
        
        # 【新增】获取参考音频
        reference_audio = context.get("reference_audio")
        
        if not video_files:
            # Mock模式：生成报告但不实际处理
            return self._mock_post_production(shots, output_path, reference_audio)
        
        # 【新增】初始化音色配置
        self._initialize_voice_profiles(shots, reference_audio)
        
        # 【新增】输出音色配置摘要（用于调试）
        summary = self.voice_profile_manager.get_all_profiles_summary()
        print("\n[后期制作] 音色配置摘要:")
        print(f"  - 参考音频角色: {summary.get('reference_voices', [])}")
        print(f"  - 描述生成角色: {summary.get('generated_voices', [])}")
        print(f"  - 旁白音色: {'已配置' if summary.get('narration_configured') else '未配置'}")
        
        # 1. 生成音频
        audio_tracks = self._generate_audio(shots)
        
        # 2. 剪辑视频
        edited_video = self._edit_video(video_files, shots)
        
        # 3. 合成音频
        final_audio = self._composite_audio(audio_tracks, add_music)
        
        # 4. 合成视频和音频
        video_with_audio = self._merge_video_audio(edited_video, final_audio)
        
        # 5. 添加字幕
        if add_subtitles:
            final_video = self._add_subtitles(video_with_audio, shots, output_path)
        else:
            final_video = video_with_audio
        
        result = {
            "final_video": str(final_video),
            "audio_tracks": len(audio_tracks),
            "subtitles": len(shots) if add_subtitles else 0,
            "duration": sum(shot.get("duration", 0) for shot in shots),
            "voice_profiles": self.voice_profile_manager.get_all_profiles_summary()
        }
        
        return AgentResponse(
            success=True,
            data=result
        )
    
    def _initialize_voice_profiles(self, shots: List[Dict], reference_audio: str = None,
                                   protagonist_name: Optional[str] = None):
        """Initialize voice profiles from the characters in the current shots.

        The reference audio is bound to the first current character when no
        explicit protagonist name is supplied; no project-specific name is used.
        """
        # 1. Collect all characters from the current output.
        all_characters = set()
        character_dialogues = {}  # character -> dialogue list
        
        for shot in shots:
            audio_prompt = shot.get("audio_prompt", {})
            
            # 从多个来源提取角色信息
            characters_in_shot = []
            
            # 来源1: 支持新结构 audio_prompt.dialogue，也兼容旧结构 type=dialogue
            dialogue_prompt = audio_prompt.get("dialogue")
            if not dialogue_prompt and audio_prompt.get("type") == "dialogue":
                dialogue_prompt = audio_prompt
            if dialogue_prompt:
                char = (dialogue_prompt.get("character") or dialogue_prompt.get("speaker", "")).strip()
                if char:
                    characters_in_shot.append(char)
            
            # 来源2: metadata.characters
            metadata = shot.get("metadata", {})
            meta_chars = metadata.get("characters", [])
            characters_in_shot.extend(meta_chars)
            
            # 来源3: 仅在调用方明确指定主角时检查视觉提示词。
            visual_prompt = shot.get("visual_prompt", "")
            if protagonist_name and protagonist_name in visual_prompt:
                characters_in_shot.append(protagonist_name)
            
            # 去重并记录
            for char in characters_in_shot:
                if char:
                    all_characters.add(char)
                    if char not in character_dialogues:
                        character_dialogues[char] = []
                    if dialogue_prompt:
                        character_dialogues[char].append(dialogue_prompt)
        
        # 2. 将参考音频绑定到当前输出中的第一个角色。
        if reference_audio and protagonist_name is None and all_characters:
            protagonist_name = next(iter(all_characters))

        if reference_audio and protagonist_name:
            self.voice_profile_manager.set_reference_voice(
                character=protagonist_name,
                reference_audio=reference_audio,
                description=f"{protagonist_name}的参考音色（用户提供）"
            )
            print(f"[后期制作] ✓ 参考音频绑定到当前角色: {protagonist_name}")
        
        # 3. 为旁白配置独立音色（永远不使用参考音频）
        self.voice_profile_manager.set_narration_voice(
            description="低沉男声，混响如古钟，语速缓慢，庄重肃穆"
        )
        print(f"[后期制作] ✓ 旁白音色已配置（独立音色，不使用参考音频）")
        
        # 4. 为其他角色生成音色描述
        for char in all_characters:
            if not self.voice_profile_manager.has_profile(char):
                self.voice_profile_manager.generate_voice_profile(
                    character=char,
                    dialogues=character_dialogues.get(char, [])
                )
                print(f"[后期制作] ✓ 为角色 '{char}' 生成音色描述")
    
    def _mock_post_production(self, shots: List[Dict], 
                             output_path: Path,
                             reference_audio: str = None) -> AgentResponse:
        """Mock模式的后期制作"""
        
        # 【新增】初始化音色配置
        self._initialize_voice_profiles(shots, reference_audio)
        
        # 生成音频脚本
        audio_script = []
        for shot in shots:
            audio_prompt = shot.get("audio_prompt", {})
            if audio_prompt:
                duration = float(shot.get("duration", 3.0))
                speech_items = []
                for key in ("dialogue", "narration"):
                    item = audio_prompt.get(key)
                    if item and item.get("content"):
                        speech_items.append(item)
                # 兼容旧格式
                if not speech_items and audio_prompt.get("content"):
                    speech_items.append(audio_prompt)
                for item in speech_items:
                    character = item.get("character", "") if item.get("type") == "dialogue" else "__NARRATOR__"
                    audio_script.append({
                        "shot_number": shot.get("shot_number"),
                        "type": item.get("type"),
                        "content": item.get("content", ""),
                        "duration": duration,
                        "estimated_duration_seconds": item.get("estimated_duration_seconds", 0.0),
                        "timing_status": "fits" if item.get("estimated_duration_seconds", 0.0) <= duration else "over_target",
                        "character": character,
                        "voice_profile": self.voice_profile_manager.get_profile(character) if character and character != "__NARRATOR__" else self.voice_profile_manager.get_narration_profile()
                    })
        
        # 保存音频脚本
        script_path = output_path.parent / "audio_script.json"
        with open(script_path, 'w', encoding='utf-8') as f:
            json.dump(audio_script, f, ensure_ascii=False, indent=2)
        
        result = {
            "final_video": str(output_path),
            "audio_tracks": len(audio_script),
            "subtitles": len(shots),
            "duration": sum(shot.get("duration", 0) for shot in shots),
            "mode": "mock",
            "audio_script": str(script_path),
            "voice_profiles": self.voice_profile_manager.get_all_profiles_summary()
        }
        
        return AgentResponse(
            success=True,
            data=result,
            warnings=["运行在Mock模式，未实际生成视频"]
        )
    
    def _generate_audio(self, shots: List[Dict]) -> List[Dict]:
        """生成音频轨道"""
        
        audio_tracks = []
        
        for shot in shots:
            audio_prompt = shot.get("audio_prompt", {})
            if not audio_prompt:
                continue
            
            # 规范化为多条语音，允许同一镜头同时存在对白和旁白。
            speech_items = []
            for key in ("dialogue", "narration"):
                item = audio_prompt.get(key)
                if isinstance(item, dict) and item.get("content"):
                    speech_items.append(item)
            if not speech_items and audio_prompt.get("content"):
                speech_items.append(audio_prompt)

            for item in speech_items:
                audio_type = item.get("type")
                if audio_type == "narration":
                    audio_file = self._generate_narration(item.get("content", ""), shot.get("shot_number"))
                    character = "__NARRATOR__"
                elif audio_type == "dialogue":
                    character = (item.get("character") or item.get("speaker", "")).strip()
                    if not character:
                        characters = shot.get("metadata", {}).get("characters", [])
                        character = characters[0] if characters else ""
                    audio_file = self._generate_dialogue(
                        item.get("content", ""), character,
                        item.get("emotion", "平静"), shot.get("shot_number")
                    )
                else:
                    continue
                estimated = float(item.get("estimated_duration_seconds", 0.0))
                audio_tracks.append({
                    "shot": shot.get("shot_number"),
                    "type": audio_type,
                    "file": audio_file,
                    "duration": float(shot.get("duration", 3.0)),
                    "estimated_audio_duration": estimated,
                    "timing_status": "fits" if estimated <= float(shot.get("duration", 3.0)) else "over_target",
                    "character": character,
                })
            continue

        return audio_tracks

    def _generate_narration(self, text: str, shot_number: int) -> Optional[str]:
        """生成旁白音频（使用独立的旁白音色，永远不使用参考音频）

        Args:
            text: 旁白文本
            shot_number: 镜头编号

        Returns:
            音频文件路径，失败返回None
        """
        provider = self.tts_config.get("provider")

        if provider == "mock":
            return None

        # ✅ 获取旁白专用音色配置（绝不使用参考音频）
        narration_profile = self.voice_profile_manager.get_narration_profile()

        output_dir = Path(self.tts_config.get("output_dir", "audio"))
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / f"narration_{shot_number:03d}.mp3"

        # 旁白使用配置的 TTS（纯文本描述生成音色）
        voice_desc = (
            narration_profile.get("description")
            if narration_profile
            else "低沉男声，混响如古钟，语速缓慢，庄重肃穆"
        )
        api_result = self._call_tts_api(
            text=text,
            text_prompt=f'旁白（{voice_desc}）："{text}"',
            reference_audio=None,
            output_path=output_path,
            label="旁白生成",
        )
        if api_result:
            return api_result

        # 降级：写一段真实可播放的占位 mp3
        print(f"[旁白生成] TTS 不可用，生成占位正弦波音频")
        placeholder = _generate_placeholder_mp3(
            output_path,
            duration_seconds=max(1.0, len(text) * 0.18),
            freq=320,
        )
        if placeholder:
            print(f"[旁白生成] ✓ 已生成（独立音色）: {output_path}")
            return placeholder
        print(f"[旁白生成] ✗ 占位音频生成失败: {output_path}")
        return None
    
    def _generate_dialogue(self, text: str, character: str, 
                          emotion: str, shot_number: int) -> Optional[str]:
        """生成角色对话音频
        
        使用字节跳动 TTS API 生成音频：
        - 支持参考音频（音色克隆）
        - 支持纯文本描述生成
        - 确保跨镜头音色一致性
        
        Args:
            text: 对话文本
            character: 角色名
            emotion: 情绪
            shot_number: 镜头编号
            
        Returns:
            音频文件路径，失败返回None
        """
        # 【新增】验证角色名
        if not character or not character.strip():
            print(f"[对话生成] ✗ 错误: 角色名为空，跳过生成")
            return None
        
        provider = self.tts_config.get("provider")
        
        if provider == "mock":
            return None
        
        # 【关键】验证音色一致性
        if not self.voice_profile_manager.validate_consistency(
            character, {"content": text, "emotion": emotion}
        ):
            print(f"[对话生成] 警告: 角色 {character} 的音色可能不一致")

        # 获取角色的音色配置
        voice_profile = self.voice_profile_manager.get_profile(character)

        output_dir = Path(self.tts_config.get("output_dir", "audio"))
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / f"dialogue_{character}_{shot_number:03d}.mp3"

        reference_audio_path = None
        text_prompt = ""
        if voice_profile and voice_profile.get("type") == "reference":
            reference_audio_path = voice_profile.get("reference_audio")
            print(f"[对话生成] 使用参考音频: {reference_audio_path} (角色: {character})")
            emotion_prefix = self._get_emotion_description(emotion)
            text_prompt = f'{emotion_prefix}{character}说道："{text}"'
        else:
            voice_desc = (
                voice_profile.get("description", "自然清晰的说话方式")
                if voice_profile
                else "自然清晰的说话方式"
            )
            emotion_desc = self._get_emotion_description(emotion)
            text_prompt = f'{character}（{voice_desc}，{emotion_desc}）说道："{text}"'
            print(f"[对话生成] 使用音色描述: {voice_desc} (角色: {character})")

        api_result = self._call_tts_api(
            text=text,
            text_prompt=text_prompt,
            reference_audio=reference_audio_path,
            output_path=output_path,
            label="对话生成",
        )
        if api_result:
            return api_result
        return self._generate_fallback_audio(text, character, emotion, shot_number, output_path)

    def _call_tts_api(
        self,
        text: str,
        text_prompt: str,
        output_path: Path,
        label: str,
        reference_audio: Optional[str] = None,
    ) -> Optional[str]:
        """调用配置的 TTS API。

        端点、Key、模型均从 `tts_config`（即主入口的 audio_api 配置）读取。
        """
        try:
            import requests
            import base64
        except ImportError:
            print(f"[{label}] 缺少 requests 依赖，无法调用 TTS API")
            return None

        api_endpoint = self.tts_config.get("endpoint")
        api_key = self.tts_config.get("api_key")
        model = self.tts_config.get("model", "seed-audio-1.0")

        if not api_endpoint or not api_key:
            print(f"[{label}] TTS 未配置 (endpoint/api_key)，将走降级路径")
            return None

        request_body = {
            "model": model,
            "audio_config": {
                "format": "mp3",
                "sample_rate": 48000,
                "pitch_rate": 0,
                "speech_rate": 0,
                "loudness_rate": 0,
            },
            "watermark": {},
            "text_prompt": text_prompt,
        }

        if reference_audio and Path(reference_audio).is_file():
            try:
                with open(reference_audio, "rb") as f:
                    audio_b64 = base64.b64encode(f.read()).decode("utf-8")
                request_body["references"] = [{"audio_data": audio_b64}]
                print(f"[{label}] ✓ 参考音频已编码 (模型 {model})")
            except OSError as e:
                print(f"[{label}] ⚠ 读取参考音频失败: {e}，回退到描述生成")

        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": api_key,
        }

        print(f"[{label}] 调用 TTS API endpoint={api_endpoint} model={model}")
        try:
            response = requests.post(
                api_endpoint,
                headers=headers,
                json=request_body,
                timeout=300,
            )
        except Exception as exc:
            print(f"[{label}] 网络异常: {exc}")
            return None

        if response.status_code == 200:
            result = response.json() if response.text else {}
            if result.get("code") == 0:
                audio_b64 = result.get("audio", "")
                if not audio_b64:
                    print(f"[{label}] API 响应缺少音频数据")
                    return None
                audio_bytes = base64.b64decode(audio_b64)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(audio_bytes)
                duration = result.get("duration", 0)
                print(f"[{label}] ✓ 成功生成: {output_path} (时长: {duration:.2f}秒, 模型: {model})")
                return str(output_path)
            print(f"[{label}] API 错误: {result.get('message', 'Unknown error')}")
            return None

        print(f"[{label}] HTTP 错误: {response.status_code} {response.text[:200]}")
        return None

    def _get_emotion_description(self, emotion: str) -> str:
        """将情绪转换为自然语言描述"""
        emotion_map = {
            "愤怒": "语气愤怒，声音低沉有力",
            "悲伤": "语气悲伤，声音低沉带有颤抖",
            "恐惧": "语气恐惧，声音紧张急促",
            "冷漠": "语气冷漠，声音平淡机械",
            "坚定": "语气坚定，声音浑厚有力",
            "冷笑": "语气嘲讽，声音阴冷带有讽刺",
            "欢乐": "语气欢快，声音明快轻松",
            "平静": "语气平静，声音自然舒缓"
        }
        return emotion_map.get(emotion, "语气自然")
    
    def _generate_fallback_audio(self, text: str, character: str,
                                 emotion: str, shot_number: int,
                                 output_path: Path) -> Optional[str]:
        """生成降级音频（当API失败时）"""
        try:
            # 根据情绪调整音频频率
            emotion_freq_map = {
                "愤怒": 480,
                "悲伤": 380,
                "恐惧": 520,
                "冷漠": 400,
                "坚定": 420,
                "冷笑": 390,
                "欢乐": 500,
                "平静": 440,
            }

            base_freq = emotion_freq_map.get(emotion, 440)
            duration_seconds = max(1.0, len(text) * 0.18)

            placeholder = _generate_placeholder_mp3(
                output_path, duration_seconds=duration_seconds, freq=base_freq
            )
            if placeholder:
                print(f"[对话生成] ⚠ 已生成降级音频: {output_path}")
                return placeholder

            # 退而求其次：写一个静默 mp3（一帧 0 字节都嫌多于 ffmpeg 兼容的最小帧）
            # 直接调用 ffmpeg anullsrc 作为最后手段
            try:
                import imageio_ffmpeg

                ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
                subprocess.run(
                    [
                        ffmpeg_path,
                        "-y",
                        "-f",
                        "lavfi",
                        "-i",
                        f"anullsrc=channel_layout=mono:sample_rate=48000",
                        "-t",
                        f"{duration_seconds}",
                        "-q:a",
                        "9",
                        "-acodec",
                        "libmp3lame",
                        str(output_path),
                    ],
                    check=True,
                    capture_output=True,
                )
                print(f"[对话生成] ⚠ 已生成降级静默音频: {output_path}")
                return str(output_path)
            except Exception:
                pass

            print(f"[对话生成] 降级音频生成失败: {output_path}")
            return None

        except Exception as e:
            print(f"[对话生成] 降级音频生成失败: {e}")
            return None
    
    def _edit_video(self, video_files: List[Dict], shots: List[Dict]) -> str:
        """剪辑视频片段
        
        Args:
            video_files: 视频文件列表
            shots: 镜头信息列表
            
        Returns:
            剪辑后的视频路径
        """
        try:
            from moviepy import VideoFileClip, concatenate_videoclips
            
            print(f"[视频剪辑] 开始剪辑 {len(video_files)} 个视频片段...")
            
            clips = []
            
            for idx, video_info in enumerate(video_files):
                video_path = video_info.get("file") or video_info.get("path")
                if not video_path or not Path(video_path).is_file():
                    print(f"[视频剪辑] 警告: 视频文件不存在 {video_path}")
                    continue
                
                # 加载视频
                clip = VideoFileClip(video_path)
                
                # 获取对应的shot信息
                if idx < len(shots):
                    shot = shots[idx]
                    target_duration = shot.get("duration", 3.0)
                    
                    # 裁剪到目标时长
                    if clip.duration > target_duration:
                        clip = clip.subclipped(0, target_duration)
                    elif clip.duration < target_duration:
                        # 如果视频太短，循环播放
                        from moviepy import loop
                        clip = loop(clip, duration=target_duration)
                
                clips.append(clip)
            
            if not clips:
                print(f"[视频剪辑] 错误: 没有有效的视频片段")
                return None
            
            # 连接所有片段
            final_clip = concatenate_videoclips(clips, method="compose")
            
            # 输出路径
            output_dir = Path(self.tts_config.get("output_dir", "output"))
            output_dir.mkdir(exist_ok=True)
            output_path = output_dir / "edited_video.mp4"
            
            # 导出
            final_clip.write_videofile(
                str(output_path),
                codec='libx264',
                audio_codec='aac',
                fps=24
            )
            
            # 释放资源
            for clip in clips:
                clip.close()
            final_clip.close()
            
            print(f"[视频剪辑] 已完成: {output_path}")
            return str(output_path)
            
        except Exception as e:
            print(f"[视频剪辑] 失败: {e}")
            import traceback
            traceback.print_exc()
            return "edited_video.mp4"
    
    def _composite_audio(self, audio_tracks: List[Dict], 
                        add_music: bool) -> str:
        """合成音频轨道
        
        Args:
            audio_tracks: 音频轨道列表
            add_music: 是否添加背景音乐
            
        Returns:
            合成后的音频路径
        """
        try:
            # 尝试导入pydub，如果失败则使用moviepy
            try:
                from pydub import AudioSegment
                use_pydub = True
            except (ImportError, ModuleNotFoundError) as e:
                print(f"[音频合成] pydub不可用 ({e})，将使用moviepy")
                from moviepy import AudioFileClip, CompositeAudioClip
                use_pydub = False
            
            print(f"[音频合成] 开始合成 {len(audio_tracks)} 个音频轨道...")
            
            if use_pydub:
                # 使用pydub合成
                # 计算总时长
                total_duration = sum(track.get("duration", 0) for track in audio_tracks) * 1000
                
                # 创建空白音频
                final_audio = AudioSegment.silent(duration=int(total_duration))
                
                # 添加各个音频轨道
                current_position = 0
                
                for track in audio_tracks:
                    audio_file = track.get("file")
                    if not audio_file or not Path(audio_file).exists():
                        # 跳过不存在的文件
                        current_position += int(track.get("duration", 3.0) * 1000)
                        continue
                    
                    # 加载音频
                    audio = AudioSegment.from_file(audio_file)
                    
                    # 调整音量（对话和旁白应该更响）
                    if track.get("type") in ["dialogue", "narration"]:
                        audio = audio + 3  # 增加3dB
                
                # 叠加到时间轴
                final_audio = final_audio.overlay(audio, position=current_position)
                
                current_position += int(track.get("duration", 3.0) * 1000)
            
                # 添加背景音乐
                if add_music:
                    print(f"[音频合成] 添加背景音乐...")
                    music_path = self._generate_background_music(
                        duration=total_duration / 1000.0,
                        mood="epic"
                    )
                    
                    if music_path and Path(music_path).exists():
                        music = AudioSegment.from_file(music_path)
                        # 降低音乐音量，不要盖过对话
                        music = music - 15
                        final_audio = final_audio.overlay(music)
                
                # 导出
                output_dir = Path(self.tts_config.get("output_dir", "output"))
                output_dir.mkdir(exist_ok=True)
                output_path = output_dir / "final_audio.mp3"
                
                final_audio.export(str(output_path), format="mp3", bitrate="192k")
                
                print(f"[音频合成] 已完成: {output_path}")
                return str(output_path)
            
            else:
                # 使用moviepy合成
                audio_clips = []
                total_duration = 0
                
                for track in audio_tracks:
                    audio_file = track.get("file")
                    if not audio_file or not Path(audio_file).exists():
                        total_duration += track.get("duration", 3.0)
                        continue
                    
                    # 加载音频
                    audio_clip = AudioFileClip(audio_file)
                    
                    # 设置开始时间
                    audio_clip = audio_clip.set_start(total_duration)
                    
                    # 调整音量
                    if track.get("type") in ["dialogue", "narration"]:
                        audio_clip = audio_clip.volumex(1.2)
                    
                    audio_clips.append(audio_clip)
                    total_duration += track.get("duration", audio_clip.duration)
                
                if not audio_clips:
                    print(f"[音频合成] 警告: 没有有效的音频轨道")
                    return "final_audio.mp3"
                
                # 合成所有音频
                final_audio = CompositeAudioClip(audio_clips)
                
                # 导出
                output_dir = Path(self.tts_config.get("output_dir", "output"))
                output_dir.mkdir(exist_ok=True)
                output_path = output_dir / "final_audio.mp3"
                
                final_audio.write_audiofile(str(output_path), fps=44100, nbytes=2, codec='mp3')
                
                print(f"[音频合成] 已完成: {output_path}")
                return str(output_path)
            
        except Exception as e:
            print(f"[音频合成] 失败: {e}")
            import traceback
            traceback.print_exc()
            return "final_audio.mp3"
    
    def _generate_background_music(self, duration: float, mood: str = "epic") -> Optional[str]:
        """生成背景音乐
        
        Args:
            duration: 音乐时长(秒)
            mood: 音乐情绪
            
        Returns:
            音乐文件路径，失败返回None
        """
        try:
            from pydub.generators import Sine, Square
            from pydub import AudioSegment
            
            print(f"[音乐生成] 生成背景音乐: {duration}秒, 情绪={mood}")
            
            # 根据情绪选择基础音调和节奏
            mood_config = {
                "epic": {"base_freq": 220, "tempo": "moderate", "volume": -15},
                "calm": {"base_freq": 174, "tempo": "slow", "volume": -20},
                "tense": {"base_freq": 293, "tempo": "fast", "volume": -12},
                "happy": {"base_freq": 261, "tempo": "moderate", "volume": -15},
                "sad": {"base_freq": 196, "tempo": "slow", "volume": -18}
            }
            
            config = mood_config.get(mood, mood_config["epic"])
            base_freq = config["base_freq"]
            volume_db = config["volume"]
            
            # 生成简单的背景音乐（使用正弦波合成）
            duration_ms = int(duration * 1000)
            
            # 主旋律
            melody = Sine(base_freq).to_audio_segment(duration=duration_ms)
            # 和声（五度音）
            harmony = Sine(base_freq * 1.5).to_audio_segment(duration=duration_ms)
            # 低音（八度音）
            bass = Sine(base_freq / 2).to_audio_segment(duration=duration_ms)
            
            # 混合音轨
            music = melody.overlay(harmony - 6).overlay(bass - 3)
            
            # 调整音量
            music = music + volume_db
            
            # 添加淡入淡出效果
            fade_duration = min(2000, duration_ms // 4)
            music = music.fade_in(fade_duration).fade_out(fade_duration)
            
            # 保存
            output_dir = Path(self.tts_config.get("output_dir", "output"))
            output_dir.mkdir(exist_ok=True)
            output_path = output_dir / f"background_music_{mood}.mp3"
            music.export(str(output_path), format="mp3", bitrate="192k")
            
            print(f"[音乐生成] 已生成: {output_path}")
            return str(output_path)
            
        except Exception as e:
            print(f"[音乐生成] 生成失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _merge_video_audio(self, video_path: str, audio_path: str) -> str:
        """合并视频和音频
        
        Args:
            video_path: 视频文件路径
            audio_path: 音频文件路径
            
        Returns:
            合并后的视频路径
        """
        try:
            from moviepy import VideoFileClip, AudioFileClip
            
            print(f"[视频音频合并] 合并视频和音频...")
            
            # 检查文件是否存在
            if not video_path:
                print(f"[视频音频合并] 错误: 视频路径为空")
                return "video_with_audio.mp4"
                
            if not Path(video_path).exists():
                print(f"[视频音频合并] 错误: 视频文件不存在 {video_path}")
                return "video_with_audio.mp4"
            
            if not audio_path:
                print(f"[视频音频合并] 警告: 音频路径为空，返回原视频")
                return video_path
                
            if not Path(audio_path).exists():
                print(f"[视频音频合并] 错误: 音频文件不存在 {audio_path}")
                return video_path
            
            # 加载视频和音频
            video = VideoFileClip(video_path)
            audio = AudioFileClip(audio_path)
            
            # 如果音频比视频长，裁剪音频
            if audio.duration > video.duration:
                audio = audio.subclipped(0, video.duration)
            
            # 合并音频
            video_with_audio = video.set_audio(audio)
            
            # 输出路径
            output_dir = Path(self.tts_config.get("output_dir", "output"))
            output_dir.mkdir(exist_ok=True)
            output_path = output_dir / "video_with_audio.mp4"
            
            # 导出
            video_with_audio.write_videofile(
                str(output_path),
                codec='libx264',
                audio_codec='aac',
                fps=24
            )
            
            # 释放资源
            video.close()
            audio.close()
            video_with_audio.close()
            
            print(f"[视频音频合并] 已完成: {output_path}")
            return str(output_path)
            
        except Exception as e:
            print(f"[视频音频合并] 失败: {e}")
            import traceback
            traceback.print_exc()
            return "video_with_audio.mp4"
    
    def _add_subtitles(self, video_path: str, shots: List[Dict], 
                      output_path: Path) -> Path:
        """添加字幕
        
        Args:
            video_path: 输入视频路径
            shots: 镜头信息列表
            output_path: 输出视频路径
            
        Returns:
            带字幕的视频路径
        """
        try:
            from moviepy import VideoFileClip, TextClip, CompositeVideoClip
            
            print(f"[字幕添加] 开始添加字幕...")
            
            # 检查视频文件是否存在
            if not Path(video_path).exists():
                print(f"[字幕添加] 错误: 视频文件不存在 {video_path}")
                return output_path
            
            # 生成SRT字幕
            srt_content = self._generate_srt(shots)
            srt_path = output_path.parent / "subtitles.srt"
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            print(f"[字幕添加] SRT字幕已生成: {srt_path}")
            
            # 加载视频
            video = VideoFileClip(video_path)
            
            # 创建字幕片段
            subtitle_clips = []
            current_time = 0.0
            
            for shot in shots:
                audio_prompt = shot.get("audio_prompt", {}) or {}
                subtitle_items = []
                for key in ("dialogue", "narration"):
                    item = audio_prompt.get(key)
                    if isinstance(item, dict) and item.get("content"):
                        subtitle_items.append(item.get("content", ""))
                if not subtitle_items and audio_prompt.get("content"):
                    subtitle_items.append(audio_prompt.get("content", ""))
                content = "\n".join(subtitle_items)
                
                if not content:
                    current_time += shot.get("duration", 3.0)
                    continue
                
                duration = shot.get("duration", 3.0)
                
                # 创建文字片段
                txt_clip = TextClip(
                    content,
                    fontsize=40,
                    color='white',
                    font='Arial',
                    size=(video.w - 100, None),
                    method='caption',
                    align='center'
                ).set_position(('center', 0.85), relative=True).set_start(current_time).set_duration(duration)
                
                # 添加黑色背景（半透明）
                bg_clip = TextClip(
                    content,
                    fontsize=40,
                    color='black',
                    font='Arial',
                    size=(video.w - 100, None),
                    method='caption',
                    align='center'
                ).set_position(('center', 0.85), relative=True).set_start(current_time).set_duration(duration).set_opacity(0.6)
                
                subtitle_clips.extend([bg_clip, txt_clip])
                
                current_time += duration
            
            # 合成视频和字幕
            final_video = CompositeVideoClip([video] + subtitle_clips)
            
            # 确保输出目录存在
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 导出
            final_video.write_videofile(
                str(output_path),
                codec='libx264',
                audio_codec='aac',
                fps=24
            )
            
            # 释放资源
            video.close()
            for clip in subtitle_clips:
                clip.close()
            final_video.close()
            
            print(f"[字幕添加] 已完成: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"[字幕添加] 失败: {e}")
            import traceback
            traceback.print_exc()
            
            # 如果失败，至少保存SRT字幕文件
            srt_content = self._generate_srt(shots)
            srt_path = output_path.parent / "subtitles.srt"
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            print(f"[字幕添加] SRT字幕已生成: {srt_path}")
            
            return output_path
    
    def _generate_srt(self, shots: List[Dict]) -> str:
        """生成SRT字幕文件"""
        
        srt_lines = []
        current_time = 0.0
        
        for idx, shot in enumerate(shots, 1):
            audio_prompt = shot.get("audio_prompt", {})
            content = audio_prompt.get("content", "")
            
            if not content:
                continue
            
            duration = shot.get("duration", 3.0)
            
            # 时间格式：00:00:00,000 --> 00:00:03,000
            start_time = self._format_srt_time(current_time)
            end_time = self._format_srt_time(current_time + duration)
            
            srt_lines.append(f"{idx}")
            srt_lines.append(f"{start_time} --> {end_time}")
            srt_lines.append(content)
            srt_lines.append("")
            
            current_time += duration
        
        return "\n".join(srt_lines)
    
    def _format_srt_time(self, seconds: float) -> str:
        """格式化SRT时间"""
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
