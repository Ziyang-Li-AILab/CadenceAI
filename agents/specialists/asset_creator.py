# -*- coding: utf-8 -*-
"""
资产创建Agent - 为角色和场景生成参考图

职责：
1. 基于世界观中的角色定义，生成角色参考图
2. 基于世界观中的场景定义，生成场景参考图
3. 存储生成的图片，供后续分镜、视频生成阶段使用
"""

import json
import re
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from core.base_agent import BaseAgent, AgentResponse
from core.world_database import WorldDatabase


def _clean_prompt_output(text: str) -> str:
    """清洗 LLM 输出：去 markdown、去引号、去前缀、压缩空白。"""
    if not text:
        return ""
    out = text.strip()

    # 去 markdown 代码块围栏
    out = re.sub(r"^```[a-zA-Z0-9_\-]*\s*", "", out)
    out = re.sub(r"\s*```\s*$", "", out)

    # 去「Prompt：」「提示词：」之类的前缀
    out = re.sub(r"^\s*(prompt|提示词|正向提示词)\s*[:：]\s*", "", out, flags=re.IGNORECASE)

    # 去首尾成对引号 / 书名号 / 方括号
    pairs = {'"': '"', "'": "'", "“": "”", "「": "」", "《": "》", "[": "]"}
    if len(out) >= 2 and out[0] in pairs and out[-1] == pairs[out[0]]:
        out = out[1:-1].strip()

    # 压缩空白（保留单空格），换行统一为空格
    out = re.sub(r"\s+", " ", out).strip()
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 通用（角色/道具）元提示词常量
# 复用方式：_build_prop_prompt 直接使用本组常量；_build_location_prompt 使用
# 下方的 _LOCATION 变体以贴合场景需求；_STYLE_DIRECTIVE 为所有类别共享。
# ─────────────────────────────────────────────────────────────────────────────

_STYLE_DIRECTIVE = (
    "【目标风格（最高优先级）】\n"
    "目标风格: {target_format}。\n"
    "所有视觉表现——材质、光影、色温、镜头语言、景别、渲染标准、负面提示词——"
    "必须严格服从目标风格，不得偏离、不得折衷、不得用其它风格覆盖。"
)

_META_SYSTEM_ROLE = (
    "你是一位顶级的角色与道具概念设计师兼电影摄影指导，"
    "专门为 Midjourney / Stable Diffusion / 即梦 / 可灵 等文生图与文生视频模型"
    "撰写由用户目标风格严格控制的电影级写实角色/道具提示词。"
    "你输出的提示词必须材质可辨、光影明确、镜头语言专业、尺度关系可信。"
)

_META_RULES = """\
# 硬性输出规则
1. 只输出提示词本身。禁止任何解释、前言、标题、编号、项目符号、\
markdown 代码块或换行分段，全文一气呵成。
2. 语言风格：中文描述为主，关键专业术语保留英文\
（如 Volumetric light、PBR、UE5、8K、HDR、IMAX、Film grain、\
Global Illumination、Air perspective）。
3. 主体必须优先服从目标风格；缺少细节时按目标风格补足真实可信的视觉细节。
4. 信息密度必须高，具体化到可视觉还原的程度。
5. 必须依次覆盖以下 10 个模块，自然衔接、不重复、不啰嗦，模块顺序固定：
   ① 风格与画质标签（电影级写实 / 目标风格 / 8K / HDR / UE5 / PBR）
   ② 主体定调（名称、类型、世界观、整体气质：冷厉 / 粗粝 / 工业 / 神秘）
   ③ 形态与结构（真实人体或物体的结构、关节、组件、轮廓、比例、姿态）
   ④ 核心特征（脸型 / 五官 / 表情 / 机械部件 / 标志性装饰 / 关键视觉识别点）
   ⑤ 服饰与装备（材质、层叠、做旧痕迹、徽记、纹饰、配饰）
   ⑥ 材质对比（锈蚀金属 / 风化皮革 / 粗粝布料 / 玻璃 / 橡胶的真实质感）
   ⑦ 布光与氛围（关键光、轮廓光、阴影方向、空气感、体积光、胶片颗粒）
   ⑧ 镜头与焦段（景别、机位高度、镜头焦段、透视强度、画幅比例）
   ⑨ 尺度参照（必须给出人体或参照物等真实尺度锚点）
   ⑩ 渲染标准与负面提示词（固定收尾段落，见 _META_FIXED_TAIL）
6. 若主体信息中缺少具体时代或风格特征，可基于目标风格与用途补足真实细节。
7. 所有结构必须符合真实承重、透视和尺度关系，避免魔法拼贴感。
8. 全文长度：单角色或单道具 250–500 中文字符
"""

_META_FIXED_TAIL = (
    "渲染标准：8K超高清，PBR材质，UE5引擎级渲染，全局光照（Global Illumination），"
    "电影级色彩分级（Cinematic Color Grading），HDR光照，环境光遮蔽（AO），"
    "高细节纹理（High-detail Texture），锐利对焦（Sharp Focus）。"
    "负面提示词（Negative Prompt）：避免低分辨率、模糊、过曝、欠曝、色偏、"
    "塑料感、卡通化、油画笔触、过饱和、廉价合成、人物畸形、多余手指、"
    "文字水印、签名、边框、构图失衡。"
)


_META_SYSTEM_ROLE_LOCATION = (
    "你是一位顶级的场景概念设计师兼电影摄影指导，"
    "专门为 Midjourney / Stable Diffusion / 即梦 / 可灵 等文生图与文生视频模型"
    "撰写由用户目标风格严格控制的电影级写实场景提示词。"
    "你输出的提示词必须空间结构清晰、材质可辨、光影明确、镜头语言专业、尺度关系可信。"
)

