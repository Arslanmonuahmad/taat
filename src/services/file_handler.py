import os
import tempfile
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import requests
from telegram import File
import uuid
import mimetypes

logger = logging.getLogger(__name__)

class FileHandler:
    """Service for handling file uploads and downloads"""
    
    def __init__(self):
        self.upload_dir = os.path.join(os.path.dirname(__file__), '../../uploads')
        self.max_file_size = int(os.getenv('MAX_FILE_SIZE_MB', 50)) * 1024 * 1024  # Convert MB to bytes
        
        # Ensure upload directory exists
        os.makedirs(self.upload_dir, exist_ok=True)
        
        # Supported file types
        self.supported_image_types = {'.jpg', '.jpeg', '.png', '.webp'}
        self.supported_video_types = {'.mp4', '.mov', '.avi', '.mkv'}
    
    async def download_telegram_file(self, file: File, file_type: str = 'image') -> Dict[str, Any]:
        """Download file from Telegram servers"""
        try:
            # Check file size
            if file.file_size > self.max_file_size:
                return {
                    'success': False,
                    'error': f'File too large. Maximum size is {self.max_file_size // (1024*1024)}MB'
                }
            
            # Generate unique filename
            file_extension = self._get_file_extension(file.file_path)
            if not file_extension:
                file_extension = '.jpg' if file_type == 'image' else '.mp4'
            
            filename = f"{file_type}_{uuid.uuid4().hex[:8]}{file_extension}"
            local_path = os.path.join(self.upload_dir, filename)
            
            # Download the file
            await file.download_to_drive(local_path)
            
            # Verify file was downloaded
            if not os.path.exists(local_path):
                return {'success': False, 'error': 'Failed to download file'}
            
            # Verify file type
            if not self._is_supported_file_type(local_path, file_type):
                os.remove(local_path)  # Clean up
                return {
                    'success': False,
                    'error': f'Unsupported file type. Supported {file_type} types: {self._get_supported_types(file_type)}'
                }
            
            logger.info(f"Downloaded Telegram file to {local_path}")
            
            return {
                'success': True,
                'local_path': local_path,
                'filename': filename,
                'file_size': os.path.getsize(local_path),
                'file_type': file_type
            }
            
        except Exception as e:
            logger.error(f"Error downloading Telegram file: {e}")
            return {'success': False, 'error': str(e)}
    
    def _get_file_extension(self, file_path: str) -> Optional[str]:
        """Extract file extension from file path"""
        if not file_path:
            return None
        
        path = Path(file_path)
        return path.suffix.lower()
    
    def _is_supported_file_type(self, file_path: str, expected_type: str) -> bool:
        """Check if file type is supported"""
        extension = self._get_file_extension(file_path)
        
        if expected_type == 'image':
            return extension in self.supported_image_types
        elif expected_type == 'video':
            return extension in self.supported_video_types
        
        return False
    
    def _get_supported_types(self, file_type: str) -> str:
        """Get supported file types as string"""
        if file_type == 'image':
            return ', '.join(self.supported_image_types)
        elif file_type == 'video':
            return ', '.join(self.supported_video_types)
        return ''
    
    def validate_image_file(self, file_path: str) -> Dict[str, Any]:
        """Validate image file"""
        try:
            from PIL import Image
            
            # Check if file exists
            if not os.path.exists(file_path):
                return {'valid': False, 'error': 'File not found'}
            
            # Try to open with PIL
            with Image.open(file_path) as img:
                # Check image dimensions
                width, height = img.size
                
                if width < 100 or height < 100:
                    return {'valid': False, 'error': 'Image too small (minimum 100x100 pixels)'}
                
                if width > 4096 or height > 4096:
                    return {'valid': False, 'error': 'Image too large (maximum 4096x4096 pixels)'}
                
                # Check if image has faces (basic validation)
                # This is a placeholder - in production, you might want to use face detection
                
                return {
                    'valid': True,
                    'width': width,
                    'height': height,
                    'format': img.format,
                    'mode': img.mode
                }
                
        except Exception as e:
            return {'valid': False, 'error': f'Invalid image file: {str(e)}'}
    
    def validate_video_file(self, file_path: str) -> Dict[str, Any]:
        """Validate video file"""
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                return {'valid': False, 'error': 'File not found'}
            
            # Basic file size check
            file_size = os.path.getsize(file_path)
            if file_size > self.max_file_size:
                return {'valid': False, 'error': 'Video file too large'}
            
            # For now, just check file extension
            # In production, you might want to use ffmpeg to validate video
            extension = self._get_file_extension(file_path)
            if extension not in self.supported_video_types:
                return {'valid': False, 'error': 'Unsupported video format'}
            
            return {
                'valid': True,
                'file_size': file_size,
                'extension': extension
            }
            
        except Exception as e:
            return {'valid': False, 'error': f'Invalid video file: {str(e)}'}
    
    def cleanup_file(self, file_path: str) -> bool:
        """Clean up a file"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up file: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error cleaning up file {file_path}: {e}")
            return False
    
    def cleanup_old_uploads(self, hours_old: int = 24) -> int:
        """Clean up old uploaded files"""
        try:
            import time
            cutoff_time = time.time() - (hours_old * 60 * 60)
            cleaned_count = 0
            
            for filename in os.listdir(self.upload_dir):
                file_path = os.path.join(self.upload_dir, filename)
                if os.path.isfile(file_path) and os.path.getmtime(file_path) < cutoff_time:
                    if self.cleanup_file(file_path):
                        cleaned_count += 1
            
            logger.info(f"Cleaned up {cleaned_count} old upload files")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old uploads: {e}")
            return 0
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get file information"""
        try:
            if not os.path.exists(file_path):
                return {'exists': False}
            
            stat = os.stat(file_path)
            mime_type, _ = mimetypes.guess_type(file_path)
            
            return {
                'exists': True,
                'size': stat.st_size,
                'created': stat.st_ctime,
                'modified': stat.st_mtime,
                'mime_type': mime_type,
                'extension': self._get_file_extension(file_path)
            }
            
        except Exception as e:
            logger.error(f"Error getting file info for {file_path}: {e}")
            return {'exists': False, 'error': str(e)}
    
    def create_temp_file(self, suffix: str = '') -> str:
        """Create a temporary file"""
        fd, path = tempfile.mkstemp(suffix=suffix, dir=self.upload_dir)
        os.close(fd)  # Close the file descriptor
        return path
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        try:
            total_size = 0
            file_count = 0
            
            for filename in os.listdir(self.upload_dir):
                file_path = os.path.join(self.upload_dir, filename)
                if os.path.isfile(file_path):
                    total_size += os.path.getsize(file_path)
                    file_count += 1
            
            return {
                'total_files': file_count,
                'total_size_bytes': total_size,
                'total_size_mb': total_size / (1024 * 1024),
                'upload_dir': self.upload_dir
            }
            
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {'error': str(e)}

