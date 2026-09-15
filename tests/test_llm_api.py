#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试豆包LLM API"""

import os
import requests
import json

# API配置
endpoint = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
api_key = os.getenv("ARK_LLM_API_KEY") or os.getenv("VOLC_API_KEY") or os.getenv("ARK_API_KEY", "")
model = "doubao-seed-evolving"

print("正在测试豆包LLM API...", flush=True)
print(f"Endpoint: {endpoint}", flush=True)
print(f"Model: {model}", flush=True)

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

payload = {
    "model": model,
    "messages": [
        {"role": "user", "content": "你好，请用一句话介绍你自己。"}
    ]
}

try:
    print("\n发送请求...", flush=True)
    response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
    
    print(f"\n响应状态码: {response.status_code}", flush=True)
    print(f"响应头: {dict(response.headers)}", flush=True)
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n完整响应: {json.dumps(result, ensure_ascii=False, indent=2)}", flush=True)
        
        if 'choices' in result and len(result['choices']) > 0:
            content = result['choices'][0]['message']['content']
            print(f"\n✓ API调用成功！", flush=True)
            print(f"回复内容: {content}", flush=True)
        else:
            print(f"\n✗ 响应格式异常，没有找到choices", flush=True)
    else:
        print(f"\n✗ API调用失败", flush=True)
        print(f"错误内容: {response.text}", flush=True)
        
except requests.exceptions.Timeout:
    print(f"\n✗ 请求超时（30秒）", flush=True)
except Exception as e:
    print(f"\n✗ 发生错误: {e}", flush=True)
    import traceback
    traceback.print_exc()