_META_RULES_LOCATION = """\
# 硬性输出规则
1. 只输出提示词本身。禁止任何解释、前言、标题、编号、项目符号、\
markdown 代码块或换行分段，全文一气呵成。
2. 语言风格：中文描述为主，关键专业术语保留英文\
（如 Volumetric light、PBR、UE5、8K、HDR、IMAX、Film grain、\
Global Illumination、Air perspective）。
4. 场景必须优先服从目标风格；。
5. 信息密度必须高，具体化到可视觉还原的程度：
4. 必须依次覆盖以下 10 个模块，自然衔接、不重复、不啰嗦，模块内容仅供参考，请根据实际主题自拟：
   ① 风格与画质标签（电影级写实 / 中东废土 / 工业遗迹 / 8K / HDR / UE5 / PBR）
   ② 场景定调（名称、类型、世界观、整体气质：压抑 / 荒凉 / 粗粝 / 紧张）
   ③ 空间结构与布局（真实地形或工业遗迹的非对称布局、动线、废墟层次、由近及远的空间逻辑）
   ④ 核心主体（坦克残骸、废弃检查站、巨型机甲、通信塔或其他符合主题的工业主体）
   ⑤ 环境细节（废旧车辆、弹痕、铁丝网、布条、补丁、沙尘、工具和真实工业痕迹）
   ⑥ 材质对比（锈蚀钢板 / 风化混凝土 / 粗粝岩石 / 尘土布料 / 玻璃与橡胶）
   ⑦ 布光与氛围（强烈沙漠阳光、沙尘暴、火花、烟尘、体积光、空气颗粒和胶片颗粒感）
   ⑧ 镜头与焦段（景别、机位高度、仰视或广角、透视强度、16:9 或超宽银幕）
   ⑨ 尺度参照（必须给出人物、车辆或机甲等真实尺度锚点）
   ⑩ 渲染标准与负面提示词（固定收尾段落）
5. 若场景信息中缺少具体时代，可基于目标风格和场景用途补足真实细节。
6. 所有结构必须符合真实承重、透视和尺度关系，避免魔法拼贴感。
7. 全文长度：单视角场景 350–650 中文字符
"""

def _resolve_view_guide_location(target_format: str, loc_type: str) -> str:
    """根据 target_format 与场景类型返回构图/视角指令。"""
    fmt = (target_format or "").strip().lower()
    ltype = (loc_type or "").strip().lower()

    # —— 多视角设定图 ——
    if any(k in fmt for k in ("sheet", "board", "layout", "multi", "设定", "多视角", "三视图")):
        return (
            "构图：多视角场景设定图（Multi-view Scene Sheet）。多视角并置，"
            "统一主体在不同视角下的轮廓、光影、尺度关系，"
            "便于视频生成阶段做参考。"
        )

    # —— 扩图 / 大全景延伸 ——
    if any(k in fmt for k in ("expand", "outpaint", "扩图", "延伸", "全景延伸")):
        return (
            "构图：扩图 / 大全景延伸任务。在原构图基础上向四周延展，"
            "保留主体、光影、材质与色温不变，新增区域与原画面无缝衔接。"
        )

    # —— 特写 / 局部 ——
    if any(k in fmt for k in ("close", "detail", "macro", "特写", "局部")):
        return (
            "构图：局部特写镜头（Close-up Detail）。85–135mm 中长焦，浅景深，"
            "聚焦核心主体的材质与工艺细节（锈蚀钢板、焊接补丁、液压管、混凝土和尘土），"
            "背景柔和虚化但仍保留场景层次与光影氛围。"
        )

    # —— 俯视 / 鸟瞰 ——
    if any(k in fmt for k in ("top", "aerial", "bird", "俯视", "鸟瞰", "顶视")):
        return (
            "构图：高机位俯瞰（Aerial / Bird's-eye View）。24–35mm 广角，"
            "完整展示地面布局、中轴对称关系与动线，建筑顶部结构与院落层次清晰，"
            "远景以空气透视渐隐。"
        )

    # —— 仰视 ——
    if any(k in fmt for k in ("low", "仰视", "低机位")):
        return (
            "构图：低机位仰视（Low-angle）。14–24mm 超广角，极强透视，"
            "仰拍核心主体以强化压迫感与体量感，顶部结构汇聚于画面上方，"
            "天光或殿顶光束为视觉引导。"
        )

    # —— 远景 / 全景 ——
    if any(k in fmt for k in ("wide", "far", "panorama", "全景", "远景", "超宽")):
        return (
            "构图：超宽银幕全景（Ultra-wide Panorama）。21:9 或 2.35:1 画幅，"
            "24mm 广角，机位平视略低，主体建筑居中或黄金分割，"
            "以渺小人物或参照物反衬场景浩瀚体量，前后景层次分明。"
        )

    # —— 默认：单视角全景 ——
    if any(k in ltype for k in ("室内", "殿", "宫", "room", "indoor")):
        return (
            "构图：室内正面全景（Interior Front View）。24–35mm 广角，"
            "机位位于殿门内侧平视，中轴对称布局，纵深进深明确，"
            "体积光自高处斜射入殿，前景/中景/背景层次清晰。"
        )
    return (
        "构图：单视角电影全景（Cinematic Wide Shot）。24–50mm，"
        "机位平视，主体结构完整入画，前后景层次分明，"
        "远景以空气透视渐隐，画面留白克制，气势恢宏。"
    )


def _clean_prompt_output_location(text: str) -> str:
    """清洗 LLM 输出：去 markdown、去引号、去前缀、压缩空白。"""
    if not text:
        return ""
    out = text.strip()

    out = re.sub(r"^```[a-zA-Z0-9_\-]*\s*", "", out)
    out = re.sub(r"\s*```\s*$", "", out)
    out = re.sub(
        r"^\s*(prompt|提示词|正向提示词|场景提示词)\s*[:：]\s*",
        "", out, flags=re.IGNORECASE,
    )

    pairs = {'"': '"', "'": "'", "“": "”", "「": "」", "《": "》", "[": "]"}
    if len(out) >= 2 and out[0] in pairs and out[-1] == pairs[out[0]]:
        out = out[1:-1].strip()

    out = re.sub(r"\s+", " ", out).strip()
    return out


