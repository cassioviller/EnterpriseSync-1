"""
E2E Tests for SIGE v9.0 Modules
Verifies that pages load without 500 errors and have expected UI elements
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Usuario
from werkzeug.security import generate_password_hash
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class E2ETestRunner:
    def __init__(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.results = {
            'passed': [],
            'failed': [],
            'errors': []
        }
        self.session_cookie = None
        
    def setup_test_user(self):
        """Ensure test user exists"""
        with self.app.app_context():
            user = Usuario.query.filter_by(email='admin.e2e.test@empresateste.com').first()
            if not user:
                logger.warning("Test user not found - attempting to create")
                try:
                    from models import TipoUsuario
                    user = Usuario(
                        nome='Admin E2E Test',
                        email='admin.e2e.test@empresateste.com',
                        password_hash=generate_password_hash('Teste@2025'),
                        tipo_usuario=TipoUsuario.ADMIN,
                        ativo=True
                    )
                    db.session.add(user)
                    db.session.commit()
                    logger.info(f"Created test user with id: {user.id}")
                except Exception as e:
                    logger.error(f"Could not create test user: {e}")
                    return False
            else:
                logger.info(f"Found existing test user with id: {user.id}")
            return True
    
    def login(self):
        """Perform login and get session"""
        logger.info("Attempting login...")
        
        response = self.client.post('/login', data={
            'email': 'admin.e2e.test@empresateste.com',
            'password': 'Teste@2025'
        }, follow_redirects=False)
        
        if response.status_code in [302, 303]:
            logger.info(f"Login redirected to: {response.headers.get('Location')}")
            if '/dashboard' in response.headers.get('Location', '') or '/login' not in response.headers.get('Location', ''):
                logger.info("Login successful!")
                return True
        
        logger.warning(f"Login response status: {response.status_code}")
        
        response = self.client.get('/dashboard', follow_redirects=True)
        if response.status_code == 200 and b'dashboard' in response.data.lower():
            logger.info("Already logged in or login succeeded!")
            return True
        
        return response.status_code != 401
    
    def test_route(self, route, expected_elements=None, module_name=""):
        """Test a single route"""
        try:
            logger.info(f"Testing route: {route}")
            response = self.client.get(route, follow_redirects=True)
            
            status_code = response.status_code
            content = response.data.decode('utf-8', errors='replace')
            
            if status_code == 500:
                error_msg = f"500 Internal Server Error on {route}"
                if 'Erro' in content or 'error' in content.lower():
                    error_preview = content[:500] if len(content) > 500 else content
                    error_msg += f" - Content preview: {error_preview}"
                self.results['failed'].append({
                    'module': module_name,
                    'route': route,
                    'status': status_code,
                    'error': error_msg
                })
                logger.error(f"FAILED: {route} - Status 500")
                return False
            
            if status_code == 404:
                self.results['failed'].append({
                    'module': module_name,
                    'route': route,
                    'status': status_code,
                    'error': f"404 Not Found - Route does not exist"
                })
                logger.error(f"FAILED: {route} - Status 404")
                return False
            
            if status_code == 401 or status_code == 403:
                self.results['failed'].append({
                    'module': module_name,
                    'route': route,
                    'status': status_code,
                    'error': f"Authentication/Authorization error ({status_code})"
                })
                logger.error(f"FAILED: {route} - Auth error {status_code}")
                return False
            
            if status_code != 200:
                self.results['failed'].append({
                    'module': module_name,
                    'route': route,
                    'status': status_code,
                    'error': f"Unexpected status code: {status_code}"
                })
                logger.warning(f"UNEXPECTED: {route} - Status {status_code}")
                return False
            
            elements_found = []
            elements_missing = []
            
            if expected_elements:
                for element in expected_elements:
                    if element.lower() in content.lower():
                        elements_found.append(element)
                    else:
                        elements_missing.append(element)
            
            self.results['passed'].append({
                'module': module_name,
                'route': route,
                'status': status_code,
                'elements_found': elements_found,
                'elements_missing': elements_missing
            })
            
            if elements_missing:
                logger.warning(f"PASSED with warnings: {route} - Missing elements: {elements_missing}")
            else:
                logger.info(f"PASSED: {route}")
            
            return True
            
        except Exception as e:
            self.results['errors'].append({
                'module': module_name,
                'route': route,
                'error': str(e)
            })
            logger.error(f"ERROR: {route} - {str(e)}")
            return False
    
    def run_test_plan_1_relatorios(self):
        """Test Plan 1: Relatórios Module"""
        logger.info("\n" + "="*60)
        logger.info("TEST PLAN 1: RELATÓRIOS MODULE")
        logger.info("="*60)
        
        self.test_route('/folha/relatorios', 
                       ['relatório', 'folha', 'holerite'],
                       'Relatórios - Folha')
        
        self.test_route('/contabilidade/relatorios',
                       ['relatório', 'contabil', 'contabilidade'],
                       'Relatórios - Contabilidade')
        
        self.test_route('/ponto/',
                       ['ponto', 'funcionário', 'registro'],
                       'Ponto Eletrônico')
    
    def run_test_plan_2_alimentacao(self):
        """Test Plan 2: Alimentação Module"""
        logger.info("\n" + "="*60)
        logger.info("TEST PLAN 2: ALIMENTAÇÃO MODULE")
        logger.info("="*60)
        
        self.test_route('/alimentacao/',
                       ['alimentação', 'refeição', 'restaurante'],
                       'Alimentação - Principal')
        
        self.test_route('/alimentacao/itens',
                       ['item', 'itens', 'alimentação'],
                       'Alimentação - Itens')
        
        self.test_route('/alimentacao/restaurantes',
                       ['restaurante', 'lista'],
                       'Alimentação - Restaurantes')
    
    def run_test_plan_3_frota(self):
        """Test Plan 3: Frota (Vehicles) Module"""
        logger.info("\n" + "="*60)
        logger.info("TEST PLAN 3: FROTA MODULE")
        logger.info("="*60)
        
        self.test_route('/frota/',
                       ['veículo', 'frota', 'placa'],
                       'Frota - Dashboard')
        
        self.test_route('/frota/veiculos',
                       ['veículo', 'lista', 'placa'],
                       'Frota - Veículos')
    
    def run_test_plan_4_folha_extras(self):
        """Test Plan 4: Folha Pagamento Extras"""
        logger.info("\n" + "="*60)
        logger.info("TEST PLAN 4: FOLHA PAGAMENTO EXTRAS")
        logger.info("="*60)
        
        self.test_route('/folha/',
                       ['folha', 'pagamento', 'funcionário'],
                       'Folha - Principal')
        
        self.test_route('/folha/dashboard',
                       ['folha', 'dashboard', 'pagamento'],
                       'Folha - Dashboard')
        
        self.test_route('/folha/adiantamentos',
                       ['adiantamento', 'valor', 'funcionário'],
                       'Folha - Adiantamentos')
    
    def run_test_plan_5_contabilidade_extras(self):
        """Test Plan 5: Contabilidade Extras"""
        logger.info("\n" + "="*60)
        logger.info("TEST PLAN 5: CONTABILIDADE EXTRAS")
        logger.info("="*60)
        
        self.test_route('/contabilidade/',
                       ['contabilidade', 'contábil'],
                       'Contabilidade - Principal')
        
        self.test_route('/contabilidade/dashboard',
                       ['contabilidade', 'dashboard'],
                       'Contabilidade - Dashboard')
        
        self.test_route('/contabilidade/centros-custo',
                       ['centro', 'custo'],
                       'Contabilidade - Centros de Custo')
    
    def run_test_plan_6_almoxarifado_extras(self):
        """Test Plan 6: Almoxarifado Extras"""
        logger.info("\n" + "="*60)
        logger.info("TEST PLAN 6: ALMOXARIFADO EXTRAS")
        logger.info("="*60)
        
        self.test_route('/almoxarifado/',
                       ['almoxarifado', 'estoque', 'material'],
                       'Almoxarifado - Dashboard')
        
        self.test_route('/almoxarifado/entrada',
                       ['entrada', 'material', 'almoxarifado'],
                       'Almoxarifado - Entrada')
    
    def run_test_plan_7_usuarios(self):
        """Test Plan 7: Usuários Module"""
        logger.info("\n" + "="*60)
        logger.info("TEST PLAN 7: USUÁRIOS MODULE")
        logger.info("="*60)
        
        self.test_route('/usuarios',
                       ['usuário', 'lista', 'email'],
                       'Usuários - Lista')
    
    def print_results(self):
        """Print final test results"""
        print("\n" + "="*80)
        print("E2E TEST RESULTS - SIGE v9.0 MODULES")
        print("="*80)
        
        print(f"\n📊 SUMMARY:")
        print(f"   ✅ Passed: {len(self.results['passed'])}")
        print(f"   ❌ Failed: {len(self.results['failed'])}")
        print(f"   ⚠️  Errors: {len(self.results['errors'])}")
        
        if self.results['passed']:
            print(f"\n✅ PASSED TESTS ({len(self.results['passed'])}):")
            for result in self.results['passed']:
                print(f"   [{result['module']}] {result['route']} - Status {result['status']}")
                if result.get('elements_missing'):
                    print(f"      ⚠️ Missing elements: {result['elements_missing']}")
        
        if self.results['failed']:
            print(f"\n❌ FAILED TESTS ({len(self.results['failed'])}):")
            for result in self.results['failed']:
                print(f"   [{result['module']}] {result['route']}")
                print(f"      Status: {result['status']}")
                print(f"      Error: {result['error']}")
        
        if self.results['errors']:
            print(f"\n⚠️ TEST ERRORS ({len(self.results['errors'])}):")
            for result in self.results['errors']:
                print(f"   [{result['module']}] {result['route']}")
                print(f"      Error: {result['error']}")
        
        print("\n" + "="*80)
        
        return self.results
    
    def run_all_tests(self):
        """Run all test plans"""
        logger.info("Starting E2E Tests for SIGE v9.0")
        
        self.setup_test_user()
        
        if not self.login():
            logger.error("Login failed! Attempting to continue with tests anyway...")
        
        self.run_test_plan_1_relatorios()
        self.run_test_plan_2_alimentacao()
        self.run_test_plan_3_frota()
        self.run_test_plan_4_folha_extras()
        self.run_test_plan_5_contabilidade_extras()
        self.run_test_plan_6_almoxarifado_extras()
        self.run_test_plan_7_usuarios()
        
        return self.print_results()


if __name__ == '__main__':
    runner = E2ETestRunner()
    results = runner.run_all_tests()
    
    failed_count = len(results['failed']) + len(results['errors'])
    if failed_count > 0:
        sys.exit(1)
    sys.exit(0)
