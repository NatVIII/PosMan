"""
Poster management routes.

Handles upload, listing, viewing, editing, and deleting posters.
"""

import io
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import (
    Blueprint, render_template, request, redirect, url_for, 
    flash, current_app, send_file, abort, jsonify, g
)
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from .auth import login_required, admin_required, upload_allowed
from .poster import PosterManager
from .pdf_processor import PDFProcessor
from .config import config_loader
from .id_generator import id_generator

logger = logging.getLogger(__name__)

bp = Blueprint('posters', __name__, url_prefix='/posters')

def get_poster_manager() -> PosterManager:
    """Get poster manager instance with current app config."""
    data_path = Path(current_app.config.get('DATA_PATH', './data'))
    config = {
        'default_price': 12.00,
        'seller': 'Party For Socialism and Liberation',
    }
    return PosterManager(data_path, config)

def get_pdf_processor():
    """Get PDF processor instance."""
    return PDFProcessor()

def get_taxonomy_data():
    """Get taxonomy data for templates."""
    taxonomy = config_loader.load_taxonomy_config()
    return {
        'sources': taxonomy.get('sources', []),
        'categories': taxonomy.get('categories', []),
    }

def get_bleed_config():
    """Get bleed template configuration for templates."""
    bleed_config = config_loader.load_bleed_template_config()
    result = bleed_config.get('bleed_template', {})
    print(f"\n=== GET_BLEED_CONFIG DEBUG ===")
    print(f"Loaded bleed_config: {bleed_config}")
    print(f"Result (bleed_template key): {result}")
    print(f"Trim values in result: top={result.get('trim_top')}, bottom={result.get('trim_bottom')}, left={result.get('trim_left')}, right={result.get('trim_right')}")
    print(f"==============================\n")
    return result

def get_taxonomy_mappings():
    """Get taxonomy mappings for ID lookup."""
    taxonomy = config_loader.load_taxonomy_config()
    sources = {s['id']: s for s in taxonomy.get('sources', [])}
    categories = {c['id']: c for c in taxonomy.get('categories', [])}
    return sources, categories

def enrich_poster_with_taxonomy(poster):
    """Add display names to poster data using taxonomy mappings."""
    sources_map, categories_map = get_taxonomy_mappings()
    
    # Add source display name
    source_id = poster.get('source', '')
    if source_id in sources_map:
        poster['source_display'] = sources_map[source_id]['name']
    else:
        # Fallback to ID (or original free text)
        poster['source_display'] = source_id
    
    # Add category display name
    category_id = poster.get('categories', '')
    if category_id in categories_map:
        poster['categories_display'] = categories_map[category_id]['name']
    else:
        poster['categories_display'] = category_id
    
    return poster


def convert_image_to_pdf(image_file):
    """Convert uploaded image file to PDF bytes using PDFProcessor."""
    pdf_processor = PDFProcessor()
    return pdf_processor.convert_image_to_pdf(image_file)

