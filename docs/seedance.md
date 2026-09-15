# Seedance 2.0 多图生视频调用示例

## 接口信息

| 项目 | 说明 |
|------|------|
| 提交任务 | `POST {BASE_URL}/v1/video/generations` |
| 查询结果 | `GET {BASE_URL}/v1/video/generations/{task_id}` |
| 模型名称 | `doubao-seedance-2-0-260128` / `doubao-seedance-2-0-fast-260128` |
| 鉴权方式 | `Authorization: Bearer {API_KEY}` |

## 图片 Role 说明

| role | 说明 | 数量限制 |
|------|------|---------|
| `first_frame` | 首帧图，视频从该图开始 | 最多 1 张 |
| `last_frame` | 尾帧图，视频以该图结束 | 最多 1 张 |
| `reference_image` | 参考图，用于风格/角色参考 | 可多张 |

> `first_frame` 和 `last_frame` 可同时使用，实现首尾帧控制。

---

## 一、首帧 + 尾帧 + 参考图（多图）

### cURL

```bash
curl -X POST "${BASE_URL}/v1/video/generations" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "doubao-seedance-2-0-260128",
    "prompt": "多图生视频",
    "metadata": {
        "content": [
            {
                "type": "text",
                "text": "猫咪从沙发优雅地跳到窗台上，阳光透过窗帘洒落，毛发在光线中闪烁"
            },
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/cat_on_sofa.jpg"},
                "role": "first_frame"
            },
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/cat_on_window.jpg"},
                "role": "last_frame"
            },
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/warm_style_ref.jpg"},
                "role": "reference_image"
            }
        ],
        "duration": 5,
        "resolution": "720p",
        "ratio": "16:9",
        "generate_audio": true
    }
}'
```

### Python

```python
import requests
import time

BASE_URL = "https://your-api-domain.com"
API_KEY = "your-api-key"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# ========== 1. 提交任务：首帧 + 尾帧 + 参考图 ==========
payload = {
    "model": "doubao-seedance-2-0-260128",
    "prompt": "多图生视频",
    "metadata": {
        "content": [
            {
                "type": "text",
                "text": "猫咪从沙发优雅地跳到窗台上，阳光透过窗帘洒落，毛发在光线中闪烁"
            },
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/cat_on_sofa.jpg"},
                "role": "first_frame"
            },
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/cat_on_window.jpg"},
                "role": "last_frame"
            },
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/warm_style_ref.jpg"},
                "role": "reference_image"
            }
        ],
        "duration": 5,
        "resolution": "720p",
        "ratio": "16:9",
        "generate_audio": True
    }
}

response = requests.post(f"{BASE_URL}/v1/video/generations", headers=headers, json=payload)
result = response.json()
task_id = result["task_id"]
print(f"任务已提交，task_id: {task_id}")

# ========== 2. 轮询查询结果 ==========
while True:
    resp = requests.get(
        f"{BASE_URL}/v1/video/generations/{task_id}",
        headers={"Authorization": f"Bearer {API_KEY}"}
    )
    data = resp.json()
    task = data.get("data", data)
    status = task.get("status", "").upper()

    print(f"状态: {status}")

    if status in ("SUCCESS", "SUCCEEDED"):
        video_url = task.get("result_url", "")
        print(f"生成成功！视频地址: {video_url}")
        break
    elif status in ("FAILURE", "FAILED"):
        print(f"生成失败: {task.get('fail_reason', '未知错误')}")
        break

    time.sleep(15)
```

---

## 二、多张参考图（风格/角色控制）

适用场景：传入多张参考图控制视频的画面风格和人物形象。

### cURL

```bash
curl -X POST "${BASE_URL}/v1/video/generations" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "doubao-seedance-2-0-260128",
    "prompt": "多参考图",
    "metadata": {
        "content": [
            {
                "type": "text",
                "text": "一位穿白裙的女孩在樱花树下转圈起舞，花瓣随风飘落，画面唯美"
            },
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/girl_portrait.jpg"},
                "role": "reference_image"
            },
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/cherry_blossom_scene.jpg"},
                "role": "reference_image"
            },
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/dance_pose_ref.jpg"},
                "role": "reference_image"
            }
        ],
        "duration": 8,
        "resolution": "720p",
        "ratio": "9:16",
        "generate_audio": true
    }
}'
```

