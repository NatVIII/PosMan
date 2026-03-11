"""
PDF processing engine for Poster Management System.

Handles bug generation, thumbnail creation, and PDF manipulation.
Based on legacy bug generation script (bug.backup112325.py).
"""

import io
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List

import qrcode
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import portrait
from reportlab.lib.utils import ImageReader

from .config import config_loader

logger = logging.getLogger(__name__)


class PDFProcessorError(Exception):
    """Raised when PDF processing fails."""


class PDFProcessor:
    """Process PDF posters by adding bugs and generating thumbnails."""
    
    def __init__(self, template_config: Optional[Dict[str, Any]] = None):
        """Initialize processor with template configuration."""
        if template_config is None:
            loaded = config_loader.load_template_config()
            template_config = loaded.get('template', {}) if loaded else {}
        self.template_config = template_config or {}
        self.global_config = self.template_config.get('global', {})
        self.bug_config = self.global_config.get('bug', {})
        
        # Load logo if path exists
        self.logo_image = None
        logo_config = self.global_config.get('logo', {})
        logo_path = logo_config.get('path')
        if logo_path and Path(logo_path).exists():
            try:
                self.logo_image = Image.open(logo_path).convert("RGBA")
                logger.info(f"Loaded logo from {logo_path}")
            except Exception as e:
                logger.warning(f"Failed to load logo from {logo_path}: {e}")
        
        # Font cache
        self._font_cache = {}
        
        # Page size (12x18 inches in points: 864 x 1296)
        self.PAGE_W_PT = 864
        self.PAGE_H_PT = 1296
    
    def process_poster(self, source_pdf_path: Path, output_pdf_path: Path,
                       poster_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a poster PDF by adding bug and generating thumbnail.
        
        Args:
            source_pdf_path: Path to source PDF file
            output_pdf_path: Path where processed PDF should be saved
            poster_id: Unique poster identifier
            metadata: Poster metadata (title, price, categories, source, etc.)
        
        Returns:
            Dictionary with processing results (thumbnail_path, dimensions, etc.)
        """
        # Ensure output directory exists
        output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if source PDF exists
        if not source_pdf_path.exists():
            raise PDFProcessorError(f"Source PDF not found: {source_pdf_path}")
        
        logger.info(f"Processing poster {poster_id} from {source_pdf_path}")
        
        # Generate bug image
        bug_image = self._build_bug_image(poster_id, metadata)
        
        # Create PDF page with bug image
        bug_pdf_bytes = self._bug_image_to_pdf_page(bug_image)
        
        # Append bug page to original PDF
        self._append_bug_page_to_pdf(source_pdf_path, output_pdf_path, bug_pdf_bytes)
        
        # Generate thumbnail
        thumbnail_path = self._generate_thumbnail(output_pdf_path, poster_id)
        
        # Determine poster orientation and dimensions
        dimensions = self._get_pdf_dimensions(output_pdf_path)
        
        # Rotate if landscape and configured for horizontal orientation
        orientation = dimensions[2]
        if (orientation == 'landscape' and 
            self.bug_config.get('horizontal_orientation', 'landscape') == 'landscape'):
            rotated_path = output_pdf_path.with_stem(f"{poster_id}_rotated")
            self.rotate_for_landscape(output_pdf_path, rotated_path)
            # Replace original with rotated
            rotated_path.replace(output_pdf_path)
            logger.info(f"Rotated landscape poster {poster_id}")
        
        return {
            'thumbnail_path': thumbnail_path,
            'dimensions': dimensions,
            'bug_applied': True,
            'poster_id': poster_id,
            'processed_at': datetime.now().isoformat(),
        }
    
    def _find_font_path(self) -> Optional[str]:
        """Find a TrueType font on the system."""
        candidates = [
            "/home/natbf/.fonts/BentonSans.otf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path
        return None
    
    def _load_font(self, size_px: int):
        """Load font with caching."""
        if size_px in self._font_cache:
            return self._font_cache[size_px]
        
        path = self._find_font_path()
        if path:
            try:
                font = ImageFont.truetype(path, size_px)
                self._font_cache[size_px] = font
                return font
            except Exception as e:
                logger.warning(f"Failed to load font from {path}: {e}")
        
        # Fallback to default bitmap font
        logger.warning("No TrueType font found. Using bitmap fallback (won't scale well).")
        font = ImageFont.load_default()
        self._font_cache[size_px] = font
        return font
    
    def _make_qr(self, data: str, box_size: int, border: int) -> Image.Image:
        """Generate QR code image."""
        qr = qrcode.QRCode(
            version=None,  # auto smallest version that fits
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=box_size,
            border=border,
        )
        qr.add_data(data)
        qr.make(fit=True)
        return qr.make_image(fill_color="black", back_color="white").convert("RGB")
    
    def _load_logo_fit_width(self, target_w: int) -> Optional[Image.Image]:
        """Load and resize logo to fit target width."""
        if not self.logo_image:
            return None
        
        logo = self.logo_image
        w, h = logo.size
        if w == 0 or h == 0:
            return None
        
        scale = target_w / w
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        return logo.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    def _build_bug_image(self, poster_id: str, metadata: Dict[str, Any]) -> Image.Image:
        """Build bug image with QR code, text, and logo."""
        # Get configuration values
        font_size = self.bug_config.get('font_size', 18)
        qr_box_size = self.bug_config.get('qr_box_size', 10)
        qr_border = self.bug_config.get('qr_border', 4)
        text_top_padding = self.bug_config.get('text_top_padding', 12)
        text_side_margin = self.bug_config.get('text_side_margin', 10)
        bottom_padding = self.bug_config.get('bottom_padding', 12)
        logo_top_padding = self.bug_config.get('logo_top_padding', 10)
        line_spacing = self.bug_config.get('line_spacing', 2)
        logo_width_ratio = self.bug_config.get('logo_width_ratio', 0.8)
        
        # Get metadata
        source = metadata.get('source', '')
        categories = metadata.get('categories', '')
        length_val = metadata.get('length', '')
        attribution = metadata.get('attribution', '')
        title = metadata.get('title', '')
        price = metadata.get('price', self.global_config.get('price', 12.00))
        seller = metadata.get('seller', self.global_config.get('seller', ''))
        slogans = metadata.get('slogans', self.global_config.get('slogans', []))
        
        # 1) Generate QR code
        qr_img = self._make_qr(poster_id, qr_box_size, qr_border)
        qr_w, qr_h = qr_img.size
        
        # 2) Build text lines
        lines = [
            f"ID: {poster_id}",
            f"Price: ${price:.2f}",
            f"Seller: {seller}",
        ]
        
        if title:
            lines.insert(1, f"Title: {title}")
        if source:
            lines.append(f"Source: {source}")
        if categories:
            lines.append(f"Categories: {categories}")
        if length_val:
            lines.append(f"Length (11x17): {length_val}")
        if attribution:
            lines.append(f"Attribution: {attribution}")
        
        # Add slogans
        if slogans:
            lines.append("")  # blank line
            lines.extend(slogans)
        
        label = "\n".join(lines)
        
        # 3) Load font and measure text
        font = self._load_font(font_size)
        
        # Measure text precisely
        tmp = Image.new("RGB", (1, 1), "white")
        draw_tmp = ImageDraw.Draw(tmp)
        bbox = draw_tmp.multiline_textbbox(
            (0, 0), label, font=font, align="center", spacing=line_spacing
        )
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        # 4) Calculate final dimensions
        final_w = max(qr_w, text_w + 2 * text_side_margin)
        final_h = qr_h + text_top_padding + text_h + bottom_padding
        
        # Optional logo scaled to ratio of final width
        logo_img = None
        if self.logo_image:
            target_logo_w = max(1, int(round(final_w * logo_width_ratio)))
            logo_img = self._load_logo_fit_width(target_logo_w)
            if logo_img:
                lw, lh = logo_img.size
                final_h += logo_top_padding + lh
        
        final_w = int(final_w)
        final_h = int(final_h)
        
        # 5) Compose bug image
        bug = Image.new("RGB", (final_w, final_h), "white")
        
        # Paste QR centered horizontally
        qr_x = (final_w - qr_w) // 2
        bug.paste(qr_img, (qr_x, 0))
        
        # Draw text
        draw = ImageDraw.Draw(bug)
        text_left = (final_w - text_w) // 2
        text_top = qr_h + text_top_padding
        draw.multiline_text(
            (text_left, text_top),
            label,
            font=font,
            fill="black",
            align="center",
            spacing=line_spacing,
        )
        
        # Paste logo if present
        if logo_img:
            lw, lh = logo_img.size
            logo_x = (final_w - lw) // 2
            logo_y = text_top + text_h + logo_top_padding
            
            # Handle transparency
            if logo_img.mode == "RGBA":
                bg = Image.new("RGB", (lw, lh), "white")
                bg.paste(logo_img, mask=logo_img.split()[3])
                logo_img = bg
            
            bug.paste(logo_img, (logo_x, logo_y))
        
        logger.debug(f"Built bug image {poster_id}: {final_w}x{final_h} px")
        return bug
    
    def _bug_image_to_pdf_page(self, bug_img: Image.Image) -> bytes:
        """Convert bug image to single-page PDF (bytes)."""
        # Get configuration
        dpi = self.bug_config.get('dpi', 300)
        bug_width_in = self.bug_config.get('width_in', 2.0)
        page_margin_in = self.bug_config.get('page_margin_in', 0.5)
        bug_top_frac = self.bug_config.get('top_frac', 0.1)
        
        # margins & available area
        margin_pt = page_margin_in * 72.0
        avail_w_pt = max(1.0, self.PAGE_W_PT - 2 * margin_pt)
        avail_h_pt = max(1.0, self.PAGE_H_PT - 2 * margin_pt)
        
        # target draw width (points)
        desired_w_pt = min(bug_width_in * 72.0, avail_w_pt)
        
        # aspect-preserving height
        bw, bh = bug_img.size
        if bw == 0 or bh == 0:
            raise PDFProcessorError("Bug image has zero dimension.")
        aspect = bh / float(bw)
        desired_h_pt = desired_w_pt * aspect
        if desired_h_pt > avail_h_pt:
            desired_h_pt = avail_h_pt
            desired_w_pt = desired_h_pt / aspect
        
        # raster at DPI for crisp output
        target_w_px = max(1, int(round((desired_w_pt / 72.0) * dpi)))
        target_h_px = max(1, int(round((desired_h_pt / 72.0) * dpi)))
        if (target_w_px, target_h_px) != bug_img.size:
            bug_img = bug_img.resize((target_w_px, target_h_px), Image.Resampling.LANCZOS)
        
        # horizontal center
        x = (self.PAGE_W_PT - desired_w_pt) / 2.0
        
        # vertical placement
        if bug_top_frac is None:
            # centered vertically
            y = (self.PAGE_H_PT - desired_h_pt) / 2.0
        else:
            # clamp fraction and compute top edge position from top
            f = max(0.0, min(1.0, float(bug_top_frac)))
            top_edge_from_top = f * self.PAGE_H_PT
            # convert to y (bottom-left origin): y = (page_h_pt - top_edge_from_top) - desired_h_pt
            y = (self.PAGE_H_PT - top_edge_from_top) - desired_h_pt
            # respect bottom margin
            y = max(y, margin_pt)
            # also ensure we don't cross the top margin
            y = min(y, self.PAGE_H_PT - margin_pt - desired_h_pt)
        
        # render
        png_bytes = io.BytesIO()
        bug_img.save(png_bytes, format="PNG")
        png_bytes.seek(0)
        
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=portrait((self.PAGE_W_PT, self.PAGE_H_PT)))
        c.drawImage(
            ImageReader(png_bytes),
            x, y,
            width=desired_w_pt,
            height=desired_h_pt,
            preserveAspectRatio=True,
            mask="auto",
        )
        c.showPage()
        c.save()
        buf.seek(0)
        return buf.read()
    
    def _append_bug_page_to_pdf(self, original_pdf_path: Path, output_pdf_path: Path, 
                                bug_pdf_bytes: bytes) -> None:
        """Append bug page to original PDF."""
        # Read original PDF
        reader = PdfReader(str(original_pdf_path))
        writer = PdfWriter()
        
        # Copy original pages
        for page in reader.pages:
            writer.add_page(page)
        
        # Append bug page
        extra_reader = PdfReader(io.BytesIO(bug_pdf_bytes))
        writer.add_page(extra_reader.pages[0])
        
        # Save
        with open(output_pdf_path, "wb") as f:
            writer.write(f)
        
        logger.debug(f"Appended bug page to {output_pdf_path}")
    
    def _generate_thumbnail(self, pdf_path: Path, poster_id: str) -> Path:
        """Generate thumbnail image from first page of PDF."""
        # Try to get thumbnail directory from config, fallback to relative path
        thumbnail_dir = Path(self.global_config.get('thumbnail_dir', 'data/thumbnails'))
        
        # If path is absolute and doesn't exist, try relative to current directory
        if thumbnail_dir.is_absolute() and not thumbnail_dir.parent.exists():
            # Fallback to relative path
            thumbnail_dir = Path('data/thumbnails')
        
        thumbnail_dir.mkdir(parents=True, exist_ok=True)
        
        thumbnail_path = thumbnail_dir / f"{poster_id}.jpg"
        
        try:
            # Try using pdf2image if available
            try:
                from pdf2image import convert_from_path
                
                # Convert first page to image
                images = convert_from_path(
                    str(pdf_path),
                    dpi=72,
                    first_page=1,
                    last_page=1,
                    fmt='jpeg',
                    thread_count=1
                )
                
                if images:
                    # Resize to thumbnail dimensions (300x400 max, maintain aspect)
                    img = images[0]
                    img.thumbnail((300, 400), Image.Resampling.LANCZOS)
                    
                    # Add poster ID watermark in corner
                    draw = ImageDraw.Draw(img)
                    try:
                        font = self._load_font(14)
                        draw.text((10, 10), poster_id, fill='white', font=font, stroke_width=2, stroke_fill='black')
                    except:
                        # Fallback if font loading fails
                        draw.text((10, 10), poster_id, fill='white')
                    
                    img.save(thumbnail_path, 'JPEG', quality=85, optimize=True)
                    logger.debug(f"Generated thumbnail at {thumbnail_path} from PDF")
                    return thumbnail_path
                    
            except ImportError:
                logger.warning("pdf2image not available, using placeholder")
            except Exception as e:
                logger.warning(f"pdf2image conversion failed: {e}, using placeholder")
            
            # Fallback: create placeholder
            img = Image.new('RGB', (300, 400), color='lightgray')
            draw = ImageDraw.Draw(img)
            draw.text((50, 150), f"Poster: {poster_id}", fill='black')
            draw.text((50, 180), "Thumbnail preview", fill='gray')
            img.save(thumbnail_path, 'JPEG', quality=85)
            logger.debug(f"Generated placeholder thumbnail at {thumbnail_path}")
            
        except Exception as e:
            logger.error(f"Failed to generate thumbnail: {e}")
            # Create minimal placeholder on error
            img = Image.new('RGB', (300, 400), color='lightgray')
            img.save(thumbnail_path, 'JPEG')
        
        return thumbnail_path
    
    def _get_pdf_dimensions(self, pdf_path: Path) -> Tuple[int, int, str]:
        """Get PDF dimensions and orientation."""
        reader = PdfReader(str(pdf_path))
        page = reader.pages[0]
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        
        orientation = 'portrait' if height > width else 'landscape'
        return int(width), int(height), orientation
    
    def rotate_for_landscape(self, pdf_path: Path, output_path: Path) -> None:
        """Rotate PDF pages 90° for landscape orientation."""
        reader = PdfReader(str(pdf_path))
        writer = PdfWriter()
        
        for page in reader.pages:
            page.rotate(90)
            writer.add_page(page)
        
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        logger.debug(f"Rotated PDF saved to {output_path}")
    
    def batch_process_csv(self, csv_path: Path, pdf_directory: Path, 
                          output_directory: Path) -> Dict[str, Any]:
        """
        Batch process PDFs using CSV metadata (legacy compatibility).
        
        Args:
            csv_path: Path to CSV file with poster metadata
            pdf_directory: Directory containing source PDFs
            output_directory: Directory for processed PDFs
        
        Returns:
            Processing summary
        """
        if not csv_path.exists():
            raise PDFProcessorError(f"CSV file not found: {csv_path}")
        
        if not pdf_directory.exists():
            raise PDFProcessorError(f"PDF directory not found: {pdf_directory}")
        
        output_directory.mkdir(parents=True, exist_ok=True)
        
        # Load CSV
        try:
            df = pd.read_csv(csv_path)
            # Normalize column names
            df.columns = df.columns.str.strip().str.replace(" ", "_").str.replace("(", "").str.replace(")", "")
            if "ID" not in df.columns:
                raise PDFProcessorError("CSV must contain an 'ID' column.")
            
            # Create lookup dictionary
            id_to_row = {str(row["ID"]): row for _, row in df.iterrows()}
        except Exception as e:
            raise PDFProcessorError(f"Failed to load CSV: {e}")
        
        # Process each PDF in directory
        processed = []
        errors = []
        pdf_files = list(pdf_directory.glob("*.pdf"))
        
        for pdf_file in pdf_files:
            poster_id = pdf_file.stem
            row = id_to_row.get(poster_id, {})
            
            try:
                # Safely extract and convert price
                price_str = row.get('Price')
                if price_str is None or pd.isna(price_str):
                    price_default = self.global_config.get('price')
                    price_value = float(price_default) if price_default is not None else 12.00
                else:
                    price_value = float(price_str)
                
                metadata = {
                    'source': str(row.get('Source', '')),
                    'categories': str(row.get('Categories', '')),
                    'length': str(row.get('Length_11x17', '')),
                    'attribution': str(row.get('Attribution', '')),
                    'title': str(row.get('Title', '')),
                    'price': price_value,
                }
                
                output_path = output_directory / f"{poster_id}.pdf"
                result = self.process_poster(pdf_file, output_path, poster_id, metadata)
                processed.append(result)
                logger.info(f"Processed {poster_id}")
                
            except Exception as e:
                errors.append({'poster_id': poster_id, 'error': str(e)})
                logger.error(f"Failed to process {poster_id}: {e}")
        
        return {
            'total_pdfs': len(pdf_files),
            'processed': len(processed),
            'errors': len(errors),
            'processed_ids': [p['poster_id'] for p in processed],
            'error_details': errors,
        }