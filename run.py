# run.py
from app import create_app

app = create_app()

if __name__ == '__main__':
    # host='0.0.0.0' 允许网络中的其他设备访问
    # debug=True 开启调试模式，修改代码后服务会自动重启
    app.run(host='0.0.0.0', port=5000, debug=True)