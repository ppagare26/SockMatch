@echo off
echo 🚀 Activating environment...
:: You must activate your virtual environment manually before running this script.

echo 🧹 Uninstalling any previously installed packages...
pip uninstall -y numpy rembg opencv-python-headless scikit-learn pillow fastapi uvicorn python-multipart onnxruntime

echo 📦 Installing packages from requirements.txt...
pip install -r requirements.txt

echo 🔁 Forcing reinstallation of compiled packages with NumPy 1.26.4...
pip install --force-reinstall numpy==1.26.4
pip install --force-reinstall rembg opencv-python-headless scikit-learn pillow onnxruntime

echo ✅ Verifying installed versions...
python -c "import numpy; print('NumPy version:', numpy.__version__)"
python -c "import rembg; print('rembg OK')"
python -c "import cv2; print('OpenCV OK')"
python -c "import onnxruntime; print('onnxruntime OK')"

echo 🎉 Setup complete!
pause