# 在 execute() / _resolve_view_guide_location / _find_element_references 多个地方复用，
# 把"中文 label"统一映射到磁盘目录名。
_CATEGORY_TO_DIR = {
    "角色参考图": "characters",
    "场景参考图": "locations",
    "道具参考图": "props",
}


class AssetCreator(BaseAgent):
    """
    资产创建Agent - 使用文生图模型为角色、场景、道具生成参考图

    生成的资产存储在 session 目录下：
    - assets/characters/   角色参考图
    - assets/locations/   场景参考图
    - assets/props/        道具参考图

    每个资产包含：
    - image_path: 本地存储路径
    - url: 远程URL（如果API返回）
    - prompt: 使用的提示词
    - subject: 资产主题（角色名/场景名/道具名）
    """

    # Gemini image-preview via OpenAI 兼容 chat completions
    CHAT_ENDPOINT = "https://nanoapi.poloai.top/v1/chat/completions"
    # gpt-image-2.5 via images/generations
    IMAGES_ENDPOINT = "https://nanoapi.poloai.top/v1"

    # 备选模型（按顺序尝试）
    # 把已验证能稳定返回图片的模型放最前面；2.5-preview 偶尔会"仅返回文本"（模型口头声称生成了图片，
    # 但 message.content 只是字符串，并未附带 images / image_url / b64_json），故放到最后。
    FALLBACK_MODELS = (
        "gemini-3.1-flash-image-preview",
        "gemini-3.0-flash-exp-image-generation",
        "gemini-2.5-flash-image-preview",
    )

    # 文本-only 故障的错误关键字（用于判断"模型连上了但没返回图片"的情况）
    _TEXT_ONLY_MARKERS = (
        "未找到图片数据",
        "可能仅返回文本",
        "模型可能仅返回文本",
        "no image data",
        "no images in response",
    )

    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "AssetCreator"
        self.image_api_config = self.config.get("image_api", {})
        self.api_key = self.image_api_config.get("api_key", "")
        # 端点兼容：统一存储 base_url 和 chat_endpoint
        raw_base = str(self.image_api_config.get("endpoint", "")).strip().rstrip("/")
        if not raw_base:
            raw_base = "https://nanoapi.poloai.top/v1"
        # 兼容旧配置：如果带 /chat/completions，去掉它作为 base_url
        for suffix in ("/chat/completions", "/chat/completion"):
            if raw_base.endswith(suffix):
                self._base_url = raw_base[: -len(suffix)]
                self._chat_endpoint = raw_base
                break
        else:
            self._base_url = raw_base
            self._chat_endpoint = raw_base.rstrip("/") + "/chat/completions"
        self.default_model = self.image_api_config.get("model", "gemini-3.1-flash-image-preview")
        self.default_quality = self.image_api_config.get("quality", "low")
        self.default_size = self.image_api_config.get("size", "1024x1024")
        self.request_timeout = self.image_api_config.get("timeout", 180)
        self.session_dir: Optional[Path] = None
        # OpenAI 客户端延迟初始化，避免模块加载阶段就因网络/配置缺失而报错
        self._openai_client = None

    def _use_images_api(self, model: str) -> bool:
        """判断模型是否使用 images/generations 接口（非 gpt-image 系列用 chat completions）。"""
        return model.lower().startswith("gpt-image")

    def set_session_dir(self, session_dir: Path) -> None:
        """设置 session 目录，资产将保存在此目录下"""
        self.session_dir = session_dir
        self._ensure_asset_dirs()

    def _ensure_asset_dirs(self) -> None:
        """确保资产目录存在。"""
        if not self.session_dir:
            return
        assets_root = self.session_dir / "assets"
        for category in ("characters", "locations", "props"):
            (assets_root / category).mkdir(parents=True, exist_ok=True)
            (assets_root / "prompts" / category).mkdir(parents=True, exist_ok=True)

    def _save_prompt(self, prompt: str, subject: str, category: str) -> Path:
        """将资产 prompt 保存到当前会话的 assets/prompts 目录。"""
        if not self.session_dir:
            raise RuntimeError("未设置 session 目录，无法保存 prompt")
        safe_name = "".join(
            c if c.isalnum() or c in ("_", "-") else "_"
            for c in str(subject)
        ).strip("._") or "asset"
        prompt_path = self.session_dir / "assets" / "prompts" / category / f"{safe_name}.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        return prompt_path

    def execute(self, context: Dict) -> AgentResponse:
        """
        执行资产创建

        Args:
            context: 包含以下键的字典:
                - world: WorldDatabase, 世界观数据库
                - session_dir: Path, session目录（可选）
                - target_format: str, 目标格式/风格描述（可选）

        Returns:
            AgentResponse: 包含资产结果，格式：
            {
                "characters": [{"name": str, "image_path": str, "prompt": str}, ...],
                "locations": [{"name": str, "image_path": str, "prompt": str}, ...],
                "props": [{"name": str, "image_path": str, "prompt": str}, ...],
                "all_images": [str, ...]  # 所有图片路径的列表
            }
        """
        world = context.get("world")
        session_dir = context.get("session_dir")
        target_format = context.get("target_format", "电影级写实风格")

        if session_dir:
            self.set_session_dir(Path(session_dir))

        if not world:
            return AgentResponse(
                success=False,
                error="缺少世界观数据"
            )

        if not self.session_dir:
            return AgentResponse(
                success=False,
                error="未设置session目录，请先调用 set_session_dir()"
            )

        print(f"  [AssetCreator] 开始生成资产...")
        print(f"  - 角色数: {len(world.characters)}")
        print(f"  - 场景数: {len(world.locations)}")
        print(f"  - 道具数: {len(world.props)}")

        results: Dict[str, List[Dict]] = {"characters": [], "locations": [], "props": []}
        all_paths: List[str] = []

        def save_manifest() -> None:
            """保存当前进度，便于失败后定位和续跑。"""
            results["all_images"] = all_paths
            assets_manifest_path = self.session_dir / "assets" / "manifest.json"
            with open(assets_manifest_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

        # ---- 一个统一的「生成单个资产 + 收尾处理」helper ----
        # 三个类别（characters / locations / props）共用同一份失败语义与早退策略，
        # 区别仅在 items 来源、prompt 构造器、label 文案。
        def generate_one(name: str, obj, category: str, label: str,
                         build_prompt, results_list: List[Dict]):
            print(f"    生成 {name} {label}...", end="", flush=True)
            prompt = build_prompt(name, obj, target_format)
            if not prompt:
                err = f"{label} {name} 的 prompt 生成失败（LLM 重试均未通过长度门槛）"
                print(f" X {err}")
                return err
            prompt_path = self._save_prompt(prompt, name, category)
            print(f"\n      prompt 已保存: {prompt_path}")
            print(prompt[:100])
            result = self._generate_image(prompt, subject=name, category=category)
            if not result["success"]:
                err = result["error"]
                print(f" X {err}")
                return err
            results_list.append({
                "name": name,
                "image_path": result["image_path"],
                "prompt_path": str(prompt_path),
                "prompt": prompt,
            })
            all_paths.append(result["image_path"])
            print(f" -> {Path(result['image_path']).name}")
            return None  # 成功

        # 每个类别：(label, items, builder, results_list)
        category_jobs = [
            ("角色参考图", world.characters, self._build_character_prompt, results["characters"]),
            ("场景参考图", world.locations, self._build_location_prompt, results["locations"]),
            ("道具参考图", world.props, self._build_prop_prompt, results["props"]),
        ]

        for label, items, build_prompt, results_list in category_jobs:
            if not items:
                continue
            print(f"\n  [{label}]")
            for name, obj in items.items():
                err = generate_one(name, obj, _CATEGORY_TO_DIR[label], label,
                                   build_prompt, results_list)
                if err:
                    save_manifest()
                    full_err = f"资产制作中止：{name} {label}生成失败：{err}"
                    print(f"\n  [AssetCreator] {full_err}")
                    return AgentResponse(
                        success=False,
                        error=full_err,
                        data=results,
                    )

        save_manifest()

        n_char = len(results["characters"])
        n_loc = len(results["locations"])
        n_prop = len(results["props"])
        print(
            f"\n  [AssetCreator] 资产生成完成: "
            f"{n_char}/{len(world.characters)} 角色, "
            f"{n_loc}/{len(world.locations)} 场景, "
            f"{n_prop}/{len(world.props)} 道具"
        )

        if not all_paths:
            return AgentResponse(
                success=False,
                error="资产制作失败：未生成任何有效图片，请检查 IMAGE_API_KEY、图像接口地址及模型配置",
                data=results,
            )

        return AgentResponse(
            success=True,
            data=results
        )

    # ======================== Prompt 构建 ========================

    def _build_character_prompt(self, name: str, char, target_format: str = "full") -> str:
        """
        构建角色提示词。调用 LLM 根据角色信息生成文生图 prompt。
        输出始终为正视图（Front View），target_format 控制景别：
        - "full" / "body" / "全身"：全身正视图（默认）
        - "close" / "face" / "bust" / "半身"：半身或面部正视图
        - "action" / "dynamic" / "动态"：动态正视图
        """
        # ---------------- 1. 抽取角色信息 ----------------
        role = getattr(char, 'role', 'supporting') or 'supporting'
        visual_features = getattr(char, 'visual_features', {}) or {}
        if not isinstance(visual_features, dict):
            visual_features = {}

        visual_anchors = visual_features.get("visual_anchors", []) or []
        if not isinstance(visual_anchors, list):
            visual_anchors = [str(visual_anchors)]

        affiliation = visual_features.get("affiliation", "") or ""
        speech_style = getattr(char, 'speech_pattern', '') or ""

        base_info: Dict[str, Any] = {
            "name": name,
            "role": role,
            "affiliation": affiliation,
            "speech_style": speech_style,
        }

        # 合并 visual_features 里的其他可用字段
        for k, v in visual_features.items():
            if k in ("visual_anchors", "affiliation"):
                continue
            if v:
                base_info[k] = v
        if visual_anchors:
            base_info["visual_anchors"] = visual_anchors

        # 角色对象上的其他属性
        for attr in ("personality", "background", "description",
                     "gender", "age", "title", "race"):
            val = getattr(char, attr, None)
            if val:
                base_info.setdefault(attr, val)

        # ---------------- 3. 组装元提示词 ----------------
        character_info_str = json.dumps(
            base_info, ensure_ascii=False, indent=2, default=str
        )

        prompt_llm = "\n".join(
            f"""
            根据参考图（如果有），和目标风格{target_format},改编下面的提示词模版。注意模版仅供模仿，但实际情况必须根据待生成的角色对象信息来编写。

            我提供的角色信息为：{character_info_str}

            提示词模版为：
            参考图仅提供脸型与五官比例：改编为20岁女性废土游击土匪头目“赵仙儿”。身高170cm，体重45kg，高挑纤细，清冷冷冽，沙尘磨砺感，发丝沾沙尘，破旧黑红头巾包裹，额前推着旧铜护目镜。

            配饰：弹壳串发饰、旧铜五瓣星徽、黑铁发夹、破布条绑发、颈挂旧军牌与弹壳项链。

            服饰：中东废土游击土匪风格。回收焊接钢板胸甲、粗粝工业金属肩甲、旧皮革护肩、锈蚀链条、沙色亚麻长袍、灰褐帆布绑腿、弹药带、磁吸胸挂、破旧沙尘斗篷。不对称破旧镶边，长袍侧开叉，显露修长腿部与战术绑腿。旧皮革束腰，黄铜扣具。下装修身战术长裤、模块化腿甲、沙色磨损战术长靴，金属鞋头，铁钉鞋底。

            全套饰品：弹壳与旧铜链混搭项链、皮革臂带、黄铜戒指、破布流苏腰链、弹药包、脚踝铁链。旧步枪仅作虚化剪影，不突出枪械细节。

            背景：中东废土沙漠废墟，黄昏沙尘，倒塌土坯建筑与残破拱门剪影，生锈油桶，废弃皮卡，篝火余烬，铁丝网，远处沙尘暴。冷月光与暖橙火光交织，背景虚化干净，低对比不抢人物。

            8K粗糙金属与旧皮革质感，沙尘颗粒，画面干净无杂物，明暗柔和，不抢服饰细节。

            注意请你直接输出提示词正文，不要任何解释、标题或代码块。且模版中的全部内容都要根据角色实际信息进行修改包括衣服配饰特写等等
            
            """)

        # ---------------- 4. 调用 LLM（统一走 _call_prompt_llm：含一次重试 + 长度门槛） ----------------
        return self._call_prompt_llm(prompt_llm, min_chars=150)

    def _call_llm(self, prompt: str, temperature: float = 0.7,
                  max_tokens: int = 1024) -> str:
        """调用父类 LLM 接口并清理代码块标记。"""
        return super()._call_llm(
            prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        ).strip().strip("```").strip()


    def _build_location_prompt(self, name: str, loc, target_format: str = "wide") -> str:
        """
        构建场景提示词。调用 LLM 根据场景信息生成文生图/文生视频 prompt。

        target_format 控制视角类型：
        - "sheet" / "multi" / "设定" : 多视角场景设定图
        - "expand" / "扩图"          : 扩图 / 大全景延伸
        - "wide" / "全景" / "远景"   : 超宽银幕全景
        - "top" / "俯视" / "鸟瞰"    : 高机位俯瞰
        - "low" / "仰视"             : 低机位仰视
        - "close" / "特写" / "局部"  : 局部材质/陈设特写
        - 其他                       : 单视角电影全景
        """
        # ---------------- 1. 抽取场景信息 ----------------
        loc_type = getattr(loc, 'type', '场景') or '场景'
        description = getattr(loc, 'description', '') or ''
        atmosphere = getattr(loc, 'atmosphere', '') or ''
        visual_elements = getattr(loc, 'visual_elements', []) or []
        if not isinstance(visual_elements, list):
            visual_elements = [str(visual_elements)]

        base_info: Dict[str, Any] = {
            "name": name,
            "type": loc_type,
            "description": description,
            "atmosphere": atmosphere,
            "visual_elements": visual_elements,
        }

        # 合并场景对象上其他可用字段
        for attr in ("era", "worldview", "dynasty", "style", "scale",
                     "time_of_day", "weather", "region", "tags"):
            val = getattr(loc, attr, None)
            if val:
                base_info.setdefault(attr, val)

        # ---------------- 2. 解析视角指令 ----------------
        view_guide = _resolve_view_guide_location(target_format, loc_type)

        # ---------------- 3. 组装元提示词 ----------------
        loc_info_str = json.dumps(
            base_info, ensure_ascii=False, indent=2, default=str
        )

        prompt_llm = "\n\n".join([
            _STYLE_DIRECTIVE.format(target_format=target_format),
            _META_SYSTEM_ROLE_LOCATION,
            _META_RULES_LOCATION,
            "只根据目标风格和场景信息生成。",
            "# 场景信息\n" + loc_info_str,
            "# 目标视角与构图\n" + view_guide,
            "# 任务\n"
            "请严格按照上述 10 个模块与特殊任务规则，"
            "为该场景生成一段可直接输入文生图/文生视频模型的完整提示词。"
            "空间结构、材质对比、光影、镜头焦段、尺度参照必须全部覆盖。"
            "直接输出提示词正文，不要任何解释、标题或代码块。",
        ])

        # ---------------- 4. 调用 LLM（统一走 _call_prompt_llm） ----------------
        return self._call_prompt_llm(prompt_llm, min_chars=180,
                                     cleaner=_clean_prompt_output_location)

    # ---- 复用：让 _build_character_prompt / _build_location_prompt / _build_prop_prompt 共用一套 LLM 重试 + 长度门槛 ----
    def _call_prompt_llm(self, prompt_llm: str, min_chars: int,
                         cleaner=None) -> Optional[str]:
        """统一的 LLM 调用 + 输出清洗 + 重试 + 长度门槛。

        Args:
            prompt_llm: 已拼装好的元提示词。
            min_chars: 清洗后提示词的最小字符数（低于此视为输出过短）。
            cleaner: 清洗函数，默认 _clean_prompt_output；场景可传 _clean_prompt_output_location。

        Returns:
            清洗后的提示词字符串；全部重试都失败或输出始终过短时返回 None。
        """
        cleaner = cleaner or _clean_prompt_output
        for attempt in range(2):
            try:
                raw = self._call_llm(
                    prompt_llm,
                    temperature=0.65 if attempt == 0 else 0.5,
                    max_tokens=2048,
                )
                cleaned = cleaner(raw or "")
                if len(cleaned) >= min_chars:
                    return cleaned
                print(f"  [警告] LLM 输出过短（{len(cleaned)} 字），重试中…")
            except Exception as e:
                print(f"  [警告] LLM 生成 prompt 失败（第 {attempt + 1} 次）: {e}")
        return None

    def _build_prop_prompt(self, name: str, prop, target_format: str = "full") -> Optional[str]:
        """构建道具提示词。调用 LLM 根据道具信息生成文生图 prompt。"""
        ptype = (getattr(prop, "type", "道具") or "道具").strip().lower()

        visual_elements = getattr(prop, "visual_elements", []) or []
        if not isinstance(visual_elements, list):
            visual_elements = [str(visual_elements)]
        color_palette = getattr(prop, "color_palette", []) or []
        if not isinstance(color_palette, list):
            color_palette = [str(color_palette)]

        base_info: Dict[str, Any] = {
            "name": name,
            "type": ptype,
            "description": getattr(prop, "description", "") or "",
            "significance": getattr(prop, "significance", "") or "",
            "visual_key": getattr(prop, "visual_key", "") or "",
            "owner": getattr(prop, "owner", "") or "",
            "era": getattr(prop, "era", "") or "",
            "atmosphere": getattr(prop, "atmosphere", "") or "",
            "visual_elements": visual_elements,
            "color_palette": color_palette,
        }

        prop_info_str = json.dumps(base_info, ensure_ascii=False, indent=2, default=str)

        prompt_llm = "\n\n".join([
            _STYLE_DIRECTIVE.format(target_format=target_format),
            # 复用角色的元提示词系统角色与规则——核心要点（材质、光影、镜头、渲染标准）一致
            _META_SYSTEM_ROLE,
            _META_RULES,
            _META_FIXED_TAIL,
            "只根据目标风格和道具信息生成。",
            "# 道具信息\n" + prop_info_str,
            "# 任务\n"
            "请严格按照上述规则，为这个道具生成一段可直接输入文生图模型的完整提示词。"
            "必须突出「视觉识别关键」(" + (base_info.get("visual_key") or "以 description 为准") + ")，"
            "以便后续视频生成阶段能在不同镜头中稳定检索。"
            "直接输出提示词正文，不要任何解释、标题或代码块。",
        ])

        return self._call_prompt_llm(prompt_llm, min_chars=140)

    # ======================== 参考图查找 ========================

    # 参考图根目录（固定路径，用户可在 D:\cg_create\reference_image\ 下按类别放图片）
    REFERENCE_IMAGE_ROOT = Path("D:/cg_create/reference_image")

    # 类别名 → 参考图子目录名（映射表）
    _CATEGORY_REF_DIR = {
        "characters": "character",
        "locations":  "location",
        "props":      "prop",
    }

    def _find_reference_images(self, category: str) -> List[Path]:
        """
        扫描 reference_image/{category}/ 子目录，把该目录下所有图片作为参考图返回。

        不做文件名匹配 — 只要该类别下放了图片，所有同类别的 API 请求都会附带这些图片作为风格参考。
        支持的图片格式：png / jpg / jpeg / webp / gif

        Args:
            category: 资产类别（characters / locations / props）

        Returns:
            找到的本地图片路径列表（按修改时间升序，最早的在前）
        """
        ref_dir_name = self._CATEGORY_REF_DIR.get(category, category)
        ref_dir = self.REFERENCE_IMAGE_ROOT / ref_dir_name
        if not ref_dir.is_dir():
            return []

        extensions = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
        images: List[Path] = []
        for f in ref_dir.iterdir():
            if f.is_file() and f.suffix.lower() in extensions:
                images.append(f)

        # 按修改时间排序（最早的在前）
        images.sort(key=lambda p: p.stat().st_mtime)
        if images:
            print(
                f"      参考图: 类别 [{category}] 发现 {len(images)} 张, "
                f"全部作为本次请求的风格参考: "
                f"{', '.join(f.name for f in images)}"
            )
        return images

    def _build_image_content_blocks(
        self, reference_paths: List[Path], prompt_text: str
    ) -> List[Dict[str, Any]]:
        """
        将本地参考图转换为 API 消息 content 块列表。

        返回格式符合 OpenAI multimodal user message 结构：
        [
            {"type": "text",               "text": <prompt_text>},
            {"type": "image_url", "image_url": {"url": "data:image/...;base64,..."}},
            ...
        ]

        图片格式统一使用 image/png（如果源文件是其他格式，也直接嵌入 base64，
        部分 API 支持自动识别 MIME 类型）。

        Args:
            reference_paths: 参考图本地路径列表
            prompt_text:    文字提示词

        Returns:
            混合 content 块列表
        """
        import base64

        blocks: List[Dict[str, Any]] = [{"type": "text", "text": prompt_text}]
        for img_path in reference_paths:
            try:
                data = img_path.read_bytes()
                ext = img_path.suffix.lower()
                mime = {
                    ".png":  "image/png",
                    ".jpg":  "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".webp": "image/webp",
                    ".gif":  "image/gif",
                }.get(ext, "image/png")
                b64 = base64.b64encode(data).decode("ascii")
                blocks.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                })
                print(f"      [Ref] {img_path.name} ({len(data) // 1024} KB) 已转为 base64")
            except Exception as e:
                print(f"      [Ref] 读取 {img_path.name} 失败: {e}")
        return blocks

    # ======================== 图像生成核心 ========================

    def _get_openai_client(self):
        """懒加载 OpenAI 客户端（基于 base_url 拆解）。"""
        if self._openai_client is None:
            from openai import OpenAI
            self._openai_client = OpenAI(api_key=self.api_key, base_url=self._base_url)
        return self._openai_client

    def _extract_b64_from_response(self, response_dict: Dict[str, Any]) -> Optional[str]:
        """
        从 OpenAI Chat 响应中递归提取第一张 base64 图片 data URL。

        支持两种形态：
        1. message.content 是字符串，内含 data:image/...;base64,XXXX
        2. message.content 是列表（多模态），元素 type=image_url，url 字段是 data:...;base64,XXXX
        """
        def walk(obj) -> Optional[str]:
            if isinstance(obj, dict):
                # 多模态结构：{"type": "image_url", "image_url": {"url": "data:..."}}
                if obj.get("type") == "image_url":
                    image_url = obj.get("image_url") or {}
                    if isinstance(image_url, dict):
                        url = image_url.get("url", "")
                        if isinstance(url, str) and url.startswith("data:image/"):
                            return url
                # b64_json 直接字段
                if isinstance(obj.get("b64_json"), str):
                    return f"data:image/png;base64,{obj['b64_json']}"
                # url 直接字段（http 链接）
                if isinstance(obj.get("url"), str):
                    url_val = obj["url"]
                    if url_val.startswith("data:image/"):
                        return url_val
                for v in obj.values():
                    hit = walk(v)
                    if hit:
                        return hit
            elif isinstance(obj, list):
                for v in obj:
                    hit = walk(v)
                    if hit:
                        return hit
            elif isinstance(obj, str):
                m = re.search(
                    r'data:image/(png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=]+)',
                    obj,
                )
                if m:
                    return m.group(0)
            return None

        return walk(response_dict)

    def _extract_image_url(self, response_dict: Dict[str, Any]) -> Optional[str]:
        """从响应中递归提取 http(s) 图片链接（如有）。"""
        def walk(obj) -> Optional[str]:
            if isinstance(obj, dict):
                if isinstance(obj.get("url"), str):
                    url_val = obj["url"]
                    if re.match(r"^https?://", url_val) and re.search(
                        r"\.(?:png|jpe?g|webp|gif)(?:\?|$)",
                        url_val,
                        flags=re.IGNORECASE,
                    ):
                        return url_val
                for v in obj.values():
                    hit = walk(v)
                    if hit:
                        return hit
            elif isinstance(obj, list):
                for v in obj:
                    hit = walk(v)
                    if hit:
                        return hit
            return None

        return walk(response_dict)

    def _generate_image(
        self,
        prompt: str,
        subject: str,
        category: str,
        model: str = None,
        size: str = None,
    ) -> Dict[str, Any]:
        """
        调用 Gemini image-preview 文生图 API 生成单张图片。

        Args:
            prompt: 文生图提示词
            subject: 资产主题名（用于文件名）
            category: 资产类别（characters/locations/props）
            model: 使用的模型（默认使用配置值）
            size: 图片尺寸（默认使用配置值）

        Returns:
            成功时: {"success": True, "image_path": str, "url": str}
            失败时: {"success": False, "error": str}
        """
        if not self.api_key:
            return {"success": False, "error": "缺少 API Key（IMAGE_API_KEY）"}

        model = model or self.default_model

        # 内容安全拦截后的合规降级 prompt
        safe_prompt = _safe_image_prompt(subject, category)

        # ---------- 查找本地参考图 ----------
        ref_paths = self._find_reference_images(category)
        if ref_paths:
            print(f"      将 {len(ref_paths)} 张参考图附加到 API 请求")
        # 两种 prompt 对应的 content 块（用于 chat completions multimodal 接口）
        content_blocks_normal = self._build_image_content_blocks(ref_paths, prompt)
        content_blocks_safe   = self._build_image_content_blocks(ref_paths, safe_prompt)

        def _do_request_chat(
            use_model: str,
            content_blocks: List[Dict[str, Any]],
        ) -> Dict[str, Any]:
            """Chat Completions multimodal 接口（Gemini 等）"""
            client = self._get_openai_client()
            resp = client.chat.completions.create(
                model=use_model,
                messages=[{"role": "user", "content": content_blocks}],
                extra_body={"modalities": ["text", "image"]},
                timeout=300,
            )
            data = resp.model_dump() if hasattr(resp, "model_dump") else resp

            # 优先尝试 base64
            data_url = self._extract_b64_from_response(data)
            if data_url:
                m = re.match(
                    r"data:image/(png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=]+)",
                    data_url,
                )
                if not m:
                    raise RuntimeError("解析 base64 data URL 失败")
                ext = m.group(1)
                if ext == "jpeg":
                    ext = "jpg"
                image_path = self._save_base64_image(m.group(2), subject, category)
                if image_path:
                    return {
                        "success": True,
                        "image_path": str(image_path),
                        "url": data_url[:60] + "...",
                        "model": use_model,
                    }
                raise RuntimeError("保存 base64 图片失败")

            # 其次尝试 http 链接
            http_url = self._extract_image_url(data)
            if http_url:
                image_path = self._download_image(http_url, subject, category)
                if image_path:
                    return {
                        "success": True,
                        "image_path": str(image_path),
                        "url": http_url,
                        "model": use_model,
                    }
                raise RuntimeError(f"下载图片失败: {http_url}")

            preview = json.dumps(data, ensure_ascii=False)[:500]
            raise RuntimeError(f"响应中未找到图片数据（模型可能仅返回文本）。响应片段：{preview}")

        def _do_request_images(use_model: str, use_prompt: str) -> Dict[str, Any]:
            """Images Generate 接口（gpt-image-2.5 等），不支持参考图"""
            client = self._get_openai_client()
            resp = client.images.generate(
                model=use_model,
                prompt=use_prompt,
                size=self.default_size,
                quality=self.default_quality,
                n=1,
                output_format="png",
                timeout=self.request_timeout,
            )

            # gpt-image-2.5 直接返回 data[0].b64_json
            item = resp.data[0]
            b64_str = getattr(item, "b64_json", None)
            if b64_str:
                raw = b64_str.split(",")[-1] if b64_str.startswith("data:") else b64_str
                image_path = self._save_base64_image(raw, subject, category)
                if image_path:
                    return {
                        "success": True,
                        "image_path": str(image_path),
                        "url": f"b64_json:{len(raw)}chars",
                        "model": use_model,
                    }
                raise RuntimeError("保存 base64 图片失败")

            # 备选：url 格式
            url = getattr(item, "url", None)
            if url:
                image_path = self._download_image(url, subject, category)
                if image_path:
                    return {
                        "success": True,
                        "image_path": str(image_path),
                        "url": url,
                        "model": use_model,
                    }
                raise RuntimeError(f"下载图片失败: {url}")

            raise RuntimeError(f"响应中未找到图片数据: {item}")

        def _do_request(use_model: str, content_blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
            """发一次请求，根据模型类型选择接口；chat 接口使用 content_blocks"""
            if self._use_images_api(use_model):
                # images/generations 接口不支持参考图，直接用纯文本 prompt（取第一个 text 块）
                text_prompt = next(
                    (b["text"] for b in content_blocks if b["type"] == "text"), ""
                )
                return _do_request_images(use_model, text_prompt)
            else:
                return _do_request_chat(use_model, content_blocks)

        # 第一次请求：原模型 + 原 prompt + 参考图
        try:
            return _do_request(model, content_blocks_normal)
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            print(
                f"\n  [API错误] prompt_chars={len(prompt)}, model={model}, "
                f"ref_images={len(ref_paths)}, {error}"
            )

            # 内容安全拦截 → 用合规降级 prompt 重试一次
            if _is_sensitive_content_error(error):
                print(f"\n  [降级重试] 检测到内容安全拦截，对 {subject} 使用合规降级 prompt")
                try:
                    return _do_request(model, content_blocks_safe)
                except Exception as retry_e:
                    print(
                        f"\n  [降级重试失败] model={model}, "
                        f"error={type(retry_e).__name__}: {retry_e}"
                    )
                    return {"success": False, "error": f"合规降级 prompt 也失败: {retry_e}"}

            # 模型不存在，或主模型"仅返回文本"（声称生成了图，但响应里没有图片字段）→ 依次尝试备选模型
            is_model_missing = any(
                marker in error
                for marker in ("model_not_found", "Model not found", "does not exist", "not exist")
            )
            is_text_only = any(marker in error for marker in self._TEXT_ONLY_MARKERS)
            if is_model_missing or is_text_only:
                reason = "模型不存在" if is_model_missing else "主模型仅返回文本（无图片数据）"
                print(f"\n  [切换模型] {reason}，按备选列表尝试其它模型")
                for fallback in self.FALLBACK_MODELS:
                    if fallback == model:
                        continue
                    print(f"  -> 尝试备选模型 {fallback}")
                    try:
                        return _do_request(fallback, content_blocks_normal)
                    except Exception as fb_e:
                        print(f"  [备选模型失败] {fallback}: {fb_e}")
                        continue

            return {"success": False, "error": error}

    def _download_image(self, url: str, subject: str, category: str) -> Optional[Path]:
        """下载并保存远程图片"""
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            return self._save_image_bytes(resp.content, subject, category)
        except Exception:
            return None

    def _save_base64_image(self, b64_data: str, subject: str, category: str) -> Optional[Path]:
        """保存Base64编码的图片"""
        import base64
        try:
            image_bytes = base64.b64decode(b64_data)
            return self._save_image_bytes(image_bytes, subject, category)
        except Exception:
            return None

    def _save_image_bytes(self, data: bytes, subject: str, category: str) -> Optional[Path]:
        """将图片字节数据保存到文件"""
        if not self.session_dir:
            return None

        # 生成文件名：以对象名称命名，存入 assets/{category}
        safe_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in subject)
        filename = f"{safe_name}.png"
        save_dir = self.session_dir / "assets" / category
        save_dir.mkdir(parents=True, exist_ok=True)
        filepath = save_dir / filename

        with open(filepath, 'wb') as f:
            f.write(data)

        return filepath


