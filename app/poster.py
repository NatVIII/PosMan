"""
Poster model and storage management.

Handles poster metadata storage in JSON files within the data directory.
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, TypedDict
from uuid import uuid4

logger = logging.getLogger(__name__)


class PosterInventoryRecord(TypedDict):
    """Inventory record for a specific date and action."""
    date: str
    count: int
    action: str  # 'counted', 'printed', 'adjusted'
    notes: Optional[str]
    user: Optional[str]


class PosterMetadata(TypedDict):
    """Poster metadata structure."""
    # Core identifiers
    id: str
    title: str
    source: str
    categories: str
    attribution: str
    
    # Physical properties
    length: str  # Length (11x17)
    orientation: str  # 'portrait', 'landscape'
    dimensions: Dict[str, int]  # width, height in points
    
    # Pricing
    price: float
    price_tier: str
    
    # Inventory tracking
    inventory_count: int  # Current count
    inventory_history: List[PosterInventoryRecord]
    
    # File paths (relative to data directory)
    original_pdf_path: str
    processed_pdf_path: str
    thumbnail_path: str
    
    # Kit/collection assignment
    kit: str
    collection: str
    
    # Processing metadata
    processed_at: str
    processing_notes: str
    
    # Additional metadata
    tags: List[str]
    ratings: Dict[str, float]
    slogans: List[str]
    seller: str
    
    # System metadata
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str


class PosterStorage:
    """Manages poster metadata storage in JSON files."""
    
    def __init__(self, data_path: Path):
        self.data_path = Path(data_path)
        self.metadata_dir = self.data_path / 'metadata'
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        
    def _get_metadata_path(self, poster_id: str) -> Path:
        """Get path for poster metadata file."""
        return self.metadata_dir / f"{poster_id}.json"
    
    def save(self, poster: PosterMetadata) -> None:
        """Save poster metadata to JSON file."""
        metadata_path = self._get_metadata_path(poster['id'])
        
        # Update timestamps
        now = datetime.now().isoformat()
        if 'created_at' not in poster:
            poster['created_at'] = now
        poster['updated_at'] = now
        
        # Ensure directory exists
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write JSON with indentation
        with open(metadata_path, 'w') as f:
            json.dump(poster, f, indent=2, default=str)
        
        logger.debug(f"Saved metadata for poster {poster['id']}")
    
    def load(self, poster_id: str) -> Optional[PosterMetadata]:
        """Load poster metadata from JSON file."""
        metadata_path = self._get_metadata_path(poster_id)
        
        if not metadata_path.exists():
            logger.warning(f"Metadata file not found: {metadata_path}")
            return None
        
        try:
            with open(metadata_path, 'r') as f:
                data = json.load(f)
            
            # Ensure required fields
            if 'id' not in data:
                data['id'] = poster_id
            
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse metadata for {poster_id}: {e}")
            return None
    
    def delete(self, poster_id: str) -> bool:
        """Delete poster metadata file."""
        metadata_path = self._get_metadata_path(poster_id)
        
        if metadata_path.exists():
            metadata_path.unlink()
            logger.debug(f"Deleted metadata for poster {poster_id}")
            return True
        return False
    
    def list_all(self) -> List[str]:
        """List all poster IDs with metadata files."""
        if not self.metadata_dir.exists():
            return []
        
        poster_ids = []
        for json_file in self.metadata_dir.glob("*.json"):
            poster_ids.append(json_file.stem)
        
        return sorted(poster_ids)
    
    def search(self, **kwargs) -> List[PosterMetadata]:
        """Search posters by metadata fields."""
        results = []
        
        for poster_id in self.list_all():
            poster = self.load(poster_id)
            if not poster:
                continue
            
            # Check if poster matches all search criteria
            match = True
            for key, value in kwargs.items():
                if key not in poster or poster[key] != value:
                    match = False
                    break
            
            if match:
                results.append(poster)
        
        return results


class PosterManager:
    """High-level poster management with file operations."""
    
    def __init__(self, data_path: Path, config: Optional[Dict[str, Any]] = None):
        self.data_path = Path(data_path)
        self.storage = PosterStorage(data_path)
        self.config = config or {}
        
        # Ensure directory structure
        (self.data_path / 'originals').mkdir(parents=True, exist_ok=True)
        (self.data_path / 'processed').mkdir(parents=True, exist_ok=True)
        (self.data_path / 'thumbnails').mkdir(parents=True, exist_ok=True)
    
    def create_from_upload(self, pdf_file, metadata: Dict[str, Any], 
                          user: str) -> Optional[PosterMetadata]:
        """
        Create a new poster from uploaded PDF file.
        
        Args:
            pdf_file: Uploaded file object
            metadata: Initial metadata
            user: Username who uploaded
        
        Returns:
            Poster metadata or None if failed
        """
        # Generate unique ID if not provided
        poster_id = metadata.get('id')
        if not poster_id:
            # Generate ID based on title or random
            title_prefix = metadata.get('title', 'POSTER')[:8].upper().replace(' ', '')
            poster_id = f"{title_prefix}-{uuid4().hex[:4].upper()}"
            metadata['id'] = poster_id
        
        # Save original PDF
        original_path = self.data_path / 'originals' / f"{poster_id}.pdf"
        pdf_file.save(str(original_path))
        
        # Create basic poster structure
        poster: PosterMetadata = {
            'id': poster_id,
            'title': metadata.get('title', 'Untitled Poster'),
            'source': metadata.get('source', ''),
            'categories': metadata.get('categories', ''),
            'attribution': metadata.get('attribution', ''),
            'length': metadata.get('length', ''),
            'orientation': 'portrait',  # Will be updated after processing
            'dimensions': {'width': 0, 'height': 0},
            'price': float(metadata.get('price', self.config.get('default_price', 12.00))),
            'price_tier': metadata.get('price_tier', 'standard'),
            'inventory_count': 0,
            'inventory_history': [],
            'original_pdf_path': str(original_path.relative_to(self.data_path)),
            'processed_pdf_path': '',
            'thumbnail_path': '',
            'kit': metadata.get('kit', ''),
            'collection': metadata.get('collection', ''),
            'processed_at': '',
            'processing_notes': '',
            'tags': metadata.get('tags', []),
            'ratings': {},
            'slogans': metadata.get('slogans', []),
            'seller': metadata.get('seller', self.config.get('seller', '')),
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'created_by': user,
            'updated_by': user,
        }
        
        # Save initial metadata
        self.storage.save(poster)
        logger.info(f"Created poster {poster_id} from upload")
        
        return poster
    
    def update_inventory(self, poster_id: str, count: int, action: str,
                        notes: str = '', user: str = 'system') -> bool:
        """
        Update inventory count with history tracking.
        
        Args:
            poster_id: Poster ID
            count: New count
            action: 'counted', 'printed', 'adjusted'
            notes: Optional notes
            user: Username performing action
        
        Returns:
            Success status
        """
        poster = self.storage.load(poster_id)
        if not poster:
            logger.error(f"Cannot update inventory: poster {poster_id} not found")
            return False
        
        # Create inventory record
        record: PosterInventoryRecord = {
            'date': datetime.now().isoformat(),
            'count': count,
            'action': action,
            'notes': notes,
            'user': user
        }
        
        # Update poster
        poster['inventory_count'] = count
        poster['inventory_history'].append(record)
        poster['updated_at'] = datetime.now().isoformat()
        poster['updated_by'] = user
        
        self.storage.save(poster)
        logger.info(f"Updated inventory for {poster_id}: {action} = {count}")
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics."""
        poster_ids = self.storage.list_all()
        posters = [self.storage.load(pid) for pid in poster_ids]
        posters = [p for p in posters if p]
        
        total_inventory = sum(p.get('inventory_count', 0) for p in posters)
        
        return {
            'total_posters': len(posters),
            'total_inventory': total_inventory,
            'kits': len(set(p.get('kit', '') for p in posters if p.get('kit'))),
            'collections': len(set(p.get('collection', '') for p in posters if p.get('collection'))),
            'recent_uploads': sorted(posters, 
                                    key=lambda x: x.get('created_at', ''), 
                                    reverse=True)[:5],
        }