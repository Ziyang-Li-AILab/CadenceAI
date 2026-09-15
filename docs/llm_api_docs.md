Rest api 调用示例：
用于
curl https://ark.cn-beijing.volces.com/api/v3/responses \
-H "Authorization: Bearer $ARK_API_KEY" \
-H 'Content-Type: application/json' \
-d '{
    "model": "doubao-seed-evolving",
    "input": [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image_url": "https://ark-project.tos-cn-beijing.volces.com/doc_image/ark_demo_img_1.png"
                },
                {
                    "type": "input_text",
                    "text": "你看见了什么？"
                }
            ]
        }
    ]
}'




open ai  sdk调用示例：
1. 请按如下命令安装环境
pip install --upgrade "openai>=1.0"
复制
2. 请参考如下示例代码进行调用
import os
from openai import OpenAI
# 从环境变量中获取您的API KEY，配置方法见：https://www.volcengine.com/docs/82379/1399008
api_key = os.getenv('ARK_API_KEY')
client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=api_key,
)
response = client.responses.create(
    model="doubao-seed-evolving",
    input=[
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image_url": "https://ark-project.tos-cn-beijing.volces.com/doc_image/ark_demo_img_1.png"
                },
                {
                    "type": "input_text",
                    "text": "你看见了什么？"
                },
            ],
        }
    ]
)
print(response)

火山引擎sdk调用示例：
1. 请按如下命令安装环境
pip install --upgrade "volcengine-python-sdk[ark]"
复制
2. 请参考如下示例代码进行调用
import os
from volcenginesdkarkruntime import Ark
# 从环境变量中获取您的API KEY，配置方法见：https://www.volcengine.com/docs/82379/1399008
api_key = os.getenv('ARK_API_KEY')
client = Ark(
    base_url='https://ark.cn-beijing.volces.com/api/v3',
    api_key=api_key,
)
response = client.responses.create(
    model="doubao-seed-evolving",
    input=[
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image_url": "https://ark-project.tos-cn-beijing.volces.com/doc_image/ark_demo_img_1.png"
                },
                {
                    "type": "input_text",
                    "text": "你看见了什么？"
                },
            ],
        }
    ]
)
print(response)