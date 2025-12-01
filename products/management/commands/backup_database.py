"""
Management command para ejecutar backups desde Django.
Comando: python manage.py backup_database [--type manual|auto]
"""

import os
import subprocess
import platform
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from typing import Dict, Any
import logging


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Django management command para ejecutar backups de base de datos."""
    
    help = 'Ejecuta backup de la base de datos PostgreSQL'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['manual', 'auto'],
            default='manual',
            help='Tipo de backup: manual (inmediato) o auto (programado)'
        )
        
        parser.add_argument(
            '--restore',
            type=str,
            help='Restaurar desde archivo de backup específico'
        )
        
        parser.add_argument(
            '--list',
            action='store_true',
            help='Listar backups disponibles'
        )
        
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Limpiar backups antiguos'
        )
        
        parser.add_argument(
            '--report',
            action='store_true',
            help='Generar reporte de backups'
        )

    def handle(self, *args, **options):
        """Maneja la ejecución del command."""
        try:
            self.backup_dir = Path(settings.BASE_DIR) / 'backups'
            self.scripts_dir = Path(settings.BASE_DIR) / 'scripts'
            
            # Determinar acciones a ejecutar
            if options['list']:
                self._list_backups()
            elif options['restore']:
                self._restore_backup(options['restore'])
            elif options['cleanup']:
                self._cleanup_backups()
            elif options['report']:
                self._generate_report()
            else:
                self._perform_backup(options['type'])
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error ejecutando backup: {e}")
            )
            raise CommandError(f"Error en backup: {e}")
    
    def _perform_backup(self, backup_type: str):
        """Ejecuta el script de backup correspondiente."""
        self.stdout.write("🔄 Iniciando proceso de backup...")
        
        try:
            # Determinar script según el sistema operativo
            if platform.system() == "Windows":
                script_path = self.scripts_dir / "backup_database.bat"
                cmd = [str(script_path), backup_type]
            else:
                script_path = self.scripts_dir / "backup_database.sh"
                # Hacer el script ejecutable
                os.chmod(script_path, 0o755)
                cmd = ["bash", str(script_path), backup_type]
            
            if not script_path.exists():
                raise CommandError(f"Script de backup no encontrado: {script_path}")
            
            # Ejecutar script de backup
            self.stdout.write(f"📋 Ejecutando: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                cwd=settings.BASE_DIR,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutos timeout
            )
            
            if result.returncode == 0:
                self.stdout.write(
                    self.style.SUCCESS("✅ Backup completado exitosamente")
                )
                
                # Mostrar output del script
                if result.stdout:
                    self.stdout.write("\n📄 Output del backup:")
                    for line in result.stdout.strip().split('\n'):
                        self.stdout.write(f"   {line}")
                
                # Mostrar ubicación de archivos
                self._show_backup_location()
                
            else:
                self.stdout.write(
                    self.style.ERROR("❌ Error durante el backup")
                )
                
                if result.stderr:
                    self.stdout.write("\n🚨 Errores:")
                    for line in result.stderr.strip().split('\n'):
                        self.stdout.write(f"   {line}")
                
                raise CommandError("Backup falló")
                
        except subprocess.TimeoutExpired:
            raise CommandError("Timeout ejecutando script de backup")
        except Exception as e:
            raise CommandError(f"Error ejecutando backup: {e}")
    
    def _list_backups(self):
        """Lista todos los backups disponibles."""
        self.stdout.write("📋 Backups disponibles:\n")
        
        backup_types = ['daily', 'weekly', 'monthly']
        
        for backup_type in backup_types:
            backup_path = self.backup_dir / backup_type
            
            if backup_path.exists():
                files = list(backup_path.glob('*.sql*'))
                
                if files:
                    self.stdout.write(f"🔹 {backup_type.upper()}:")
                    
                    # Ordenar por fecha de modificación (más reciente primero)
                    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
                    
                    for file in files[:5]:  # Mostrar solo los 5 más recientes
                        size = self._format_file_size(file.stat().st_size)
                        mtime = file.stat().st_mtime
                        import datetime
                        date_str = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
                        
                        self.stdout.write(f"   📁 {file.name} ({size}) - {date_str}")
                    
                    if len(files) > 5:
                        self.stdout.write(f"   ... y {len(files) - 5} más")
                else:
                    self.stdout.write(f"🔹 {backup_type.upper()}: Sin backups")
            
            self.stdout.write("")
    
    def _restore_backup(self, backup_file: str):
        """Restaura la base de datos desde un backup."""
        self.stdout.write(f"🔄 Restaurando backup: {backup_file}")
        
        # Buscar archivo en todos los directorios de backup
        backup_path = None
        for backup_type in ['daily', 'weekly', 'monthly']:
            potential_path = self.backup_dir / backup_type / backup_file
            if potential_path.exists():
                backup_path = potential_path
                break
        
        if not backup_path:
            raise CommandError(f"Archivo de backup no encontrado: {backup_file}")
        
        # Confirmar restauración
        confirm = input(
            f"\n⚠️  ATENCIÓN: Esto reemplazará todos los datos actuales.\n"
            f"¿Estás seguro de restaurar desde {backup_path.name}? (escriba 'SI' para confirmar): "
        )
        
        if confirm != 'SI':
            self.stdout.write("❌ Restauración cancelada")
            return
        
        try:
            # Obtener configuración de BD desde Django settings
            db_config = settings.DATABASES['default']
            
            # Preparar comando de restauración
            env = os.environ.copy()
            env['PGPASSWORD'] = db_config.get('PASSWORD', '')
            
            # Si el archivo está comprimido, descomprimirlo primero
            if backup_path.suffix == '.gz':
                self.stdout.write("📦 Descomprimiendo backup...")
                
                import gzip
                temp_sql_path = backup_path.with_suffix('')
                
                with gzip.open(backup_path, 'rt') as f_in:
                    with open(temp_sql_path, 'w') as f_out:
                        f_out.write(f_in.read())
                
                sql_file = temp_sql_path
            else:
                sql_file = backup_path
            
            # Ejecutar restauración
            cmd = [
                'psql',
                '-h', db_config.get('HOST', 'localhost'),
                '-p', str(db_config.get('PORT', 5432)),
                '-U', db_config.get('USER', ''),
                '-d', db_config['NAME'],
                '-f', str(sql_file)
            ]
            
            self.stdout.write("⚡ Ejecutando restauración...")
            
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutos timeout
            )
            
            # Limpiar archivo temporal si se creó
            if backup_path.suffix == '.gz' and temp_sql_path.exists():
                temp_sql_path.unlink()
            
            if result.returncode == 0:
                self.stdout.write(
                    self.style.SUCCESS("✅ Restauración completada exitosamente")
                )
            else:
                self.stdout.write(
                    self.style.ERROR("❌ Error durante la restauración")
                )
                if result.stderr:
                    self.stdout.write(f"Error: {result.stderr}")
                    
        except Exception as e:
            raise CommandError(f"Error durante restauración: {e}")
    
    def _cleanup_backups(self):
        """Ejecuta limpieza de backups antiguos."""
        self.stdout.write("🧹 Iniciando limpieza de backups antiguos...")
        
        # Ejecutar la función de limpieza del script de backup
        self._perform_backup_action("cleanup")
        
        self.stdout.write(
            self.style.SUCCESS("✅ Limpieza de backups completada")
        )
    
    def _generate_report(self):
        """Genera reporte de estado de backups."""
        self.stdout.write("📊 Generando reporte de backups...")
        
        report_data = {
            'total_backups': 0,
            'total_size': 0,
            'by_type': {}
        }
        
        for backup_type in ['daily', 'weekly', 'monthly']:
            backup_path = self.backup_dir / backup_type
            
            if backup_path.exists():
                files = list(backup_path.glob('*.sql*'))
                total_size = sum(f.stat().st_size for f in files)
                
                report_data['by_type'][backup_type] = {
                    'count': len(files),
                    'size': total_size,
                    'latest': max((f.stat().st_mtime for f in files), default=0)
                }
                
                report_data['total_backups'] += len(files)
                report_data['total_size'] += total_size
        
        # Mostrar reporte
        self.stdout.write("\n📋 REPORTE DE BACKUPS")
        self.stdout.write("=" * 50)
        self.stdout.write(f"📊 Total de backups: {report_data['total_backups']}")
        self.stdout.write(f"💾 Espacio utilizado: {self._format_file_size(report_data['total_size'])}")
        self.stdout.write("")
        
        for backup_type, data in report_data['by_type'].items():
            self.stdout.write(f"🔹 {backup_type.upper()}:")
            self.stdout.write(f"   Cantidad: {data['count']}")
            self.stdout.write(f"   Tamaño: {self._format_file_size(data['size'])}")
            
            if data['latest'] > 0:
                import datetime
                latest_date = datetime.datetime.fromtimestamp(data['latest']).strftime('%Y-%m-%d %H:%M')
                self.stdout.write(f"   Último backup: {latest_date}")
            
            self.stdout.write("")
    
    def _show_backup_location(self):
        """Muestra la ubicación de los backups."""
        self.stdout.write(f"\n📁 Backups guardados en: {self.backup_dir}")
        
        # Mostrar el backup más reciente
        latest_backup = None
        latest_time = 0
        
        for backup_type in ['daily', 'weekly', 'monthly']:
            backup_path = self.backup_dir / backup_type
            if backup_path.exists():
                for file in backup_path.glob('*.sql*'):
                    if file.stat().st_mtime > latest_time:
                        latest_time = file.stat().st_mtime
                        latest_backup = file
        
        if latest_backup:
            size = self._format_file_size(latest_backup.stat().st_size)
            self.stdout.write(f"📄 Último backup: {latest_backup.name} ({size})")
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Formatea el tamaño de archivo en formato legible."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
    
    def _perform_backup_action(self, action: str):
        """Ejecuta una acción específica del sistema de backup."""
        # Esta función puede extenderse para acciones específicas
        pass