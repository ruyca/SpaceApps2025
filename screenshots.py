"""
NASA Earthdata Screenshot Capture Script

This script generates NASA Earthdata URLs with custom coordinates and date ranges,
then captures screenshots of the loaded pages and crops them to show only the map.

Requirements:
    pip install selenium pillow
    
You'll also need ChromeDriver installed and in your PATH, or specify the path in the script.
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from PIL import Image
from datetime import datetime
import time
import os


def generate_earthdata_url(latitude, longitude, start_date, end_date, zoom=18):
    """
    Generate NASA Earthdata URL with specified parameters.
    
    Args:
        latitude (float): Latitude coordinate
        longitude (float): Longitude coordinate
        start_date (str): Start date in 'YYYY-MM-DD' format
        end_date (str): End date in 'YYYY-MM-DD' format
        zoom (float): Zoom level (default: 18)
    
    Returns:
        str: Complete NASA Earthdata URL
    """
    # Format dates to ISO 8601 with time
    start_datetime = f"{start_date}T00%3A00%3A00.000Z"
    end_datetime = f"{end_date}T23%3A59%3A59.999Z"
    
    # Build the URL
    base_url = "https://search.earthdata.nasa.gov/search/granules"
    params = (
        f"?p=C2021957657-LPCLOUD"
        f"&pg[0][v]=f"
        f"&pg[0][gsk]=-start_date"
        f"&q=C2021957657-LPCLOUD"
        f"&sp[0]={longitude}%2C{latitude}"
        f"&qt={start_datetime}%2C{end_datetime}"
        f"&tl=1562640103.056!5!!"
        f"&lat={latitude}"
        f"&long={longitude}"
        f"&zoom={zoom}"
    )
    
    return base_url + params


def crop_to_map(image_path, output_path=None):
    """
    Crop the screenshot to remove headers, sidebar, and bottom timeline.
    
    Based on the standard NASA Earthdata interface layout at 1920x1080:
    - Top red header: ~120 pixels
    - Left sidebar: ~280 pixels
    - Bottom timeline: ~60 pixels
    
    Args:
        image_path (str): Path to the original screenshot
        output_path (str, optional): Path for cropped image. If None, overwrites original.
    
    Returns:
        str: Path to the cropped image
    """
    # Open the image
    img = Image.open(image_path)
    width, height = img.size
    
    # Define crop box (left, top, right, bottom)
    # Removing: top header (~120px), left sidebar (~280px), bottom timeline (~60px)
    left = 480
    top = 120
    right = width
    bottom = height - 100
    
    # Crop the image
    cropped_img = img.crop((left, top, right, bottom))
    
    # Save the cropped image
    if output_path is None:
        output_path = image_path
    
    cropped_img.save(output_path)
    print(f"Image cropped to map area: {cropped_img.size[0]}x{cropped_img.size[1]} pixels")
    
    return output_path


def capture_earthdata_screenshot(latitude, longitude, start_date, end_date, 
                                  output_filename=None, zoom=18, wait_time=10, crop=True):
    """
    Capture a screenshot of NASA Earthdata page with specified parameters.
    
    Args:
        latitude (float): Latitude coordinate
        longitude (float): Longitude coordinate
        start_date (str): Start date in 'YYYY-MM-DD' format
        end_date (str): End date in 'YYYY-MM-DD' format
        output_filename (str, optional): Output filename for screenshot
        zoom (float): Zoom level (default: 18)
        wait_time (int): Time to wait for page to load in seconds (default: 10)
        crop (bool): Whether to crop to map area only (default: True)
    
    Returns:
        str: Path to the saved screenshot
    """
    # Generate URL
    url = generate_earthdata_url(latitude, longitude, start_date, end_date, zoom)
    print(f"Generated URL: {url}")
    
    # Set up output filename if not provided
    if output_filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"earthdata_{latitude}_{longitude}_{timestamp}.png"
    
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in background
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    
    # Initialize the driver
    driver = None
    try:
        # You may need to specify the path to chromedriver if it's not in PATH
        # service = Service('/path/to/chromedriver')
        # driver = webdriver.Chrome(service=service, options=chrome_options)
        
        driver = webdriver.Chrome(options=chrome_options)
        
        # Navigate to the URL
        print(f"Loading page...")
        driver.get(url)
        
        # Wait for the page to load
        print(f"Waiting {wait_time} seconds for page to fully load...")
        time.sleep(wait_time)
        
        # Close popup by pressing ESC then ]
        print("Closing popup with ESC key...")
        actions = ActionChains(driver)
        actions.send_keys(Keys.ESCAPE)
        actions.perform()
        time.sleep(1)  # Brief pause between key presses
        
        print("Pressing ] to show full view...")
        actions = ActionChains(driver)
        actions.send_keys(']')
        actions.perform()
        time.sleep(2)  # Wait for transition to complete
        
        # Take screenshot
        print(f"Capturing screenshot...")
        driver.save_screenshot(output_filename)
        print(f"Screenshot saved to: {output_filename}")
        
        # Crop if requested
        if crop:
            print("Cropping to map area...")
            crop_to_map(output_filename)
        
        return output_filename
        
    except Exception as e:
        print(f"Error occurred: {e}")
        raise
        
    finally:
        if driver:
            driver.quit()


def calculate_zoom(area_m2):
    """
    Calculate an approximate zoom level based on the area in square meters.
    
    Args:
        area_m2 (float): Area in square meters
    
    Returns:
        float: Estimated zoom level
    """
    if area_m2 <= 0:
        raise ValueError("Area must be a positive number.")
    
    # Approximate formula to convert area to zoom level
    zoom = 19 - (area_m2 ** 0.5 / 100)
    return max(15, min(20, zoom)) + 1  # Clamp between 15 and 20


def main():
    """
    Example usage of the screenshot capture function.
    """
    # Example coordinates (Mexico City area from your original URL)
    latitude = 20.1452006314719
    longitude = -99.0546790285769
    area_m2 = 11148.6419323683  # Example area in square meters
    zoom = calculate_zoom(area_m2)  # Calculate zoom based on area
    start_date = "2025-07-05"
    end_date = "2025-07-06"
    
    # Capture screenshot with automatic cropping
    screenshot_path = capture_earthdata_screenshot(
        latitude=round(latitude, 5),
        longitude=round(longitude, 5),
        start_date=start_date,
        end_date=end_date,
        zoom=zoom,
        wait_time=7,  # Wait 7 seconds for page to load
        crop=True  # Automatically crop to map area
    )
    
    print(f"\nScreenshot captured and cropped successfully!")
    print(f"File: {screenshot_path}")


if __name__ == "__main__":
    main()