def allowed_file(filename: Optional[str]) -> bool:
    """Check if file extension is allowed."""
    if not filename:
        return False
    allowed_extensions = {'pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions


@bp.route('/')
@login_required
def index():
    """List all posters."""
    poster_manager = get_poster_manager()
    poster_ids = poster_manager.storage.list_all()
    
    # Load posters with basic info
    posters = []
    for pid in poster_ids:
        poster = poster_manager.storage.load(pid)
        if poster:
            posters.append(enrich_poster_with_taxonomy(poster))
    
    # Sort by creation date (newest first)
    posters.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    return render_template('posters/index.html', 
                         posters=posters,
                         user=g.user)


@bp.route('/upload', methods=['GET', 'POST'])
@login_required
@upload_allowed
def upload():
    """Upload new poster PDF."""
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'pdf_file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
        
        pdf_file = request.files['pdf_file']
        
        # If user does not select file, browser submits empty file without filename
        if not pdf_file.filename or pdf_file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)
        
        if not allowed_file(pdf_file.filename):
            flash('Only PDF and image files are allowed (PDF, JPG, PNG, GIF, BMP, TIFF)', 'error')
            return redirect(request.url)
        
        # Convert image to PDF if needed
        original_filename = pdf_file.filename.lower()
        if not original_filename.endswith('.pdf'):
            try:
                # Convert image to PDF bytes
                pdf_bytes = convert_image_to_pdf(pdf_file)
                # Create a new FileStorage object with PDF content
                pdf_file = FileStorage(
                    stream=pdf_bytes,
                    filename=original_filename.rsplit('.', 1)[0] + '.pdf',
                    content_type='application/pdf'
                )
                logger.info(f"Converted image {original_filename} to PDF")
            except Exception as e:
                logger.error(f"Failed to convert image to PDF: {e}")
                flash(f'Failed to convert image to PDF: {str(e)}', 'error')
                return redirect(request.url)
        
        # Get taxonomy mappings
        sources_map, categories_map = get_taxonomy_mappings()
        
        # Get selected IDs from form
        source_id = request.form.get('source', '').strip()
        category_id = request.form.get('categories', '').strip()
        
        # Validate selected IDs exist in taxonomy
        if not source_id or source_id not in sources_map:
            flash('Invalid source selected', 'error')
            return redirect(request.url)
        if not category_id or category_id not in categories_map:
            flash('Invalid category selected', 'error')
            return redirect(request.url)
        
        # Get codes for ID generation
        source_code = sources_map[source_id]['code']
        category_code = categories_map[category_id]['code']
        
        # Generate poster ID using template
        try:
            context = {
                'source_code': source_code,
                'category_code': category_code,
            }
            poster_id = id_generator.generate_id(context)
        except Exception as e:
            logger.error(f"Failed to generate ID: {e}")
            flash('Failed to generate poster ID', 'error')
            return redirect(request.url)
        
        # Build metadata with taxonomy IDs
        metadata = {
            'id': poster_id,  # Pass generated ID
            'title': request.form.get('title', '').strip(),
            'source': source_id,  # Store ID, not free text
            'categories': category_id,  # Store ID, not free text
            'attribution': request.form.get('attribution', '').strip(),
            'length': request.form.get('length', '').strip(),
            'price': request.form.get('price', ''),  # Will be handled by poster.py with default
            'kit': request.form.get('kit', '').strip(),
            'collection': request.form.get('collection', '').strip(),
            'tags': [t.strip() for t in request.form.get('tags', '').split(',') if t.strip()],
            'slogans': [s.strip() for s in request.form.get('slogans', '').split(',') if s.strip()],
            'preview_settings': {
                'alignment': request.form.get('preview_alignment', 'middle'),
                'length_snap': request.form.get('preview_length_snap', ''),
                'orientation': request.form.get('preview_orientation', 'auto'),
                'rotation': int(request.form.get('preview_rotation', 0)),
                'fill_color': request.form.get('preview_fill_color', '#ffffff'),
                'page_number': int(request.form.get('preview_page_number', 1)),
            },
        }
        
        # Validate required fields
        if not metadata['title']:
            flash('Title is required', 'error')
            return redirect(request.url)
        
        # Create poster from upload
        poster_manager = get_poster_manager()
        poster = poster_manager.create_from_upload(pdf_file, metadata, g.user.username)
        
        if not poster:
            flash('Failed to create poster', 'error')
            return redirect(request.url)
        
        # Process PDF (add bug, generate thumbnail)
        try:
            pdf_processor = get_pdf_processor()
            
            # Prepare paths
            original_path = Path(poster_manager.data_path) / poster['original_pdf_path']
            processed_path = Path(poster_manager.data_path) / 'processed' / f"{poster['id']}.pdf"
            
            # Map taxonomy IDs to names for bug display
            source_name = sources_map.get(poster['source'], {}).get('name', poster['source'])
            category_name = categories_map.get(poster['categories'], {}).get('name', poster['categories'])
            
            # Process poster
            result = pdf_processor.process_poster(
                original_path,
                processed_path,
                poster['id'],
                {
                    'title': poster['title'],
                    'source': source_name,
                    'categories': category_name,
                    'length': poster['length'],
                    'attribution': poster['attribution'],
                    'price': poster['price'],
                    'seller': poster['seller'],
                    'slogans': poster['slogans'],
                    'preview_settings': poster.get('preview_settings', {}),
                }
            )
            
            # Update poster with processing results
            poster['processed_pdf_path'] = str(processed_path.relative_to(poster_manager.data_path))
            poster['thumbnail_path'] = str(Path(result['thumbnail_path']).relative_to(poster_manager.data_path))
            poster['dimensions'] = {
                'width': result['dimensions'][0],
                'height': result['dimensions'][1]
            }
            poster['orientation'] = result['dimensions'][2]
            poster['processed_at'] = result['processed_at']
            poster['processing_notes'] = 'Successfully processed'
            
            # Save updated metadata
            poster_manager.storage.save(poster)
            
            flash(f'Poster "{poster["title"]}" uploaded and processed successfully!', 'success')
            logger.info(f"Processed poster {poster['id']}")
            
            return redirect(url_for('posters.view', poster_id=poster['id']))
            
        except Exception as e:
            logger.error(f"Failed to process poster {poster['id']}: {e}")
            flash(f'Failed to process PDF: {str(e)}', 'error')
            # Keep the poster record but mark as failed
            poster['processing_notes'] = f'Processing failed: {str(e)}'
            poster_manager.storage.save(poster)
            return redirect(url_for('posters.view', poster_id=poster['id']))
    
    taxonomy_data = get_taxonomy_data()
    bleed_config = get_bleed_config()
    return render_template('posters/upload.html', 
                         user=g.user,
                         sources=taxonomy_data['sources'],
                         categories=taxonomy_data['categories'],
                         bleed_config=bleed_config)


@bp.route('/<poster_id>')
@login_required
def view(poster_id: str):
    """View poster details."""
    poster_manager = get_poster_manager()
    poster = poster_manager.storage.load(poster_id)
    
    if not poster:
        abort(404, description=f"Poster {poster_id} not found")
    
    poster = enrich_poster_with_taxonomy(poster)
    
    return render_template('posters/view.html', 
                         poster=poster,
                         user=g.user)


