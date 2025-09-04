import os
import sys
import tempfile
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import shutil
from src.models.database import db, FaceSwapJob, JobStatus, JobType
from src.services.credit_service import CreditService
import uuid
import json

logger = logging.getLogger(__name__)

class FaceSwapService:
    """Service for handling face swap operations using FaceFusion"""
    
    def __init__(self):
        self.credit_service = CreditService()
        self.facefusion_path = os.path.join(os.path.dirname(__file__), '../../external/facefusion')
        self.temp_dir = os.path.join(os.path.dirname(__file__), '../../temp')
        self.output_dir = os.path.join(os.path.dirname(__file__), '../../outputs')
        
        # Ensure directories exist
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Check if FaceFusion is available
        self.facefusion_available = os.path.exists(os.path.join(self.facefusion_path, 'facefusion.py'))
        
        if not self.facefusion_available:
            logger.warning("FaceFusion not found at expected path. Face swap functionality will be limited.")
    
    def create_face_swap_job(self, user_id: int, job_type: JobType, 
                           source_file_path: str, target_file_path: str = None,
                           telegram_message_id: int = None) -> FaceSwapJob:
        """Create a new face swap job"""
        try:
            job = FaceSwapJob(
                user_id=user_id,
                job_type=job_type,
                source_file_path=source_file_path,
                target_file_path=target_file_path,
                telegram_message_id=telegram_message_id,
                status=JobStatus.QUEUED
            )
            
            db.session.add(job)
            db.session.commit()
            
            logger.info(f"Created face swap job {job.id} for user {user_id}")
            return job
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating face swap job: {e}")
            raise
    
    def process_face_swap_job(self, job_id: int) -> Dict[str, Any]:
        """Process a face swap job"""
        job = FaceSwapJob.query.get(job_id)
        if not job:
            return {'success': False, 'error': 'Job not found'}
        
        try:
            # Update job status
            job.status = JobStatus.PROCESSING
            job.started_at = db.func.now()
            db.session.commit()
            
            # Check if user has enough credits
            validation = self.credit_service.validate_credit_transaction(job.user_id, job.credits_consumed)
            if not validation['valid']:
                job.status = JobStatus.FAILED
                job.error_message = validation['reason']
                db.session.commit()
                return {'success': False, 'error': validation['reason']}
            
            # Consume credits
            if not self.credit_service.consume_credits(job.user_id, job.credits_consumed):
                job.status = JobStatus.FAILED
                job.error_message = 'Failed to consume credits'
                db.session.commit()
                return {'success': False, 'error': 'Failed to consume credits'}
            
            # Process the face swap
            if job.job_type == JobType.IMAGE:
                result = self._process_image_face_swap(job)
            elif job.job_type == JobType.VIDEO:
                result = self._process_video_face_swap(job)
            else:
                result = {'success': False, 'error': 'Unsupported job type'}
            
            # Update job with result
            if result['success']:
                job.status = JobStatus.COMPLETED
                job.result_file_path = result.get('output_path')
                job.processing_metadata = result.get('metadata', {})
            else:
                job.status = JobStatus.FAILED
                job.error_message = result.get('error', 'Unknown error')
                
                # Refund credits on failure
                self.credit_service.refund_credits(
                    user_id=job.user_id,
                    amount=job.credits_consumed,
                    reason=f"Job {job.id} failed: {job.error_message}"
                )
            
            job.completed_at = db.func.now()
            db.session.commit()
            
            logger.info(f"Completed face swap job {job.id} with status {job.status.value}")
            return result
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = db.func.now()
            db.session.commit()
            
            # Refund credits on error
            self.credit_service.refund_credits(
                user_id=job.user_id,
                amount=job.credits_consumed,
                reason=f"Job {job.id} error: {str(e)}"
            )
            
            logger.error(f"Error processing face swap job {job.id}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _process_image_face_swap(self, job: FaceSwapJob) -> Dict[str, Any]:
        """Process image face swap using FaceFusion"""
        if not self.facefusion_available:
            return {'success': False, 'error': 'FaceFusion not available'}
        
        try:
            # Generate unique output filename
            output_filename = f"faceswap_{job.id}_{uuid.uuid4().hex[:8]}.png"
            output_path = os.path.join(self.output_dir, output_filename)
            
            # For image face swap, we need both source and target
            if not job.target_file_path:
                return {
                    'success': False, 
                    'error': 'Image face swap requires both source and target images. Please send two images.'
                }
            
            # Prepare FaceFusion command for headless operation
            cmd = [
                sys.executable,
                os.path.join(self.facefusion_path, 'facefusion.py'),
                'headless-run',
                '--source-paths', job.source_file_path,
                '--target-path', job.target_file_path,
                '--output-path', output_path,
                '--processors', 'face_swapper',
                '--execution-providers', 'cpu'  # Use CPU for compatibility
            ]
            
            # Run FaceFusion
            logger.info(f"Running FaceFusion command for job {job.id}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=self.facefusion_path
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                # Get file size
                file_size = os.path.getsize(output_path)
                
                return {
                    'success': True,
                    'output_path': output_path,
                    'metadata': {
                        'file_size_bytes': file_size,
                        'facefusion_stdout': result.stdout,
                        'processing_method': 'facefusion_cpu'
                    }
                }
            else:
                error_msg = result.stderr or result.stdout or 'Unknown FaceFusion error'
                logger.error(f"FaceFusion failed for job {job.id}: {error_msg}")
                return {'success': False, 'error': f'Face swap failed: {error_msg}'}
                
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Face swap processing timed out'}
        except Exception as e:
            logger.error(f"Error in image face swap: {e}")
            return {'success': False, 'error': str(e)}
    
    def _process_video_face_swap(self, job: FaceSwapJob) -> Dict[str, Any]:
        """Process video face swap using FaceFusion"""
        if not self.facefusion_available:
            return {'success': False, 'error': 'FaceFusion not available'}
        
        try:
            # Generate unique output filename
            output_filename = f"faceswap_video_{job.id}_{uuid.uuid4().hex[:8]}.mp4"
            output_path = os.path.join(self.output_dir, output_filename)
            
            # For video face swap, source is the face image, target is the video
            if not job.target_file_path:
                return {
                    'success': False, 
                    'error': 'Video face swap requires a face image and a target video.'
                }
            
            # Prepare FaceFusion command for video
            cmd = [
                sys.executable,
                os.path.join(self.facefusion_path, 'facefusion.py'),
                'headless-run',
                '--source-paths', job.source_file_path,
                '--target-path', job.target_file_path,
                '--output-path', output_path,
                '--processors', 'face_swapper',
                '--execution-providers', 'cpu'  # Use CPU for compatibility
            ]
            
            # Run FaceFusion
            logger.info(f"Running FaceFusion video command for job {job.id}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout for videos
                cwd=self.facefusion_path
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                # Get file size
                file_size = os.path.getsize(output_path)
                
                return {
                    'success': True,
                    'output_path': output_path,
                    'metadata': {
                        'file_size_bytes': file_size,
                        'facefusion_stdout': result.stdout,
                        'processing_method': 'facefusion_cpu_video'
                    }
                }
            else:
                error_msg = result.stderr or result.stdout or 'Unknown FaceFusion error'
                logger.error(f"FaceFusion video failed for job {job.id}: {error_msg}")
                return {'success': False, 'error': f'Video face swap failed: {error_msg}'}
                
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Video face swap processing timed out'}
        except Exception as e:
            logger.error(f"Error in video face swap: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_job_status(self, job_id: int) -> Optional[FaceSwapJob]:
        """Get job status"""
        return FaceSwapJob.query.get(job_id)
    
    def get_user_jobs(self, user_id: int, limit: int = 10) -> list:
        """Get user's face swap jobs"""
        return FaceSwapJob.query.filter_by(user_id=user_id).order_by(
            FaceSwapJob.created_at.desc()
        ).limit(limit).all()
    
    def cleanup_old_files(self, days_old: int = 7) -> int:
        """Clean up old output files"""
        try:
            import time
            cutoff_time = time.time() - (days_old * 24 * 60 * 60)
            cleaned_count = 0
            
            for filename in os.listdir(self.output_dir):
                file_path = os.path.join(self.output_dir, filename)
                if os.path.isfile(file_path) and os.path.getmtime(file_path) < cutoff_time:
                    os.remove(file_path)
                    cleaned_count += 1
            
            logger.info(f"Cleaned up {cleaned_count} old files")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old files: {e}")
            return 0
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get face swap system status"""
        return {
            'facefusion_available': self.facefusion_available,
            'facefusion_path': self.facefusion_path,
            'temp_dir_exists': os.path.exists(self.temp_dir),
            'output_dir_exists': os.path.exists(self.output_dir),
            'pending_jobs': FaceSwapJob.query.filter_by(status=JobStatus.QUEUED).count(),
            'processing_jobs': FaceSwapJob.query.filter_by(status=JobStatus.PROCESSING).count()
        }
    
    def create_face_swap_job(self, user_id: int, job_type: JobType, 
                           source_file_path: str, target_file_path: str = None,
                           telegram_message_id: int = None) -> FaceSwapJob:
        """Create a new face swap job"""
        try:
            job = FaceSwapJob(
                user_id=user_id,
                job_type=job_type,
                source_file_path=source_file_path,
                target_file_path=target_file_path,
                telegram_message_id=telegram_message_id,
                status=JobStatus.QUEUED
            )
            
            db.session.add(job)
            db.session.commit()
            
            logger.info(f"Created face swap job {job.id} for user {user_id}")
            return job
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating face swap job: {e}")
            raise
    
    def process_face_swap_job(self, job_id: int) -> Dict[str, Any]:
        """Process a face swap job"""
        job = FaceSwapJob.query.get(job_id)
        if not job:
            return {'success': False, 'error': 'Job not found'}
        
        try:
            # Update job status
            job.status = JobStatus.PROCESSING
            job.started_at = db.func.now()
            db.session.commit()
            
            # Check if user has enough credits
            validation = self.credit_service.validate_credit_transaction(job.user_id, job.credits_consumed)
            if not validation['valid']:
                job.status = JobStatus.FAILED
                job.error_message = validation['reason']
                db.session.commit()
                return {'success': False, 'error': validation['reason']}
            
            # Consume credits
            if not self.credit_service.consume_credits(job.user_id, job.credits_consumed):
                job.status = JobStatus.FAILED
                job.error_message = 'Failed to consume credits'
                db.session.commit()
                return {'success': False, 'error': 'Failed to consume credits'}
            
            # Process the face swap
            if job.job_type == JobType.IMAGE:
                result = self._process_image_face_swap(job)
            elif job.job_type == JobType.VIDEO:
                result = self._process_video_face_swap(job)
            else:
                result = {'success': False, 'error': 'Unsupported job type'}
            
            # Update job with result
            if result['success']:
                job.status = JobStatus.COMPLETED
                job.result_file_path = result.get('output_path')
                job.processing_metadata = result.get('metadata', {})
            else:
                job.status = JobStatus.FAILED
                job.error_message = result.get('error', 'Unknown error')
                
                # Refund credits on failure
                self.credit_service.refund_credits(
                    user_id=job.user_id,
                    amount=job.credits_consumed,
                    reason=f"Job {job.id} failed: {job.error_message}"
                )
            
            job.completed_at = db.func.now()
            db.session.commit()
            
            logger.info(f"Completed face swap job {job.id} with status {job.status.value}")
            return result
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = db.func.now()
            db.session.commit()
            
            # Refund credits on error
            self.credit_service.refund_credits(
                user_id=job.user_id,
                amount=job.credits_consumed,
                reason=f"Job {job.id} error: {str(e)}"
            )
            
            logger.error(f"Error processing face swap job {job.id}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _process_image_face_swap(self, job: FaceSwapJob) -> Dict[str, Any]:
        """Process image face swap using roop"""
        if not self.roop_available:
            return {'success': False, 'error': 'Roop not available'}
        
        try:
            # Generate unique output filename
            output_filename = f"faceswap_{job.id}_{uuid.uuid4().hex[:8]}.png"
            output_path = os.path.join(self.output_dir, output_filename)
            
            # For image face swap, we need both source and target
            # If only source is provided, we'll create a placeholder message
            if not job.target_file_path:
                return {
                    'success': False, 
                    'error': 'Image face swap requires both source and target images. Please send two images.'
                }
            
            # Prepare roop command
            cmd = [
                sys.executable,
                os.path.join(self.roop_path, 'run.py'),
                '--source', job.source_file_path,
                '--target', job.target_file_path,
                '--output', output_path,
                '--execution-provider', 'cpu',  # Use CPU for compatibility
                '--frame-processor', 'face_swapper'
            ]
            
            # Run roop
            logger.info(f"Running roop command for job {job.id}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=self.roop_path
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                # Get file size
                file_size = os.path.getsize(output_path)
                
                return {
                    'success': True,
                    'output_path': output_path,
                    'metadata': {
                        'file_size_bytes': file_size,
                        'roop_stdout': result.stdout,
                        'processing_method': 'roop_cpu'
                    }
                }
            else:
                error_msg = result.stderr or result.stdout or 'Unknown roop error'
                logger.error(f"Roop failed for job {job.id}: {error_msg}")
                return {'success': False, 'error': f'Face swap failed: {error_msg}'}
                
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Face swap processing timed out'}
        except Exception as e:
            logger.error(f"Error in image face swap: {e}")
            return {'success': False, 'error': str(e)}
    
    def _process_video_face_swap(self, job: FaceSwapJob) -> Dict[str, Any]:
        """Process video face swap using roop"""
        if not self.roop_available:
            return {'success': False, 'error': 'Roop not available'}
        
        try:
            # Generate unique output filename
            output_filename = f"faceswap_video_{job.id}_{uuid.uuid4().hex[:8]}.mp4"
            output_path = os.path.join(self.output_dir, output_filename)
            
            # For video face swap, source is the face image, target is the video
            if not job.target_file_path:
                return {
                    'success': False, 
                    'error': 'Video face swap requires a face image and a target video.'
                }
            
            # Prepare roop command for video
            cmd = [
                sys.executable,
                os.path.join(self.roop_path, 'run.py'),
                '--source', job.source_file_path,
                '--target', job.target_file_path,
                '--output', output_path,
                '--execution-provider', 'cpu',  # Use CPU for compatibility
                '--frame-processor', 'face_swapper',
                '--keep-fps'  # Maintain original video FPS
            ]
            
            # Run roop
            logger.info(f"Running roop video command for job {job.id}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout for videos
                cwd=self.roop_path
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                # Get file size
                file_size = os.path.getsize(output_path)
                
                return {
                    'success': True,
                    'output_path': output_path,
                    'metadata': {
                        'file_size_bytes': file_size,
                        'roop_stdout': result.stdout,
                        'processing_method': 'roop_cpu_video'
                    }
                }
            else:
                error_msg = result.stderr or result.stdout or 'Unknown roop error'
                logger.error(f"Roop video failed for job {job.id}: {error_msg}")
                return {'success': False, 'error': f'Video face swap failed: {error_msg}'}
                
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Video face swap processing timed out'}
        except Exception as e:
            logger.error(f"Error in video face swap: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_job_status(self, job_id: int) -> Optional[FaceSwapJob]:
        """Get job status"""
        return FaceSwapJob.query.get(job_id)
    
    def get_user_jobs(self, user_id: int, limit: int = 10) -> list:
        """Get user's face swap jobs"""
        return FaceSwapJob.query.filter_by(user_id=user_id).order_by(
            FaceSwapJob.created_at.desc()
        ).limit(limit).all()
    
    def cleanup_old_files(self, days_old: int = 7) -> int:
        """Clean up old output files"""
        try:
            import time
            cutoff_time = time.time() - (days_old * 24 * 60 * 60)
            cleaned_count = 0
            
            for filename in os.listdir(self.output_dir):
                file_path = os.path.join(self.output_dir, filename)
                if os.path.isfile(file_path) and os.path.getmtime(file_path) < cutoff_time:
                    os.remove(file_path)
                    cleaned_count += 1
            
            logger.info(f"Cleaned up {cleaned_count} old files")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old files: {e}")
            return 0
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get face swap system status"""
        return {
            'roop_available': self.roop_available,
            'roop_path': self.roop_path,
            'temp_dir_exists': os.path.exists(self.temp_dir),
            'output_dir_exists': os.path.exists(self.output_dir),
            'pending_jobs': FaceSwapJob.query.filter_by(status=JobStatus.QUEUED).count(),
            'processing_jobs': FaceSwapJob.query.filter_by(status=JobStatus.PROCESSING).count()
        }

