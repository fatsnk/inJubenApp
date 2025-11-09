import base64
import tempfile
import os
import json

from cachelib import SimpleCache
from flask import make_response
from flask import Flask, render_template, request, jsonify
from functools import wraps
from io import StringIO
from screenplain.parsers import fountain
from screenplain.export.pdf import to_pdf as to_en_pdf

from juben import normalize
from juben.pdf import to_pdf

# 获取当前脚本所在的目录
# 在 Chaquopy 环境中，这应该是 `app/src/main/python`
current_dir = os.path.dirname(os.path.realpath(__file__))

# 指定模板和静态文件夹的绝对路径
template_folder = os.path.join(current_dir, 'templates')
static_folder = os.path.join(current_dir, 'static')
files_folder = os.path.join(current_dir, 'fountain_files')

# 确保用于存储文件的文件夹存在
os.makedirs(files_folder, exist_ok=True)

app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 512
cache = SimpleCache()

def cached(timeout=0):
    def decorator(route):
        @wraps(route)
        def decorated_method(*args, **kwargs):
            key = 'route_{}'.format(request.path)
            value = cache.get(key)
            if value is None:
                value = route(*args, **kwargs)
                cache.set(key, value, timeout=timeout)
            return value
        return decorated_method
    return decorator

@app.route('/', methods=['GET'])
@cached()
def index():
    return render_template('zh.html', LANG='zh', EN_URL='/en')

@app.route('/en', methods=['GET'])
@cached()
def en():
    return render_template('en.html', LANG='en', ZH_URL='/')

@app.route('/quick_start', methods=['GET'])
@cached()
def quick_start():
    return render_template('zh_quick_start.html', LANG='zh', ZH_URL='/')

@app.route('/examples/<path:path>')
@cached()
def examples(path):
    example_file = os.path.join(app.root_path, 'examples', path)
    f = open(example_file, mode="r", encoding="utf-8")
    r = make_response(f.read())
    f.close()
    r.headers['Content-Type'] = 'text/plain; charset=UTF-8'
    return r

@app.route('/preview', methods=['GET'])
def preview_get():
    return render_template('fountain_preview.html')

@app.route('/preview', methods=['POST'])
def preview():
    input = StringIO(request.form.get('in-juben-text'))
    has_scene_num = bool(request.form.get('in-has-scene-num'))
    first_page_number = bool(request.form.get('in-first-page-num'))
    strong_scene_heading = bool(request.form.get('in-strong-scene-heading'))
    first_line_indent = bool(request.form.get('in-first-line-indent'))
    in_lang = request.form.get('in-lang')
    tmp_file = tempfile.SpooledTemporaryFile()
    suffix = "pdf"
    try:
        if in_lang == 'zh':
            input = normalize.parse(input, first_line_indent)
        filename = input.readline().replace("Title:", '').strip()
        input.seek(0)
        screenplay = fountain.parse(input)
        if in_lang == 'zh':
            to_pdf(screenplay, tmp_file._file, is_strong=strong_scene_heading, has_scene_num=has_scene_num, first_page_number=first_page_number, first_line_indent=first_line_indent)
        else:
            to_en_pdf(screenplay, tmp_file._file, is_strong=strong_scene_heading)
        tmp_file.seek(0)
        encoded_string = base64.b64encode(tmp_file.read()).decode('ascii')
        r = make_response('{"filename":"' + filename + '", "suffix":"' + suffix + '", "content":"' + encoded_string + '"}')
        r.headers['Content-Type'] = 'text/plain; charset=UTF-8'
        return r
    except:
        return locales().get('_')('Invalid Format'), 500
    finally:
        if tmp_file:
           tmp_file.close()

@app.context_processor
def locales():
    def _(text):
        if  'en' not in request.url_rule.rule:
            lang = {'Small':'小','Medium':'中','Large':'大', 'Dark Mode':'夜间模式','Active Line':'高亮当前行',
                    'Quick Start':'新手指南','Help':'使用帮助','FAQ':'常见问题','About inJuBen':'关于 in剧本','Save AS TXT':'另存为TXT','Word Count':'字数',
                    'Refresh Preview':'刷新预览','Preview Settings':'预览设置',
                    'Scene Number':'生成场景序号','Strong Scene Heading':'加粗场景标题','First Page Number':'生成首页页码','First Line Indent':'首行缩进',
                    'Download PDF':'下载PDF','Invalid Format':'输入内容格式有误或服务器失去响应，请修改后重试'}
        else:
            lang = {'About inJuBen':'About in剧本(jù běn)'}
        if text in lang:
            return lang.get(text)
        else:
            return text
    return dict(_=_)
        


# ===============================================
# ===== 文件操作 API
# ===============================================

@app.route('/api/files', methods=['GET'])
def list_files():
    """获取所有 .fountain 文件的列表"""
    try:
        files = [f for f in os.listdir(files_folder) if f.endswith('.fountain')]
        return jsonify(sorted(files))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/files/<filename>', methods=['GET'])
def get_file(filename):
    """获取特定文件的内容"""
    try:
        filepath = os.path.join(files_folder, filename)
        if not os.path.exists(filepath):
            return jsonify({"error": "File not found"}), 404
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({"filename": filename, "content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/files/<filename>', methods=['POST'])
def save_file(filename):
    """保存或创建一个新文件"""
    try:
        filepath = os.path.join(files_folder, filename)
        data = request.get_json()
        content = data.get('content', '')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({"success": True, "message": f"File '{filename}' saved."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/files/<old_filename>', methods=['PUT'])
def rename_file(old_filename):
    """重命名一个文件"""
    try:
        data = request.get_json()
        new_filename = data.get('new_filename')

        if not new_filename:
            return jsonify({"error": "New filename not provided"}), 400

        old_filepath = os.path.join(files_folder, old_filename)
        new_filepath = os.path.join(files_folder, new_filename)

        if not os.path.exists(old_filepath):
            return jsonify({"error": "File not found"}), 404
        
        if os.path.exists(new_filepath):
            return jsonify({"error": "New filename already exists"}), 409

        os.rename(old_filepath, new_filepath)
        return jsonify({"success": True, "message": f"File renamed to '{new_filename}'."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/files/<filename>', methods=['DELETE'])
def delete_file(filename):
    """删除一个文件"""
    try:
        filepath = os.path.join(files_folder, filename)
        if not os.path.exists(filepath):
            return jsonify({"error": "File not found"}), 404
        
        os.remove(filepath)
        return jsonify({"success": True, "message": f"File '{filename}' deleted."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