@bp.route('/<poster_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(poster_id: str):
    """Edit poster metadata."""
    poster_manager = get_poster_manager()
    poster = poster_manager.storage.load(poster_id)
    
    if not poster:
        abort(404, description=f"Poster {poster_id} not found")
    
    if request.method == 'POST':
        # Get taxonomy mappings for validation
        sources_map, categories_map = get_taxonomy_mappings()
        
        # Get form data
        new_source = request.form.get('source', '').strip()
        new_category = request.form.get('categories', '').strip()
        
        # Validate source and category IDs exist in taxonomy
        if new_source and new_source not in sources_map:
            flash('Invalid source selected', 'error')
            return redirect(request.url)
        if new_category and new_category not in categories_map:
            flash('Invalid category selected', 'error')
            return redirect(request.url)
        
        # Update metadata from form
        poster['title'] = request.form.get('title', poster['title']).strip()
        poster['source'] = new_source
        poster['categories'] = new_category
        poster['attribution'] = request.form.get('attribution', poster['attribution']).strip()
        poster['length'] = request.form.get('length', poster['length']).strip()
        poster['price'] = float(request.form.get('price', poster['price']))
        poster['kit'] = request.form.get('kit', poster['kit']).strip()
        poster['collection'] = request.form.get('collection', poster['collection']).strip()
        poster['tags'] = [t.strip() for t in request.form.get('tags', '').split(',') if t.strip()]
        poster['slogans'] = [s.strip() for s in request.form.get('slogans', '').split(',') if s.strip()]
        poster['updated_at'] = datetime.now().isoformat()
        poster['updated_by'] = g.user.username
        
        poster_manager.storage.save(poster)
        flash(f'Poster "{poster["title"]}" updated successfully!', 'success')
        return redirect(url_for('posters.view', poster_id=poster_id))
    
    poster = enrich_poster_with_taxonomy(poster)
    taxonomy_data = get_taxonomy_data()
    
    return render_template('posters/edit.html', 
                         poster=poster,
                         sources=taxonomy_data['sources'],
                         categories=taxonomy_data['categories'],
                         user=g.user)


@bp.route('/<poster_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(poster_id: str):
    """Delete poster and associated files."""
    poster_manager = get_poster_manager()
    poster = poster_manager.storage.load(poster_id)
    
    if not poster:
        abort(404, description=f"Poster {poster_id} not found")
    
    # Delete files
    data_path = poster_manager.data_path
    
    # Original PDF
    original_path = data_path / poster.get('original_pdf_path', '')
    if original_path.exists():
        original_path.unlink()
    
    # Processed PDF
    processed_path = data_path / poster.get('processed_pdf_path', '')
    if processed_path.exists():
        processed_path.unlink()
    
    # Thumbnail
    thumbnail_path = data_path / poster.get('thumbnail_path', '')
    if thumbnail_path.exists():
        thumbnail_path.unlink()
    
    # Delete metadata
    poster_manager.storage.delete(poster_id)
    
    flash(f'Poster "{poster.get("title", poster_id)}" deleted successfully!', 'success')
    logger.info(f"Deleted poster {poster_id}")
    
    return redirect(url_for('posters.index'))


@bp.route('/<poster_id>/thumbnail')
@login_required
def thumbnail(poster_id: str):
    """Serve thumbnail image."""
    poster_manager = get_poster_manager()
    poster = poster_manager.storage.load(poster_id)
    
    if not poster or 'thumbnail_path' not in poster:
        abort(404)
    
    thumbnail_path = Path(poster_manager.data_path) / poster['thumbnail_path']
    if not thumbnail_path.exists():
        abort(404)
    
    return send_file(thumbnail_path, mimetype='image/jpeg')


@bp.route('/<poster_id>/download')
@login_required
def download(poster_id: str):
    """Download processed PDF."""
    poster_manager = get_poster_manager()
    poster = poster_manager.storage.load(poster_id)
    
    if not poster or 'processed_pdf_path' not in poster:
        abort(404)
    
    pdf_path = Path(poster_manager.data_path) / poster['processed_pdf_path']
    if not pdf_path.exists():
        abort(404)
    
    return send_file(pdf_path, 
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f"{poster_id}.pdf")


@bp.route('/<poster_id>/inventory', methods=['POST'])
@login_required
def update_inventory(poster_id: str):
    """Update inventory count."""
    try:
        count = int(request.form.get('count', 0))
        action = request.form.get('action', 'counted')
        notes = request.form.get('notes', '').strip()
        
        poster_manager = get_poster_manager()
        success = poster_manager.update_inventory(
            poster_id, count, action, notes, g.user.username
        )
        
        if success:
            flash(f'Inventory updated to {count}', 'success')
        else:
            flash('Failed to update inventory', 'error')
            
    except ValueError:
        flash('Invalid count value', 'error')
    
    return redirect(url_for('posters.view', poster_id=poster_id))


@bp.route('/stats')
@login_required
def stats():
    """Show poster statistics."""
    poster_manager = get_poster_manager()
    stats = poster_manager.get_stats()
    
    return render_template('posters/stats.html',
                         stats=stats,
                         user=g.user)