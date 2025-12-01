"""
Test de carga para Django - 500 requests/segundo
Ejecutar desde Django con: python manage.py run_load_test

Este archivo contiene todo lo necesario para ejecutar tests de carga usando threading.
No requiere dependencias adicionales más allá de las librerías estándar de Python.
"""

import os
import sys
import django
import threading
import time
import json
import random
import urllib.request
import urllib.parse
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import statistics
import csv
from pathlib import Path

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'retail_api.settings')
django.setup()

from django.core.management.base import BaseCommand
from django.conf import settings


class LoadTestResult:
    """Clase para almacenar resultados de un request individual."""
    
    def __init__(self, endpoint: str, method: str, status_code: int, 
                 response_time: float, success: bool, error: str = None):
        self.endpoint = endpoint
        self.method = method
        self.status_code = status_code
        self.response_time = response_time
        self.success = success
        self.error = error
        self.timestamp = time.time()


class LoadTestRunner:
    """Ejecutor de tests de carga usando threading nativo de Python."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.results: List[LoadTestResult] = []
        self.start_time = None
        self.end_time = None
        self.lock = threading.Lock()
        
        # Configuración de endpoints y sus pesos
        self.endpoints = {
            '/api/products/': {'method': 'GET', 'weight': 30},
            '/api/stores/': {'method': 'GET', 'weight': 15},
            '/api/inventory/alerts/': {'method': 'GET', 'weight': 10},
            '/api/movements/': {'method': 'GET', 'weight': 5},
        }
        
        # Datos para requests POST
        self.test_data = {
            'products': [
                {
                    "name": f"Load Test Product {i}",
                    "description": f"Product created during load test {i}",
                    "price": round(random.uniform(10.0, 200.0), 2),
                    "sku": f"LOAD-{i:05d}"
                }
                for i in range(100)
            ],
            'stores': [
                {
                    "name": f"Load Test Store {i}",
                    "address": f"Test Address {i}, City {i}"
                }
                for i in range(20)
            ]
        }
    
    def make_request(self, endpoint: str, method: str = 'GET', data: dict = None) -> LoadTestResult:
        """Realiza un request HTTP individual."""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            # Preparar request
            if method == 'GET':
                req = urllib.request.Request(url, method='GET')
                req.add_header('Content-Type', 'application/json')
                
            elif method == 'POST':
                json_data = json.dumps(data or {}).encode('utf-8')
                req = urllib.request.Request(url, data=json_data, method='POST')
                req.add_header('Content-Type', 'application/json')
            
            else:
                raise ValueError(f"Método HTTP no soportado: {method}")
            
            # Realizar request
            with urllib.request.urlopen(req, timeout=30) as response:
                response_time = (time.time() - start_time) * 1000  # En milisegundos
                status_code = response.getcode()
                success = 200 <= status_code < 400
                
                return LoadTestResult(
                    endpoint=endpoint,
                    method=method,
                    status_code=status_code,
                    response_time=response_time,
                    success=success
                )
        
        except urllib.error.HTTPError as e:
            response_time = (time.time() - start_time) * 1000
            return LoadTestResult(
                endpoint=endpoint,
                method=method,
                status_code=e.code,
                response_time=response_time,
                success=False,
                error=f"HTTP {e.code}: {e.reason}"
            )
        
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return LoadTestResult(
                endpoint=endpoint,
                method=method,
                status_code=0,
                response_time=response_time,
                success=False,
                error=str(e)
            )
    
    def worker_thread(self, duration_seconds: int, requests_per_second: float):
        """Función ejecutada por cada thread worker."""
        # Calcular intervalo entre requests para este thread
        interval = 1.0 / requests_per_second
        end_time = time.time() + duration_seconds
        
        while time.time() < end_time:
            try:
                # Seleccionar endpoint basado en peso
                endpoint, config = self.select_weighted_endpoint()
                method = config['method']
                
                # Preparar datos si es POST
                data = None
                if method == 'POST':
                    if 'products' in endpoint:
                        data = random.choice(self.test_data['products'])
                    elif 'stores' in endpoint:
                        data = random.choice(self.test_data['stores'])
                
                # Realizar request
                result = self.make_request(endpoint, method, data)
                
                # Guardar resultado thread-safe
                with self.lock:
                    self.results.append(result)
                
                # Esperar antes del siguiente request
                time.sleep(max(0, interval))
                
            except Exception as e:
                print(f"Error en worker thread: {e}")
                continue
    
    def select_weighted_endpoint(self) -> Tuple[str, Dict]:
        """Selecciona un endpoint basado en los pesos configurados."""
        # Crear lista ponderada
        weighted_endpoints = []
        for endpoint, config in self.endpoints.items():
            weighted_endpoints.extend([endpoint] * config['weight'])
        
        selected_endpoint = random.choice(weighted_endpoints)
        return selected_endpoint, self.endpoints[selected_endpoint]
    
    def add_post_endpoints_dynamically(self):
        """Agrega endpoints POST dinámicamente durante el test."""
        # Agregar endpoints POST con menor peso
        post_endpoints = {
            '/api/products/': {'method': 'POST', 'weight': 8},
            '/api/stores/': {'method': 'POST', 'weight': 3},
        }
        
        # Combinar con endpoints existentes
        for endpoint, config in post_endpoints.items():
            if endpoint in self.endpoints:
                # Si ya existe, mantener el GET y agregar POST como nuevo endpoint
                post_endpoint = f"{endpoint}[POST]"
                self.endpoints[post_endpoint] = config
            else:
                self.endpoints[endpoint] = config
    
    def run_load_test(self, target_rps: int = 500, duration_minutes: int = 5, 
                      num_threads: int = 50) -> Dict[str, Any]:
        """
        Ejecuta el test de carga principal.
        
        Args:
            target_rps: Requests por segundo objetivo
            duration_minutes: Duración en minutos
            num_threads: Número de threads concurrentes
            
        Returns:
            Diccionario con resultados del test
        """
        print(f"🚀 Iniciando test de carga:")
        print(f"   Target: {target_rps} requests/segundo")
        print(f"   Duración: {duration_minutes} minutos")
        print(f"   Threads: {num_threads}")
        print(f"   Host: {self.base_url}")
        print()
        
        # Agregar endpoints POST
        self.add_post_endpoints_dynamically()
        
        # Calcular configuración por thread
        duration_seconds = duration_minutes * 60
        rps_per_thread = target_rps / num_threads
        
        # Inicializar
        self.results = []
        self.start_time = time.time()
        
        # Crear y ejecutar threads
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(
                target=self.worker_thread,
                args=(duration_seconds, rps_per_thread),
                name=f"LoadTestWorker-{i+1}"
            )
            threads.append(thread)
        
        # Iniciar todos los threads
        print("🏃‍♂️ Iniciando threads de carga...")
        start_threads = time.time()
        for thread in threads:
            thread.start()
        
        # Monitorear progreso
        self.monitor_progress(duration_seconds)
        
        # Esperar a que terminen todos los threads
        print("\n⏳ Esperando finalización de threads...")
        for thread in threads:
            thread.join()
        
        self.end_time = time.time()
        
        print("✅ Test de carga completado!")
        print()
        
        # Analizar resultados
        return self.analyze_results()
    
    def monitor_progress(self, duration_seconds: int):
        """Monitorea el progreso del test en tiempo real."""
        update_interval = 10  # Actualizar cada 10 segundos
        elapsed = 0
        
        while elapsed < duration_seconds:
            time.sleep(min(update_interval, duration_seconds - elapsed))
            elapsed += update_interval
            
            # Mostrar estadísticas actuales
            with self.lock:
                total_requests = len(self.results)
                if total_requests > 0:
                    current_rps = total_requests / elapsed
                    successful = sum(1 for r in self.results if r.success)
                    success_rate = (successful / total_requests) * 100
                    
                    print(f"⏱️  {elapsed}s - Requests: {total_requests}, "
                          f"RPS: {current_rps:.1f}, Éxito: {success_rate:.1f}%")
    
    def analyze_results(self) -> Dict[str, Any]:
        """Analiza los resultados del test de carga."""
        if not self.results:
            return {"error": "No hay resultados para analizar"}
        
        total_duration = self.end_time - self.start_time
        total_requests = len(self.results)
        successful_requests = sum(1 for r in self.results if r.success)
        failed_requests = total_requests - successful_requests
        
        # Calcular métricas de tiempo de respuesta
        response_times = [r.response_time for r in self.results if r.success]
        
        if response_times:
            avg_response_time = statistics.mean(response_times)
            median_response_time = statistics.median(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            
            # Calcular percentiles
            sorted_times = sorted(response_times)
            p95_index = int(len(sorted_times) * 0.95)
            p99_index = int(len(sorted_times) * 0.99)
            
            p95_response_time = sorted_times[p95_index] if p95_index < len(sorted_times) else max_response_time
            p99_response_time = sorted_times[p99_index] if p99_index < len(sorted_times) else max_response_time
        else:
            avg_response_time = median_response_time = min_response_time = max_response_time = 0
            p95_response_time = p99_response_time = 0
        
        # Analizar por endpoint
        endpoint_stats = {}
        for endpoint in set(r.endpoint for r in self.results):
            endpoint_results = [r for r in self.results if r.endpoint == endpoint]
            endpoint_successful = sum(1 for r in endpoint_results if r.success)
            endpoint_times = [r.response_time for r in endpoint_results if r.success]
            
            endpoint_stats[endpoint] = {
                "total_requests": len(endpoint_results),
                "successful_requests": endpoint_successful,
                "failure_rate": ((len(endpoint_results) - endpoint_successful) / len(endpoint_results)) * 100,
                "avg_response_time": statistics.mean(endpoint_times) if endpoint_times else 0,
                "requests_per_second": len(endpoint_results) / total_duration
            }
        
        # Analizar errores
        error_analysis = {}
        for result in self.results:
            if not result.success and result.error:
                error_type = result.error.split(':')[0]  # Obtener tipo de error
                if error_type not in error_analysis:
                    error_analysis[error_type] = 0
                error_analysis[error_type] += 1
        
        # Compilar resultado final
        analysis = {
            "test_summary": {
                "duration_seconds": round(total_duration, 2),
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "failed_requests": failed_requests,
                "success_rate_percent": round((successful_requests / total_requests) * 100, 2),
                "requests_per_second": round(total_requests / total_duration, 2)
            },
            "response_time_metrics": {
                "average_ms": round(avg_response_time, 2),
                "median_ms": round(median_response_time, 2),
                "min_ms": round(min_response_time, 2),
                "max_ms": round(max_response_time, 2),
                "p95_ms": round(p95_response_time, 2),
                "p99_ms": round(p99_response_time, 2)
            },
            "endpoint_breakdown": endpoint_stats,
            "error_analysis": error_analysis,
            "sla_compliance": self.check_sla_compliance(
                total_requests / total_duration,
                (successful_requests / total_requests) * 100,
                avg_response_time,
                p95_response_time
            )
        }
        
        return analysis
    
    def check_sla_compliance(self, actual_rps: float, success_rate: float, 
                           avg_response_time: float, p95_response_time: float) -> Dict[str, Any]:
        """Verifica cumplimiento de SLAs."""
        compliance = {
            "target_rps_achieved": actual_rps >= 450,  # 90% del objetivo de 500 RPS
            "acceptable_success_rate": success_rate >= 99.0,  # 99% de éxito mínimo
            "acceptable_avg_response": avg_response_time <= 1000,  # 1 segundo promedio
            "acceptable_p95_response": p95_response_time <= 2000,  # 2 segundos p95
        }
        
        compliance["overall_compliance"] = all(compliance.values())
        
        return compliance
    
    def export_results_csv(self, filename: str = None):
        """Exporta resultados a CSV."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"load_test_results_{timestamp}.csv"
        
        results_dir = Path("load_test_results")
        results_dir.mkdir(exist_ok=True)
        filepath = results_dir / filename
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'timestamp', 'endpoint', 'method', 'status_code', 
                'response_time_ms', 'success', 'error'
            ])
            
            for result in self.results:
                writer.writerow([
                    result.timestamp,
                    result.endpoint,
                    result.method,
                    result.status_code,
                    result.response_time,
                    result.success,
                    result.error or ''
                ])
        
        print(f"📊 Resultados exportados a: {filepath}")
        return str(filepath)
    
    def print_summary(self, analysis: Dict[str, Any]):
        """Imprime un resumen de los resultados."""
        summary = analysis["test_summary"]
        response_metrics = analysis["response_time_metrics"]
        sla = analysis["sla_compliance"]
        
        print("=" * 60)
        print("📊 RESUMEN DE RESULTADOS DEL TEST DE CARGA")
        print("=" * 60)
        print()
        
        print("🎯 MÉTRICAS GENERALES:")
        print(f"   Duración total: {summary['duration_seconds']} segundos")
        print(f"   Total requests: {summary['total_requests']:,}")
        print(f"   Requests exitosos: {summary['successful_requests']:,}")
        print(f"   Requests fallidos: {summary['failed_requests']:,}")
        print(f"   Tasa de éxito: {summary['success_rate_percent']}%")
        print(f"   RPS promedio: {summary['requests_per_second']:.2f}")
        print()
        
        print("⚡ TIEMPOS DE RESPUESTA:")
        print(f"   Promedio: {response_metrics['average_ms']:.2f} ms")
        print(f"   Mediana: {response_metrics['median_ms']:.2f} ms")
        print(f"   Mínimo: {response_metrics['min_ms']:.2f} ms")
        print(f"   Máximo: {response_metrics['max_ms']:.2f} ms")
        print(f"   95% percentil: {response_metrics['p95_ms']:.2f} ms")
        print(f"   99% percentil: {response_metrics['p99_ms']:.2f} ms")
        print()
        
        print("✅ CUMPLIMIENTO DE SLAs:")
        status_icon = "✅" if sla["overall_compliance"] else "❌"
        print(f"   {status_icon} Cumplimiento general: {'SÍ' if sla['overall_compliance'] else 'NO'}")
        print(f"   {'✅' if sla['target_rps_achieved'] else '❌'} RPS objetivo (450+): {'SÍ' if sla['target_rps_achieved'] else 'NO'}")
        print(f"   {'✅' if sla['acceptable_success_rate'] else '❌'} Tasa de éxito (99%+): {'SÍ' if sla['acceptable_success_rate'] else 'NO'}")
        print(f"   {'✅' if sla['acceptable_avg_response'] else '❌'} Tiempo promedio (<1s): {'SÍ' if sla['acceptable_avg_response'] else 'NO'}")
        print(f"   {'✅' if sla['acceptable_p95_response'] else '❌'} P95 tiempo (<2s): {'SÍ' if sla['acceptable_p95_response'] else 'NO'}")
        print()
        
        if analysis["error_analysis"]:
            print("🚨 ANÁLISIS DE ERRORES:")
            for error_type, count in analysis["error_analysis"].items():
                print(f"   {error_type}: {count} ocurrencias")
            print()
        
        print("📈 TOP ENDPOINTS (por volumen):")
        sorted_endpoints = sorted(
            analysis["endpoint_breakdown"].items(),
            key=lambda x: x[1]["total_requests"],
            reverse=True
        )
        
        for endpoint, stats in sorted_endpoints[:5]:
            print(f"   {endpoint}:")
            print(f"     Requests: {stats['total_requests']:,}")
            print(f"     RPS: {stats['requests_per_second']:.2f}")
            print(f"     Tiempo promedio: {stats['avg_response_time']:.2f} ms")
            print(f"     Tasa de fallo: {stats['failure_rate']:.2f}%")
        
        print("=" * 60)


