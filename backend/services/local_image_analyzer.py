"""
本地轻量图像识别优化模块
基于OpenCV的本地图像特征提取，无外部API依赖
提供基础的消防隐患视觉特征分析能力
"""

from __future__ import annotations

import os
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False


COLOR_RANGES = {
    "red": [(0, 50, 50), (10, 255, 255)],
    "red2": [(170, 50, 50), (180, 255, 255)],
    "orange": [(10, 50, 50), (25, 255, 255)],
    "yellow": [(25, 50, 50), (35, 255, 255)],
    "green": [(35, 50, 50), (85, 255, 255)],
    "blue": [(100, 50, 50), (130, 255, 255)],
    "white": [(0, 0, 200), (180, 30, 255)],
    "black": [(0, 0, 0), (180, 255, 50)],
    "gray": [(0, 0, 50), (180, 30, 200)],
}


FIRE_HAZARD_PATTERNS = {
    "消防通道堵塞": {
        "indicators": ["low_clearance", "cluttered_bottom", "narrow_passage"],
        "color_hints": ["gray", "brown"],
        "confidence_base": 0.4,
        "description": "检测到通道区域可能存在障碍物堆积"
    },
    "灭火器遮挡": {
        "indicators": ["red_partial_visibility", "foreground_objects"],
        "color_hints": ["red"],
        "confidence_base": 0.5,
        "description": "检测到红色消防设备区域，可能存在遮挡"
    },
    "消防栓遮挡": {
        "indicators": ["red_partial_visibility", "rectangular_shape_partial"],
        "color_hints": ["red"],
        "confidence_base": 0.45,
        "description": "检测到红色箱体区域，可能是消防栓或灭火器箱"
    },
    "电动车违规停放": {
        "indicators": ["two_wheel_shape", "battery_area"],
        "color_hints": ["black", "gray", "blue"],
        "confidence_base": 0.35,
        "description": "检测到疑似两轮车轮廓，需人工确认是否为电动车"
    },
    "可燃物堆积": {
        "indicators": ["cluttered_area", "brown_dominant", "paper_texture"],
        "color_hints": ["brown", "yellow", "white"],
        "confidence_base": 0.45,
        "description": "检测到大量杂乱堆放区域，疑似可燃物堆积"
    },
    "应急出口标识缺失": {
        "indicators": ["no_green_sign", "door_area"],
        "color_hints": ["green"],
        "confidence_base": 0.3,
        "description": "未检测到明显的绿色安全出口标识"
    },
    "电气线路杂乱": {
        "indicators": ["many_lines", "tangled_pattern"],
        "color_hints": ["black", "gray"],
        "confidence_base": 0.35,
        "description": "检测到密集线条纹理，疑似线路杂乱"
    },
    "配电箱周围堆物": {
        "indicators": ["rectangular_cabinet", "foreground_clutter"],
        "color_hints": ["gray", "green"],
        "confidence_base": 0.4,
        "description": "检测到疑似电气柜区域，周围可能有堆放物"
    },
}


def check_opencv_available() -> bool:
    """检查OpenCV是否可用"""
    return OPENCV_AVAILABLE


def _safe_read_image(image_path: str) -> Optional[np.ndarray]:
    """安全读取图片，处理各种路径和编码问题"""
    if not os.path.exists(image_path):
        return None
    
    try:
        img = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        return img
    except Exception:
        try:
            img = cv2.imread(image_path)
            return img
        except Exception:
            return None


