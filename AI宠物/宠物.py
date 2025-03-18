import os
import streamlit as st
from PIL import Image
import io
import base64
import requests
import json
from openai import OpenAI
import time

# 阿里云百炼API配置
DASHSCOPE_API_KEY = "sk-b8190cc0897b49b494c4dc8d6228c3bf"  # 请替换为您的阿里云DashScope API Key
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL_MULTIMODAL = "qwen-vl-plus"  # 通义千问视觉语言模型
MODEL_TEXT_TO_IMAGE = "wanx-v1"  # 阿里云百炼文生图模型

# 初始化OpenAI客户端（使用阿里云兼容模式）
client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url=BASE_URL,
)

def encode_image_to_base64(image_file):
    """将图像文件转换为base64编码"""
    try:
        # 打开图像文件
        image = Image.open(image_file)
        
        # 转换为RGB模式（处理RGBA等其他模式）
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # 调整图像大小以减小文件大小
        max_size = 500
        image.thumbnail((max_size, max_size), Image.LANCZOS)
        
        # 保存为JPEG，中等质量
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=80)
        buffered.seek(0)
        
        # 转换为base64
        img_base64 = base64.b64encode(buffered.read()).decode('utf-8')
        return img_base64
    except Exception as e:
        st.error(f"图像编码错误: {str(e)}")
        raise

def generate_pet_description(image_file):
    """使用阿里云通义千问API生成宠物描述"""
    try:
        # 将图片转换为base64格式
        base64_image = encode_image_to_base64(image_file)
        
        # 使用OpenAI兼容模式调用API
        completion = client.chat.completions.create(
            model=MODEL_MULTIMODAL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "这是一张宠物图片，请详细描述这只宠物的特征，包括品种、毛色、体型特征、精神状态等。请用通俗易懂的语言描述，语气要温暖友好。"
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        }
                    ]
                }
            ]
        )
        
        # 从响应中提取文本
        return completion.choices[0].message.content
            
    except Exception as e:
        st.error(f"API调用错误: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return "无法生成描述，请尝试上传更小的图片或稍后再试。"

def generate_anime_pet(description):
    """使用阿里云百炼API生成动漫风格宠物图片"""
    try:
        # 构建请求URL
        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
        
        # 构建请求体
        payload = {
            "model": "wanx2.1-t2i-turbo",
            "input": {
                "prompt": f"生成一张可爱的动漫风格宠物图片，基于以下描述：{description}。画风要可爱、精致，像宫崎骏动画风格。"
            },
            "parameters": {
                "size": "1024*1024",  # 图片尺寸
                "n": 1  # 生成图片数量
            }
        }
        
        # 生成请求头
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
            "X-DashScope-Async": "enable"  # 启用异步模式
        }
        
        # 发送请求
        response = requests.post(url, headers=headers, json=payload)
        
        # 处理响应
        if response.status_code == 200:
            result = response.json()
            
            # 检查是否是异步任务
            if "output" in result and "task_id" in result["output"]:
                task_id = result["output"]["task_id"]
                st.info(f"图片生成任务已提交，任务ID: {task_id}")
                
                # 轮询检查任务状态
                task_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
                task_headers = {
                    "Authorization": f"Bearer {DASHSCOPE_API_KEY}"
                }
                
                max_attempts = 30
                for attempt in range(max_attempts):
                    time.sleep(2)  # 每2秒检查一次
                    task_response = requests.get(task_url, headers=task_headers)
                    
                    if task_response.status_code == 200:
                        task_result = task_response.json()
                        status = task_result.get("output", {}).get("task_status")
                        
                        if status == "SUCCEEDED":
                            # 任务完成，获取结果
                            if "results" in task_result["output"] and len(task_result["output"]["results"]) > 0:
                                image_url = task_result["output"]["results"][0].get("url")
                                if image_url:
                                    # 下载图片
                                    img_response = requests.get(image_url)
                                    if img_response.status_code == 200:
                                        # 将图片数据转换为PIL图像
                                        image = Image.open(io.BytesIO(img_response.content))
                                        # 在Streamlit中显示图片
                                        st.image(image, caption="AI生成的动漫风格宠物", use_column_width=True)
                                        return True
                            break
                        elif status == "FAILED":
                            st.error(f"图片生成任务失败: {task_result}")
                            return False
                        
                        st.info(f"任务状态: {status}，继续等待...")
                    else:
                        st.error(f"检查任务状态失败: {task_response.status_code} - {task_response.text}")
                        return False
                
                st.error("等待任务完成超时")
                return False
            
            # 非异步任务的处理（保留原有逻辑以防万一）
            elif "output" in result and "results" in result["output"] and len(result["output"]["results"]) > 0:
                image_url = result["output"]["results"][0].get("url")
                if image_url:
                    # 下载图片
                    img_response = requests.get(image_url)
                    if img_response.status_code == 200:
                        # 将图片数据转换为PIL图像
                        image = Image.open(io.BytesIO(img_response.content))
                        # 在Streamlit中显示图片
                        st.image(image, caption="AI生成的动漫风格宠物", use_column_width=True)
                        return True
                    else:
                        st.error(f"下载生成的图片失败: {img_response.status_code}")
                        return False
                else:
                    st.error("返回的数据中没有图片URL")
                    return False
            else:
                st.error("未能获取到生成的图片数据")
                return False
        else:
            st.error(f"生成图片失败: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        st.error(f"生成动漫图片时出错: {str(e)}")
        return False

# Streamlit 界面
def main():
    st.title("🐾 AI宠物描述生成器")
    st.write("上传一张宠物的图片，AI 将为您生成暖心的描述！")
    
    # 确保文件上传器正确显示
    uploaded_file = st.file_uploader("选择一张宠物图片", type=["jpg", "jpeg", "png"], key="pet_image_uploader")
    
    if uploaded_file is not None:
        try:
            # 显示上传的图片
            image = Image.open(uploaded_file)
            st.image(image, caption="上传的宠物图片", use_column_width=True)
            
            # 生成描述按钮
            if st.button("✨ 生成描述", key="generate_button"):
                with st.spinner("正在仔细观察您的宠物..."):
                    # 重新打开文件，因为之前的操作可能已经消耗了文件对象
                    uploaded_file.seek(0)
                    description = generate_pet_description(uploaded_file)
                    st.write("### 🌟 宠物描述")
                    st.write(description)
                
                with st.spinner("正在创作动漫风格图片..."):
                    success = generate_anime_pet(description)
                    if success:
                        st.write("### 🎨 动漫风格图片")
                    else:
                        st.error("未能生成动漫风格图片")
        
        except Exception as e:
            st.error(f"处理图片时出现错误: {str(e)}")
    else:
        # 添加提示信息，让用户知道需要上传图片
        st.info("👆 请点击上方区域上传宠物图片")

if __name__ == "__main__":
    main()