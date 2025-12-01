@echo off
REM =============================================================================
REM SISTEMA DE BACKUPS PARA WINDOWS - RETAIL API
REM =============================================================================
REM Script de backup para PostgreSQL en entorno Windows
REM Uso: backup_database.bat [manual|auto]
REM =============================================================================

setlocal enabledelayedexpansion

REM Configuración
set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%..\"
set "BACKUP_DIR=%PROJECT_DIR%backups"
set "LOG_FILE=%BACKUP_DIR%\backup.log"

REM Configuración de base de datos (por defecto)
if "%DB_NAME%"=="" set "DB_NAME=retail_api_db"
if "%DB_USER%"=="" set "DB_USER=retail_user"
if "%DB_PASSWORD%"=="" set "DB_PASSWORD=retail_password"
if "%DB_HOST%"=="" set "DB_HOST=localhost"
if "%DB_PORT%"=="" set "DB_PORT=5432"

REM Configuración de retención
set "DAILY_RETENTION=7"
set "WEEKLY_RETENTION=4"
set "MONTHLY_RETENTION=6"

REM =============================================================================
REM FUNCIONES
REM =============================================================================

:log_message
    set "level=%1"
    set "message=%2"
    for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set "current_date=%%c-%%a-%%b"
    for /f "tokens=1-2 delims=: " %%a in ("%time%") do set "current_time=%%a:%%b"
    echo [%current_date% %current_time%] [%level%] %message% >> "%LOG_FILE%"
    echo [%level%] %message%
goto :eof

:check_dependencies
    echo Verificando dependencias...
    
    REM Verificar si pg_dump está disponible
    pg_dump --version >nul 2>&1
    if errorlevel 1 (
        call :log_message "ERROR" "pg_dump no encontrado. Instala PostgreSQL client."
        echo ❌ Error: pg_dump no está disponible
        echo Instala PostgreSQL client tools desde: https://www.postgresql.org/download/windows/
        exit /b 1
    )
    
    REM Verificar si 7zip está disponible (para comprimir)
    7z >nul 2>&1
    if errorlevel 1 (
        call :log_message "WARNING" "7zip no encontrado, usando compresión nativa"
        echo ⚠️  7zip no encontrado, los backups no serán comprimidos
    )
    
    call :log_message "INFO" "Dependencias verificadas"
goto :eof

:setup_directories
    call :log_message "INFO" "Configurando directorios..."
    
    if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"
    if not exist "%BACKUP_DIR%\daily" mkdir "%BACKUP_DIR%\daily"
    if not exist "%BACKUP_DIR%\weekly" mkdir "%BACKUP_DIR%\weekly"
    if not exist "%BACKUP_DIR%\monthly" mkdir "%BACKUP_DIR%\monthly"
    if not exist "%BACKUP_DIR%\temp" mkdir "%BACKUP_DIR%\temp"
    
    if not exist "%LOG_FILE%" echo. > "%LOG_FILE%"
    
    call :log_message "SUCCESS" "Directorios configurados"
goto :eof

:check_database_connection
    call :log_message "INFO" "Verificando conexión a base de datos..."
    
    set "PGPASSWORD=%DB_PASSWORD%"
    
    pg_isready -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d %DB_NAME% >nul 2>&1
    if errorlevel 1 (
        call :log_message "ERROR" "No se puede conectar a la base de datos"
        echo ❌ Error de conexión a PostgreSQL
        echo Verifica que el servidor esté ejecutándose y las credenciales sean correctas
        exit /b 1
    )
    
    call :log_message "SUCCESS" "Conexión exitosa a base de datos"
goto :eof

:determine_backup_type
    REM Obtener día de la semana (1=Monday, 7=Sunday)
    for /f "skip=1 delims=" %%a in ('wmic path win32_localtime get dayofweek /value') do (
        for /f "delims=" %%b in ("%%a") do (
            set "%%b"
        )
    )
    
    REM Obtener día del mes
    for /f "tokens=3 delims=/ " %%a in ("%date%") do set "day_of_month=%%a"
    
    REM Determinar tipo de backup
    if "%day_of_month%"=="01" (
        set "backup_type=monthly"
    ) else if "%dayofweek%"=="1" (
        set "backup_type=weekly"
    ) else (
        set "backup_type=daily"
    )
goto :eof

:perform_backup
    set "backup_type=%1"
    
    REM Generar timestamp
    for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set "date_part=%%c%%a%%b"
    for /f "tokens=1-2 delims=: " %%a in ("%time%") do set "time_part=%%a%%b"
    set "timestamp=%date_part%_%time_part%"
    
    set "backup_filename=%DB_NAME%_%backup_type%_%timestamp%.sql"
    set "backup_path=%BACKUP_DIR%\%backup_type%\%backup_filename%"
    set "temp_path=%BACKUP_DIR%\temp\%DB_NAME%_temp_%timestamp%.sql"
    
    call :log_message "INFO" "Iniciando backup %backup_type%: %backup_filename%"
    
    REM Configurar password
    set "PGPASSWORD=%DB_PASSWORD%"
    
    REM Realizar dump
    pg_dump -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d %DB_NAME% --verbose --clean --no-owner --no-privileges --format=plain > "%temp_path%" 2>>"%LOG_FILE%"
    
    if errorlevel 1 (
        call :log_message "ERROR" "Error ejecutando pg_dump"
        if exist "%temp_path%" del "%temp_path%"
        exit /b 1
    )
    
    REM Intentar comprimir con 7zip
    7z >nul 2>&1
    if not errorlevel 1 (
        7z a -tgzip "%backup_path%.gz" "%temp_path%" >nul 2>&1
        if not errorlevel 1 (
            del "%temp_path%"
            set "final_backup_path=%backup_path%.gz"
            call :log_message "SUCCESS" "Backup comprimido: %backup_filename%.gz"
        ) else (
            copy "%temp_path%" "%backup_path%" >nul
            del "%temp_path%"
            set "final_backup_path=%backup_path%"
            call :log_message "SUCCESS" "Backup completado: %backup_filename%"
        )
    ) else (
        copy "%temp_path%" "%backup_path%" >nul
        del "%temp_path%"
        set "final_backup_path=%backup_path%"
        call :log_message "SUCCESS" "Backup completado: %backup_filename%"
    )
    
    REM Mostrar tamaño del archivo
    for %%A in ("%final_backup_path%") do (
        set "file_size=%%~zA"
        call :log_message "INFO" "Tamaño del backup: !file_size! bytes"
    )
    
    echo ✅ Backup guardado: %final_backup_path%