def _detect_color_regions(hsv_img: np.ndarray, color_name: str) -> Tuple[int, float]:
    """检测特定颜色区域的像素数和占比"""
    if color_name not in COLOR_RANGES:
        return 0, 0.0
    
    total_pixels = hsv_img.shape[0] * hsv_img.shape[1]
    if total_pixels == 0:
        return 0, 0.0
    
    if color_name == "red":
        lower1, upper1 = COLOR_RANGES["red"]
        lower2, upper2 = COLOR_RANGES["red2"]
        mask1 = cv2.inRange(hsv_img, np.array(lower1), np.array(upper1))
        mask2 = cv2.inRange(hsv_img, np.array(lower2), np.array(upper2))
        mask = cv2.bitwise_or(mask1, mask2)
    else:
        lower, upper = COLOR_RANGES[color_name]
        mask = cv2.inRange(hsv_img, np.array(lower), np.array(upper))
    
    pixel_count = cv2.countNonZero(mask)
    ratio = pixel_count / total_pixels
    return pixel_count, ratio


def _analyze_color_distribution(hsv_img: np.ndarray) -> Dict[str, Any]:
    """分析图像颜色分布"""
    colors = {}
    for color_name in COLOR_RANGES:
        if color_name == "red2":
            continue
        pixels, ratio = _detect_color_regions(hsv_img, color_name)
        colors[color_name] = {
            "pixel_count": pixels,
            "ratio": round(ratio * 100, 2)
        }
    
    dominant_colors = sorted(
        [(c, v["ratio"]) for c, v in colors.items()],
        key=lambda x: x[1],
        reverse=True
    )[:5]
    
    return {
        "color_distribution": colors,
        "dominant_colors": [c for c, _ in dominant_colors],
        "dominant_color_ratios": dominant_colors
    }


