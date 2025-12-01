#!/bin/bash

# =============================================================================
# SISTEMA DE BACKUPS AUTOMATIZADO PARA RETAIL API
# =============================================================================
# Este script realiza backups automáticos de PostgreSQL con rotación
# Uso: ./backup_database.sh [manual|auto]
# =============================================================================

set -e  # Salir si cualquier comando falla

# Configuración
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"
LOG_FILE="$BACKUP_DIR/backup.log"

# Configuración de base de datos (desde .env o por defecto)
DB_NAME="${DB_NAME:-retail_api_db}"
DB_USER="${DB_USER:-retail_user}"
DB_PASSWORD="${DB_PASSWORD:-retail_password}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

# Configuración de retención
DAILY_RETENTION=7    # Mantener 7 backups diarios
WEEKLY_RETENTION=4   # Mantener 4 backups semanales
MONTHLY_RETENTION=6  # Mantener 6 backups mensuales

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# FUNCIONES UTILITARIAS
# =============================================================================

log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

log_info() {
    log "INFO" "$1"
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    log "SUCCESS" "$1"
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    log "WARNING" "$1"
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    log "ERROR" "$1"
    echo -e "${RED}❌ $1${NC}"
}

# Verificar si PostgreSQL está disponible
check_database_connection() {
    log_info "Verificando conexión a la base de datos..."
    
    export PGPASSWORD="$DB_PASSWORD"
    
    if pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
        log_success "Conexión a base de datos exitosa"
        return 0
    else
        log_error "No se puede conectar a la base de datos"
        return 1
    fi
}

# Crear directorios necesarios
setup_directories() {
    log_info "Configurando directorios de backup..."
    
    mkdir -p "$BACKUP_DIR"/{daily,weekly,monthly,temp}
    
    # Crear archivo de log si no existe
    touch "$LOG_FILE"
    
    log_success "Directorios configurados"
}

# Realizar backup de la base de datos
perform_backup() {
    local backup_type="$1"
    local timestamp=$(date '+%Y%m%d_%H%M%S')
    local backup_filename="${DB_NAME}_${backup_type}_${timestamp}.sql.gz"
    local backup_path="$BACKUP_DIR/$backup_type/$backup_filename"
    local temp_path="$BACKUP_DIR/temp/${DB_NAME}_temp_${timestamp}.sql"
    
    log_info "Iniciando backup $backup_type: $backup_filename"
    
    # Configurar password para pg_dump
    export PGPASSWORD="$DB_PASSWORD"
    
    # Realizar dump
    if pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        --verbose --clean --no-owner --no-privileges \
        --format=plain > "$temp_path" 2>>"$LOG_FILE"; then
        
        # Comprimir backup
        if gzip -c "$temp_path" > "$backup_path"; then
            rm "$temp_path"
            
            local size=$(du -h "$backup_path" | cut -f1)
            log_success "Backup completado: $backup_filename ($size)"
            
            # Verificar integridad del archivo comprimido
            if gzip -t "$backup_path"; then
                log_success "Integridad del backup verificada"
                echo "$backup_path"
                return 0
            else
                log_error "Backup corrupto, eliminando archivo"
                rm "$backup_path"
                return 1
            fi
        else
            log_error "Error comprimiendo backup"
            rm "$temp_path"
            return 1
        fi
    else
        log_error "Error ejecutando pg_dump"
        rm -f "$temp_path"
        return 1
    fi
}

# Limpiar backups antiguos
cleanup_old_backups() {
    log_info "Iniciando limpieza de backups antiguos..."
    
    # Limpiar backups diarios
    local daily_count=$(find "$BACKUP_DIR/daily" -name "*.sql.gz" | wc -l)
    if [ "$daily_count" -gt "$DAILY_RETENTION" ]; then
        find "$BACKUP_DIR/daily" -name "*.sql.gz" -type f \
            -printf '%T@ %p\n' | sort -n | head -n -"$DAILY_RETENTION" | \
            cut -d' ' -f2- | xargs rm -f
        log_info "Backups diarios limpiados (mantener $DAILY_RETENTION)"
    fi
    
    # Limpiar backups semanales
    local weekly_count=$(find "$BACKUP_DIR/weekly" -name "*.sql.gz" | wc -l)
    if [ "$weekly_count" -gt "$WEEKLY_RETENTION" ]; then
        find "$BACKUP_DIR/weekly" -name "*.sql.gz" -type f \
            -printf '%T@ %p\n' | sort -n | head -n -"$WEEKLY_RETENTION" | \
            cut -d' ' -f2- | xargs rm -f
        log_info "Backups semanales limpiados (mantener $WEEKLY_RETENTION)"
    fi
    
    # Limpiar backups mensuales
    local monthly_count=$(find "$BACKUP_DIR/monthly" -name "*.sql.gz" | wc -l)
    if [ "$monthly_count" -gt "$MONTHLY_RETENTION" ]; then
        find "$BACKUP_DIR/monthly" -name "*.sql.gz" -type f \
            -printf '%T@ %p\n' | sort -n | head -n -"$MONTHLY_RETENTION" | \
            cut -d' ' -f2- | xargs rm -f
        log_info "Backups mensuales limpiados (mantener $MONTHLY_RETENTION)"
    fi
    
    # Limpiar archivos temporales
    find "$BACKUP_DIR/temp" -type f -mtime +1 -delete
    
    log_success "Limpieza completada"
}

