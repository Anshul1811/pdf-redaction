import fitz  # PyMuPDF
from io import BytesIO
import cv2
import numpy as np
from PIL import Image
from modules.utils import merge_predictions
import pytesseract



def apply_redaction(text, predictions):
    # Apply redaction to all detected PII
    merged_predictions = merge_predictions(predictions)
    merged_predictions = sorted(merged_predictions, key=lambda x: x['start'], reverse=True)
    redacted_text = list(text)
    for pred in merged_predictions:
        # Skip non-entities
        if pred.get('entity', 'O') != 'O':
            start, end = pred['start'], pred['end']
            for i in range(start, end):
                redacted_text[i] = ''
            redacted_text[start] = '[REDACTED]'
    redacted_text = ''.join(redacted_text)
    return redacted_text

def redact_pdf(pipe, file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    full_text = ""
    ocr_text = ""
    
    # Extract text and process images with OCR
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        
        # Extract regular text
        page_text = page.get_text()
        full_text += page_text + "\n"
        
        # Extract and process images for OCR
        image_list = page.get_images()
        for img_index, img in enumerate(image_list):
            try:
                # Get image data
                xref = img[0]
                pix = fitz.Pixmap(doc, xref)
                
                # Convert to PIL Image
                if pix.n - pix.alpha < 4:  # GRAY or RGB
                    img_data = pix.tobytes("png")
                    pil_image = Image.open(BytesIO(img_data))
                    
                    # Apply OCR using pytesseract (auto-detect path)
                    
                    # Convert PIL image to cv2 format for preprocessing
                    img_cv = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                    
                    # Enhanced preprocessing for better OCR
                    gray = cv2.GaussianBlur(gray, (5, 5), 0)
                    gray = cv2.convertScaleAbs(gray, alpha=2.0, beta=0)
                    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 21, 5)
                    
                    # Extract text from image
                    image_text = pytesseract.image_to_string(thresh, config='--psm 6 --oem 3')
                    if image_text.strip():
                        ocr_text += f"[Image {page_num+1}-{img_index+1}]: {image_text.strip()}\n"
                
                pix = None  # Clean up
                
            except Exception as e:
                continue
    
    # Combine regular text and OCR text for PII detection
    combined_text = full_text + "\n" + ocr_text
    
    # Use mask_text to get proper PII detection with NER + regex
    from modules.model import mask_text
    redacted_text = mask_text(pipe, combined_text)
    
    # For now, just create a simple PDF with redacted text
    # TODO: Implement proper PDF redaction that preserves formatting
    new_doc = fitz.open()
    
    # Split redacted text into pages (roughly 50 lines per page)
    lines = redacted_text.split('\n')
    lines_per_page = 50
    
    for i in range(0, len(lines), lines_per_page):
        page_lines = lines[i:i+lines_per_page]
        page_text = '\n'.join(page_lines)
        
        # Create new page
        new_page = new_doc.new_page(width=595, height=842)  # A4 size
        
        # Insert text with better formatting
        text_rect = fitz.Rect(50, 50, 545, 792)  # Leave margins
        new_page.insert_textbox(text_rect, page_text, fontsize=10, fontname="Helvetica")
    
    # If no text, create at least one page
    if len(new_doc) == 0:
        new_page = new_doc.new_page(width=595, height=842)
        new_page.insert_text((50, 50), "No content to display", fontsize=12)
    
    output = BytesIO()
    new_doc.save(output)
    output.seek(0)
    return output, redacted_text

def redact_txt_file(pipe, file):
    text = file.read().decode('utf-8')
    
    # Use mask_text to get proper PII detection with NER + regex
    from modules.model import mask_text
    return mask_text(pipe, text)

