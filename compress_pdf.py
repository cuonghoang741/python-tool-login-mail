"""
PDF Compression Script - Convert PDF to images then back to PDF
This method significantly reduces file size
"""
import fitz  # PyMuPDF
import os

def compress_pdf_via_image(input_path, output_path, dpi=100, image_quality=60):
    """
    Compress PDF by converting each page to image and back
    dpi: resolution (lower = smaller file, default 150 is good balance)
    image_quality: JPEG quality 1-100 (lower = smaller)
    """
    print(f"Opening: {input_path}")
    src_doc = fitz.open(input_path)
    
    total_pages = len(src_doc)
    print(f"Converting {total_pages} pages at {dpi} DPI, quality={image_quality}...")
    
    # Create new PDF
    dst_doc = fitz.open()
    
    for page_num in range(total_pages):
        print(f"  Processing page {page_num + 1}/{total_pages}...", end='\r')
        
        page = src_doc[page_num]
        
        # Render page to image
        zoom = dpi / 72  # 72 is default PDF DPI
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        # Convert to JPEG bytes with compression
        img_bytes = pix.tobytes("jpeg", jpg_quality=image_quality)
        
        # Create new page with same dimensions
        rect = page.rect
        new_page = dst_doc.new_page(width=rect.width, height=rect.height)
        
        # Insert image to fill the page
        new_page.insert_image(rect, stream=img_bytes)
    
    print(f"\nSaving to: {output_path}")
    dst_doc.save(output_path, garbage=4, deflate=True)
    
    src_doc.close()
    dst_doc.close()
    
    # Report sizes
    original = os.path.getsize(input_path)
    compressed = os.path.getsize(output_path)
    reduction = ((original - compressed) / original) * 100
    
    print(f"\n{'='*50}")
    print(f"Original:   {original / 1024 / 1024:.2f} MB")
    print(f"Compressed: {compressed / 1024 / 1024:.2f} MB")
    print(f"Saved:      {reduction:.1f}%")
    print(f"{'='*50}")
    
    if reduction > 0:
        print(f"\n✓ File compressed successfully: {output_path}")
    else:
        print(f"\n✗ File could not be compressed further")
    
    return output_path

if __name__ == "__main__":
    input_file = "Tin 1 - HUBT 2025.pdf"
    output_file = "Tin 1 - HUBT 2025_compressed.pdf"
    
    # Lower DPI and quality = smaller file (but lower quality)
    # DPI 100 and quality 50 gives good compression while maintaining readability
    compress_pdf_via_image(input_file, output_file, dpi=100, image_quality=50)
