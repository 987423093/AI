import os
import streamlit as st
from PIL import Image
import io
import base64
import requests
import json
from openai import OpenAI
import time
import datetime
import uuid

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
        description = completion.choices[0].message.content
        
        # 保存到session_state以便页面刷新后恢复
        st.session_state.last_description = description
        
        return description
            
    except Exception as e:
        st.error(f"API调用错误: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return "无法生成描述，请尝试上传更小的图片或稍后再试。"

def generate_anime_pet(description):
    """使用阿里云百炼API生成动漫风格宠物图片"""
    try:
        # 检查用户配额
        has_quota, remaining = check_user_quota()
        if not has_quota:
            st.error("您今日的图片生成次数已达上限（10次/天）。请明天再来尝试！")
            return False
        
        # 构建请求URL
        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
        
        # 提取宠物品种和特征的关键信息
        pet_features = description.split("。")[0:3]  # 取描述的前几句话作为关键特征
        pet_features_text = "。".join(pet_features)
        
        # 构建更详细的提示词，强调保持原图特征
        prompt = f"""生成一张可爱的动漫风格宠物图片，基于以下描述：{pet_features_text}
        要求：
        1. 必须完全保持与原图宠物相同的姿势、姿态和动作，包括身体朝向、头部角度和四肢位置
        2. 必须精确匹配原图宠物的确切品种和种类
        3. 必须精确匹配原图宠物的毛色、花纹和颜色分布
        4. 必须保持与原图宠物相同的体型比例和特征
        5. 画风可爱、精致，像宫崎骏或迪士尼动画风格
        6. 明亮温暖的色调，细腻的毛发纹理
        7. 大眼睛，表情生动可爱，但表情应与原图相符
        8. 简洁干净的背景，突出宠物形象
        9. 如果原图中有多个宠物，请保持它们之间的相对位置和互动关系
        """
        
        # 构建请求体
        payload = {
            "model": "wanx2.1-t2i-plus",
            "input": {
                "prompt": prompt
            },
            "parameters": {
                "size": "1024*1024",  # 图片尺寸
                "n": 1,  # 生成图片数量
                "negative_prompt": "变形, 错误姿势, 不同姿势, 不同角度, 不同朝向, 错误品种, 错误颜色, 错误花纹, 错误体型, 多余的宠物, 缺少的宠物"  # 负面提示词，避免特征变化
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
                st.info(f"图片生成任务已提交，请耐心等待...")
                
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
                                        # 在Streamlit中显示图片，使用use_container_width替代use_column_width
                                        st.image(image, caption="AI生成的动漫风格宠物", use_container_width=True)
                                        # 增加用户使用次数
                                        increment_user_usage()
                                        # 更新显示的剩余次数
                                        _, remaining = check_user_quota()
                                        st.markdown(f'<div class="quota-info">今日剩余生成次数：{remaining}次（每天10次）</div>', unsafe_allow_html=True)
                                        return True
                            break
                        elif status == "FAILED":
                            st.error(f"图片生成任务失败: {task_result}")
                            return False
                        
                        st.info(f"正在生成图片，请稍候...")
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
                        # 在Streamlit中显示图片，使用use_container_width替代use_column_width
                        st.image(image, caption="AI生成的动漫风格宠物", use_container_width=True)
                        # 增加用户使用次数
                        increment_user_usage()
                        # 更新显示的剩余次数
                        _, remaining = check_user_quota()
                        st.markdown(f'<div class="quota-info">今日剩余生成次数：{remaining}次（每天10次）</div>', unsafe_allow_html=True)
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
    # 设置页面配置
    st.set_page_config(
        page_title="AI宠物描述生成器",
        page_icon="🐾",
        layout="centered",
        initial_sidebar_state="collapsed"
    )
    
    # 自定义CSS样式
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.2rem;
        color: #FF6B6B;
        text-align: center;
        margin-bottom: 1rem;
        font-weight: bold;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #4ECDC4;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
        font-weight: bold;
    }
    .description {
        font-size: 1.1rem;
        color: #555;
        margin-bottom: 1rem;
        text-align: center;
    }
    .info-box {
        background-color: #F8F9FA;
        padding: 1.2rem;
        border-radius: 10px;
        border-left: 5px solid #4ECDC4;
        margin-bottom: 1.5rem;
        margin-top: 0.5rem;
    }
    .result-box {
        background-color: #F8F9FA;
        padding: 1.2rem;
        border-radius: 10px;
        border-left: 5px solid #FF6B6B;
        margin-top: 0.5rem;
        margin-bottom: 1rem;
    }
    .stButton>button {
        background-color: #FF6B6B;
        color: white;
        font-weight: bold;
        border: none;
        border-radius: 5px;
        padding: 0.5rem 1rem;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #FF8E8E;
    }
    .footer {
        text-align: center;
        color: #888;
        font-size: 0.8rem;
        margin-top: 2rem;
    }
    /* 移动端优化 */
    @media (max-width: 768px) {
        .main-header {
            font-size: 1.8rem;
        }
        .sub-header {
            font-size: 1.3rem;
        }
        .description {
            font-size: 1rem;
        }
    }
    /* 打字机效果的光标 */
    .typing-cursor {
        display: inline-block;
        width: 10px;
        height: 20px;
        background-color: #333;
        animation: blink 1s infinite;
    }
    @keyframes blink {
        0% { opacity: 1; }
        50% { opacity: 0; }
        100% { opacity: 1; }
    }
    /* 减少元素间距 */
    .stMarkdown p {
        margin-bottom: 0.5rem;
    }
    div.block-container {
        padding-top: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 页面标题和介绍
    st.markdown('<div class="main-header">🐾 AI宠物描述生成器</div>', unsafe_allow_html=True)
    st.markdown('<div class="description">上传一张宠物的图片，AI将为您生成暖心的描述和可爱的动漫风格图片！</div>', unsafe_allow_html=True)
    
    # 单列垂直布局，适合移动端 - 直接连接标题和上传区域
    st.markdown('<div class="sub-header">📸 上传宠物照片</div><div class="info-box">', unsafe_allow_html=True)
    
    # 文件上传器
    uploaded_file = st.file_uploader("选择一张宠物图片", type=["jpg", "jpeg", "png"], key="pet_image_uploader")
    if not uploaded_file:
        st.markdown("👆 请点击上方区域上传宠物图片")
        st.markdown("支持JPG、JPEG和PNG格式")
    
    # 显示用户配额信息
    has_quota, remaining = check_user_quota()
    st.markdown(f'<div class="quota-info">今日剩余生成次数：{remaining}次（每天10次）</div>', unsafe_allow_html=True)
    
    # 关闭info-box
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 显示上传的图片
    if uploaded_file is not None:
        try:
            image = Image.open(uploaded_file)
            st.image(image, caption="上传的宠物图片", use_container_width=True)
            
            # 生成描述按钮
            if st.button("✨ 生成宠物描述和动漫图片", key="generate_button"):
                # 保存按钮状态
                st.session_state.generate_clicked = True
                
                # 生成描述
                with st.spinner("🔍 正在仔细观察您的宠物..."):
                    # 重新打开文件，因为之前的操作可能已经消耗了文件对象
                    uploaded_file.seek(0)
                    
                    # 显示描述结果标题和框，合并为一个HTML标记
                    st.markdown('<div class="sub-header">🐶 宠物描述</div><div class="result-box">', unsafe_allow_html=True)
                    
                    # 创建一个空的占位符用于流式输出
                    description_placeholder = st.empty()
                    
                    # 流式生成描述
                    description = generate_pet_description_stream(uploaded_file, description_placeholder)
                    
                    # 关闭result-box
                    st.markdown('</div>', unsafe_allow_html=True)
                
                # 生成动漫图片
                with st.spinner("🎨 正在创作动漫风格图片..."):
                    # 合并标题和框为一个HTML标记
                    st.markdown('<div class="sub-header">🎨 动漫风格图片</div><div class="result-box">', unsafe_allow_html=True)
                    success = generate_anime_pet(description)
                    if not success:
                        st.error("未能生成动漫风格图片，请稍后再试")
                    # 关闭result-box
                    st.markdown('</div>', unsafe_allow_html=True)
                
                # 重置按钮
                if st.button("🔄 重新开始", key="reset_button"):
                    st.session_state.generate_clicked = False
                    st.experimental_rerun()
        except Exception as e:
            st.error(f"处理图片时出现错误: {str(e)}")
    
    # 如果已经生成过结果但页面刷新了，重新显示结果
    elif st.session_state.get('generate_clicked', False) and 'last_description' in st.session_state:
        # 合并标题和框为一个HTML标记
        st.markdown('<div class="sub-header">🐶 宠物描述</div><div class="result-box">', unsafe_allow_html=True)
        st.write(st.session_state.last_description)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # 重置按钮
        if st.button("🔄 重新开始", key="reset_button"):
            st.session_state.generate_clicked = False
            if 'last_description' in st.session_state:
                del st.session_state.last_description
            st.experimental_rerun()
    
    # 页脚
    st.markdown('<div class="footer">由AI技术提供支持 | 使用阿里云百炼API</div>', unsafe_allow_html=True)

def generate_pet_description_stream(image_file, placeholder):
    """使用阿里云通义千问API生成宠物描述，并流式输出"""
    try:
        # 将图片转换为base64格式
        base64_image = encode_image_to_base64(image_file)
        
        # 使用OpenAI兼容模式调用API，启用流式输出
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
            ],
            stream=True  # 启用流式输出
        )
        
        # 用于累积完整的描述
        full_description = ""
        displayed_text = ""
        
        # 逐步处理流式响应
        for chunk in completion:
            if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content is not None:
                # 获取当前块的内容
                content = chunk.choices[0].delta.content
                
                # 累积完整描述
                full_description += content
                
                # 模拟打字效果，每次显示更多的文本
                displayed_text += content
                
                # 更新显示
                placeholder.markdown(displayed_text + "▌", unsafe_allow_html=True)
                
                # 控制显示速度
                time.sleep(0.03)  # 可以调整这个值来控制"打字"速度
        
        # 最终显示完整文本（不带光标）
        placeholder.markdown(full_description, unsafe_allow_html=True)
        
        # 保存到session_state以便页面刷新后恢复
        st.session_state.last_description = full_description
        
        return full_description
            
    except Exception as e:
        error_msg = f"API调用错误: {str(e)}"
        placeholder.error(error_msg)
        import traceback
        st.error(traceback.format_exc())
        return "无法生成描述，请尝试上传更小的图片或稍后再试。"

def check_user_quota():
    """检查用户是否还有剩余配额"""
    user_id = get_user_id()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # 初始化用户配额跟踪
    if 'user_quotas' not in st.session_state:
        st.session_state.user_quotas = {}
    
    # 初始化今天的用户配额
    if today not in st.session_state.user_quotas:
        st.session_state.user_quotas[today] = {}
    
    # 初始化特定用户的配额
    if user_id not in st.session_state.user_quotas[today]:
        st.session_state.user_quotas[today][user_id] = 0
    
    # 检查是否超过限制 (10次/天)
    if st.session_state.user_quotas[today][user_id] >= 10:
        return False, 10 - st.session_state.user_quotas[today][user_id]
    
    return True, 10 - st.session_state.user_quotas[today][user_id]

def get_user_id():
    """获取用户唯一标识，使用会话ID作为简单实现"""
    # 使用会话状态存储用户ID，避免使用可能被浏览器阻止的外部API
    if 'user_id' not in st.session_state:
        # 生成一个基于时间的随机ID
        today = datetime.datetime.now().strftime("%Y%m%d")
        random_id = str(uuid.uuid4())[:8]
        st.session_state.user_id = f"{today}-{random_id}"
    
    return st.session_state.user_id

def increment_user_usage():
    """增加用户使用次数"""
    user_id = get_user_id()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # 检查用户配额
    has_quota, remaining = check_user_quota()
    if has_quota:
        # 增加用户使用次数
        st.session_state.user_quotas[today][user_id] += 1

if __name__ == "__main__":
    # 初始化session_state
    if 'generate_clicked' not in st.session_state:
        st.session_state.generate_clicked = False
    
    main()