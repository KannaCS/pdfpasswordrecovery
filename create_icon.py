import os
from PIL import Image, ImageDraw, ImageFont

def create_icon():
    """Create a PDF password recovery icon"""
    # Create image with transparent background
    img_size = 512  # Large size for quality
    img = Image.new('RGBA', (img_size, img_size), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Colors
    pdf_red = (220, 53, 69)
    lock_color = (52, 58, 64)
    highlight = (255, 193, 7)
    
    # Draw PDF document shape
    margin = int(img_size * 0.15)
    doc_width = img_size - 2 * margin
    doc_height = int(doc_width * 1.3)
    
    # Document shape
    draw.rounded_rectangle(
        [(margin, margin), (margin + doc_width, margin + doc_height)],
        radius=int(img_size * 0.05),
        fill=pdf_red
    )
    
    # PDF text
    font_size = int(img_size * 0.2)
    try:
        # Try to use Arial Bold if available
        font = ImageFont.truetype("arial.ttf", font_size, encoding="unic")
    except:
        # Fall back to default font
        font = ImageFont.load_default()
        
    # Draw "PDF" text
    text = "PDF"
    text_width, text_height = draw.textsize(text, font=font) if hasattr(draw, 'textsize') else (font_size * 3, font_size)
    text_x = margin + (doc_width - text_width) / 2
    text_y = margin + int(doc_height * 0.2)
    draw.text((text_x, text_y), text, font=font, fill="white")
    
    # Draw lock
    lock_size = int(img_size * 0.45)
    lock_x = margin + (doc_width - lock_size) / 2
    lock_y = margin + int(doc_height * 0.5)
    
    # Lock body
    draw.rounded_rectangle(
        [(lock_x, lock_y), (lock_x + lock_size, lock_y + lock_size)],
        radius=int(lock_size * 0.2),
        fill=lock_color,
        outline=highlight,
        width=int(img_size * 0.01)
    )
    
    # Lock shackle
    shackle_width = int(lock_size * 0.6)
    shackle_height = int(lock_size * 0.4)
    shackle_x = lock_x + (lock_size - shackle_width) / 2
    shackle_top_y = lock_y - shackle_height
    
    # Draw the shackle (U shape)
    draw.rounded_rectangle(
        [(shackle_x, shackle_top_y), 
         (shackle_x + shackle_width, lock_y)],
        radius=int(shackle_width * 0.25),
        outline=lock_color,
        width=int(img_size * 0.04)
    )
    
    # Keyhole
    keyhole_x = lock_x + lock_size / 2
    keyhole_y = lock_y + lock_size / 2
    keyhole_radius = int(lock_size * 0.1)
    draw.ellipse(
        [(keyhole_x - keyhole_radius, keyhole_y - keyhole_radius),
         (keyhole_x + keyhole_radius, keyhole_y + keyhole_radius)],
        fill=highlight
    )
    
    # Draw a key line below the circle
    key_line_width = int(lock_size * 0.05)
    key_line_height = int(lock_size * 0.2)
    draw.rectangle(
        [(keyhole_x - key_line_width / 2, keyhole_y),
         (keyhole_x + key_line_width / 2, keyhole_y + key_line_height)],
        fill=highlight
    )
    
    # Save the icon in multiple sizes for the .ico file
    sizes = [16, 32, 48, 64, 128, 256]
    icon_images = []
    
    for size in sizes:
        resized_img = img.resize((size, size), Image.LANCZOS)
        icon_images.append(resized_img)
    
    # Save as .ico file
    icon_path = os.path.join(os.path.dirname(__file__), "kanna_icon.ico")
    icon_images[0].save(
        icon_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=icon_images[1:]
    )
    
    print(f"Icon created and saved to {icon_path}")
    return icon_path

if __name__ == "__main__":
    create_icon()
