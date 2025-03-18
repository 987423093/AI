import os
from openai import OpenAI
import streamlit as st
from PIL import Image
import io
import base64

# 初始化 DeepSeek 客户端
client = OpenAI(
    api_key="sk-4e1900deadb04c2ba81718cca8616f16",  # 直接设置API密钥
    base_url="https://api.deepseek.com/v1"
)

def encode_image_to_base64(image):
    if isinstance(image, Image.Image):
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        image_bytes = buffered.getvalue()
    else:
        image_bytes = image.read()
    return base64.b64encode(image_bytes).decode('utf-8')

def generate_pet_description(image):
    # 将图片转换为 base64 格式
    base64_image = encode_image_to_base64(image)
    
    # 调用 DeepSeek Vision API
    response = client.chat.completions.create(
        model="deepseek-vision",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "请详细描述这只宠物的特征，包括：品种、毛色、体型特征、精神状态等。请用通俗易懂的语言描述，语气要温暖友好。"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        max_tokens=500
    )
    
    return response.choices[0].message.content

# Streamlit 界面
def main():
    st.title("🐾 AI宠物描述生成器")
    st.write("上传一张宠物的图片，AI 将为您生成暖心的描述！")
    
    uploaded_file = st.file_uploader("选择一张宠物图片", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        # 显示上传的图片
        image = Image.open(uploaded_file)
        st.image(image, caption="上传的宠物图片", use_column_width=True)
        
        # 生成描述按钮
        if st.button("✨ 生成描述"):
            with st.spinner("正在仔细观察您的宠物..."):
                try:
                    description = generate_pet_description(uploaded_file)
                    st.write("### 🌟 宠物描述")
                    st.write(description)
                except Exception as e:
                    st.error(f"生成描述时出现错误: {str(e)}")

if __name__ == "__main__":
    main()