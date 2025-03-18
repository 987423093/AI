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
import re

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

def generate_anime_pet(description, style="宫崎骏"):
    """使用阿里云百炼API生成动漫风格宠物图片"""
    try:
        # 检查用户配额
        has_quota, remaining = check_user_quota()
        if not has_quota:
            st.error("您今日的图片生成次数已达上限（10次/天）。请明天再来尝试！")
            return False
        
        # 构建请求URL
        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
        
        # 使用完整描述作为关键特征
        pet_features_text = description  # 使用全部描述，而不是只取前几句
        
        # 尝试从描述中提取品种和颜色信息
        
        # 提取品种信息
        breed_match = re.search(r'这是一只(.*?)(?:犬|猫|兔|鸟|鹦鹉|仓鼠|豚鼠|蜥蜴|龟|鱼)', description)
        breed = breed_match.group(1) + breed_match.group(2) if breed_match else ""
        
        # 提取颜色信息
        color_match = re.search(r'(黑|白|灰|棕|黄|橙|红|蓝|绿|米|奶油|金|银|褐|咖啡|巧克力|双色|三色|多色)(色|毛)', description)
        color = color_match.group(1) if color_match else ""
        
        # 根据选择的风格构建提示词
        style_prompts = {
            "宫崎骏": f"""生成一张高质量的宫崎骏风格宠物图片，必须严格遵循以下要求：
            
            1. 宠物品种：必须是{breed if breed else "与原图完全相同的品种"}，不得更改或混合其他品种特征
            2. 毛色和花纹：必须是{color if color else "与原图完全相同的颜色"}，包括所有花纹、斑点和颜色分布
            3. 姿势和姿态：必须与原图中的宠物保持完全相同的姿势、动作和身体朝向
            4. 宫崎骏风格：温暖柔和的色调，圆润的线条，富有表现力的大眼睛，细腻的毛发纹理
            5. 艺术特点：类似《龙猫》《千与千寻》《哈尔的移动城堡》的温馨画风，手绘质感
            6. 光影效果：柔和的自然光线，温暖的色彩过渡，轻微的水彩晕染效果
            7. 背景：简洁温馨的自然环境，如草地、森林或温暖的室内场景，带有宫崎骏电影中常见的自然元素
            8. 表情：保持宠物原有表情的同时，增添一丝灵动和温暖感
            """,
            
            "迪士尼": f"""生成一张高质量的迪士尼动画风格宠物图片，必须严格遵循以下要求：
            
            1. 宠物品种：必须是{breed if breed else "与原图完全相同的品种"}，不得更改或混合其他品种特征
            2. 毛色和花纹：必须是{color if color else "与原图完全相同的颜色"}，包括所有花纹、斑点和颜色分布
            3. 姿势和姿态：必须与原图中的宠物保持完全相同的姿势、动作和身体朝向
            4. 迪士尼风格：明亮饱和的色彩，圆润流畅的线条，夸张的表情，大而有神的眼睛
            5. 艺术特点：类似《疯狂动物城》《狮子王》的现代迪士尼风格，精细的毛发渲染，生动的表情
            6. 光影效果：明亮的光线，清晰的阴影，强调立体感的渲染
            7. 背景：简洁明亮的背景，可能包含迪士尼风格的装饰元素
            8. 表情：保持宠物原有表情的基础上，增添迪士尼角色般的生动表现力
            """,
            
            "皮克斯": f"""生成一张高质量的皮克斯3D动画风格宠物图片，必须严格遵循以下要求：
            
            1. 宠物品种：必须是{breed if breed else "与原图完全相同的品种"}，不得更改或混合其他品种特征
            2. 毛色和花纹：必须是{color if color else "与原图完全相同的颜色"}，包括所有花纹、斑点和颜色分布
            3. 姿势和姿态：必须与原图中的宠物保持完全相同的姿势、动作和身体朝向
            4. 皮克斯风格：3D渲染效果，细腻的质感，逼真但略带卡通感的形象
            5. 艺术特点：类似《玩具总动员》《寻梦环游记》《心灵奇旅》的精细3D建模风格
            6. 光影效果：精细的光影处理，柔和的环境光，细腻的材质反射
            7. 背景：简洁但有深度的背景，可能包含皮克斯风格的环境元素
            8. 表情：保持宠物原有表情的基础上，增添皮克斯角色般的情感表现力
            """,
            
            "水彩画": f"""生成一张高质量的水彩画风格宠物图片，必须严格遵循以下要求：
            
            1. 宠物品种：必须是{breed if breed else "与原图完全相同的品种"}，不得更改或混合其他品种特征
            2. 毛色和花纹：必须是{color if color else "与原图完全相同的颜色"}，包括所有花纹、斑点和颜色分布
            3. 姿势和姿态：必须与原图中的宠物保持完全相同的姿势、动作和身体朝向
            4. 水彩画风格：柔和的色彩融合，轻微的水彩晕染效果，透明感的层次
            5. 艺术特点：手绘质感，自然的色彩过渡，轻柔的笔触，略带模糊的边缘
            6. 光影效果：柔和的光线表现，淡雅的色调，轻微的水彩纸肌理
            7. 背景：简约的水彩背景，可能有轻微的水渍效果或留白
            8. 表情：保持宠物原有表情，通过水彩的柔和特性表现宠物的温柔气质
            """,
            
            "像素艺术": f"""生成一张高质量的像素艺术风格宠物图片，必须严格遵循以下要求：
            
            1. 宠物品种：必须是{breed if breed else "与原图完全相同的品种"}，不得更改或混合其他品种特征
            2. 毛色和花纹：必须是{color if color else "与原图完全相同的颜色"}，包括所有花纹、斑点和颜色分布
            3. 姿势和姿态：必须与原图中的宠物保持完全相同的姿势、动作和身体朝向
            4. 像素艺术风格：清晰可见的像素方块，有限的色彩调色板，复古游戏风格
            5. 艺术特点：类似16位或32位游戏时代的像素艺术，方块化的形象，简化但辨识度高的细节
            6. 光影效果：简化的阴影表现，有限的色阶过渡，点阵化的高光
            7. 背景：简单的像素艺术背景，可能包含复古游戏元素
            8. 表情：通过最少的像素点表达宠物的表情和性格
            """
        }
        
        # 获取选定风格的提示词
        prompt = style_prompts.get(style, style_prompts["宫崎骏"])
        
        # 添加通用结尾
        prompt += f"""
        
        原图宠物完整描述：{pet_features_text}
        
        重要提示：这是一个{style}风格改造任务，但必须保持宠物的品种、颜色和关键特征完全一致，让原宠物主人能一眼认出自己的宠物。
        """
        
        # 构建请求体
        payload = {
            "model": "wanx2.1-t2i-turbo",
            "input": {
                "prompt": prompt
            },
            "parameters": {
                "size": "1024*1024",  # 图片尺寸
                "n": 1,  # 生成图片数量
                "negative_prompt": "变形, 错误姿势, 不同姿势, 不同角度, 不同朝向, 错误品种, 错误颜色, 错误花纹, 错误体型, 多余的宠物, 缺少的宠物, 品种混合, 品种变化, 颜色变化, 不同品种, 过度卡通化, 过度简化, 科幻元素, 机械部件, 不自然的颜色"  # 负面提示词
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
                                        st.image(image, caption=f"AI生成的{style}风格宠物", use_container_width=True)
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
                        st.image(image, caption=f"AI生成的{style}风格宠物", use_container_width=True)
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
        page_title="宠物动漫形象生成器",
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
    .quota-info {
        text-align: center;
        background-color: #F0F8FF;
        padding: 0.5rem;
        border-radius: 5px;
        margin-bottom: 1rem;
        font-size: 0.9rem;
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
    
    /* 修改文件上传器样式 */
    .stFileUploader > div > div {
        border: none !important;
        box-shadow: none !important;
    }
    
    .stFileUploader > div > div > span {
        display: none !important;
    }
    
    .stFileUploader > div {
        padding: 0 !important;
        background-color: transparent !important;
    }
    
    /* 隐藏左侧括号 */
    .stFileUploader > div > div::before {
        content: none !important;
    }
    
    /* 上传按钮样式 */
    .stFileUploader label[data-testid="stFileUploadDropzone"] {
        background-color: #f8f9fa;
        border: 2px dashed #4ECDC4 !important;
        border-radius: 10px;
        padding: 20px !important;
    }
    
    .stFileUploader label[data-testid="stFileUploadDropzone"]:hover {
        background-color: #f0f8ff;
        border-color: #FF6B6B !important;
    }
    
    /* 移除所有元素的红框和左侧括号 */
    div.element-container {
        border: none !important;
    }
    
    div.element-container::before {
        content: none !important;
    }
    
    /* 移除图片容器的边框和括号 */
    div.stImage {
        border: none !important;
        box-shadow: none !important;
    }
    
    div.stImage::before {
        content: none !important;
    }
    
    /* 移除所有可能的括号和边框 */
    div[data-testid="stVerticalBlock"] > div::before {
        content: none !important;
    }
    
    div[data-testid="stVerticalBlock"] > div {
        border: none !important;
        box-shadow: none !important;
    }
    
    /* 移除结果区域的边框 */
    .result-box {
        border: none !important;
        border-left: 5px solid #FF6B6B !important;
    }
    
    /* 移除文本区域的边框和括号 */
    .stTextArea > div {
        border: none !important;
        box-shadow: none !important;
    }
    
    .stTextArea > div::before {
        content: none !important;
    }
    
    /* 移除所有可能的文本输入区域的边框和括号 */
    [data-testid="stText"], 
    [data-testid="stMarkdown"],
    textarea,
    .stTextInput > div,
    .stTextInput > div > div {
        border: none !important;
        box-shadow: none !important;
    }
    
    [data-testid="stText"]::before, 
    [data-testid="stMarkdown"]::before,
    textarea::before,
    .stTextInput > div::before,
    .stTextInput > div > div::before {
        content: none !important;
    }
    
    /* 确保所有文本区域没有边框和括号 */
    div[data-baseweb="textarea"] {
        border: none !important;
        box-shadow: none !important;
    }
    
    div[data-baseweb="textarea"]::before {
        content: none !important;
    }
    
    /* 风格选择器样式 */
    .style-selector {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-bottom: 1rem;
    }
    
    .style-option {
        flex: 1;
        min-width: 100px;
        text-align: center;
        padding: 10px;
        border: 2px solid #e0e0e0;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.3s;
    }
    
    .style-option:hover {
        border-color: #4ECDC4;
        background-color: #f0f8ff;
    }
    
    .style-option.selected {
        border-color: #FF6B6B;
        background-color: #fff0f0;
    }
    
    .style-option img {
        width: 100%;
        height: 80px;
        object-fit: cover;
        border-radius: 5px;
        margin-bottom: 5px;
    }
    
    .style-option p {
        margin: 0;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 页面标题和介绍
    st.markdown('<div class="main-header">🐾 萌宠动漫形象生成器</div>', unsafe_allow_html=True)
    st.markdown('<div class="description">上传一张宠物照片，立即获得可爱的动漫风格形象和暖心描述！</div>', unsafe_allow_html=True)
    
    # 显示用户配额信息
    has_quota, remaining = check_user_quota()
    st.markdown(f'<div class="quota-info">今日剩余生成次数：{remaining}次（每天10次）</div>', unsafe_allow_html=True)
    
    # 单列垂直布局，适合移动端 - 直接连接标题和上传区域
    st.markdown('<div class="sub-header">📸 上传宠物照片</div>', unsafe_allow_html=True)
    
    # 文件上传器 - 不再使用info-box包装
    uploaded_file = st.file_uploader("选择一张宠物图片", type=["jpg", "jpeg", "png"], key="pet_image_uploader")
    if not uploaded_file:
        st.markdown("👆 请点击上方区域上传宠物图片")
        st.markdown("支持JPG、JPEG和PNG格式")
    
    # 显示上传的图片
    if uploaded_file is not None:
        try:
            image = Image.open(uploaded_file)
            st.image(image, caption="上传的宠物图片", use_container_width=True)
            
            # 添加风格选择
            st.markdown('<div class="sub-header">🎨 选择动漫风格</div>', unsafe_allow_html=True)
            
            # 定义可用的风格选项
            styles = ["宫崎骏", "迪士尼", "皮克斯", "水彩画", "像素艺术"]
            
            # 使用session_state存储选择的风格
            if 'selected_style' not in st.session_state:
                st.session_state.selected_style = styles[0]  # 默认选择宫崎骏风格
            
            # 创建风格选择器
            cols = st.columns(len(styles))
            for i, style in enumerate(styles):
                with cols[i]:
                    # 使用按钮来选择风格
                    if st.button(style, key=f"style_{style}"):
                        st.session_state.selected_style = style
            
            # 显示当前选择的风格
            st.markdown(f"<p style='text-align:center; margin-top:10px;'>当前选择: <b>{st.session_state.selected_style}</b></p>", unsafe_allow_html=True)
            
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
                with st.spinner(f"🎨 正在创作{st.session_state.selected_style}风格图片..."):
                    # 显示标题，但不使用result-box包装
                    st.markdown(f'<div class="sub-header">🎨 {st.session_state.selected_style}风格图片</div>', unsafe_allow_html=True)
                    success = generate_anime_pet(description, st.session_state.selected_style)
                    if not success:
                        st.error(f"未能生成{st.session_state.selected_style}风格图片，请稍后再试")
                
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

def analyze_pet_image(image_bytes):
    """使用千问VL模型分析宠物图片"""
    try:
        import os
        import base64
        from openai import OpenAI
        
        # 将图片转换为base64编码
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        # 初始化OpenAI客户端（使用百炼兼容模式）
        client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        
        # 构建提示词
        prompt = """请详细分析这张宠物照片，包括：
        1. 宠物的品种、颜色、体型特征
        2. 宠物的姿势、表情和可能的情绪状态
        3. 宠物的特殊标记或独特特征
        4. 宠物的毛发特点、长度和质地
        
        请用温暖亲切的语言，以"这是一只..."开头，描述这只宠物，就像在向一个爱宠人士介绍这只可爱的动物。
        描述要详细生动，突出这只宠物的独特之处，长度在150-200字之间。
        不要提及照片质量、背景环境或人类。只关注宠物本身。"""
        
        # 发送请求
        completion = client.chat.completions.create(
            model="qwen-vl-plus",  # 使用千问VL模型
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }]
        )
        
        # 提取回复内容
        description = completion.choices[0].message.content
        
        # 保存描述到会话状态
        st.session_state.description = description
        
        return description
    
    except Exception as e:
        st.error(f"分析图片时出错: {str(e)}")
        return None

if __name__ == "__main__":
    # 初始化session_state
    if 'generate_clicked' not in st.session_state:
        st.session_state.generate_clicked = False
    
    main()