# Determinar tipo de backup basado en fecha
determine_backup_type() {
    local day_of_week=$(date '+%u')  # 1=Monday, 7=Sunday
    local day_of_month=$(date '+%d')
    
    # Primer día del mes = backup mensual
    if [ "$day_of_month" = "01" ]; then
        echo "monthly"
    # Domingo = backup semanal
    elif [ "$day_of_week" = "7" ]; then
        echo "weekly"
    # Otros días = backup diario
    else
        echo "daily"
    fi
}

# Generar reporte de backups
generate_backup_report() {
    log_info "Generando reporte de backups..."
    
    local report_file="$BACKUP_DIR/backup_report_$(date '+%Y%m%d').txt"
    
    cat > "$report_file" << EOF
=====================================
REPORTE DE BACKUPS - RETAIL API
=====================================
Fecha: $(date '+%Y-%m-%d %H:%M:%S')
Base de datos: $DB_NAME
Host: $DB_HOST:$DB_PORT

BACKUPS DIARIOS (últimos $DAILY_RETENTION):
EOF
    
    find "$BACKUP_DIR/daily" -name "*.sql.gz" -type f -printf '%T@ %TY-%Tm-%Td %TH:%TM %s %p\n' | \
        sort -nr | head -n "$DAILY_RETENTION" | \
        awk '{printf "  %s %s  %s  %s\n", $2, $3, $4, $5}' >> "$report_file"
    
    cat >> "$report_file" << EOF

BACKUPS SEMANALES (últimos $WEEKLY_RETENTION):
EOF
    
    find "$BACKUP_DIR/weekly" -name "*.sql.gz" -type f -printf '%T@ %TY-%Tm-%Td %TH:%TM %s %p\n' | \
        sort -nr | head -n "$WEEKLY_RETENTION" | \
        awk '{printf "  %s %s  %s  %s\n", $2, $3, $4, $5}' >> "$report_file"
    
    cat >> "$report_file" << EOF

BACKUPS MENSUALES (últimos $MONTHLY_RETENTION):
EOF
    
    find "$BACKUP_DIR/monthly" -name "*.sql.gz" -type f -printf '%T@ %TY-%Tm-%Td %TH:%TM %s %p\n' | \
        sort -nr | head -n "$MONTHLY_RETENTION" | \
        awk '{printf "  %s %s  %s  %s\n", $2, $3, $4, $5}' >> "$report_file"
    
    local total_size=$(du -sh "$BACKUP_DIR" | cut -f1)
    echo -e "\nEspacio total utilizado: $total_size" >> "$report_file"
    
    log_success "Reporte generado: $report_file"
    echo "$report_file"
}

# Enviar notificación (webhook o email)
send_notification() {
    local status="$1"
    local message="$2"
    local backup_file="$3"
    
    # Aquí puedes agregar notificaciones a Slack, Discord, Email, etc.
    # Ejemplo básico:
    log_info "Notificación: [$status] $message"
    
    # Ejemplo de webhook (descomenta y configura)
    # if [ ! -z "$WEBHOOK_URL" ]; then
    #     curl -X POST "$WEBHOOK_URL" \
    #         -H "Content-Type: application/json" \
    #         -d "{\"status\":\"$status\",\"message\":\"$message\",\"backup\":\"$backup_file\"}"
    # fi
}

# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================

main() {
    local mode="${1:-auto}"
    
    echo "🔄 Iniciando sistema de backups - Retail API"
    echo "Modo: $mode | Fecha: $(date)"
    echo "=========================================="
    
    # Configurar directorios
    setup_directories
    
    # Verificar conexión a BD
    if ! check_database_connection; then
        send_notification "ERROR" "No se puede conectar a la base de datos"
        exit 1
    fi
    
    # Determinar tipo de backup
    local backup_type
    if [ "$mode" = "manual" ]; then
        backup_type="daily"
        log_info "Backup manual solicitado"
    else
        backup_type=$(determine_backup_type)
        log_info "Backup automático programado: $backup_type"
    fi
    
    # Realizar backup
    local backup_file
    if backup_file=$(perform_backup "$backup_type"); then
        send_notification "SUCCESS" "Backup $backup_type completado exitosamente" "$backup_file"
        
        # Limpiar backups antiguos
        cleanup_old_backups
        
        # Generar reporte
        generate_backup_report
        
        log_success "Proceso de backup completado exitosamente"
        echo "📁 Backup guardado en: $backup_file"
        
    else
        send_notification "ERROR" "Error durante el proceso de backup $backup_type"
        log_error "Proceso de backup falló"
        exit 1
    fi
}

# =============================================================================
# VALIDACIONES Y EJECUCIÓN
# =============================================================================

# Verificar dependencias
command -v pg_dump >/dev/null 2>&1 || { 
    log_error "pg_dump no está instalado. Instala PostgreSQL client."
    exit 1
}

command -v pg_isready >/dev/null 2>&1 || {
    log_error "pg_isready no está disponible. Instala PostgreSQL client."
    exit 1
}

# Cargar variables de entorno si existe .env
if [ -f "$PROJECT_DIR/.env" ]; then
    export $(cat "$PROJECT_DIR/.env" | grep -v '^#' | xargs)
fi

# Ejecutar función principal
main "$@"