def _analyze_texture_complexity(gray_img: np.ndarray) -> Dict[str, Any]:
    """分析纹理复杂度（用于判断杂乱程度）"""
    try:
        laplacian = cv2.Laplacian(gray_img, cv2.CV_64F)
        texture_variance = np.var(laplacian)
        
        edges = cv2.Canny(gray_img, 50, 150)
        edge_density = cv2.countNonZero(edges) / (gray_img.shape[0] * gray_img.shape[1])
        
        sobelx = cv2.Sobel(gray_img, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray_img, cv2.CV_64F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(sobelx**2 + sobely**2)
        avg_gradient = np.mean(gradient_magnitude)
        
        clutter_score = min(1.0, (texture_variance / 10000 + edge_density * 5 + avg_gradient / 100) / 3)
        
        return {
            "texture_variance": round(float(texture_variance), 2),
            "edge_density": round(float(edge_density * 100), 2),
            "avg_gradient": round(float(avg_gradient), 2),
            "clutter_score": round(float(clutter_score), 3),
            "clutter_level": "高" if clutter_score > 0.6 else "中" if clutter_score > 0.3 else "低"
        }
    except Exception as e:
        return {
            "error": str(e),
            "clutter_score": 0.5,
            "clutter_level": "中"
        }


def _analyze_shape_features(gray_img: np.ndarray) -> Dict[str, Any]:
    """分析形状特征"""
    try:
        _, thresh = cv2.threshold(gray_img, 127, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        total_contours = len(contours)
        
        rectangles = 0
        circles = 0
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 100:
                continue
            
            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = float(w) / h if h > 0 else 0
            extent = float(area) / (w * h) if w * h > 0 else 0
            
            if 0.3 < aspect_ratio < 3.0 and extent > 0.6:
                rectangles += 1
            
            perimeter = cv2.arcLength(cnt, True)
            circularity = 4 * np.pi * area / (perimeter ** 2) if perimeter > 0 else 0
            if circularity > 0.7:
                circles += 1
        
        return {
            "total_contours": total_contours,
            "rectangle_count": rectangles,
            "circle_count": circles,
            "shape_complexity": min(1.0, total_contours / 50)
        }
    except Exception as e:
        return {
            "error": str(e),
            "total_contours": 0,
            "rectangle_count": 0,
            "circle_count": 0
        }


def _analyze_spatial_distribution(img: np.ndarray) -> Dict[str, Any]:
    """分析空间分布（上下左右区域的亮度、颜色等）"""
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    regions = {
        "top": hsv[:h//3, :],
        "middle": hsv[h//3:2*h//3, :],
        "bottom": hsv[2*h//3:, :],
        "left": hsv[:, :w//3],
        "center": hsv[:, w//3:2*w//3],
        "right": hsv[:, 2*w//3:]
    }
    
    region_analysis = {}
    for name, region in regions.items():
        if region.size == 0:
            region_analysis[name] = {"brightness": 0, "saturation": 0}
            continue
        avg_v = np.mean(region[:, :, 2])
        avg_s = np.mean(region[:, :, 1])
        region_analysis[name] = {
            "brightness": round(float(avg_v), 1),
            "saturation": round(float(avg_s), 1)
        }
    
    bottom_brightness = region_analysis.get("bottom", {}).get("brightness", 0)
    top_brightness = region_analysis.get("top", {}).get("brightness", 0)
    bottom_clutter = bottom_brightness < top_brightness * 0.8
    
    return {
        "regions": region_analysis,
        "bottom_darker": bottom_clutter,
        "bottom_ratio": round(bottom_brightness / top_brightness, 2) if top_brightness > 0 else 1.0
    }


def _detect_lines(gray_img: np.ndarray) -> Dict[str, Any]:
    """检测直线（用于判断线路杂乱程度）"""
    try:
        edges = cv2.Canny(gray_img, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 100)
        
        line_count = len(lines) if lines is not None else 0
        
        horizontal = 0
        vertical = 0
        diagonal = 0
        
        if lines is not None:
            for line in lines:
                rho, theta = line[0]
                angle = theta * 180 / np.pi
                if angle < 15 or angle > 165:
                    horizontal += 1
                elif 75 < angle < 105:
                    vertical += 1
                else:
                    diagonal += 1
        
        line_density = line_count / (gray_img.shape[0] * gray_img.shape[1]) * 10000
        
        return {
            "total_lines": line_count,
            "horizontal_lines": horizontal,
            "vertical_lines": vertical,
            "diagonal_lines": diagonal,
            "line_density": round(float(line_density), 3),
            "line_complexity": min(1.0, line_count / 30)
        }
    except Exception as e:
        return {
            "error": str(e),
            "total_lines": 0,
            "line_complexity": 0
        }


def _infer_hazards_from_features(
    color_data: Dict[str, Any],
    texture_data: Dict[str, Any],
    shape_data: Dict[str, Any],
    spatial_data: Dict[str, Any],
    line_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """基于特征推断消防隐患"""
    hazards = []
    
    clutter_score = texture_data.get("clutter_score", 0.5)
    dominant_colors = color_data.get("dominant_colors", [])
    
    red_ratio = color_data.get("color_distribution", {}).get("red", {}).get("ratio", 0)
    
    if clutter_score > 0.5 and spatial_data.get("bottom_darker", False):
        confidence = min(0.85, 0.4 + clutter_score * 0.4 + (0.1 if "brown" in dominant_colors[:3] else 0))
        hazards.append({
            "name": "消防通道堵塞",
            "confidence": round(confidence, 2),
            "evidence": [
                f"图像杂乱程度: {texture_data.get('clutter_level', '中')} ({clutter_score:.2f})",
                f"底部区域偏暗，可能有障碍物遮挡",
                f"主要颜色: {', '.join(dominant_colors[:3])}"
            ],
            "severity": "B级" if confidence > 0.6 else "C级"
        })
    
    if red_ratio > 2.0:
        confidence = min(0.8, 0.5 + red_ratio * 0.05)
        if shape_data.get("rectangle_count", 0) > 3:
            confidence = min(0.85, confidence + 0.15)
            hazards.append({
                "name": "消防栓/灭火器箱检测",
                "confidence": round(confidence, 2),
                "evidence": [
                    f"红色区域占比: {red_ratio:.1f}%",
                    f"检测到 {shape_data.get('rectangle_count', 0)} 个矩形轮廓",
                    "疑似消防设施，需人工确认是否被遮挡"
                ],
                "severity": "C级"
            })
        else:
            hazards.append({
                "name": "灭火器/消防设备检测",
                "confidence": round(confidence, 2),
                "evidence": [
                    f"红色区域占比: {red_ratio:.1f}%",
                    "检测到红色消防设备特征颜色",
                    "需人工确认设备完整性和遮挡情况"
                ],
                "severity": "C级"
            })
    
    if clutter_score > 0.55 and ("brown" in dominant_colors[:2] or "yellow" in dominant_colors[:2]):
        confidence = min(0.8, 0.45 + clutter_score * 0.35)
        hazards.append({
            "name": "可燃物堆积",
            "confidence": round(confidence, 2),
            "evidence": [
                f"图像杂乱程度: {texture_data.get('clutter_level', '中')}",
                f"主要颜色包含棕/黄色系，疑似纸箱、木材等可燃物",
                f"边缘密度: {texture_data.get('edge_density', 0)}%"
            ],
            "severity": "B级" if confidence > 0.6 else "C级"
        })
    
    if line_data.get("line_complexity", 0) > 0.4 and line_data.get("total_lines", 0) > 15:
        confidence = min(0.75, 0.35 + line_data["line_complexity"] * 0.4)
        hazards.append({
            "name": "电气线路杂乱",
            "confidence": round(confidence, 2),
            "evidence": [
                f"检测到 {line_data.get('total_lines', 0)} 条直线",
                f"线路密度: {line_data.get('line_density', 0)}",
                f"水平: {line_data.get('horizontal_lines', 0)}, 垂直: {line_data.get('vertical_lines', 0)}, 斜向: {line_data.get('diagonal_lines', 0)}"
            ],
            "severity": "C级"
        })
    
    green_ratio = color_data.get("color_distribution", {}).get("green", {}).get("ratio", 0)
    if green_ratio < 1.0 and shape_data.get("rectangle_count", 0) < 2:
        confidence = 0.35
        hazards.append({
            "name": "安全标识检测",
            "confidence": round(confidence, 2),
            "evidence": [
                f"绿色区域占比: {green_ratio:.1f}%（安全出口标识通常为绿色）",
                "未检测到明显的安全出口标识特征",
                "需人工确认现场是否有合规的安全标识"
            ],
            "severity": "C级"
        })
    
    if not hazards:
        hazards.append({
            "name": "未检测到明显隐患",
            "confidence": 0.6,
            "evidence": [
                "基于图像特征分析未发现明显的消防隐患模式",
                "建议结合人工巡检进行综合判断",
                f"图像杂乱度: {texture_data.get('clutter_level', '中')}"
            ],
            "severity": "无风险"
        })
    
    hazards.sort(key=lambda x: x["confidence"], reverse=True)
    return hazards


def analyze_image_local(image_path: str) -> Dict[str, Any]:
    """
    基于OpenCV的本地图像分析
    
    Args:
        image_path: 图片路径
        
    Returns:
        分析结果字典
    """
    if not OPENCV_AVAILABLE:
        return {
            "success": False,
            "error": "OpenCV未安装，无法进行本地图像分析",
            "hazards": [],
            "used_local_vision": False,
            "provider": "none",
            "model": "none",
            "description": "未安装OpenCV，无法进行本地图像分析。请安装opencv-python以启用本地图像识别。"
        }
    
    img = _safe_read_image(image_path)
    if img is None:
        return {
            "success": False,
            "error": "无法读取图片文件",
            "hazards": [],
            "used_local_vision": False,
            "provider": "local_opencv",
            "model": "fire-inspection-local-v1",
            "description": "图片读取失败，请检查图片格式和路径。"
        }
    
    try:
        h, w = img.shape[:2]
        
        hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        color_data = _analyze_color_distribution(hsv_img)
        texture_data = _analyze_texture_complexity(gray_img)
        shape_data = _analyze_shape_features(gray_img)
        spatial_data = _analyze_spatial_distribution(img)
        line_data = _detect_lines(gray_img)
        
        hazards = _infer_hazards_from_features(
            color_data, texture_data, shape_data, spatial_data, line_data
        )
        
        risk_level = "低风险"
        risk_score = 25
        high_conf_hazards = [h for h in hazards if h.get("confidence", 0) > 0.6 and h.get("severity") != "无风险"]
        if high_conf_hazards:
            a_count = len([h for h in high_conf_hazards if h.get("severity") == "A级"])
            b_count = len([h for h in high_conf_hazards if h.get("severity") == "B级"])
            if a_count > 0:
                risk_level = "严重风险"
                risk_score = 80 + a_count * 5
            elif b_count >= 2:
                risk_level = "高风险"
                risk_score = 65 + b_count * 5
            elif b_count >= 1:
                risk_level = "中风险"
                risk_score = 45 + b_count * 10
        
        visual_evidence = [
            f"图像尺寸: {w}x{h}",
            f"主色调: {', '.join(color_data.get('dominant_colors', [])[:3])}",
            f"杂乱程度: {texture_data.get('clutter_level', '中')} ({texture_data.get('clutter_score', 0):.2f})",
            f"边缘密度: {texture_data.get('edge_density', 0)}%",
            f"检测到 {shape_data.get('total_contours', 0)} 个轮廓区域",
            f"检测到 {line_data.get('total_lines', 0)} 条直线"
        ]
        
        return {
            "success": True,
            "hazards": [h["name"] for h in hazards if h.get("severity") != "无风险"],
            "hazard_details": hazards,
            "description": f"本地图像分析完成。检测到{len(high_conf_hazards)}项疑似隐患，主要类型：{', '.join([h['name'] for h in hazards[:3]])}。",
            "risk_reasons": [
                f"基于颜色、纹理、形状等多维度特征分析",
                f"图像杂乱度为{texture_data.get('clutter_level', '中')}，" + ("存在较高隐患风险" if texture_data.get('clutter_score', 0) > 0.5 else "整体较为规整"),
                f"检测到{len(high_conf_hazards)}项置信度高于60%的疑似隐患"
            ],
            "visual_evidence": visual_evidence,
            "used_local_vision": True,
            "used_vision_api": False,
            "local_image_fallback": False,
            "provider": "local_opencv",
            "model": "fire-inspection-local-v1",
            "image_info": {
                "width": w,
                "height": h,
                "file_size": os.path.getsize(image_path) if os.path.exists(image_path) else 0
            },
            "feature_analysis": {
                "color_distribution": color_data,
                "texture": texture_data,
                "shape": shape_data,
                "spatial": spatial_data,
                "lines": line_data
            },
            "risk_level": risk_level,
            "risk_score": risk_score,
            "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "hazards": [],
            "used_local_vision": True,
            "provider": "local_opencv",
            "model": "fire-inspection-local-v1",
            "description": f"本地图像分析出错: {str(e)}"
        }


def get_local_vision_status() -> Dict[str, Any]:
    """获取本地视觉识别能力状态"""
    return {
        "available": OPENCV_AVAILABLE,
        "provider": "local_opencv" if OPENCV_AVAILABLE else "none",
        "model": "fire-inspection-local-v1" if OPENCV_AVAILABLE else "none",
        "capabilities": [
            "颜色分布检测",
            "纹理复杂度分析",
            "形状轮廓检测",
            "空间分布分析",
            "直线检测",
            "消防隐患初筛"
        ] if OPENCV_AVAILABLE else [],
        "supported_hazards": list(FIRE_HAZARD_PATTERNS.keys()) if OPENCV_AVAILABLE else [],
        "install_hint": "pip install opencv-python numpy" if not OPENCV_AVAILABLE else ""
    }
