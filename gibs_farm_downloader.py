"""
NASA GIBS Landsat High-Resolution Farm Image Downloader
Optimized for maximum resolution using Landsat's 30m native resolution
"""

import os
import requests
import math
from datetime import datetime, timedelta
from PIL import Image as PILImage
from io import BytesIO
import numpy as np
from typing import Tuple, Optional, List
import json

class GIBSFarmImageDownloader:
    """
    Downloads high-resolution Landsat satellite imagery from NASA GIBS
    """
    
    # GIBS WMS endpoint
    WMS_URL = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"
    
    # Landsat and other high-resolution layers
    # Landsat has 30m native resolution - the best available from GIBS
    LAYERS = {
        # PRIMARY - Landsat layers (30m resolution)
        'landsat_weld': {
            'name': 'Landsat_WELD_CorrectedReflectance_TrueColor_Global_Monthly',
            'resolution': 30,
            'temporal': 'monthly',
            'description': 'Landsat WELD monthly composite - Best for consistent coverage'
        },
        'landsat_weld_annual': {
            'name': 'Landsat_WELD_CorrectedReflectance_TrueColor_Global_Annual',
            'resolution': 30,
            'temporal': 'annual', 
            'description': 'Landsat WELD annual composite - Most stable, less recent'
        },
        
        # HLS (Harmonized Landsat-Sentinel) - Also 30m
        'hls_landsat': {
            'name': 'HLS_False_Color_Landsat',
            'resolution': 30,
            'temporal': 'daily',
            'description': 'Harmonized Landsat - More recent data'
        },
        'hls_sentinel': {
            'name': 'HLS_False_Color_Sentinel',
            'resolution': 30,
            'temporal': 'daily',
            'description': 'Harmonized Sentinel - More frequent updates'
        },
        'hls_s30': {
            'name': 'HLS_S30_Nadir_BRDF_Adjusted_Reflectance',
            'resolution': 30,
            'temporal': 'daily',
            'description': 'HLS S30 - Adjusted for viewing angle'
        },
        'hls_l30': {
            'name': 'HLS_L30_Nadir_BRDF_Adjusted_Reflectance', 
            'resolution': 30,
            'temporal': 'daily',
            'description': 'HLS L30 - Landsat adjusted reflectance'
        },
        
        # FALLBACK - Lower resolution but always available
        'viirs_noaa20': {
            'name': 'VIIRS_NOAA20_CorrectedReflectance_TrueColor',
            'resolution': 375,
            'temporal': 'daily',
            'description': 'VIIRS - Daily updates, lower resolution fallback'
        },
        'modis_terra': {
            'name': 'MODIS_Terra_CorrectedReflectance_TrueColor',
            'resolution': 250,
            'temporal': 'daily',
            'description': 'MODIS - Daily updates, moderate resolution'
        }
    }
    
    def __init__(self):
        """Initialize the downloader"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'GIBS-Landsat-Downloader/1.0'
        })
    
    def calculate_bbox_from_point(self, lat: float, lon: float, 
                                  width_meters: float, height_meters: float) -> Tuple[float, float, float, float]:
        """
        Calculate bounding box from center point
        """
        # Earth's radius in meters
        R = 6371000
        
        # Calculate degrees per meter at this latitude
        meters_per_deg_lat = (2 * math.pi * R) / 360
        meters_per_deg_lon = (2 * math.pi * R * math.cos(math.radians(lat))) / 360
        
        # Calculate offset in degrees
        half_width_deg = (width_meters / 2) / meters_per_deg_lon
        half_height_deg = (height_meters / 2) / meters_per_deg_lat
        
        # Calculate bounding box
        min_lon = lon - half_width_deg
        max_lon = lon + half_width_deg
        min_lat = lat - half_height_deg
        max_lat = lat + half_height_deg
        
        return (min_lon, min_lat, max_lon, max_lat)
    
    def find_best_landsat_date(self, lat: float, lon: float, layer_key: str = 'landsat_weld') -> Optional[str]:
        """
        Find the best available date for Landsat imagery at this location
        """
        print(f"\n🔍 Finding best Landsat date for location...")
        
        layer_info = self.LAYERS[layer_key]
        layer_name = layer_info['name']
        
        # Different date strategies based on temporal resolution
        if layer_info['temporal'] == 'monthly':
            # Try last 6 months
            dates_to_try = []
            current = datetime.now()
            for i in range(6):
                date = current - timedelta(days=i*30)
                dates_to_try.append(date.strftime('%Y-%m-%d'))
        elif layer_info['temporal'] == 'annual':
            # Try last 3 years
            dates_to_try = []
            current_year = datetime.now().year
            for year in range(current_year, current_year-3, -1):
                dates_to_try.append(f"{year}-06-01")  # Mid-year
        else:  # daily
            # Try last 16 days (Landsat revisit period)
            dates_to_try = [
                (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
                for i in range(0, 17)
            ]
        
        # Test each date
        bbox = self.calculate_bbox_from_point(lat, lon, 500, 500)
        
        for date_str in dates_to_try:
            print(f"  Testing {date_str}...", end="")
            
            params = {
                'service': 'WMS',
                'request': 'GetMap',
                'version': '1.1.1',
                'layers': layer_name,
                'styles': '',
                'format': 'image/jpeg',
                'srs': 'EPSG:4326',
                'bbox': f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
                'width': 256,
                'height': 256,
                'time': date_str
            }
            
            try:
                response = self.session.get(self.WMS_URL, params=params, timeout=10)
                
                if response.status_code == 200 and 'image' in response.headers.get('content-type', ''):
                    # Check if image has valid content
                    img = PILImage.open(BytesIO(response.content))
                    pixels = np.array(img)
                    
                    # Check if not black and has some variation
                    if pixels.mean() > 10 and pixels.std() > 5:
                        print(" ✓ Good imagery found!")
                        return date_str
                    else:
                        print(" ⚠️ Black/uniform")
                else:
                    print(" ✗")
            except Exception as e:
                print(f" ✗ Error")
        
        return None
    
    def download_landsat_closeup(self, 
                                lat: float,
                                lon: float,
                                width_meters: float = 300,
                                height_meters: float = 300,
                                output_path: Optional[str] = None,
                                force_date: Optional[str] = None,
                                layer_key: str = 'landsat_weld') -> str:
        """
        Download a close-up Landsat image with maximum possible resolution
        
        Args:
            lat: Center latitude
            lon: Center longitude  
            width_meters: Width of area in meters (smaller = more detailed view)
            height_meters: Height of area in meters
            output_path: Where to save the image
            force_date: Force a specific date (YYYY-MM-DD) or None to auto-detect
            layer_key: Which Landsat layer to use
            
        Returns:
            Path to saved image
        """
        print("\n" + "="*60)
        print("🛰️  LANDSAT HIGH-RESOLUTION CLOSE-UP IMAGE")
        print("="*60)
        
        if layer_key not in self.LAYERS:
            print(f"⚠️  Unknown layer '{layer_key}', using 'landsat_weld'")
            layer_key = 'landsat_weld'
        
        layer_info = self.LAYERS[layer_key]
        layer_name = layer_info['name']
        native_resolution = layer_info['resolution']
        
        print(f"\n📊 Image Parameters:")
        print(f"  Location: {lat:.6f}, {lon:.6f}")
        print(f"  Coverage: {width_meters}m × {height_meters}m")
        print(f"  Layer: {layer_key}")
        print(f"  Description: {layer_info['description']}")
        print(f"  Native Resolution: {native_resolution}m/pixel")
        
        # Find best available date if not forced
        if force_date:
            date_str = force_date
            print(f"  Using specified date: {date_str}")
        else:
            date_str = self.find_best_landsat_date(lat, lon, layer_key)
            if not date_str:
                print("\n⚠️  No good Landsat data found, trying fallback...")
                return self.download_fallback_image(lat, lon, width_meters, height_meters, output_path)
        
        # Calculate bounding box
        bbox = self.calculate_bbox_from_point(lat, lon, width_meters, height_meters)
        
        # For close-up images, we want maximum pixels
        # WMS has a limit of about 8192x8192 pixels
        # Calculate pixels to match or exceed native resolution
        pixels_per_meter = 1.0 / native_resolution
        ideal_width_px = int(width_meters * pixels_per_meter)
        ideal_height_px = int(height_meters * pixels_per_meter)
        
        # Apply oversampling for smoother visualization (2x-4x native resolution)
        oversample_factor = 4  # This gives us smoother images when zoomed in
        target_width_px = min(ideal_width_px * oversample_factor, 8192)
        target_height_px = min(ideal_height_px * oversample_factor, 8192)
        
        # Calculate effective resolution
        effective_resolution = width_meters / target_width_px
        
        print(f"\n🎯 Resolution Details:")
        print(f"  Native pixels for area: {ideal_width_px}×{ideal_height_px}")
        print(f"  Oversampling: {oversample_factor}x")
        print(f"  Requesting: {target_width_px}×{target_height_px} pixels")
        print(f"  Effective resolution: {effective_resolution:.2f}m/pixel")
        
        # Prepare WMS parameters
        params = {
            'service': 'WMS',
            'request': 'GetMap',
            'version': '1.1.1',
            'layers': layer_name,
            'styles': '',
            'format': 'image/jpeg',  # JPEG for smaller file sizes
            'transparent': 'false',
            'srs': 'EPSG:4326',
            'crs': 'EPSG:4326',
            'bbox': f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
            'width': target_width_px,
            'height': target_height_px,
            'time': date_str
        }
        
        print(f"\n⏳ Downloading Landsat image...")
        print(f"  Date: {date_str}")
        
        try:
            response = self.session.get(self.WMS_URL, params=params, timeout=60)
            
            if response.status_code == 200 and 'image' in response.headers.get('content-type', ''):
                img = PILImage.open(BytesIO(response.content))
                
                # Check if image is valid
                pixels = np.array(img)
                if pixels.mean() < 5 or pixels.std() < 2:
                    print("⚠️  Image appears to be black/invalid, trying different parameters...")
                    return self.download_with_tile_method(lat, lon, width_meters, height_meters, 
                                                         layer_key, date_str, output_path)
                
                # Save the image
                if output_path is None:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    output_path = f"landsat_closeup_{lat:.4f}_{lon:.4f}_{timestamp}.jpg"
                
                # Save with high quality
                img.save(output_path, 'JPEG', quality=95, optimize=True)
                
                file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
                
                print(f"\n✅ SUCCESS! Landsat image saved")
                print(f"  Path: {output_path}")
                print(f"  Dimensions: {img.width}×{img.height} pixels")
                print(f"  File size: {file_size_mb:.2f} MB")
                print(f"  Coverage: {width_meters}×{height_meters} meters")
                print(f"  Resolution: {effective_resolution:.2f}m/pixel")
                
                return output_path
                
            else:
                print(f"❌ Failed to get image (HTTP {response.status_code})")
                return self.download_fallback_image(lat, lon, width_meters, height_meters, output_path)
                
        except Exception as e:
            print(f"❌ Error downloading: {e}")
            return self.download_fallback_image(lat, lon, width_meters, height_meters, output_path)
    
    def download_with_tile_method(self, lat: float, lon: float,
                                 width_meters: float, height_meters: float,
                                 layer_key: str, date_str: str,
                                 output_path: Optional[str]) -> str:
        """
        Alternative method: Download multiple tiles and stitch them for very large images
        """
        print("\n📐 Using tile-based method for better coverage...")
        
        layer_info = self.LAYERS[layer_key]
        layer_name = layer_info['name']
        
        # Divide area into tiles
        tile_size_meters = 150  # Each tile covers 150m
        tiles_x = max(1, int(width_meters / tile_size_meters))
        tiles_y = max(1, int(height_meters / tile_size_meters))
        
        # Pixels per tile (high resolution)
        pixels_per_tile = 1024
        
        print(f"  Downloading {tiles_x}×{tiles_y} grid of tiles...")
        
        # Calculate full bbox
        full_bbox = self.calculate_bbox_from_point(lat, lon, width_meters, height_meters)
        
        # Create final image
        final_width = pixels_per_tile * tiles_x
        final_height = pixels_per_tile * tiles_y
        final_image = PILImage.new('RGB', (final_width, final_height))
        
        # Download each tile
        successful = 0
        for row in range(tiles_y):
            for col in range(tiles_x):
                # Calculate tile bbox
                tile_width_deg = (full_bbox[2] - full_bbox[0]) / tiles_x
                tile_height_deg = (full_bbox[3] - full_bbox[1]) / tiles_y
                
                tile_min_lon = full_bbox[0] + col * tile_width_deg
                tile_max_lon = tile_min_lon + tile_width_deg
                tile_min_lat = full_bbox[1] + row * tile_height_deg
                tile_max_lat = tile_min_lat + tile_height_deg
                
                tile_bbox = (tile_min_lon, tile_min_lat, tile_max_lon, tile_max_lat)
                
                params = {
                    'service': 'WMS',
                    'request': 'GetMap',
                    'version': '1.1.1',
                    'layers': layer_name,
                    'format': 'image/jpeg',
                    'srs': 'EPSG:4326',
                    'bbox': f"{tile_bbox[0]},{tile_bbox[1]},{tile_bbox[2]},{tile_bbox[3]}",
                    'width': pixels_per_tile,
                    'height': pixels_per_tile,
                    'time': date_str
                }
                
                try:
                    response = self.session.get(self.WMS_URL, params=params, timeout=30)
                    if response.status_code == 200:
                        tile_img = PILImage.open(BytesIO(response.content))
                        x_pos = col * pixels_per_tile
                        y_pos = (tiles_y - row - 1) * pixels_per_tile
                        final_image.paste(tile_img, (x_pos, y_pos))
                        successful += 1
                        print(f"  Tile [{row},{col}] ✓")
                except:
                    print(f"  Tile [{row},{col}] ✗")
        
        if successful > 0:
            if output_path is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_path = f"landsat_tiled_{lat:.4f}_{lon:.4f}_{timestamp}.jpg"
            
            final_image.save(output_path, 'JPEG', quality=95)
            print(f"\n✅ Saved tiled image: {output_path}")
            return output_path
        else:
            raise Exception("Failed to download any tiles")
    
    def download_fallback_image(self, lat: float, lon: float,
                               width_meters: float, height_meters: float,
                               output_path: Optional[str]) -> str:
        """
        Fallback to VIIRS/MODIS when Landsat isn't available
        """
        print("\n🔄 Falling back to VIIRS (daily coverage)...")
        
        layer_name = self.LAYERS['viirs_noaa20']['name']
        bbox = self.calculate_bbox_from_point(lat, lon, width_meters, height_meters)
        date_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # For VIIRS, use appropriate resolution
        width_px = min(int(width_meters / 3), 4096)  # ~3m/pixel oversampled
        height_px = min(int(height_meters / 3), 4096)
        
        params = {
            'service': 'WMS',
            'request': 'GetMap',
            'version': '1.1.1',
            'layers': layer_name,
            'format': 'image/jpeg',
            'srs': 'EPSG:4326',
            'bbox': f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
            'width': width_px,
            'height': height_px,
            'time': date_str
        }
        
        response = self.session.get(self.WMS_URL, params=params, timeout=60)
        
        if response.status_code == 200:
            img = PILImage.open(BytesIO(response.content))
            
            if output_path is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_path = f"viirs_fallback_{lat:.4f}_{lon:.4f}_{timestamp}.jpg"
            
            img.save(output_path, 'JPEG', quality=95)
            print(f"✅ Saved VIIRS fallback image: {output_path}")
            return output_path
        else:
            raise Exception("All download methods failed")
    
    def test_all_landsat_layers(self, lat: float, lon: float):
        """
        Test all Landsat and HLS layers to find which ones work
        """
        print("\n🔬 Testing all Landsat/HLS layers for your location...")
        print(f"  Location: {lat:.6f}, {lon:.6f}\n")
        
        working_layers = []
        
        # Test only Landsat and HLS layers
        landsat_layers = [k for k in self.LAYERS.keys() if 'landsat' in k or 'hls' in k]
        
        for layer_key in landsat_layers:
            layer_info = self.LAYERS[layer_key]
            print(f"  Testing {layer_key}...")
            print(f"    Resolution: {layer_info['resolution']}m")
            print(f"    Temporal: {layer_info['temporal']}")
            
            date = self.find_best_landsat_date(lat, lon, layer_key)
            if date:
                print(f"    ✅ Working! Best date: {date}")
                working_layers.append((layer_key, date))
            else:
                print(f"    ❌ No valid data found")
            print()
        
        if working_layers:
            print(f"✅ Found {len(working_layers)} working Landsat/HLS layers")
            print("\nBest options:")
            for layer, date in working_layers[:3]:
                print(f"  • {layer} (date: {date})")
        else:
            print("⚠️  No Landsat data available, will use VIIRS/MODIS fallback")
        
        return working_layers


# Convenience function
def download_landsat_farm_image(lat: float, lon: float, 
                               area_size: float = 300,
                               output_path: Optional[str] = None) -> str:
    """
    Simple function to download the best available Landsat image
    
    Args:
        lat: Latitude of farm center
        lon: Longitude of farm center  
        area_size: Size of square area in meters (default 300m for close-up)
        output_path: Where to save the image
        
    Returns:
        Path to saved image
    """
    downloader = GIBSFarmImageDownloader()
    
    # First, test what's available
    print("Testing Landsat availability...")
    working = downloader.test_all_landsat_layers(lat, lon)
    
    if working:
        # Use the best available layer
        best_layer, best_date = working[0]
        return downloader.download_landsat_closeup(
            lat=lat,
            lon=lon,
            width_meters=area_size,
            height_meters=area_size,
            layer_key=best_layer,
            force_date=best_date,
            output_path=output_path
        )
    else:
        # Fallback to daily imagery
        print("No Landsat available, using VIIRS...")
        return downloader.download_landsat_closeup(
            lat=lat,
            lon=lon,
            width_meters=area_size,
            height_meters=area_size,
            layer_key='viirs_noaa20',
            output_path=output_path
        )


if __name__ == "__main__":
    # Your location
    lat = 20.1381967836148
    lon = -99.056869712403
    
    print("="*60)
    print("🛰️  NASA GIBS LANDSAT HIGH-RESOLUTION DOWNLOADER")
    print("="*60)
    
    downloader = GIBSFarmImageDownloader()
    
    # Step 1: Test what Landsat data is available
    print("\n1️⃣  CHECKING LANDSAT AVAILABILITY")
    working_layers = downloader.test_all_landsat_layers(lat, lon)
    
    if not working_layers:
        print("\n⚠️  No Landsat data found for your location.")
        print("This could be due to:")
        print("  • Cloud coverage in recent images")
        print("  • Limited Landsat coverage in your area")
        print("  • Data processing delays")
        print("\nUsing VIIRS/MODIS instead (lower resolution but daily coverage)")
    
    # Step 2: Download the best available close-up image
    print("\n2️⃣  DOWNLOADING CLOSE-UP IMAGE")
    
    try:
        if working_layers:
            # Use the best Landsat layer
            best_layer, best_date = working_layers[0]
            output = downloader.download_landsat_closeup(
                lat=lat,
                lon=lon,
                width_meters=200,  # 200m x 200m for very close-up view
                height_meters=200,
                layer_key=best_layer,
                force_date=best_date,
                output_path="landsat_closeup.jpg"
            )
        else:
            # Use fallback
            output = downloader.download_landsat_closeup(
                lat=lat,
                lon=lon,
                width_meters=300,  # Slightly larger area for VIIRS
                height_meters=300,
                layer_key='viirs_noaa20',
                output_path="viirs_closeup.jpg"
            )
        
        print(f"\n✅ SUCCESS! Image saved: {output}")
        
        # Step 3: Also try different area sizes for comparison
        print("\n3️⃣  DOWNLOADING DIFFERENT SCALES FOR COMPARISON")
        
        # Small area - maximum detail
        downloader.download_landsat_closeup(
            lat=lat, lon=lon,
            width_meters=100,  # 100m x 100m - very close
            height_meters=100,
            output_path="ultra_closeup_100m.jpg"
        )
        
        # Medium area
        downloader.download_landsat_closeup(
            lat=lat, lon=lon,
            width_meters=500,  # 500m x 500m
            height_meters=500,
            output_path="medium_view_500m.jpg"
        )
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    print("\n" + "="*60)
    print("📝 SUMMARY")
    print("="*60)
    print("\n🎯 For the BEST close-up images:")
    print("  1. Use area_size between 100-300 meters")
    print("  2. Landsat gives best resolution (30m native)")
    print("  3. Check multiple dates if first attempt is cloudy")
    print("  4. VIIRS/MODIS work as daily fallback options")
    print("\n💡 The tile method is best for very large areas,")
    print("   but for close-ups, a single high-res request works better!")
    print("="*60)