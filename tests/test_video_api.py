"""
视频API测试脚本
用于验证API配置和账户状态
"""
import os
import requests
import json
import sys

# API配置
API_KEY = os.getenv("ARK_VIDEO_API_KEY") or os.getenv("ARK_API_KEY", "")
BASE_URL = "https://www.moyu.cn"
MODEL = "doubao-seedance-2-5-260628"

def test_simple_video():
    """测试简单的文生视频"""
    print("=" * 60)
    print("测试1: 简单文生视频 (5秒)")
    print("=" * 60)
    
    headers = {"Authorization": f"Bearer {API_KEY}"}
    payload = {
        "model": MODEL,
        "prompt": "test video",
        "metadata": {
            "content": [
                {"type": "text", "text": "一只橘色的猫咪在阳光下的花园里追逐蝴蝶"}
            ],
            "duration": 5,
            "resolution": "720p",
            "ratio": "9:16",
            "generate_audio": True
        }
    }
    
    try:
        print(f"请求URL: {BASE_URL}/v1/video/generations")
        print(f"请求数据: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        print("\n发送请求...")
        
        resp = requests.post(
            f"{BASE_URL}/v1/video/generations",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"状态码: {resp.status_code}")
        print(f"响应: {json.dumps(resp.json(), ensure_ascii=False, indent=2)}")
        
        if resp.status_code == 200:
            task_id = resp.json().get('task_id')
            print(f"\n✓ 任务提交成功! Task ID: {task_id}")
            return True, task_id
        else:
            print(f"\n✗ 任务提交失败")
            return False, None
            
    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
        return False, None

def test_image_reference_video():
    """测试带角色参考图的视频生成"""
    print("\n" + "=" * 60)
    print("测试2: 图片参考生成视频 (5秒)")
    print("=" * 60)
    
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    # 读取角色参考图
    import base64
    try:
        with open("D:/cg_create/photos/3.jpg", 'rb') as f:
            img_base64 = base64.b64encode(f.read()).decode()
    except Exception as e:
        print(f"✗ 无法读取参考图: {e}")
        return False, None
    
    payload = {
        "model": MODEL,
        "prompt": "character reference video",
        "metadata": {
            "content": [
                {"type": "text", "text": "一个年轻士兵站在军事基地前，表情坚毅，目光锐利"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"},
                    "role": "reference_image"
                }
            ],
            "duration": 5,
            "resolution": "720p",
            "ratio": "9:16",
            "generate_audio": True
        }
    }
    
    try:
        print(f"请求URL: {BASE_URL}/v1/video/generations")
        print(f"请求数据: (含base64图片，已省略)")
        print("\n发送请求...")
        
        resp = requests.post(
            f"{BASE_URL}/v1/video/generations",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"状态码: {resp.status_code}")
        print(f"响应: {json.dumps(resp.json(), ensure_ascii=False, indent=2)}")
        
        if resp.status_code == 200:
            task_id = resp.json().get('task_id')
            print(f"\n✓ 任务提交成功! Task ID: {task_id}")
            return True, task_id
        else:
            print(f"\n✗ 任务提交失败")
            return False, None
            
    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
        return False, None

def query_task(task_id):
    """查询任务状态"""
    print("\n" + "=" * 60)
    print(f"查询任务状态: {task_id}")
    print("=" * 60)
    
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    try:
        resp = requests.get(
            f"{BASE_URL}/v1/video/generations/{task_id}",
            headers=headers,
            timeout=30
        )
        
        print(f"状态码: {resp.status_code}")
        result = resp.json()
        print(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
        
        if resp.status_code == 200:
            status = result.get('data', {}).get('status', 'UNKNOWN')
            print(f"\n任务状态: {status}")
            return True
        else:
            return False
            
    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
        return False

if __name__ == "__main__":
    print("\n视频生成API测试工具")
    print("=" * 60)
    print(f"API密钥: {API_KEY[:20]}...")
    print(f"模型: {MODEL}")
    print(f"基础URL: {BASE_URL}")
    print()
    
    # 测试1: 简单文生视频
    success1, task_id1 = test_simple_video()
    
    # 测试2: 带参考图的视频
    success2, task_id2 = test_image_reference_video()
    
    # 如果有成功的任务，查询状态
    if success1 and task_id1:
        query_task(task_id1)
    
    if success2 and task_id2:
        query_task(task_id2)
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"测试1 (简单文生视频): {'✓ 通过' if success1 else '✗ 失败'}")
    print(f"测试2 (图片参考视频): {'✓ 通过' if success2 else '✗ 失败'}")
    
    if not (success1 or success2):
        print("\n⚠️  所有测试失败，请检查:")
        print("   1. API密钥是否有效")
        print("   2. 账户余额是否充足(需≥30元)")
        print("   3. 网络连接是否正常")
        sys.exit(1)
    else:
        print("\n✓ 至少一个测试通过，API配置正确!")
        sys.exit(0)
