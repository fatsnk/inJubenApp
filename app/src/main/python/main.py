import os
import sys

# 将当前目录添加到 sys.path，以便能够导入 in_juben
sys.path.append(os.path.dirname(os.path.realpath(__file__)))

def main(fonts_path=None):
    """
    Chaquopy 的入口点。
    这个函数将在一个后台线程中被调用，以启动 Flask 服务器。
    """
    # 如果从安卓端传递了字体路径，则设置到环境变量中
    if fonts_path:
        os.environ['INJUBEN_FONTS_PATH'] = fonts_path

    # 在设置环境变量之后再导入 app
    from in_juben import app

    # 在本地主机上运行 Flask 应用
    # 端口可以根据需要更改
    app.run(host='0.0.0.0', port=5021)

# 如果直接运行此脚本，也启动服务器（用于测试）
if __name__ == '__main__':
    main()