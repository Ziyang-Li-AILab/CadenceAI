"""
Video Generation API Module

统一的视频生成API封装，支持多个视频生成服务。
"""

import time
import base64
import requests
from typing import Dict, Any, Optional, List
from pathlib import Path
from enum import Enum


class VideoProvider(Enum):
    """视频生成服务提供商"""
    SEEDANCE = "seedance"
    MOYU = "moyu"


class VideoGenerationError(Exception):
    """视频生成错误"""
    pass


class VideoAPI:
    """视频生成API统一接口"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化API客户端
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.video_config = config.get("api_config", {}).get("video", {})
        
        # 当前使用的提供商
        self.provider = self._detect_provider()
        
        # API配置
        self.api_key = self.video_config.get("api_key", "")
        self.endpoint = self.video_config.get("endpoint", "")
        self.model = self.video_config.get("model", "seedance-1.5-pro")
        
        # 默认参数
        self.default_params = {
            "ratio": "9:16",
            "resolution": "720p",
            "generate_audio": True
        }
        
        print(f"✓ VideoAPI初始化: provider={self.provider.value}, model={self.model}")
    
    def _detect_provider(self) -> VideoProvider:
        """
        检测视频服务提供商
        
        Returns:
            提供商枚举值
        """
        endpoint = self.video_config.get("endpoint", "")
        
        if "seedance" in endpoint.lower() or "doubao" in endpoint.lower():
            return VideoProvider.SEEDANCE
        elif "moyu" in endpoint.lower():
            return VideoProvider.MOYU
        else:
            # 默认使用Seedance
            return VideoProvider.SEEDANCE
    
    def generate_video(self,
                      prompt: str,
                      duration: int = 8,
                      reference_images: Optional[List[str]] = None,
                      negative_prompt: Optional[str] = None,
                      style_params: Optional[Dict[str, Any]] = None,
                      max_retries: int = 1) -> Dict[str, Any]:
        """
        生成视频（统一接口）
        
        Args:
            prompt: 视频生成提示词
            duration: 视频时长（秒）
            reference_images: 参考图片路径列表
            negative_prompt: 负面提示词
            style_params: 风格参数
            max_retries: 最大重试次数
            
        Returns:
            生成结果字典，包含:
            - video_url: 视频URL
            - video_path: 本地保存路径（如果下载）
            - task_id: 任务ID
            - duration: 实际时长
            - success: 是否成功
        """
        if self.provider == VideoProvider.SEEDANCE:
            return self._generate_seedance(
                prompt=prompt,
                duration=duration,
                reference_images=reference_images,
                negative_prompt=negative_prompt,
                style_params=style_params,
                max_retries=max_retries
            )
        elif self.provider == VideoProvider.MOYU:
            return self._generate_moyu(
                prompt=prompt,
                duration=duration,
                max_retries=max_retries
            )
        else:
            raise VideoGenerationError(f"不支持的提供商: {self.provider}")
    
    def _generate_seedance(self,
                          prompt: str,
                          duration: int,
                          reference_images: Optional[List[str]],
                          negative_prompt: Optional[str],
                          style_params: Optional[Dict[str, Any]],
                          max_retries: int) -> Dict[str, Any]:
        """
        使用Seedance生成视频
        
        Args:
            prompt: 提示词
            duration: 时长
            reference_images: 参考图列表
            negative_prompt: 负面提示词
            style_params: 风格参数
            max_retries: 最大重试次数
            
        Returns:
            生成结果
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 构建content数组
        content = [{"type": "text", "text": prompt}]
        
        # 添加参考图片
        if reference_images:
            for img_path in reference_images:
                if Path(img_path).exists():
                    with open(img_path, 'rb') as f:
                        img_base64 = base64.b64encode(f.read()).decode()
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"},
                        "role": "reference_image"
                    })
        
        # 构建metadata
        metadata = {
            "content": content,
            "duration": duration,
            "ratio": style_params.get("ratio", "9:16") if style_params else "9:16",
            "resolution": style_params.get("resolution", "720p") if style_params else "720p",
            "generate_audio": True
        }
        
        # 添加负面提示词
        if negative_prompt:
            metadata["negative_prompt"] = negative_prompt
        
        # 添加风格参数
        if style_params:
            if "camera_movement" in style_params:
                metadata["camera_movement"] = style_params["camera_movement"]
            if "lighting" in style_params:
                metadata["lighting"] = style_params["lighting"]
        
        payload = {
            "model": self.model,
            "prompt": "video generation",
            "metadata": metadata
        }
        
        # 提交任务（带重试）
        task_id = None
        for attempt in range(1, max_retries + 1):
            try:
                print(f"      → [尝试 {attempt}/{max_retries}] 提交Seedance任务...")
                
                resp = requests.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                resp.raise_for_status()
                
                result = resp.json()
                task_id = result.get("task_id") or result.get("id")
                
                if not task_id:
                    raise VideoGenerationError(f"API响应中没有task_id: {result}")
                
                print(f"      ✓ 任务提交成功: {task_id}")
                break
                
            except requests.exceptions.RequestException as e:
                print(f"      ✗ 提交失败: {e}")
                if attempt == max_retries:
                    raise VideoGenerationError(f"任务提交失败（已重试{max_retries}次）: {e}")
                time.sleep(2 ** attempt)  # 指数退避
        
        # 轮询结果
        video_url = self._poll_seedance_result(task_id, headers)
        
        return {
            "video_url": video_url,
            "video_path": None,  # 由调用方决定是否下载
            "task_id": task_id,
            "duration": duration,
            "success": True
        }
    
    def _poll_seedance_result(self, task_id: str, headers: Dict[str, str]) -> str:
        """
        轮询Seedance任务结果
        
        Args:
            task_id: 任务ID
            headers: 请求头
            
        Returns:
            视频URL
        """
        max_wait = 600  # 最长等待10分钟
        poll_interval = 10  # 每10秒查询一次
        start_time = time.time()
        
        query_url = f"{self.endpoint}/{task_id}"
        
        while time.time() - start_time < max_wait:
            time.sleep(poll_interval)
            
            try:
                resp = requests.get(query_url, headers=headers, timeout=30)
                resp.raise_for_status()
                result = resp.json()
                
                # 解析状态
                data = result.get("data", {})
                status = data.get("status", "UNKNOWN")
                progress = data.get("progress", "0%")
                
                print(f"      → 状态: {status} | 进度: {progress}")
                
                if status == "SUCCESS" or status == "COMPLETED":
                    # 提取视频URL
                    content = data.get("data", {}).get("content", {})
                    video_url = content.get("video_url") or content.get("url")
                    
                    if not video_url:
                        raise VideoGenerationError(f"成功但无视频URL: {result}")
                    
                    print(f"      ✓ 视频生成成功")
                    return video_url
                
                elif status == "FAILURE" or status == "FAILED":
                    fail_reason = data.get("fail_reason", "Unknown")
                    raise VideoGenerationError(f"生成失败: {fail_reason}")
                
            except requests.exceptions.RequestException as e:
                print(f"      ⚠️  查询失败: {e}")
                # 继续等待
        
        raise VideoGenerationError("生成超时（10分钟）")
    
    def _generate_moyu(self,
                       prompt: str,
                       duration: int,
                       max_retries: int) -> Dict[str, Any]:
        """
        使用摸鱼API生成视频（简化版）
        
        Args:
            prompt: 提示词
            duration: 时长
            max_retries: 最大重试次数
            
        Returns:
            生成结果
        """
        # TODO: 实现摸鱼API逻辑
        raise VideoGenerationError("Moyu API暂不支持，请使用Seedance")
    
    def download_video(self, video_url: str, output_path: Path) -> Path:
        """
        下载视频到本地
        
        Args:
            video_url: 视频URL
            output_path: 输出路径
            
        Returns:
            本地文件路径
        """
        print(f"      → 下载视频...")
        
        try:
            resp = requests.get(video_url, timeout=120, stream=True)
            resp.raise_for_status()
            
            # 确保目录存在
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入文件
            with open(output_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = output_path.stat().st_size / (1024 * 1024)  # MB
            print(f"      ✓ 下载完成: {output_path.name} ({file_size:.1f}MB)")
            
            return output_path
            
        except requests.exceptions.RequestException as e:
            raise VideoGenerationError(f"视频下载失败: {e}")
    
    def batch_generate(self,
                      prompts: List[Dict[str, Any]],
                      parallel: bool = False) -> List[Dict[str, Any]]:
        """
        批量生成视频
        
        Args:
            prompts: 提示词列表，每个元素是generate_video的参数字典
            parallel: 是否并行提交（仅提交，不等待）
            
        Returns:
            生成结果列表
        """
        results = []
        
        for i, prompt_params in enumerate(prompts, 1):
            print(f"\n   [{i}/{len(prompts)}] 生成视频...")
            
            try:
                result = self.generate_video(**prompt_params)
                results.append(result)
            except VideoGenerationError as e:
                print(f"   ✗ 失败: {e}")
                results.append({
                    "success": False,
                    "error": str(e)
                })
        
        return results
    
    def get_quota(self) -> Dict[str, Any]:
        """
        获取API配额信息
        
        Returns:
            配额信息字典
        """
        # TODO: 实现配额查询
        return {
            "available": True,
            "remaining": "unknown"
        }
