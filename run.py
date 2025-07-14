"""
This script provides access to both CLI and web interfaces.
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path


def run_streamlit():
    """Launch the Streamlit web application."""
    print("🌟 Starting UK Renewable Energy Dashboard...")
    print("📊 Web interface will open in your browser")
    print("🛑 Press Ctrl+C to stop the application")
    print("-" * 50)
    
    try:
        script_dir = Path(__file__).parent
        streamlit_app = script_dir / "streamlit_app.py"
        
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            str(streamlit_app),
            "--server.port", "8501",
            "--server.headless", "false",
            "--browser.gatherUsageStats", "false"
        ])
    except KeyboardInterrupt:
        print("\n👋 Dashboard stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error starting Streamlit: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


def run_cli(*args):
    """Launch the CLI version."""
    print("🖥️  Starting CLI interface...")
    try:
        script_dir = Path(__file__).parent
        main_script = script_dir / "main.py"
        subprocess.run([sys.executable, str(main_script)] + list(args))
    except Exception as e:
        print(f"❌ Error starting CLI: {e}")
        sys.exit(1)


def install_dependencies():
    print("📦 Installing dependencies...")
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ], check=True)
        print("✅ Dependencies installed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing dependencies: {e}")
        sys.exit(1)


def check_dependencies():
    required_packages = {
        'streamlit': 'streamlit',
        'pandas': 'pandas', 
        'matplotlib': 'matplotlib',
        'plotly': 'plotly',
        'requests': 'requests',
        'python-dotenv': 'dotenv'
    }
    
    missing_packages = []
    for package_name, import_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(package_name)
    
    if missing_packages:
        print(f"⚠️  Missing packages: {', '.join(missing_packages)}")
        print("💡 Run: python run.py --install-deps")
        return False
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="UK Renewable Energy Dashboard Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py                           # Launch Streamlit web interface
  python run.py --web                     # Launch Streamlit web interface
  python run.py --cli                     # Launch CLI interface
  python run.py --cli fetch-year 2023     # Run CLI command
  python run.py --install-deps            # Install dependencies
  python run.py --check-deps              # Check dependencies
        """
    )
    
    parser.add_argument('--web', action='store_true', 
                       help='Launch Streamlit web interface (default)')
    parser.add_argument('--cli', action='store_true',
                       help='Launch CLI interface')
    parser.add_argument('--install-deps', action='store_true',
                       help='Install required dependencies')
    parser.add_argument('--check-deps', action='store_true',
                       help='Check if dependencies are installed')
    
    # Parse known args to allow passing through to CLI
    args, unknown = parser.parse_known_args()
    
    print("🌟 UK Renewable Energy Dashboard")
    print("=" * 50)
    
    if args.install_deps:
        install_dependencies()
        return
    
    if args.check_deps:
        if check_dependencies():
            print("✅ All dependencies are installed!")
        return
    
    if not check_dependencies():
        return
    
    if args.cli:
        run_cli(*unknown)
    else:
        if unknown:
            print("⚠️  Extra arguments ignored in web mode:", unknown)
        run_streamlit()


if __name__ == "__main__":
    main()
