# run.py
import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    # 从环境变量中获取端口，为本地运行提供灵活性
    port = int(os.environ.get('PORT', 5000))
    
    # 在本地直接运行时，debug 模式可以从环境变量控制
    # 例如，在 .env 文件中设置 DEBUG=True
    # 默认情况下，为了安全，debug 应为 False
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() in ['true', '1', 't']
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)