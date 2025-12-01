"""
Utilidades adicionales para el sistema de backups.
Funciones para validación, monitoreo y mantenimiento.
"""

import os
import gzip
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
import logging


logger = logging.getLogger(__name__)


class BackupValidator:
    """Validador de integridad de backups."""
    
    def __init__(self, backup_dir: Path):
        self.backup_dir = Path(backup_dir)
        self.checksums_file = self.backup_dir / "checksums.json"
    
    def calculate_checksum(self, file_path: Path) -> str:
        """Calcula el checksum SHA256 de un archivo."""
        sha256_hash = hashlib.sha256()
        
        try:
            # Manejar archivos comprimidos
            if file_path.suffix == '.gz':
                with gzip.open(file_path, 'rb') as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        sha256_hash.update(chunk)
            else:
                with open(file_path, 'rb') as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        sha256_hash.update(chunk)
            
            return sha256_hash.hexdigest()
            
        except Exception as e:
            logger.error(f"Error calculando checksum para {file_path}: {e}")
            return ""
    
    def store_checksum(self, file_path: Path, checksum: str):
        """Almacena el checksum de un archivo."""
        checksums = self.load_checksums()
        
        checksums[str(file_path.name)] = {
            "checksum": checksum,
            "created": datetime.now().isoformat(),
            "size": file_path.stat().st_size
        }
        
        self.save_checksums(checksums)
    
    def load_checksums(self) -> Dict[str, Any]:
        """Carga los checksums almacenados."""
        if self.checksums_file.exists():
            try:
                with open(self.checksums_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error cargando checksums: {e}")
        
        return {}
    
    def save_checksums(self, checksums: Dict[str, Any]):
        """Guarda los checksums en disco."""
        try:
            with open(self.checksums_file, 'w') as f:
                json.dump(checksums, f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando checksums: {e}")
    
    def validate_backup(self, file_path: Path) -> bool:
        """Valida la integridad de un backup."""
        checksums = self.load_checksums()
        filename = file_path.name
        
        if filename not in checksums:
            logger.warning(f"No hay checksum almacenado para {filename}")
            return False
        
        stored_checksum = checksums[filename]["checksum"]
        current_checksum = self.calculate_checksum(file_path)
        
        if stored_checksum == current_checksum:
            logger.info(f"Backup {filename} validado exitosamente")
            return True
        else:
            logger.error(f"Backup {filename} está corrupto!")
            return False
    
    def validate_all_backups(self) -> Dict[str, bool]:
        """Valida todos los backups disponibles."""
        results = {}
        
        for backup_type in ['daily', 'weekly', 'monthly']:
            backup_path = self.backup_dir / backup_type
            
            if backup_path.exists():
                for file_path in backup_path.glob('*.sql*'):
                    results[str(file_path)] = self.validate_backup(file_path)
        
        return results


class BackupMonitor:
    """Monitor de sistema de backups."""
    
    def __init__(self, backup_dir: Path):
        self.backup_dir = Path(backup_dir)
        self.metrics = {
            'last_backup': None,
            'backup_count': 0,
            'total_size': 0,
            'oldest_backup': None,
            'newest_backup': None,
            'failed_validations': []
        }
    
    def collect_metrics(self) -> Dict[str, Any]:
        """Recolecta métricas del sistema de backups."""
        all_backups = []
        total_size = 0
        
        for backup_type in ['daily', 'weekly', 'monthly']:
            backup_path = self.backup_dir / backup_type
            
            if backup_path.exists():
                for file_path in backup_path.glob('*.sql*'):
                    stat = file_path.stat()
                    all_backups.append({
                        'path': file_path,
                        'type': backup_type,
                        'size': stat.st_size,
                        'mtime': stat.st_mtime
                    })
                    total_size += stat.st_size
        
        if all_backups:
            # Ordenar por fecha de modificación
            all_backups.sort(key=lambda x: x['mtime'])
            
            self.metrics.update({
                'backup_count': len(all_backups),
                'total_size': total_size,
                'oldest_backup': all_backups[0],
                'newest_backup': all_backups[-1],
                'last_backup': datetime.fromtimestamp(all_backups[-1]['mtime'])
            })
        
        return self.metrics
    
    def check_backup_freshness(self, max_age_hours: int = 25) -> bool:
        """Verifica si hay backups recientes."""
        metrics = self.collect_metrics()
        
        if not metrics['last_backup']:
            return False
        
        age = datetime.now() - metrics['last_backup']
        return age.total_seconds() < (max_age_hours * 3600)
    
    def generate_health_report(self) -> Dict[str, Any]:
        """Genera reporte de salud del sistema de backups."""
        metrics = self.collect_metrics()
        
        # Verificar validaciones
        validator = BackupValidator(self.backup_dir)
        validation_results = validator.validate_all_backups()
        
        failed_validations = [
            path for path, valid in validation_results.items() if not valid
        ]
        
        health_status = "healthy"
        issues = []
        
        # Verificar si hay backups recientes
        if not self.check_backup_freshness():
            health_status = "warning"
            issues.append("No hay backups recientes (últimas 25 horas)")
        
        # Verificar validaciones fallidas
        if failed_validations:
            health_status = "critical"
            issues.append(f"{len(failed_validations)} backups con validación fallida")
        
        # Verificar espacio en disco
        try:
            disk_usage = self.backup_dir.stat()
            # Simplificación - en producción usar shutil.disk_usage()
            if metrics['total_size'] > 10 * 1024 * 1024 * 1024:  # 10GB
                health_status = "warning"
                issues.append("Uso de disco alto para backups")
        except Exception:
            pass
        
        return {
            'status': health_status,
            'issues': issues,
            'metrics': metrics,
            'failed_validations': failed_validations,
            'last_check': datetime.now().isoformat()
        }


class BackupNotifier:
    """Sistema de notificaciones para backups."""
    
    def __init__(self, config: Dict[str, str]):
        self.config = config
        self.smtp_server = config.get('SMTP_SERVER')
        self.smtp_port = int(config.get('SMTP_PORT', 587))
        self.smtp_user = config.get('SMTP_USER')
        self.smtp_password = config.get('SMTP_PASSWORD')
        self.webhook_url = config.get('BACKUP_WEBHOOK_URL')
        self.email_to = config.get('BACKUP_EMAIL_TO')
        self.email_from = config.get('BACKUP_EMAIL_FROM')
    
    def send_email_notification(self, subject: str, body: str, is_html: bool = False):
        """Envía notificación por email."""
        if not all([self.smtp_server, self.smtp_user, self.smtp_password, self.email_to]):
            logger.warning("Configuración de email incompleta")
            return False
        
        try:
            msg = MimeMultipart()
            msg['From'] = self.email_from or self.smtp_user
            msg['To'] = self.email_to
            msg['Subject'] = subject
            
            msg.attach(MimeText(body, 'html' if is_html else 'plain'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email enviado: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando email: {e}")
            return False
    
    def send_webhook_notification(self, payload: Dict[str, Any]):
        """Envía notificación via webhook."""
        if not self.webhook_url:
            logger.warning("URL de webhook no configurada")
            return False
        
        try:
            import urllib.request
            import urllib.parse
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status == 200:
                    logger.info("Webhook enviado exitosamente")
                    return True
                else:
                    logger.warning(f"Webhook respondió con status {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error enviando webhook: {e}")
            return False
    
    def notify_backup_success(self, backup_file: str, backup_type: str, size: int):
        """Notifica backup exitoso."""
        subject = f"✅ Backup {backup_type} exitoso - Retail API"
        body = f"""
        Backup completado exitosamente:
        
        📁 Archivo: {backup_file}
        📊 Tipo: {backup_type}
        💾 Tamaño: {self._format_size(size)}
        🕒 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        self.send_email_notification(subject, body)
        
        webhook_payload = {
            "status": "success",
            "type": backup_type,
            "file": backup_file,
            "size": size,
            "timestamp": datetime.now().isoformat()
        }
        self.send_webhook_notification(webhook_payload)
    
    def notify_backup_failure(self, backup_type: str, error: str):
        """Notifica fallo en backup."""
        subject = f"❌ Backup {backup_type} FALLÓ - Retail API"
        body = f"""
        ATENCIÓN: El backup ha fallado
        
        📊 Tipo: {backup_type}
        🚨 Error: {error}
        🕒 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        Por favor revisar el sistema de backups inmediatamente.
        """
        
        self.send_email_notification(subject, body)
        
        webhook_payload = {
            "status": "error",
            "type": backup_type,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        self.send_webhook_notification(webhook_payload)
    
    def notify_health_check(self, health_report: Dict[str, Any]):
        """Notifica resultado de check de salud."""
        if health_report['status'] in ['warning', 'critical']:
            emoji = "⚠️" if health_report['status'] == 'warning' else "🚨"
            subject = f"{emoji} Alerta de Backups - Retail API"
            
            body = f"""
            Estado del sistema de backups: {health_report['status'].upper()}
            
            Problemas detectados:
            {chr(10).join(f"• {issue}" for issue in health_report['issues'])}
            
            Métricas:
            • Total backups: {health_report['metrics']['backup_count']}
            • Último backup: {health_report['metrics']['last_backup']}
            • Tamaño total: {self._format_size(health_report['metrics']['total_size'])}
            
            Fecha del check: {health_report['last_check']}
            """
            
            self.send_email_notification(subject, body)
    
    def _format_size(self, size_bytes: int) -> str:
        """Formatea tamaño en bytes a formato legible."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"


def cleanup_orphaned_files(backup_dir: Path, dry_run: bool = True) -> List[str]:
    """Limpia archivos huérfanos y temporales."""
    removed_files = []
    
    # Buscar archivos temporales antiguos
    temp_dir = backup_dir / "temp"
    if temp_dir.exists():
        cutoff_time = datetime.now() - timedelta(days=1)
        
        for file_path in temp_dir.iterdir():
            if file_path.is_file():
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mtime < cutoff_time:
                    if not dry_run:
                        file_path.unlink()
                    removed_files.append(str(file_path))
    
    # Buscar archivos sin checksums (posiblemente corruptos)
    validator = BackupValidator(backup_dir)
    checksums = validator.load_checksums()
    
    for backup_type in ['daily', 'weekly', 'monthly']:
        backup_path = backup_dir / backup_type
        
        if backup_path.exists():
            for file_path in backup_path.glob('*.sql*'):
                if file_path.name not in checksums:
                    logger.warning(f"Archivo sin checksum encontrado: {file_path}")
                    # Generar checksum para archivos existentes
                    checksum = validator.calculate_checksum(file_path)
                    if checksum and not dry_run:
                        validator.store_checksum(file_path, checksum)
    
    return removed_files


def get_backup_statistics(backup_dir: Path) -> Dict[str, Any]:
    """Obtiene estadísticas detalladas de backups."""
    stats = {
        'by_type': {},
        'by_month': {},
        'total_files': 0,
        'total_size': 0,
        'average_size': 0,
        'oldest_backup': None,
        'newest_backup': None
    }
    
    all_files = []
    
    for backup_type in ['daily', 'weekly', 'monthly']:
        backup_path = backup_dir / backup_type
        type_stats = {
            'count': 0,
            'size': 0,
            'oldest': None,
            'newest': None
        }
        
        if backup_path.exists():
            files = list(backup_path.glob('*.sql*'))
            
            for file_path in files:
                file_stat = file_path.stat()
                file_info = {
                    'path': file_path,
                    'type': backup_type,
                    'size': file_stat.st_size,
                    'mtime': file_stat.st_mtime
                }
                
                all_files.append(file_info)
                
                type_stats['count'] += 1
                type_stats['size'] += file_stat.st_size
                
                if type_stats['oldest'] is None or file_stat.st_mtime < type_stats['oldest']:
                    type_stats['oldest'] = file_stat.st_mtime
                
                if type_stats['newest'] is None or file_stat.st_mtime > type_stats['newest']:
                    type_stats['newest'] = file_stat.st_mtime
        
        stats['by_type'][backup_type] = type_stats
    
    # Estadísticas globales
    if all_files:
        stats['total_files'] = len(all_files)
        stats['total_size'] = sum(f['size'] for f in all_files)
        stats['average_size'] = stats['total_size'] / stats['total_files']
        
        sorted_files = sorted(all_files, key=lambda x: x['mtime'])
        stats['oldest_backup'] = sorted_files[0]['mtime']
        stats['newest_backup'] = sorted_files[-1]['mtime']
        
        # Agrupar por mes
        for file_info in all_files:
            month_key = datetime.fromtimestamp(file_info['mtime']).strftime('%Y-%m')
            if month_key not in stats['by_month']:
                stats['by_month'][month_key] = {'count': 0, 'size': 0}
            
            stats['by_month'][month_key]['count'] += 1
            stats['by_month'][month_key]['size'] += file_info['size']
    
    return stats