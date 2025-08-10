"""
Health Staleness Job - Monitor health data delivery freshness
"""
import logging
from datetime import datetime, timedelta
from .scheduler import JobResult
from ..db import Database

logger = logging.getLogger(__name__)


async def health_staleness_handler(payload):
    """Monitor health data freshness and alert if stale"""
    try:
        max_staleness_hours = payload.get("max_staleness_hours", 24)
        alert_threshold_hours = payload.get("alert_threshold_hours", 48)
        
        db = Database()
        db.initialize()
        
        result = await _check_health_staleness(db, max_staleness_hours, alert_threshold_hours)
        
        db.close()
        return result
        
    except Exception as e:
        logger.error(f"Health staleness job failed: {e}")
        return JobResult(
            success=False,
            message=f"Health staleness check failed: {str(e)}"
        )


async def _check_health_staleness(db: Database, max_staleness_hours: int, alert_threshold_hours: int) -> JobResult:
    """Check for stale health data and generate alerts"""
    try:
        # Calculate cutoff times
        staleness_cutoff = int((datetime.now() - timedelta(hours=max_staleness_hours)).timestamp())
        alert_cutoff = int((datetime.now() - timedelta(hours=alert_threshold_hours)).timestamp())
        
        # Find latest health summaries by type
        health_types = ['sleep', 'hr', 'hrv', 'workout', 'nutrition', 'mood']
        
        staleness_report = {}
        alerts = []
        total_stale = 0
        total_critical = 0
        
        for health_type in health_types:
            # Get latest health summary of this type
            latest_entries = db.search_entities(
                entity_type='health_summary',
                limit=1
            )
            
            # Filter by health type in payload
            latest_for_type = None
            for entity in latest_entries:
                payload = entity.get('payload', {})
                if payload.get('type') == health_type:
                    latest_for_type = entity
                    break
            
            if latest_for_type:
                last_update = latest_for_type['created']
                hours_ago = (int(datetime.now().timestamp()) - last_update) / 3600
                
                status = "fresh"
                if last_update < staleness_cutoff:
                    status = "stale"
                    total_stale += 1
                    
                    if last_update < alert_cutoff:
                        status = "critical"
                        total_critical += 1
                        alerts.append({
                            'type': 'health_data_stale',
                            'severity': 'critical',
                            'message': f'No {health_type} data received in {hours_ago:.1f} hours',
                            'health_type': health_type,
                            'hours_since_last': hours_ago
                        })
                    else:
                        alerts.append({
                            'type': 'health_data_stale', 
                            'severity': 'warning',
                            'message': f'{health_type.title()} data is {hours_ago:.1f} hours old',
                            'health_type': health_type,
                            'hours_since_last': hours_ago
                        })
                
                staleness_report[health_type] = {
                    'last_update': datetime.fromtimestamp(last_update).isoformat(),
                    'hours_ago': round(hours_ago, 1),
                    'status': status
                }
            else:
                # No data ever received for this type
                staleness_report[health_type] = {
                    'last_update': None,
                    'hours_ago': None,
                    'status': 'missing'
                }
                
                alerts.append({
                    'type': 'health_data_missing',
                    'severity': 'warning',
                    'message': f'No {health_type} data has ever been received',
                    'health_type': health_type
                })
        
        # Generate summary
        if total_critical > 0:
            severity = 'critical'
            message = f"Critical: {total_critical} health data types haven't been updated in over {alert_threshold_hours} hours"
        elif total_stale > 0:
            severity = 'warning'
            message = f"Warning: {total_stale} health data types are stale (>{max_staleness_hours}h old)"
        else:
            severity = 'ok'
            message = "All health data is fresh"
        
        # Store alerts as entities if any
        if alerts:
            for alert in alerts:
                alert_entity = {
                    'id': f"health_alert_{int(datetime.now().timestamp())}_{alert['health_type']}",
                    'type': 'system_alert',
                    'payload': {
                        'id': alert['health_type'],
                        'alert_type': alert['type'],
                        'severity': alert['severity'],
                        'message': alert['message'],
                        'health_type': alert.get('health_type'),
                        'hours_since_last': alert.get('hours_since_last'),
                        'created_at': datetime.now().isoformat()
                    },
                    'tags': ['health', 'staleness', alert['severity']],
                    'assistant_id': 'archie_health_monitor'
                }
                
                db.insert_entity(alert_entity)
        
        logger.info(f"🩺 Health staleness check complete: {severity}")
        logger.info(f"   Fresh: {len(health_types) - total_stale}, Stale: {total_stale}, Critical: {total_critical}")
        
        return JobResult(
            success=True,
            message=message,
            data={
                'severity': severity,
                'staleness_report': staleness_report,
                'total_fresh': len(health_types) - total_stale,
                'total_stale': total_stale,
                'total_critical': total_critical,
                'alerts_generated': len(alerts),
                'alerts': alerts
            }
        )
        
    except Exception as e:
        logger.error(f"Health staleness check failed: {e}")
        return JobResult(
            success=False,
            message=f"Health staleness check failed: {str(e)}"
        )


async def get_health_freshness_report() -> dict:
    """Get current health data freshness report"""
    try:
        db = Database()
        db.initialize()
        
        # Get all health summaries grouped by type
        health_entities = db.search_entities(
            entity_type='health_summary',
            limit=1000,
            include_archived=False
        )
        
        # Group by health type and find latest for each
        type_latest = {}
        for entity in health_entities:
            payload = entity.get('payload', {})
            health_type = payload.get('type')
            
            if health_type:
                if health_type not in type_latest or entity['created'] > type_latest[health_type]['created']:
                    type_latest[health_type] = entity
        
        # Build freshness report
        report = {}
        now = datetime.now()
        
        for health_type, entity in type_latest.items():
            last_update = datetime.fromtimestamp(entity['created'])
            hours_ago = (now - last_update).total_seconds() / 3600
            
            report[health_type] = {
                'last_update': last_update.isoformat(),
                'hours_ago': round(hours_ago, 1),
                'entity_id': entity['id'],
                'status': 'fresh' if hours_ago < 24 else 'stale' if hours_ago < 48 else 'critical'
            }
        
        db.close()
        return report
        
    except Exception as e:
        logger.error(f"Failed to get health freshness report: {e}")
        return {'error': str(e)}