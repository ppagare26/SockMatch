import colorsys
import cv2
import numpy as np
from typing import Dict, List,Optional
from sklearn.cluster import KMeans
from concurrent.futures import ThreadPoolExecutor
import os
from ultralytics import YOLO
from PIL import Image
from rembg import remove

# Initialize YOLO model (keep your existing model loading code)
script_dir = os.path.dirname(os.path.abspath(__file__))
yolo_model_path = os.path.abspath(os.path.join(script_dir, "..", "..", "model", "model.pt"))
yolo_model = YOLO(yolo_model_path)


def detect_and_process_shoe(image_path: str, confidence_threshold: float = 0.5) -> Optional[np.ndarray]:
    """Detects shoes and returns processed RGBA image without saving"""
    print("🔍 Detecting shoes...")

    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"❌ Image not found: {image_path}")

    results = yolo_model(image)
    detections = results[0].boxes
    detections = [d for d in detections if d.conf >= confidence_threshold]

    if not detections:
        raise ValueError("❌ No shoes detected in the image.")

    for detection in detections:
        x1, y1, x2, y2 = map(int, detection.xyxy[0])
        cropped = image[y1:y2, x1:x2]

        if cropped.size == 0:
            continue

        # Process and remove background
        shoe_pil = Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
        shoe_no_bg = remove(shoe_pil)  # RGBA image

        # Convert to numpy and verify content
        rgba = np.array(shoe_no_bg)
        if np.any(rgba[:, :, 3] > 0):  # Check if has visible pixels
            print("✅ Successfully processed shoe")
            return rgba

    raise ValueError("❌ No valid shoes were processed.")

def extract_shoe_attributes(rgba_array: np.ndarray, num_colors: int = 3) -> Dict[str, any]:
    """
    Analyze shoe attributes in parallel:
    - Colors (with improved clustering)
    - Height (based on aspect ratio)
    - Design (pattern detection)
    Returns: {'colors': [], 'height': str, 'design': str, 'error': Optional[str]}
    """
    result = {
        "colors": [],
        "height": "unknown",
        "design": "unknown",
        "error": None
    }

    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all analysis tasks in parallel
            color_future = executor.submit(
                extract_colors,
                rgba_array,
                num_colors
            )
            height_future = executor.submit(
                calculate_height,
                rgba_array
            )
            design_future = executor.submit(
                detect_design,
                rgba_array
            )

            # Get results
            result["colors"] = color_future.result()
            result["height"] = height_future.result()
            result["design"] = design_future.result()

    except Exception as e:
        result["error"] = str(e)

    return result


def extract_colors(rgba_array: np.ndarray, num_colors: int) -> List[str]:
    """Improved color extraction with LAB space clustering"""
    try:
        # Extract only opaque pixels
        alpha = rgba_array[:, :, 3]
        rgb_pixels = rgba_array[alpha > 0][:, :3]

        if len(rgb_pixels) < 10:
            return ["unknown"]

        # White balance correction
        def auto_white_balance(img):
            lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
            avg_a = np.mean(lab[:, :, 1])
            avg_b = np.mean(lab[:, :, 2])
            lab[:, :, 1] = lab[:, :, 1] - ((avg_a - 128) * (lab[:, :, 0] / 255.0) * 1.1)
            lab[:, :, 2] = lab[:, :, 2] - ((avg_b - 128) * (lab[:, :, 0] / 255.0) * 1.1)
            return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

        balanced = auto_white_balance(rgb_pixels.reshape(1, -1, 3)).reshape(-1, 3)

        # Convert to HSV for clustering
        hsv = cv2.cvtColor(balanced.reshape(1, -1, 3), cv2.COLOR_RGB2HSV).reshape(-1, 3)
        kmeans = KMeans(n_clusters=num_colors, n_init=20)
        kmeans.fit(hsv)

        # Process clusters
        def hsv_to_shoe_color(h, s, v):
            h, s, v = h * 2, s / 255.0, v / 255.0
            if v < 0.15: return "black"
            if v > 0.85 and s < 0.15: return "white"
            if s < 0.2: return "gray" if v < 0.6 else "off-white"
            if h < 15 or h >= 345:
                return "red"
            elif 15 <= h < 40:
                return "brown" if (s < 0.4 or v < 0.5) else "orange"
            elif 40 <= h < 65:
                return "yellow"
            elif 65 <= h < 160:
                return "green"
            elif 160 <= h < 200:
                return "teal"
            elif 200 <= h < 250:
                return "blue"
            elif 250 <= h < 290:
                return "purple"
            elif 290 <= h < 345:
                return "pink"
            return "neutral"

        named_colors = []
        for center in kmeans.cluster_centers_:
            named_colors.append(hsv_to_shoe_color(*center))

        return named_colors[:num_colors]

    except Exception as e:
        print(f"Color extraction error: {e}")
        return ["unknown"]
from skimage.measure import label, regionprops

def calculate_height(rgba_array: np.ndarray) -> str:
    """Estimate shoe height more robustly using bounding box and aspect ratio."""
    try:
        gray = np.mean(rgba_array[:, :, :3], axis=2)  # Ignore alpha
        mask = gray > 20  # Simple threshold to isolate shoe pixels
        labeled = label(mask)
        props = regionprops(labeled)

        if not props:
            return "unknown"

        # Use the largest region assuming it's the shoe
        largest = max(props, key=lambda r: r.area)
        minr, minc, maxr, maxc = largest.bbox
        height = maxr - minr
        width = maxc - minc
        ratio = height / width

        if ratio > 1.4:
            return "high-top"
        elif ratio > 1.0:
            return "mid-top"
        return "low-top"
    except Exception:
        return "unknown"



def detect_design(rgba_array: np.ndarray) -> str:
    """Detect patterns using edge analysis"""
    try:
        gray = cv2.cvtColor(rgba_array[:, :, :3], cv2.COLOR_RGB2GRAY)

        # Edge detection
        edges = cv2.Canny(gray, 50, 150)

        # Detect lines
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=30,
            minLineLength=20,
            maxLineGap=10
        )

        if lines is not None and len(lines) > 2:
            return "striped"

        # Check for other patterns
        contours, _ = cv2.findContours(
            edges,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        if len(contours) > 5:
            return "patterned"

        return "solid"
    except Exception:
        return "unknown"


def rgb_to_name(rgb: np.ndarray) -> str:
    """Enhanced color naming with better thresholds"""
    r, g, b = rgb
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    h = h * 360

    if v < 0.15: return "black"
    if v > 0.9 and s < 0.1: return "white"
    if s < 0.2: return "gray" if v < 0.7 else "off-white"

    if h < 15 or h >= 345:
        return "red"
    elif 15 <= h < 40:
        return "orange" if s > 0.5 else "brown"
    elif 40 <= h < 65:
        return "yellow"
    elif 65 <= h < 160:
        return "green"
    elif 160 <= h < 200:
        return "teal"
    elif 200 <= h < 250:
        return "blue"
    elif 250 <= h < 290:
        return "purple"
    elif 290 <= h < 345:
        return "pink"

    return "neutral"