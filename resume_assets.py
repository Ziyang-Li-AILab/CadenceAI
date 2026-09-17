# -*- coding: utf-8 -*-
"""Resume asset generation: skip existing, only generate remaining."""
import json
import os
import sys
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


# --- Load API keys (same logic as run_complete_pipeline.py) ---
def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and value and not os.getenv(name):
            os.environ[name] = value


_load_env_file(Path(__file__).resolve().parent / "configs" / "api_keys.env")

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


# Build config the same way run_complete_pipeline.py does
CONFIG = {
    "llm": {
        "endpoint": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "api_key": _first_env("ARK_LLM_API_KEY", "VOLC_API_KEY"),
        "model": "doubao-seed-evolving",
        "temperature": 0.7,
        "max_tokens": 20000,
    },
    "image_api": {
        "api_key": _first_env("IMAGE_API_KEY"),
        "endpoint": "https://nanoapi.poloai.top/v1/chat/completions",
        "model": "gemini-3.1-flash-image-preview",
        "size": "",
        "steps": 0,
    },
    "audio_api": {
        "api_key": _first_env("AUDIO_API_KEY", "TTS_API_KEY"),
    },
}


# --- Core logic ---
from core.world_database import WorldDatabase
from agents.specialists.asset_creator import AssetCreator

SESSION_DIR = Path(r"d:\cg_create\pipeline_output\20260916_101908")
WORLD_PATH = SESSION_DIR / "01_world.json"
TARGET_FORMAT = "中东废土"  # 中东废土工业废土风


def has_image(name: str, category: str) -> bool:
    """Whether a generated image for the subject already exists (and non-empty)."""
    safe_name = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in str(name)).strip("._") or "asset"
    img = SESSION_DIR / "assets" / category / f"{safe_name}.png"
    return img.exists() and img.stat().st_size > 1024


def load_existing_manifest() -> dict:
    manifest_path = SESSION_DIR / "assets" / "manifest.json"
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"characters": [], "locations": [], "all_images": []}


def main() -> int:
    world = WorldDatabase.load(WORLD_PATH)
    creator = AssetCreator(CONFIG)
    creator.set_session_dir(SESSION_DIR)

    existing = load_existing_manifest()
    existing_chars = {c["name"] for c in existing.get("characters", [])}
    existing_locs = {l["name"] for l in existing.get("locations", [])}

    print(f"[Resume] World: {len(world.characters)} chars, {len(world.locations)} locs")
    print(f"[Resume] Already done: chars={sorted(existing_chars)}, locs={sorted(existing_locs)}")

    results_chars = list(existing.get("characters", []))
    results_locs = list(existing.get("locations", []))
    results_props = list(existing.get("props", []))
    all_imgs = list(existing.get("all_images", []))
    existing_props = {p["name"] for p in results_props}

    # 复用「生成单个资产 + 落盘 manifest」的统一逻辑
    def generate_one(name: str, obj, category: str, prompt_builder,
                     results_list: list, existing_set: set) -> bool:
        """返回 True 表示成功，False 表示失败需中断续跑。"""
        print(f"\n[{category_to_label[category]}] generating {name} ...", flush=True)
        prompt = prompt_builder(name, obj, TARGET_FORMAT)
        if not prompt:
            print(f"  X failed: prompt 生成失败（LLM 重试均未通过长度门槛）")
            return False
        prompt_path = creator._save_prompt(prompt, name, category)
        print(f"  prompt -> {prompt_path.name}")

        result = creator._generate_image(prompt, subject=name, category=category)
        if not result.get("success"):
            print(f"  X failed: {result.get('error')}")
            return False
        print(f"  OK -> {Path(result['image_path']).name}")
        results_list.append({
            "name": name,
            "image_path": result["image_path"],
            "prompt_path": str(prompt_path),
            "prompt": prompt_path.read_text(encoding="utf-8"),
        })
        all_imgs.append(result["image_path"])
        existing_set.add(name)
        existing[category_to_results_key[category]] = results_list
        existing["all_images"] = all_imgs
        (SESSION_DIR / "assets" / "manifest.json").write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return True

    category_to_label = {"characters": "角色", "locations": "场景", "props": "道具"}
    category_to_results_key = {"characters": "characters", "locations": "locations", "props": "props"}

    # ============ Characters ============
    pending_chars = [
        n for n in world.characters
        if n not in existing_chars or not has_image(n, "characters")
    ]
    print(f"\n[Resume] Pending characters: {pending_chars}")
    for name in pending_chars:
        if not generate_one(name, world.characters[name], "characters",
                            creator._build_character_prompt, results_chars, existing_chars):
            print(f"[Resume] stop at '{name}' — will resume next time")
            return 1

    # ============ Locations ============
    pending_locs = [
        n for n in world.locations
        if n not in existing_locs or not has_image(n, "locations")
    ]
    print(f"\n[Resume] Pending locations: {pending_locs}")
    for name in pending_locs:
        if not generate_one(name, world.locations[name], "locations",
                            creator._build_location_prompt, results_locs, existing_locs):
            print(f"[Resume] stop at '{name}' — will resume next time")
            return 1

    # ============ Props ============
    pending_props = [
        n for n in world.props
        if n not in existing_props or not has_image(n, "props")
    ]
    print(f"\n[Resume] Pending props: {pending_props}")
    for name in pending_props:
        if not generate_one(name, world.props[name], "props",
                            creator._build_prop_prompt, results_props, existing_props):
            print(f"[Resume] stop at '{name}' — will resume next time")
            return 1

    print(
        f"\n[Resume] DONE. "
        f"characters={len(results_chars)}, "
        f"locations={len(results_locs)}, "
        f"props={len(results_props)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
