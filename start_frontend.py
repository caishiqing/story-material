#!/usr/bin/env python3
"""
Simple HTTP server for the Audio Management System frontend
"""

import os
import sys
import webbrowser
import subprocess
from pathlib import Path
import time
import requests


def check_backend():
    """Check if backend is running"""
    try:
        response = requests.get('http://localhost:8000/health', timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'healthy':
                print("✅ 后端服务运行正常")
                return True
    except:
        pass

    print("⚠️  后端服务未运行，请先启动后端服务：")
    print("   python server.py")
    return False


def start_server(port=8080):
    """Start a simple HTTP server for the frontend"""
    frontend_dir = Path(__file__).parent / 'frontend'

    if not frontend_dir.exists():
        print("❌ frontend 目录不存在")
        return False

    print(f"🚀 启动前端服务器在端口 {port}...")
    print(f"📁 服务目录: {frontend_dir}")

    # Change to frontend directory
    os.chdir(frontend_dir)

    try:
        # Try to start server using Python's built-in HTTP server
        if sys.version_info >= (3, 7):
            # Python 3.7+
            subprocess.run([
                sys.executable, '-m', 'http.server', str(port),
                '--bind', 'localhost'
            ])
        else:
            # Python < 3.7
            subprocess.run([
                sys.executable, '-m', 'http.server', str(port)
            ])
    except KeyboardInterrupt:
        print("\n⏹️  服务器已停止")
    except FileNotFoundError:
        print("❌ Python HTTP 服务器启动失败")
        return False

    return True


def main():
    """Main function"""
    print("=" * 50)
    print("🎵 音效素材管理系统")
    print("=" * 50)

    # Check if we're in the right directory
    if not Path('frontend').exists():
        print("❌ 请在项目根目录运行此脚本")
        sys.exit(1)

    # Check backend status
    backend_ok = check_backend()
    if not backend_ok:
        choice = input("\n是否继续启动前端？(y/N): ").strip().lower()
        if choice not in ['y', 'yes']:
            print("退出...")
            sys.exit(0)

    # Parse command line arguments
    port = 8080
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"❌ 无效端口号: {sys.argv[1]}")
            sys.exit(1)

    print(f"\n📱 前端服务将启动在: http://localhost:{port}")
    print("📋 启动后将自动打开浏览器")
    print("🔴 按 Ctrl+C 停止服务器")

    # Start server in a separate process and open browser
    try:
        # Open browser after a short delay
        def open_browser():
            time.sleep(2)  # Wait for server to start
            webbrowser.open(f'http://localhost:{port}/demo.html')

        import threading
        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()

        # Start server (this will block)
        start_server(port)

    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
