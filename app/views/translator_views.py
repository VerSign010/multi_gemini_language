# app/views/translator_views.py
from flask import Blueprint, render_template, request, jsonify
import google.generativeai as genai
import logging

translator_bp = Blueprint('translator', __name__)

@translator_bp.route('/translator')
def translator_page():
    languages = {"自动检测": "auto", "中文 (简体)": "Chinese (Simplified)", "英文": "English", "德文": "German"}
    styles = {"默认 (平衡)": "default", "正式书面": "formal", "口语化": "colloquial"}
    return render_template('translator.html', languages=languages, styles=styles)

@translator_bp.route('/translate_text', methods=['POST'])
def translate_text():
    try:
        data = request.get_json()
        text = data.get('text')
        source_lang = data.get('source_lang', 'auto')
        target_lang = data.get('target_lang', 'Chinese (Simplified)')
        style = data.get('style', 'default')
        model_name = data.get('model_name', 'gemini-2.5-pro')
        prompt = f"Translate the following text from {source_lang} to {target_lang}. Style: {style}.\n\nText: {text}"
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return jsonify({'result1': response.text, 'result2': ''})
    except Exception as e:
        logging.error(f"/translate_text 错误: {e}")
        return jsonify({'error': str(e)}), 500