class Command(BaseCommand):
    """Management command para ejecutar el test de carga."""
    
    help = 'Ejecuta test de carga de 500 requests/segundo para la API de Retail'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--rps',
            type=int,
            default=500,
            help='Requests por segundo objetivo (default: 500)'
        )
        parser.add_argument(
            '--duration',
            type=int,
            default=5,
            help='Duración en minutos (default: 5)'
        )
        parser.add_argument(
            '--threads',
            type=int,
            default=50,
            help='Número de threads concurrentes (default: 50)'
        )
        parser.add_argument(
            '--host',
            type=str,
            default='http://localhost:8000',
            help='Host objetivo (default: http://localhost:8000)'
        )
        parser.add_argument(
            '--export-csv',
            action='store_true',
            help='Exportar resultados a CSV'
        )
    
    def handle(self, *args, **options):
        """Ejecuta el test de carga."""
        try:
            # Crear runner
            runner = LoadTestRunner(base_url=options['host'])
            
            # Ejecutar test
            results = runner.run_load_test(
                target_rps=options['rps'],
                duration_minutes=options['duration'],
                num_threads=options['threads']
            )
            
            # Mostrar resumen
            runner.print_summary(results)
            
            # Exportar CSV si se solicita
            if options['export_csv']:
                runner.export_results_csv()
            
            # Verificar SLAs
            if not results["sla_compliance"]["overall_compliance"]:
                self.stdout.write(
                    self.style.WARNING("⚠️  Algunos SLAs no se cumplieron. Revisa los resultados.")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS("✅ Todos los SLAs se cumplieron exitosamente.")
                )
                
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING("\n⚠️  Test interrumpido por el usuario.")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error ejecutando test de carga: {e}")
            )
            import traceback
            traceback.print_exc()


# Función principal para ejecución directa del archivo
def main():
    """Función principal para ejecutar el test directamente."""
    print("🚀 Ejecutando test de carga directo...")
    
    # Crear runner con configuración por defecto
    runner = LoadTestRunner()
    
    try:
        # Ejecutar test de carga
        results = runner.run_load_test(
            target_rps=500,
            duration_minutes=2,  # Test corto para prueba directa
            num_threads=50
        )
        
        # Mostrar resultados
        runner.print_summary(results)
        
        # Exportar resultados
        csv_file = runner.export_results_csv()
        print(f"\n📁 Archivo CSV generado: {csv_file}")
        
    except KeyboardInterrupt:
        print("\n⚠️  Test interrumpido por el usuario.")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Si se ejecuta directamente el archivo
    main()