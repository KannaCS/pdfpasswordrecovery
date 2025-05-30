from PIL import Image
import os

def save_icon_for_readme():
    """Save the app icon as a PNG for the README"""
    # Create screenshots directory if it doesn't exist
    screenshots_dir = os.path.join(os.path.dirname(__file__), "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)
    
    # Open the ICO file
    icon_path = os.path.join(os.path.dirname(__file__), "kanna_icon.ico")
    img = Image.open(icon_path)
    
    # Save the largest size as PNG for the README
    output_path = os.path.join(screenshots_dir, "app_icon.png")
    img.save(output_path, format="PNG")
    
    print(f"Saved app icon to {output_path}")
    
if __name__ == "__main__":
    save_icon_for_readme()
