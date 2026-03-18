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
from qrcode import constants
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import portrait
from reportlab.lib.utils import ImageReader
from pdf2image import convert_from_path, convert_from_bytes

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
        
        # Load bleed configuration
        try:
            bleed_config = config_loader.load_bleed_template_config()
            self.bleed_config = bleed_config.get('bleed_template', {})
            logger.info(f"Loaded bleed config: {self.bleed_config}")
            # Debug print to console as well
            print(f"\n=== PDF PROCESSOR CONFIG LOADING ===")
            print(f"Bleed config dict: {self.bleed_config}")
            print(f"Trim values: top={self.bleed_config.get('trim_top')}, "
                  f"bottom={self.bleed_config.get('trim_bottom')}, "
                  f"left={self.bleed_config.get('trim_left')}, "
                  f"right={self.bleed_config.get('trim_right')}")
            print(f"=====================================\n")
        except Exception as e:
            logger.warning(f"Failed to load bleed config: {e}")
            self.bleed_config = {}
        
        # Page size from bleed config or default (12x18 inches in points: 864 x 1296)
        paper_width_in = self.bleed_config.get('paper_width', 12.0)
        paper_height_in = self.bleed_config.get('paper_height', 18.0)
        self.PAGE_W_PT = int(paper_width_in * 72)  # 72 points per inch
        self.PAGE_H_PT = int(paper_height_in * 72)
        print(f"Paper size: {paper_width_in}x{paper_height_in} in = {self.PAGE_W_PT}x{self.PAGE_H_PT} pts")
        
        # Bleed and safe margins (legacy)
        self.bleed_margin_in = self.bleed_config.get('bleed_margin', 0.125)
        self.safe_margin_in = self.bleed_config.get('safe_margin', 0.25)
        self.standard_lengths = self.bleed_config.get('standard_lengths', [11.0, 13.75, 17.0])
        
        # Trim lines (new, preferred over safe_margin)
        self.trim_top_in = self.bleed_config.get('trim_top', self.safe_margin_in)
        self.trim_bottom_in = self.bleed_config.get('trim_bottom', self.safe_margin_in)
        self.trim_left_in = self.bleed_config.get('trim_left', self.safe_margin_in)
        self.trim_right_in = self.bleed_config.get('trim_right', self.safe_margin_in)
        
        # Convert to points
        self.bleed_margin_pt = int(self.bleed_margin_in * 72)
        self.safe_margin_pt = int(self.safe_margin_in * 72)
        self.trim_top_pt = int(self.trim_top_in * 72)
        self.trim_bottom_pt = int(self.trim_bottom_in * 72)
        self.trim_left_pt = int(self.trim_left_in * 72)
        self.trim_right_pt = int(self.trim_right_in * 72)
        
        # Content area (within trim lines)
        self.content_width_pt = self.PAGE_W_PT - self.trim_left_pt - self.trim_right_pt
        self.content_height_pt = self.PAGE_H_PT - self.trim_top_pt - self.trim_bottom_pt
    
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
        
        # Apply preview settings if provided
        preview_settings = metadata.get('preview_settings')
        effective_source_path = source_pdf_path
        intermediate_path = None
        if preview_settings:
            logger.info(f"Applying preview settings for {poster_id}: {preview_settings}")
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                intermediate_path = Path(tmp.name)
            try:
                self._apply_preview_settings(source_pdf_path, intermediate_path, preview_settings)
                effective_source_path = intermediate_path
            except Exception as e:
                logger.warning(f"Failed to apply preview settings: {e}. Using original PDF.")
                if intermediate_path and intermediate_path.exists():
                    intermediate_path.unlink()
                intermediate_path = None
        
        # Generate bug image
        bug_image = self._build_bug_image(poster_id, metadata)
        
        # Create PDF page with bug image
        bug_pdf_bytes = self._bug_image_to_pdf_page(bug_image)
        
        # Append bug page to effective source PDF
        self._append_bug_page_to_pdf(effective_source_path, output_pdf_path, bug_pdf_bytes)
        
        # Clean up intermediate PDF if created
        if intermediate_path and intermediate_path.exists():
            intermediate_path.unlink()
        
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
            error_correction=constants.ERROR_CORRECT_L,
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
    
    def _create_background_page(self, fill_color: str) -> bytes:
        """Create a single-page PDF with solid fill color background."""
        from reportlab.lib.colors import HexColor, white
        from reportlab.lib.pagesizes import portrait as portrait_size
        
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=portrait_size((self.PAGE_W_PT, self.PAGE_H_PT)))
        
        try:
            color = HexColor(fill_color)
        except:
            color = white
        
        c.setFillColor(color)
        c.rect(0, 0, self.PAGE_W_PT, self.PAGE_H_PT, fill=1, stroke=0)
        c.showPage()
        c.save()
        buf.seek(0)
        return buf.read()
    
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
        # Ensure price is a float for formatting
        if price is not None:
            try:
                price = float(price)
            except (ValueError, TypeError):
                price = 0.0
        else:
            price = 0.0
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
    
    def _generate_thumbnail(self, source, poster_id: str) -> Path:
        """Generate thumbnail from source (Path to PDF/image file or PIL Image)."""
        # Try to get thumbnail directory from config, fallback to absolute /data/thumbnails
        thumbnail_dir = Path(self.global_config.get('thumbnail_dir', '/data/thumbnails'))
        # Ensure directory is within /data for security
        data_path = Path('/data')
        try:
            # Resolve to absolute path and check if it's within data_path
            resolved = thumbnail_dir.resolve()
            if data_path.exists() and not resolved.is_relative_to(data_path):
                # Fallback to relative path within current working directory
                thumbnail_dir = Path('data/thumbnails')
        except (RuntimeError, ValueError):
            # If resolution fails (e.g., infinite symlink), use default
            thumbnail_dir = Path('data/thumbnails')
        thumbnail_dir.mkdir(parents=True, exist_ok=True)
        
        thumbnail_path = thumbnail_dir / f"{poster_id}.jpg"
        
        try:
            img = None
            if isinstance(source, Path):
                # Source is a file path
                if source.suffix.lower() == '.pdf':
                    # Convert PDF to image using pdf2image
                    try:
                        from pdf2image import convert_from_path
                        images = convert_from_path(
                            str(source),
                            dpi=72,
                            first_page=1,
                            last_page=1,
                            fmt='jpeg',
                            thread_count=1
                        )
                        if images:
                            img = images[0]
                    except ImportError:
                        logger.warning("pdf2image not available, using placeholder")
                    except Exception as e:
                        logger.warning(f"pdf2image conversion failed: {e}, using placeholder")
                else:
                    # Assume image file
                    try:
                        img = Image.open(source)
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                    except Exception as e:
                        logger.warning(f"Failed to open image file: {e}")
            else:
                # Assume source is PIL Image
                img = source
            
            if img is None:
                # Fallback: create placeholder
                img = Image.new('RGB', (300, 400), color='lightgray')
                draw = ImageDraw.Draw(img)
                draw.text((50, 150), f"Poster: {poster_id}", fill='black')
                draw.text((50, 180), "Thumbnail preview", fill='gray')
                img.save(thumbnail_path, 'JPEG', quality=85)
                logger.debug(f"Generated placeholder thumbnail at {thumbnail_path}")
                return thumbnail_path
            
            # Resize to thumbnail dimensions (300x400 max, maintain aspect)
            img.thumbnail((300, 400), Image.Resampling.LANCZOS)
            
            # Add poster ID watermark in corner
            try:
                draw = ImageDraw.Draw(img)
                font = self._load_font(14)
                draw.text((10, 10), poster_id, fill='white', font=font, stroke_width=2, stroke_fill='black')
            except Exception:
                # Fallback if font loading fails
                draw.text((10, 10), poster_id, fill='white')
            
            img.save(thumbnail_path, 'JPEG', quality=85, optimize=True)
            logger.debug(f"Generated thumbnail at {thumbnail_path}")
            return thumbnail_path
            
        except Exception as e:
            logger.error(f"Failed to generate thumbnail: {e}")
            # Create minimal placeholder on error
            img = Image.new('RGB', (300, 400), color='lightgray')
            img.save(thumbnail_path, 'JPEG')
            return thumbnail_path
    
    def _apply_preview_settings(self, source_pdf_path: Path, output_pdf_path: Path, preview_settings: Dict[str, Any]) -> None:
        """
        Apply preview settings (bleed, alignment, fill color, length snapping, orientation) to PDF.
        Transforms source PDF according to preview settings and bleed configuration.
        Uses PNG-based processing for accurate positioning.
        """
        logger.info(f"Applying preview settings via PNG: {preview_settings}")
        
        # Extract settings with defaults
        alignment = preview_settings.get('alignment', 'middle')
        length_snap = preview_settings.get('length_snap', '')
        orientation_setting = preview_settings.get('orientation', 'auto')
        rotation = int(preview_settings.get('rotation', 0))
        fill_color = preview_settings.get('fill_color', '#ffffff')
        page_number = preview_settings.get('page_number', 1)
        
        # Validate page number
        reader = PdfReader(str(source_pdf_path))
        if page_number < 1 or page_number > len(reader.pages):
            page_number = 1  # Default to first page
        
        # Convert source PDF page to PNG
        png_image = self.convert_to_png(source_pdf_path, dpi=300, page_number=page_number)
        
        # Process PNG with trim and alignment
        processed_image = self.process_png_with_trim(png_image, preview_settings, fill_color)
        
        # Save processed image as PDF
        processed_image.save(output_pdf_path, format='PDF', resolution=300.0)
        
        logger.info(f"Applied preview settings via PNG to {output_pdf_path}")
        
        # Debug logging with dimensions
        paper_width_in = self.PAGE_W_PT / 72.0
        paper_height_in = self.PAGE_H_PT / 72.0
        logger.debug(f"Paper size: {paper_width_in:.2f}x{paper_height_in:.2f} in")
        logger.debug(f"Trim: T={self.trim_top_in:.2f}, B={self.trim_bottom_in:.2f}, "
                     f"L={self.trim_left_in:.2f}, R={self.trim_right_in:.2f} in")
        logger.debug(f"Alignment: {alignment}, Orientation: {orientation_setting}, "
                     f"Length snap: {length_snap}, Fill color: {fill_color}")
    
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
     
    def convert_image_to_pdf(self, image_file) -> io.BytesIO:
        """Convert uploaded image file to PDF bytes."""
        try:
            # Open image
            img = Image.open(image_file)
            # Convert to RGB if necessary (e.g., PNG with alpha)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Create PDF bytes
            pdf_bytes = io.BytesIO()
            img.save(pdf_bytes, format='PDF', resolution=300.0)
            pdf_bytes.seek(0)
            return pdf_bytes
        except Exception as e:
            logger.error(f"Failed to convert image to PDF: {e}")
            raise PDFProcessorError(f"Image conversion failed: {e}")
    
    def convert_to_png(self, source_path: Path, dpi: int = 300, page_number: int = 1) -> Image.Image:
        """Convert any file (PDF or image) to PNG Image."""
        try:
            if source_path.suffix.lower() == '.pdf':
                # Convert PDF to image using pdf2image
                images = convert_from_path(str(source_path), dpi=dpi, first_page=page_number, last_page=page_number)
                if not images:
                    raise PDFProcessorError(f"Failed to convert PDF to image: {source_path}")
                return images[0]  # Return requested page
            else:
                # Open image file directly
                img = Image.open(source_path)
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                return img
        except Exception as e:
            logger.error(f"Failed to convert to PNG: {e}")
            raise PDFProcessorError(f"PNG conversion failed: {e}")
    
    def process_png_with_trim(self, png_image: Image.Image, preview_settings: Dict[str, Any], fill_color: str = '#ffffff') -> Image.Image:
        """Process PNG image with trim lines and alignment."""
        try:
            # Extract settings
            alignment = preview_settings.get('alignment', 'middle')
            length_snap = preview_settings.get('length_snap', '')
            orientation_setting = preview_settings.get('orientation', 'auto')
            rotation = int(preview_settings.get('rotation', 0))
            
            # Get dimensions in pixels (assuming image is at target DPI)
            img_width_px = png_image.width
            img_height_px = png_image.height
            
            # Determine initial orientation (for auto-detection)
            source_orientation = 'portrait' if img_height_px > img_width_px else 'landscape'
            
            # Step 1: Apply rotation if specified
            if rotation != 0:
                # Rotate image by specified angle (must be multiple of 90)
                if rotation in (90, 270):
                    png_image = png_image.rotate(rotation, expand=True)
                else:  # 180
                    png_image = png_image.rotate(rotation)
                # Swap width/height if rotation is 90 or 270 degrees
                if rotation % 180 != 0:
                    img_width_px, img_height_px = img_height_px, img_width_px
            else:
                # Apply orientation-based rotation (legacy behavior)
                target_orientation = orientation_setting
                if orientation_setting == 'auto':
                    target_orientation = source_orientation
                needs_rotation = (
                    (target_orientation == 'landscape' and source_orientation == 'portrait') or
                    (target_orientation == 'portrait' and source_orientation == 'landscape')
                )
                if needs_rotation:
                    png_image = png_image.rotate(90, expand=True)
                    img_width_px, img_height_px = img_height_px, img_width_px
            
            # Step 2: Apply length snapping if specified
            if length_snap:
                try:
                    target_length_in = float(length_snap)
                    dpi = 300
                    target_height_px = int(target_length_in * dpi)
                    # Scale width proportionally to maintain aspect ratio
                    scale_factor = target_height_px / img_height_px
                    img_width_px = int(img_width_px * scale_factor)
                    img_height_px = target_height_px
                    # Resize image
                    png_image = png_image.resize((img_width_px, img_height_px), Image.Resampling.LANCZOS)
                except ValueError:
                    logger.warning(f"Invalid length_snap value: {length_snap}")
            
            # Paper dimensions at 300 DPI (default)
            dpi = 300
            paper_width_in = self.PAGE_W_PT / 72.0
            paper_height_in = self.PAGE_H_PT / 72.0
            paper_width_px = int(paper_width_in * dpi)
            paper_height_px = int(paper_height_in * dpi)
            
            # Trim margins in pixels (using instance variables)
            trim_top_px = int(self.trim_top_in * dpi)
            trim_bottom_px = int(self.trim_bottom_in * dpi)
            trim_left_px = int(self.trim_left_in * dpi)
            trim_right_px = int(self.trim_right_in * dpi)
            
            # Content area within trim lines
            content_width_px = paper_width_px - trim_left_px - trim_right_px
            content_height_px = paper_height_px - trim_top_px - trim_bottom_px
            
            # Scale image to fit within content area (maintain aspect ratio)
            scale_x = content_width_px / img_width_px
            scale_y = content_height_px / img_height_px
            scale = min(scale_x, scale_y)
            
            scaled_width_px = int(img_width_px * scale)
            scaled_height_px = int(img_height_px * scale)
            
            # Resize image
            if scale != 1.0:
                png_image = png_image.resize((scaled_width_px, scaled_height_px), Image.Resampling.LANCZOS)
            
            # Horizontal centering within trim lines
            offset_x_px = trim_left_px + (content_width_px - scaled_width_px) // 2
            
            # Vertical alignment relative to trim lines
            if alignment == 'top':
                offset_y_px = trim_top_px
            elif alignment == 'bottom':
                offset_y_px = paper_height_px - trim_bottom_px - scaled_height_px
            else:  # middle (default)
                offset_y_px = trim_top_px + (content_height_px - scaled_height_px) // 2
            
            # Create canvas with fill color
            if fill_color.lower() == '#ffffff' or fill_color.lower() == 'ffffff':
                canvas_color = (255, 255, 255)
            else:
                # Parse hex color
                hex_color = fill_color.lstrip('#')
                canvas_color = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            
            canvas_img = Image.new('RGB', (paper_width_px, paper_height_px), canvas_color)
            
            # Paste scaled image onto canvas
            canvas_img.paste(png_image, (offset_x_px, offset_y_px))
            
            # Debug logging
            logger.debug(f"PNG processing: paper={paper_width_px}x{paper_height_px} px, "
                        f"trim=[T={trim_top_px}, B={trim_bottom_px}, L={trim_left_px}, R={trim_right_px}] px, "
                        f"content={content_width_px}x{content_height_px} px, "
                        f"scaled={scaled_width_px}x{scaled_height_px} px, "
                        f"offset=({offset_x_px}, {offset_y_px}) px, alignment={alignment}, "
                        f"orientation={orientation_setting}, length_snap={length_snap}")
            
            print(f"\n=== PNG PROCESSING DEBUG ===")
            print(f"Paper: {paper_width_px}x{paper_height_px} px")
            print(f"Trim: T={trim_top_px}, B={trim_bottom_px}, L={trim_left_px}, R={trim_right_px} px")
            print(f"Content area: {content_width_px}x{content_height_px} px")
            print(f"Image scaled: {scaled_width_px}x{scaled_height_px} px")
            print(f"Offset: ({offset_x_px}, {offset_y_px}) px")
            print(f"Alignment: {alignment}")
            print(f"Orientation: {orientation_setting}")
            print(f"Length snap: {length_snap}")
            print(f"============================\n")
            
            return canvas_img
        except Exception as e:
            logger.error(f"Failed to process PNG with trim: {e}")
            raise PDFProcessorError(f"PNG processing failed: {e}")
    
    def process_poster_via_png(self, source_path: Path, output_pdf_path: Path, 
                               poster_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Process poster using PNG intermediate for reliable positioning."""
        try:
            # Extract preview settings from metadata
            preview_settings = metadata.get('preview_settings', {})
            fill_color = preview_settings.get('fill_color', '#ffffff')
            
            # Step 1: Convert source to PNG
            png_image = self.convert_to_png(source_path, dpi=300)
            
            # Step 2: Process PNG with trim and alignment
            processed_image = self.process_png_with_trim(png_image, preview_settings, fill_color)
            
            # Step 3: Add bug overlay (existing bug generation)
            bug_image = self._build_bug_image(poster_id, metadata)
            
            # Step 4: Create final PDF with bug page
            # First, save processed image as PDF
            processed_pdf_bytes = io.BytesIO()
            processed_image.save(processed_pdf_bytes, format='PDF', resolution=300.0)
            processed_pdf_bytes.seek(0)
            
            # Create bug page PDF
            bug_pdf_bytes = self._create_bug_page_pdf(bug_image)
            
            # Combine processed page and bug page
            writer = PdfWriter()
            
            # Add processed page
            processed_reader = PdfReader(processed_pdf_bytes)
            writer.add_page(processed_reader.pages[0])
            
            # Add bug page
            bug_reader = PdfReader(io.BytesIO(bug_pdf_bytes))
            writer.add_page(bug_reader.pages[0])
            
            # Save output PDF
            with open(output_pdf_path, 'wb') as f:
                writer.write(f)
            
            # Generate thumbnail from processed image (without bug)
            thumbnail_path = self._generate_thumbnail(processed_image, poster_id)
            
            # Get dimensions from processed image
            width_in = processed_image.width / 300.0
            height_in = processed_image.height / 300.0
            orientation = 'portrait' if height_in > width_in else 'landscape'
            
            return {
                'dimensions': (width_in, height_in, orientation),
                'thumbnail_path': thumbnail_path,
                'processed_at': datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to process poster via PNG: {e}")
            raise PDFProcessorError(f"PNG-based processing failed: {e}")
    
    def _create_bug_page_pdf(self, bug_image: Image.Image) -> bytes:
        """Convert bug image to PDF page."""
        buf = io.BytesIO()
        bug_image.save(buf, format='PDF', resolution=300.0)
        buf.seek(0)
        return buf.read()
    