### Python

```python
payload = {
    "model": "doubao-seedance-2-0-260128",
    "prompt": "多参考图",
    "metadata": {
        "content": [
            {
                "type": "text",
                "text": "一位穿白裙的女孩在樱花树下转圈起舞，花瓣随风飘落，画面唯美"
            },
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/girl_portrait.jpg"},
                "role": "reference_image"
            },
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/cherry_blossom_scene.jpg"},
                "role": "reference_image"
            },
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/dance_pose_ref.jpg"},
                "role": "reference_image"
            }
        ],
        "duration": 8,
        "resolution": "720p",
        "ratio": "9:16",
        "generate_audio": True
    }
}

response = requests.post(f"{BASE_URL}/v1/video/generations", headers=headers, json=payload)
print(response.json())
```

---

## 三、图片 + 视频 + 音频（全模态）

适用场景：同时传入参考图、参考视频和参考音频，生成带有指定风格和声音的视频。

### cURL

```bash
curl -X POST "${BASE_URL}/v1/video/generations" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "doubao-seedance-2-0-260128",
    "prompt": "全模态生成",
    "metadata": {
        "content": [
            {
                "type": "text",
                "text": "一位吉他手在夕阳海滩弹唱，海浪轻拍沙滩，画面温暖治愈"
            },
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/guitarist.jpg"},
                "role": "first_frame"
            },
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/beach_sunset.jpg"},
                "role": "reference_image"
            },
            {
                "type": "video_url",
                "video_url": {"url": "https://example.com/guitar_playing.mp4"},
                "role": "reference_video"
            },
            {
                "type": "audio_url",
                "audio_url": {"url": "https://example.com/acoustic_guitar.mp3"},
                "role": "reference_audio"
            }
        ],
        "duration": 10,
        "resolution": "720p",
        "ratio": "16:9",
        "generate_audio": true
    }
}'
```

### Python

```python
payload = {
    "model": "doubao-seedance-2-0-260128",
    "prompt": "全模态生成",
    "metadata": {
        "content": [
            {
                "type": "text",
                "text": "一位吉他手在夕阳海滩弹唱，海浪轻拍沙滩，画面温暖治愈"
            },
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/guitarist.jpg"},
                "role": "first_frame"
            },
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/beach_sunset.jpg"},
                "role": "reference_image"
            },
            {
                "type": "video_url",
                "video_url": {"url": "https://example.com/guitar_playing.mp4"},
                "role": "reference_video"
            },
            {
                "type": "audio_url",
                "audio_url": {"url": "https://example.com/acoustic_guitar.mp3"},
                "role": "reference_audio"
            }
        ],
        "duration": 10,
        "resolution": "720p",
        "ratio": "16:9",
        "generate_audio": True
    }
}

response = requests.post(f"{BASE_URL}/v1/video/generations", headers=headers, json=payload)
print(response.json())
```

---

## 四、联网搜索 + 图片

在 `metadata` 中添加 `tools` 字段开启联网搜索，模型会结合搜索结果优化视频生成。

### Python

```python
payload = {
    "model": "doubao-seedance-2-0-260128",
    "prompt": "联网搜索生成",
    "metadata": {
        "content": [
            {
                "type": "text",
                "text": "2026年巴黎奥运会开幕式的精彩回顾"
            },
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/paris_stadium.jpg"},
                "role": "reference_image"
            }
        ],
        "duration": 10,
        "resolution": "720p",
        "ratio": "16:9",
        "generate_audio": True,
        "tools": [{"type": "web_search"}]
    }
}

response = requests.post(f"{BASE_URL}/v1/video/generations", headers=headers, json=payload)
print(response.json())
```


