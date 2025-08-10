"""
ArchieOS Prune Manager - Automated file pruning and cold storage rotation
"""
import os
import shutil
import gzip
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import json
import logging

logger = logging.getLogger(__name__)


class PruneManager:
    """
    Manages automatic pruning and archival of old files in ArchieOS
    """
    
    # Default aging policies (in days)
    DEFAULT_POLICIES = {
        'hot_to_warm': 7,      # Move from hot to warm after 7 days
        'warm_to_cold': 30,    # Move to cold storage after 30 days
        'compress_cold': 90,   # Compress files in cold storage after 90 days
        'archive_threshold': 365,  # Consider for deletion after 1 year
        'temp_cleanup': 1      # Clean temp files after 1 day
    }
    
    def __init__(self, storage_path: str = None, policies: Dict[str, int] = None):
        base_dir = Path(__file__).parent.parent
        
        if storage_path is None:
            storage_path = base_dir / "storage"
        
        self.storage_path = Path(storage_path)
        self.policies = policies or self.DEFAULT_POLICIES.copy()
        
        # Ensure cold storage directory exists
        (self.storage_path / "cold").mkdir(exist_ok=True)
        (self.storage_path / "cold" / "compressed").mkdir(exist_ok=True)
        
        logger.info("🧹 Archie: Prune Manager initialized - Ready to keep things tidy!")
    
    def run_pruning_cycle(self) -> Dict[str, Any]:
        """
        Run a complete pruning cycle across all storage tiers
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "actions": [],
            "files_moved": 0,
            "files_compressed": 0,
            "files_deleted": 0,
            "space_freed_mb": 0
        }
        
        try:
            # Clean temporary files
            temp_result = self.cleanup_temp_files()
            results["actions"].append(temp_result)
            results["files_deleted"] += temp_result.get("files_deleted", 0)
            
            # Rotate files through storage tiers
            rotation_result = self.rotate_storage_tiers()
            results["actions"].append(rotation_result)
            results["files_moved"] += rotation_result.get("files_moved", 0)
            
            # Compress old cold storage files
            compress_result = self.compress_cold_storage()
            results["actions"].append(compress_result)
            results["files_compressed"] += compress_result.get("files_compressed", 0)
            
            # Calculate total space freed
            results["space_freed_mb"] = sum(
                action.get("space_freed_mb", 0) 
                for action in results["actions"]
            )
            
            logger.info(f"✅ Pruning cycle complete: {results['files_moved']} moved, "
                       f"{results['files_compressed']} compressed, {results['files_deleted']} deleted")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Pruning cycle failed: {e}")
            results["error"] = str(e)
            return results
    
    def cleanup_temp_files(self) -> Dict[str, Any]:
        """
        Clean up temporary files older than threshold
        """
        temp_dir = self.storage_path / "temp"
        threshold_date = datetime.now() - timedelta(days=self.policies['temp_cleanup'])
        
        files_deleted = 0
        space_freed = 0
        
        if temp_dir.exists():
            for file_path in temp_dir.rglob("*"):
                if file_path.is_file():
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    
                    if file_time < threshold_date:
                        file_size = file_path.stat().st_size
                        try:
                            file_path.unlink()
                            files_deleted += 1
                            space_freed += file_size
                        except Exception as e:
                            logger.warning(f"Could not delete temp file {file_path}: {e}")
        
        logger.info(f"🗑️ Cleaned {files_deleted} temp files, freed {space_freed / 1024 / 1024:.2f} MB")
        
        return {
            "action": "cleanup_temp",
            "files_deleted": files_deleted,
            "space_freed_mb": round(space_freed / 1024 / 1024, 2),
            "threshold_days": self.policies['temp_cleanup']
        }
    
    def rotate_storage_tiers(self) -> Dict[str, Any]:
        """
        Move files between storage tiers based on age
        """
        files_moved = 0
        movements = []
        
        # Hot to Warm rotation
        hot_threshold = datetime.now() - timedelta(days=self.policies['hot_to_warm'])
        hot_moves = self._rotate_tier("hot", "warm", hot_threshold)
        files_moved += hot_moves
        movements.append({"from": "hot", "to": "warm", "count": hot_moves})
        
        # Warm to Cold rotation
        cold_threshold = datetime.now() - timedelta(days=self.policies['warm_to_cold'])
        cold_moves = self._rotate_tier("warm", "cold", cold_threshold)
        files_moved += cold_moves
        movements.append({"from": "warm", "to": "cold", "count": cold_moves})
        
        logger.info(f"📦 Rotated {files_moved} files between storage tiers")
        
        return {
            "action": "rotate_tiers",
            "files_moved": files_moved,
            "movements": movements,
            "policies": {
                "hot_to_warm_days": self.policies['hot_to_warm'],
                "warm_to_cold_days": self.policies['warm_to_cold']
            }
        }
    
    def compress_cold_storage(self) -> Dict[str, Any]:
        """
        Compress files in cold storage that are old enough
        """
        cold_dir = self.storage_path / "cold"
        compressed_dir = cold_dir / "compressed"
        compress_threshold = datetime.now() - timedelta(days=self.policies['compress_cold'])
        
        files_compressed = 0
        space_saved = 0
        
        for file_path in cold_dir.iterdir():
            if file_path.is_file() and not file_path.suffix == '.gz':
                file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                
                if file_time < compress_threshold:
                    original_size = file_path.stat().st_size
                    compressed_path = compressed_dir / f"{file_path.name}.gz"
                    
                    try:
                        # Compress file
                        with open(file_path, 'rb') as f_in:
                            with gzip.open(compressed_path, 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        
                        # Update metadata if exists
                        meta_path = file_path.with_suffix(f"{file_path.suffix}.meta.json")
                        if meta_path.exists():
                            new_meta_path = compressed_path.with_suffix(".meta.json")
                            shutil.move(str(meta_path), str(new_meta_path))
                            
                            # Update metadata with compression info
                            with open(new_meta_path, 'r') as f:
                                metadata = json.load(f)
                            
                            metadata['compressed'] = True
                            metadata['compressed_at'] = datetime.now().isoformat()
                            metadata['original_size'] = original_size
                            metadata['compressed_size'] = compressed_path.stat().st_size
                            
                            with open(new_meta_path, 'w') as f:
                                json.dump(metadata, f, indent=2)
                        
                        # Remove original file
                        file_path.unlink()
                        
                        compressed_size = compressed_path.stat().st_size
                        space_saved += original_size - compressed_size
                        files_compressed += 1
                        
                    except Exception as e:
                        logger.warning(f"Could not compress {file_path}: {e}")
        
        logger.info(f"🗜️ Compressed {files_compressed} files, saved {space_saved / 1024 / 1024:.2f} MB")
        
        return {
            "action": "compress_cold",
            "files_compressed": files_compressed,
            "space_saved_mb": round(space_saved / 1024 / 1024, 2),
            "threshold_days": self.policies['compress_cold']
        }
    
    def identify_archive_candidates(self) -> List[Dict[str, Any]]:
        """
        Identify files that are candidates for deletion based on age and access
        """
        archive_threshold = datetime.now() - timedelta(days=self.policies['archive_threshold'])
        candidates = []
        
        # Check cold storage for very old files
        cold_dir = self.storage_path / "cold"
        
        for file_path in cold_dir.rglob("*"):
            if file_path.is_file() and not file_path.name.endswith('.meta.json'):
                file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                
                if file_time < archive_threshold:
                    # Check metadata for access info
                    meta_path = None
                    if file_path.suffix == '.gz':
                        meta_path = file_path.with_suffix('.meta.json')
                    else:
                        meta_path = file_path.with_suffix(f"{file_path.suffix}.meta.json")
                    
                    access_count = 0
                    last_accessed = None
                    
                    if meta_path and meta_path.exists():
                        with open(meta_path, 'r') as f:
                            metadata = json.load(f)
                            access_count = metadata.get('access_count', 0)
                            last_accessed = metadata.get('accessed_at')
                    
                    candidates.append({
                        "file_path": str(file_path),
                        "age_days": (datetime.now() - file_time).days,
                        "size_mb": round(file_path.stat().st_size / 1024 / 1024, 2),
                        "access_count": access_count,
                        "last_accessed": last_accessed,
                        "recommendation": "archive" if access_count == 0 else "review"
                    })
        
        # Sort by age and low access
        candidates.sort(key=lambda x: (x['access_count'], -x['age_days']))
        
        logger.info(f"📋 Identified {len(candidates)} files as archive candidates")
        
        return candidates
    
    def set_policy(self, policy_name: str, days: int) -> bool:
        """
        Update a pruning policy
        """
        if policy_name in self.policies:
            self.policies[policy_name] = days
            logger.info(f"📝 Updated policy {policy_name} to {days} days")
            return True
        return False
    
    def get_storage_analysis(self) -> Dict[str, Any]:
        """
        Analyze storage usage and provide recommendations
        """
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "tiers": {},
            "recommendations": []
        }
        
        # Analyze each tier
        for tier in ['hot', 'warm', 'cold']:
            tier_path = self._get_tier_path(tier)
            if tier_path.exists():
                files = list(tier_path.rglob("*"))
                file_count = sum(1 for f in files if f.is_file() and not f.name.endswith('.meta.json'))
                total_size = sum(f.stat().st_size for f in files if f.is_file())
                
                # Calculate average age
                if file_count > 0:
                    total_age = sum(
                        (datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)).days
                        for f in files if f.is_file() and not f.name.endswith('.meta.json')
                    )
                    avg_age = total_age / file_count
                else:
                    avg_age = 0
                
                analysis["tiers"][tier] = {
                    "file_count": file_count,
                    "total_size_mb": round(total_size / 1024 / 1024, 2),
                    "average_age_days": round(avg_age, 1)
                }
        
        # Generate recommendations
        hot_data = analysis["tiers"].get("hot", {})
        if hot_data.get("average_age_days", 0) > self.policies['hot_to_warm']:
            analysis["recommendations"].append(
                f"Consider running tier rotation - hot storage has files averaging "
                f"{hot_data['average_age_days']} days old"
            )
        
        cold_data = analysis["tiers"].get("cold", {})
        if cold_data.get("total_size_mb", 0) > 1000:  # If cold storage > 1GB
            analysis["recommendations"].append(
                "Cold storage is over 1GB - consider compressing old files"
            )
        
        return analysis
    
    def _rotate_tier(self, from_tier: str, to_tier: str, threshold: datetime) -> int:
        """
        Move files from one tier to another based on age
        """
        from_path = self._get_tier_path(from_tier)
        to_path = self._get_tier_path(to_tier)
        
        if not from_path.exists():
            return 0
        
        files_moved = 0
        
        for meta_file in from_path.rglob("*.meta.json"):
            try:
                with open(meta_file, 'r') as f:
                    metadata = json.load(f)
                
                # Check file age
                created_at = datetime.fromisoformat(metadata['created_at'])
                if created_at < threshold:
                    # Find actual file
                    file_path = Path(metadata['absolute_path'])
                    if file_path.exists():
                        # Determine new path
                        relative_path = file_path.relative_to(from_path)
                        new_path = to_path / relative_path
                        new_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Move file and metadata
                        shutil.move(str(file_path), str(new_path))
                        
                        # Update metadata
                        metadata['tier'] = to_tier
                        metadata['absolute_path'] = str(new_path)
                        metadata['path'] = str(new_path.relative_to(self.storage_path))
                        metadata['tier_moved_at'] = datetime.now().isoformat()
                        
                        # Save updated metadata
                        new_meta_path = new_path.with_suffix(f"{new_path.suffix}.meta.json")
                        with open(new_meta_path, 'w') as f:
                            json.dump(metadata, f, indent=2)
                        
                        # Remove old metadata
                        meta_file.unlink()
                        
                        files_moved += 1
                        
            except Exception as e:
                logger.warning(f"Could not rotate file {meta_file}: {e}")
        
        return files_moved
    
    def _get_tier_path(self, tier: str) -> Path:
        """
        Get the path for a storage tier
        """
        if tier == "hot":
            return self.storage_path / "plugins"
        elif tier == "warm":
            return self.storage_path / "media"
        elif tier == "cold":
            return self.storage_path / "cold"
        else:
            return self.storage_path / tier
    
    def close(self):
        """Clean shutdown"""
        logger.info("🏁 Archie: Prune Manager shutting down gracefully")