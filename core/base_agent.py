# -*- coding: utf-8 -*-
"""
Agent基类 - 所有专业Agent的父类
定义通用接口和工具方法
"""

import json
import time
import requests
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AgentResponse:
    """Agent响应封装"""
    success: bool
    data: Any = None
    error: str = ""
    warnings: List[str] = None
    suggestions: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.suggestions is None:
            self.suggestions = []


class BaseAgent(ABC):
    """Agent基类"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.llm_config = self.config.get("llm", {})
        self.name = self.__class__.__name__
    
    @abstractmethod
    def execute(self, context: Dict) -> AgentResponse:
        """执行Agent任务"""
        pass
    
    def _call_llm(self, prompt: str, system_prompt: str = None, 
                  temperature: float = 0.7, max_tokens: int = 2000) -> str:
        """调用LLM，带重试机制"""
        import time
        
        headers = {
            "Authorization": f"Bearer {self.llm_config.get('api_key', '')}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.llm_config.get('model', 'doubao'),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens if max_tokens > 2000 else self.llm_config.get('max_tokens', 20000)  # 优先使用函数参数，否则使用配置
        }
        
        # 重试配置
        max_retries = 1
        base_timeout = 1200 
        backoff_factor = 1.0  # 不再指数增长，保持固定超时
        
        print(f"  [Agent:{self.name}] 调用LLM...", end="", flush=True)
        
        last_error = None
        for attempt in range(max_retries):
            try:
                # 固定超时时间，避免过长等待
                timeout = base_timeout
                
                resp = requests.post(
                    self.llm_config.get('endpoint', ''),
                    headers=headers,
                    json=payload,
                    timeout=timeout
                )
                resp.raise_for_status()
                result = resp.json()
                content = result['choices'][0]['message']['content']
                
                # 成功时显示信息
                if attempt > 0:
                    print(f" OK (重试{attempt}次, {resp.elapsed.total_seconds():.1f}s)")
                else:
                    print(f" OK ({resp.elapsed.total_seconds():.1f}s)")
                return content
                
            except requests.exceptions.Timeout as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 指数退避: 1s, 2s, 4s
                    print(f" 超时(第{attempt+1}次)，等待{wait_time}秒后重试...", end="", flush=True)
                    time.sleep(wait_time)
                else:
                    print(f" 超时(第{attempt+1}次)，已达最大重试次数")
                    
            except requests.exceptions.HTTPError as e:
                last_error = e
                # HTTP错误通常不需要重试（如401、404等）
                print(f" HTTP错误: {e}")
                raise
                
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f" 失败(第{attempt+1}次): {e}，等待{wait_time}秒后重试...", end="", flush=True)
                    time.sleep(wait_time)
                else:
                    print(f" 失败(第{attempt+1}次): {e}")
        
        # 所有重试都失败
        raise last_error
    
    def _extract_json(self, text: str) -> Optional[Dict]:
        """从文本中提取JSON - 增强版，支持修复常见问题"""
        import re
        
        # 尝试1: 直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 尝试2: 提取代码块
        json_blocks = re.findall(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        for block in json_blocks:
            try:
                return json.loads(block.strip())
            except json.JSONDecodeError:
                continue
        
        # 尝试3: 提取花括号内容
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            json_str = text[start:end+1]
            
            # 尝试直接解析
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
            
            # 尝试4: 修复常见问题
            try:
                # 修复尾部逗号
                json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                # 修复单引号
                json_str = json_str.replace("'", '"')
                # 修复换行符问题
                json_str = json_str.replace('\n', '\\n')
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _save_output(self, data: Any, filename: str, output_dir: Path) -> Path:
        """保存输出到文件"""
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / filename
        
        if isinstance(data, (dict, list)):
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(str(data))
        
        print(f"  [Agent:{self.name}] 保存输出: {filepath}")
        return filepath


class QualityGate:
    """质量门 - 检查输出是否符合标准"""
    
    def __init__(self):
        self.rules = {
            "prompt_length_max": 1000,  # 【修复】从300提高到1000，允许详细的视觉描述（但防止3000+字的污染）
            "prompt_length_min": 50,
            "must_have_character_ref": True,
            "forbidden_terms": [
                "情感丰富", "内心挣扎", "意味深长", 
                "深情凝视", "复杂情感", "内心独白",
                "充满", "深深", "仿佛", "似乎"
            ],
            "required_visual_elements": ["镜头", "光线", "构图"],
            "required_terms": {
                "video_prompt": ["场景", "人物", "动作"],
                "dialogue": ["speaker", "text"]
            }
        }
        self.check_history = []  # 记录所有检查历史
    
    def validate_prompt(self, prompt: Dict, shot_number: int = 0) -> AgentResponse:
        """验证提示词质量"""
        warnings = []
        suggestions = []
        errors = []
        
        visual_prompt = prompt.get("visual_prompt", "")
        prompt_length = len(visual_prompt)
        
        # 长度检查
        if prompt_length > self.rules["prompt_length_max"]:
            warnings.append(
                f"提示词过长({prompt_length}字)，建议控制在{self.rules['prompt_length_max']}字以内"
            )
            suggestions.append("精简提示词：移除细节描写，保留核心视觉元素")
        elif prompt_length < self.rules["prompt_length_min"]:
            warnings.append(f"提示词过短({prompt_length}字)，可能缺乏足够的视觉指导")
            suggestions.append("添加具体的视觉元素：光线、构图、氛围")
        
        # 禁用词检查
        found_forbidden = []
        for term in self.rules["forbidden_terms"]:
            if term in visual_prompt:
                found_forbidden.append(term)
        
        if found_forbidden:
            warnings.append(f"包含不可视觉化的抽象描述: {', '.join(found_forbidden)}")
            suggestions.append("将抽象描述替换为具体可视觉化的元素")
        
        # 角色一致性检查
        if self.rules["must_have_character_ref"]:
            if not prompt.get("use_character_ref") and not prompt.get("character_description"):
                warnings.append("缺少角色一致性描述，可能导致角色外观不一致")
                suggestions.append("添加角色的显著特征描述")
        
        # 必要元素检查
        has_scene = "场景" in visual_prompt or "环境" in visual_prompt
        has_lighting = "光" in visual_prompt or "阴影" in visual_prompt
        has_composition = "镜头" in visual_prompt or "构图" in visual_prompt
        
        if not has_scene:
            warnings.append("缺少场景描述")
        if not has_lighting:
            warnings.append("缺少光线描述")
        if not has_composition:
            warnings.append("缺少镜头构图描述")
        
        # 记录检查历史
        check_record = {
            "shot_number": shot_number,
            "prompt_length": prompt_length,
            "warnings_count": len(warnings),
            "passed": len(errors) == 0
        }
        self.check_history.append(check_record)
        
        critical_warnings = [w for w in warnings if "无法" in w or "失败" in w]
        passed = len(critical_warnings) == 0 and len(errors) == 0
        
        return AgentResponse(
            success=passed,
            data=prompt if passed else None,
            warnings=warnings,
            suggestions=suggestions,
            error="; ".join(errors) if errors else ""
        )
    
    def validate_script(self, script: Dict) -> AgentResponse:
        """验证剧本质量"""
        warnings = []
        suggestions = []
        errors = []
        
        if "segments" not in script:
            errors.append("剧本缺少segments结构")
            return AgentResponse(success=False, error="剧本结构不完整")
        
        # 检查角色对话
        has_dialogue = False
        dialogue_count = 0
        narrator_only_count = 0
        
        for segment in script.get("segments", []):
            for shot in segment.get("shots", []):
                dialogue = shot.get("character_dialogue") or {}  # 修复：可能为None
                if dialogue:
                    speaker = dialogue.get("speaker", "").lower()
                    if speaker and "旁白" not in speaker and "narrator" not in speaker:
                        has_dialogue = True
                        dialogue_count += 1
                    else:
                        narrator_only_count += 1
        
        if not has_dialogue:
            warnings.append("剧本缺少角色对话，只有旁白")
            suggestions.append("为关键角色添加对话，增强叙事深度")
        elif dialogue_count < 3:
            warnings.append(f"角色对话较少({dialogue_count}处)，建议增加")
        
        # 检查叙事节奏
        total_shots = sum(len(seg.get("shots", [])) for seg in script.get("segments", []))
        if total_shots < 5:
            warnings.append(f"镜头数量较少({total_shots}个)，叙事可能不够丰富")
        elif total_shots > 15:
            warnings.append(f"镜头数量过多({total_shots}个)，可能导致节奏过快")
        
        # 检查时长
        total_duration = script.get("duration", 0)
        if total_duration == 0:
            warnings.append("未设置总时长")
        
        return AgentResponse(
            success=len(errors) == 0,
            warnings=warnings,
            suggestions=suggestions,
            error="; ".join(errors) if errors else ""
        )
    
    def get_quality_report(self) -> Dict:
        """获取质量检查报告"""
        if not self.check_history:
            return {"message": "No checks performed yet"}
        
        total_checks = len(self.check_history)
        passed_checks = sum(1 for c in self.check_history if c["passed"])
        avg_warnings = sum(c["warnings_count"] for c in self.check_history) / total_checks
        
        return {
            "total_checks": total_checks,
            "passed": passed_checks,
            "failed": total_checks - passed_checks,
            "pass_rate": f"{passed_checks/total_checks*100:.1f}%",
            "avg_warnings_per_shot": f"{avg_warnings:.2f}"
        }