goto :eof

:cleanup_old_backups
    call :log_message "INFO" "Limpiando backups antiguos..."
    
    REM Limpiar backups diarios (mantener solo los más recientes)
    pushd "%BACKUP_DIR%\daily"
    for /f "skip=%DAILY_RETENTION%" %%f in ('dir /b /o-d *.sql *.sql.gz 2^>nul') do (
        del "%%f" >nul 2>&1
        call :log_message "INFO" "Eliminado backup diario antiguo: %%f"
    )
    popd
    
    REM Limpiar backups semanales
    pushd "%BACKUP_DIR%\weekly"
    for /f "skip=%WEEKLY_RETENTION%" %%f in ('dir /b /o-d *.sql *.sql.gz 2^>nul') do (
        del "%%f" >nul 2>&1
        call :log_message "INFO" "Eliminado backup semanal antiguo: %%f"
    )
    popd
    
    REM Limpiar backups mensuales
    pushd "%BACKUP_DIR%\monthly"
    for /f "skip=%MONTHLY_RETENTION%" %%f in ('dir /b /o-d *.sql *.sql.gz 2^>nul') do (
        del "%%f" >nul 2>&1
        call :log_message "INFO" "Eliminado backup mensual antiguo: %%f"
    )
    popd
    
    REM Limpiar archivos temporales
    del "%BACKUP_DIR%\temp\*" >nul 2>&1
    
    call :log_message "SUCCESS" "Limpieza completada"
goto :eof

:generate_report
    call :log_message "INFO" "Generando reporte de backups..."
    
    set "report_file=%BACKUP_DIR%\backup_report_%date_part%.txt"
    
    echo ===================================== > "%report_file%"
    echo REPORTE DE BACKUPS - RETAIL API >> "%report_file%"
    echo ===================================== >> "%report_file%"
    echo Fecha: %date% %time% >> "%report_file%"
    echo Base de datos: %DB_NAME% >> "%report_file%"
    echo Host: %DB_HOST%:%DB_PORT% >> "%report_file%"
    echo. >> "%report_file%"
    echo BACKUPS DIARIOS: >> "%report_file%"
    
    pushd "%BACKUP_DIR%\daily"
    for %%f in (*.sql *.sql.gz) do (
        echo   %%f %%~tf %%~zf bytes >> "%report_file%"
    )
    popd
    
    echo. >> "%report_file%"
    echo BACKUPS SEMANALES: >> "%report_file%"
    
    pushd "%BACKUP_DIR%\weekly"
    for %%f in (*.sql *.sql.gz) do (
        echo   %%f %%~tf %%~zf bytes >> "%report_file%"
    )
    popd
    
    echo. >> "%report_file%"
    echo BACKUPS MENSUALES: >> "%report_file%"
    
    pushd "%BACKUP_DIR%\monthly"
    for %%f in (*.sql *.sql.gz) do (
        echo   %%f %%~tf %%~zf bytes >> "%report_file%"
    )
    popd
    
    call :log_message "SUCCESS" "Reporte generado: %report_file%"
goto :eof

:main
    set "mode=%1"
    if "%mode%"=="" set "mode=auto"
    
    echo 🔄 Sistema de Backups - Retail API
    echo Modo: %mode% ^| Fecha: %date% %time%
    echo ==========================================
    
    REM Verificar dependencias
    call :check_dependencies
    if errorlevel 1 exit /b 1
    
    REM Configurar directorios
    call :setup_directories
    
    REM Verificar conexión
    call :check_database_connection
    if errorlevel 1 exit /b 1
    
    REM Determinar tipo de backup
    if "%mode%"=="manual" (
        set "backup_type=daily"
        call :log_message "INFO" "Backup manual solicitado"
    ) else (
        call :determine_backup_type
        call :log_message "INFO" "Backup automático: !backup_type!"
    )
    
    REM Realizar backup
    call :perform_backup !backup_type!
    if errorlevel 1 (
        call :log_message "ERROR" "Error durante backup"
        echo ❌ Backup falló
        exit /b 1
    )
    
    REM Limpiar backups antiguos
    call :cleanup_old_backups
    
    REM Generar reporte
    call :generate_report
    
    call :log_message "SUCCESS" "Proceso completado exitosamente"
    echo ✅ Backup completado exitosamente
goto :eof

REM =============================================================================
REM CARGAR VARIABLES DE ENTORNO Y EJECUTAR
REM =============================================================================

REM Cargar .env si existe
if exist "%PROJECT_DIR%.env" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%PROJECT_DIR%.env") do (
        if not "%%a"=="" if not "%%a:~0,1%"=="#" set "%%a=%%b"
    )
)

REM Ejecutar función principal
call :main %1

endlocal