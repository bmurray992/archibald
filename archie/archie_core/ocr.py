"""
ArchieOS OCR Pipeline - Document text extraction and processing
"""
import os
import hashlib
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image
import pytesseract
import magic
from pdfminer.high_level import extract_text as extract_pdf_text
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTTextContainer
import io

logger = logging.getLogger(__name__)


class OCRResult:
    """OCR processing result"""
    
    def __init__(self, success: bool, text: str = "", confidence: float = 0.0, 
                 page_count: int = 1, metadata: Optional[Dict] = None):
        self.success = success
        self.text = text
        self.confidence = confidence
        self.page_count = page_count
        self.metadata = metadata or {}
        self.word_count = len(text.split()) if text else 0


class OCRProcessor:
    """Handles OCR processing for various document types"""
    
    def __init__(self):
        # Supported file types
        self.supported_image_types = {'.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif'}
        self.supported_doc_types = {'.pdf'}
        
        # OCR settings
        self.tesseract_config = '--oem 3 --psm 6'  # Use neural net LSTM engine, assume single uniform block
        
        # Create thumbnails directory
        self.thumbnails_dir = self._get_thumbnails_dir()
        self.thumbnails_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("🔍 OCR processor initialized")
    
    def _get_thumbnails_dir(self) -> Path:
        """Get thumbnails directory path"""
        data_root = os.getenv("ARCHIE_DATA_ROOT", "./storage")
        return Path(data_root) / "thumbnails"
    
    async def process_file(self, file_path: Path, file_content: bytes = None) -> OCRResult:
        """Process a file through OCR pipeline"""
        
        if not file_path.exists() and file_content is None:
            return OCRResult(False, metadata={"error": "File not found and no content provided"})
        
        # Determine file type
        if file_content:
            mime_type = magic.from_buffer(file_content, mime=True)
        else:
            mime_type = magic.from_file(str(file_path), mime=True)
        
        file_extension = file_path.suffix.lower()
        
        try:
            # Route to appropriate processor
            if file_extension in self.supported_image_types or mime_type.startswith('image/'):
                result = await self._process_image(file_path, file_content)
            elif file_extension == '.pdf' or mime_type == 'application/pdf':
                result = await self._process_pdf(file_path, file_content)
            else:
                return OCRResult(False, metadata={
                    "error": f"Unsupported file type: {file_extension} ({mime_type})"
                })
            
            # Generate thumbnail if successful
            if result.success:
                thumbnail_path = await self._generate_thumbnail(file_path, file_content)
                result.metadata['thumbnail_path'] = str(thumbnail_path) if thumbnail_path else None
            
            return result
            
        except Exception as e:
            logger.error(f"OCR processing failed for {file_path}: {e}")
            return OCRResult(False, metadata={"error": str(e)})
    
    async def _process_image(self, file_path: Path, file_content: bytes = None) -> OCRResult:
        """Process image files through OCR"""
        
        try:
            # Load image
            if file_content:
                image = Image.open(io.BytesIO(file_content))
            else:
                image = Image.open(file_path)
            
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Run OCR
            ocr_data = pytesseract.image_to_data(image, config=self.tesseract_config, output_type=pytesseract.Output.DICT)
            text = pytesseract.image_to_string(image, config=self.tesseract_config)
            
            # Calculate confidence (average of word confidences > 0)
            confidences = [int(conf) for conf in ocr_data['conf'] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            # Extract metadata
            metadata = {
                'image_size': image.size,
                'image_mode': image.mode,
                'words_detected': len([w for w in ocr_data['text'] if w.strip()]),
                'avg_confidence': round(avg_confidence, 2)
            }
            
            # Clean up text
            cleaned_text = self._clean_ocr_text(text)
            
            return OCRResult(
                success=bool(cleaned_text.strip()),
                text=cleaned_text,
                confidence=avg_confidence / 100.0,  # Normalize to 0-1
                page_count=1,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Image OCR failed: {e}")
            return OCRResult(False, metadata={"error": str(e)})
    
    async def _process_pdf(self, file_path: Path, file_content: bytes = None) -> OCRResult:
        """Process PDF files through text extraction and OCR if needed"""
        
        try:
            # Try text extraction first (for PDFs with selectable text)
            if file_content:
                pdf_file = io.BytesIO(file_content)
            else:
                pdf_file = str(file_path)
            
            try:
                extracted_text = extract_pdf_text(pdf_file)
                
                # If we got good text extraction, use it
                if extracted_text and len(extracted_text.strip()) > 50:  # Arbitrary threshold
                    
                    # Count pages
                    if file_content:
                        pdf_file_for_pages = io.BytesIO(file_content)
                    else:
                        pdf_file_for_pages = open(file_path, 'rb')
                    
                    try:
                        page_count = len(list(PDFPage.get_pages(pdf_file_for_pages)))
                    except:
                        page_count = 1
                    finally:
                        if hasattr(pdf_file_for_pages, 'close'):
                            pdf_file_for_pages.close()
                    
                    cleaned_text = self._clean_ocr_text(extracted_text)
                    
                    return OCRResult(
                        success=True,
                        text=cleaned_text,
                        confidence=0.95,  # High confidence for extracted text
                        page_count=page_count,
                        metadata={
                            'extraction_method': 'text_extraction',
                            'page_count': page_count
                        }
                    )
                    
            except Exception as text_extract_error:
                logger.warning(f"PDF text extraction failed, will try OCR: {text_extract_error}")
            
            # Fall back to OCR for image-based PDFs
            return await self._pdf_ocr_fallback(file_path, file_content)
            
        except Exception as e:
            logger.error(f"PDF processing failed: {e}")
            return OCRResult(False, metadata={"error": str(e)})
    
    async def _pdf_ocr_fallback(self, file_path: Path, file_content: bytes = None) -> OCRResult:
        """OCR fallback for image-based PDFs using pdf2image"""
        
        try:
            # This would require pdf2image library for full implementation
            # For now, return a placeholder indicating OCR is needed
            
            return OCRResult(
                success=False,
                metadata={
                    "error": "PDF OCR requires pdf2image library",
                    "suggestion": "Install with: pip install pdf2image"
                }
            )
            
        except Exception as e:
            logger.error(f"PDF OCR fallback failed: {e}")
            return OCRResult(False, metadata={"error": str(e)})
    
    async def _generate_thumbnail(self, file_path: Path, file_content: bytes = None) -> Optional[Path]:
        """Generate thumbnail for visual files"""
        
        try:
            # Create thumbnail filename based on file hash
            if file_content:
                file_hash = hashlib.md5(file_content).hexdigest()
            else:
                with open(file_path, 'rb') as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()
            
            thumbnail_filename = f"{file_hash}_thumb.jpg"
            thumbnail_path = self.thumbnails_dir / thumbnail_filename
            
            # Skip if thumbnail already exists
            if thumbnail_path.exists():
                return thumbnail_path
            
            # Generate thumbnail
            if file_content:
                image = Image.open(io.BytesIO(file_content))
            else:
                # For PDFs, we'd need to convert first page to image
                if file_path.suffix.lower() == '.pdf':
                    # Skip PDF thumbnails for now without pdf2image
                    return None
                
                image = Image.open(file_path)
            
            # Create thumbnail (max 300x300, maintain aspect ratio)
            image.thumbnail((300, 300), Image.Resampling.LANCZOS)
            
            # Convert to RGB if needed
            if image.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
                image = background
            
            # Save thumbnail
            image.save(thumbnail_path, 'JPEG', quality=85, optimize=True)
            
            logger.debug(f"Generated thumbnail: {thumbnail_path}")
            return thumbnail_path
            
        except Exception as e:
            logger.warning(f"Thumbnail generation failed: {e}")
            return None
    
    def _clean_ocr_text(self, text: str) -> str:
        """Clean and normalize OCR text"""
        
        if not text:
            return ""
        
        # Remove excessive whitespace
        lines = []
        for line in text.split('\n'):
            cleaned_line = ' '.join(line.split())  # Remove extra spaces
            if cleaned_line:  # Only keep non-empty lines
                lines.append(cleaned_line)
        
        # Join lines with proper spacing
        cleaned_text = '\n'.join(lines)
        
        # Remove common OCR artifacts (optional - be careful not to over-clean)
        # This could be expanded based on common issues you encounter
        
        return cleaned_text.strip()
    
    def get_file_hash(self, file_content: bytes) -> str:
        """Calculate hash for file deduplication"""
        return hashlib.sha256(file_content).hexdigest()
    
    def is_supported_file(self, file_path: Path) -> bool:
        """Check if file type is supported for OCR"""
        file_extension = file_path.suffix.lower()
        return file_extension in (self.supported_image_types | self.supported_doc_types)
    
    async def batch_process(self, file_paths: List[Path]) -> List[Tuple[Path, OCRResult]]:
        """Process multiple files in batch"""
        
        results = []
        
        for file_path in file_paths:
            if not self.is_supported_file(file_path):
                results.append((file_path, OCRResult(False, metadata={
                    "error": f"Unsupported file type: {file_path.suffix}"
                })))
                continue
            
            try:
                result = await self.process_file(file_path)
                results.append((file_path, result))
                
                logger.info(f"Processed {file_path.name}: "
                          f"{'success' if result.success else 'failed'} "
                          f"({result.word_count} words)")
                
            except Exception as e:
                logger.error(f"Batch processing failed for {file_path}: {e}")
                results.append((file_path, OCRResult(False, metadata={"error": str(e)})))
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get OCR processor statistics"""
        
        thumbnail_count = len(list(self.thumbnails_dir.glob("*_thumb.jpg"))) if self.thumbnails_dir.exists() else 0
        
        return {
            'supported_image_types': list(self.supported_image_types),
            'supported_doc_types': list(self.supported_doc_types),
            'thumbnails_generated': thumbnail_count,
            'thumbnails_dir': str(self.thumbnails_dir),
            'tesseract_available': self._check_tesseract_availability()
        }
    
    def _check_tesseract_availability(self) -> bool:
        """Check if Tesseract is available"""
        try:
            pytesseract.get_tesseract_version()
            return True
        except:
            return False


# Global OCR processor instance
_ocr_processor: Optional[OCRProcessor] = None


def get_ocr_processor() -> OCRProcessor:
    """Get or create OCR processor instance"""
    global _ocr_processor
    if _ocr_processor is None:
        _ocr_processor = OCRProcessor()
    return _ocr_processor


# Convenience functions
async def process_document(file_path: Path, file_content: bytes = None) -> OCRResult:
    """Process a document through OCR"""
    processor = get_ocr_processor()
    return await processor.process_file(file_path, file_content)


def is_ocr_supported(file_path: Path) -> bool:
    """Check if file is supported for OCR"""
    processor = get_ocr_processor()
    return processor.is_supported_file(file_path)