# ============================================================================
#  内容安全降级 & 错误识别工具（模块级函数）
# ============================================================================

_SENSITIVE_KEYWORDS = (
    "safety",
    "policy",
    "violation",
    "content_policy",
    "blocked",
    "blocked_reason",
    "inappropriate",
    "harmful",
    "成人",
    "裸露",
    "色情",
    "血腥",
    "暴力",
    "违禁",
    "敏感词",
    "内容安全",
    "内容过滤",
    "审查",
)


def _is_sensitive_content_error(error: str) -> bool:
    """判断错误信息是否属于内容安全拦截。"""
    if not error:
        return False
    low = str(error).lower()
    return any(kw.lower() in low for kw in _SENSITIVE_KEYWORDS)


def _safe_image_prompt(subject: str, category: str) -> str:
    """生成一个不含敏感描述的合规降级提示词，用于内容安全拦截后的重试。"""
    cat = (category or "asset").strip()
    name = (subject or "主体").strip()
    if cat == "characters":
        return (
            f"超写实电影级风格，角色概念设定图（Character Concept Art）。"
            f"主体：{name}。"
            f"全身正视图，标准人设稿比例（约 8 头身），干净纯色背景，正面朝向镜头，"
            f"服装/装甲与配件完整可见，材质与光影写实可信，"
            f"体积光，胶片颗粒感，8K，PBR。"
        )
    if cat == "locations":
        return (
            f"超写实电影级风格，场景概念图（Environment Concept Art）。"
            f"场景：{name}。"
            f"单视角全景，24mm 广角，机位平视，主体结构完整入画，"
            f"前后景层次分明，远景以空气透视渐隐，"
            f"体积光，胶片颗粒感，HDR，全局光照，8K，PBR，画面干净无杂物。"
        )
    if cat == "props":
        return (
            f"超写实电影级风格，道具概念图（Prop Concept Art）。"
            f"道具：{name}。"
            f"中景构图，正面朝向镜头，置于干净的台面上，"
            f"重点呈现材质细节、磨损、铭文与色彩对比，"
            f"体积光，胶片颗粒感，HDR，8K，PBR，画面干净无杂物。"
        )
    return (
        f"超写实电影级风格，{name}。正面构图，正对镜头，"
        f"材质与光影写实可信，体积光，胶片颗粒感，8K，PBR，画面干净无杂物。"
    )
