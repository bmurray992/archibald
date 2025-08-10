#!/usr/bin/env python3
"""
Comprehensive test runner for ArchieOS
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description="Running command", ignore_errors=False):
    """Run a shell command and handle output"""
    print(f"\n{'='*60}")
    print(f"{description}: {' '.join(cmd)}")
    print('='*60)
    
    try:
        result = subprocess.run(cmd, check=not ignore_errors, capture_output=False)
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
        else:
            print(f"❌ {description} failed with return code {result.returncode}")
            if not ignore_errors:
                return False
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        return False if not ignore_errors else True


def setup_environment():
    """Set up test environment"""
    print("🚀 Setting up test environment...")
    
    # Set environment variables
    env_vars = {
        'ARCHIE_TEST_MODE': 'true',
        'ARCHIE_LOG_LEVEL': 'WARNING',
        'ARCHIE_SECRET_KEY': 'test-secret-key-for-testing',
        'ARCHIE_JWT_ISS': 'archie-test',
        'ARCHIE_JWT_EXP_DAYS': '1',
        'PYTHONPATH': str(Path.cwd())
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
        print(f"  {key}={value}")


def check_dependencies():
    """Check if all required dependencies are installed"""
    print("🔍 Checking dependencies...")
    
    required_packages = [
        'pytest',
        'pytest-cov',
        'pytest-asyncio',
        'coverage',
        'fastapi',
        'pydantic',
        'cryptography'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing packages: {', '.join(missing_packages)}")
        print("Run: pip install -r requirements.txt pytest-cov pytest-asyncio")
        return False
    
    print("✅ All dependencies are installed")
    return True


def run_unit_tests(verbose=False, coverage=True):
    """Run unit tests"""
    cmd = ['python', '-m', 'pytest']
    
    # Basic options
    cmd.extend(['tests/', '-m', 'unit or not integration'])
    
    if verbose:
        cmd.append('-v')
    else:
        cmd.append('-q')
    
    if coverage:
        cmd.extend([
            '--cov=archie_core',
            '--cov=api',
            '--cov-report=term-missing',
            '--cov-report=html:htmlcov',
            '--cov-report=xml:coverage.xml'
        ])
    
    cmd.extend(['--tb=short', '--strict-markers'])
    
    return run_command(cmd, "Unit tests")


def run_integration_tests(verbose=False):
    """Run integration tests"""
    cmd = ['python', '-m', 'pytest']
    
    cmd.extend(['tests/', '-m', 'integration'])
    
    if verbose:
        cmd.append('-v')
    
    cmd.extend(['--tb=short', '--strict-markers'])
    
    return run_command(cmd, "Integration tests", ignore_errors=True)


def run_api_tests(verbose=False):
    """Run API tests"""
    cmd = ['python', '-m', 'pytest']
    
    cmd.extend(['tests/', '-m', 'api'])
    
    if verbose:
        cmd.append('-v')
    
    cmd.extend(['--tb=short', '--strict-markers'])
    
    return run_command(cmd, "API tests")


def run_specific_tests(test_pattern, verbose=False):
    """Run specific tests matching pattern"""
    cmd = ['python', '-m', 'pytest']
    
    cmd.extend(['tests/', '-k', test_pattern])
    
    if verbose:
        cmd.append('-v')
    
    cmd.extend(['--tb=short'])
    
    return run_command(cmd, f"Tests matching '{test_pattern}'")


def run_coverage_report():
    """Generate and display coverage report"""
    print("\n📊 Generating coverage report...")
    
    # Generate reports
    commands = [
        (['coverage', 'report'], "Coverage summary"),
        (['coverage', 'html'], "HTML coverage report"),
        (['coverage', 'xml'], "XML coverage report")
    ]
    
    for cmd, description in commands:
        run_command(cmd, description, ignore_errors=True)
    
    print("\n📁 Coverage reports generated:")
    print("  - Terminal summary (above)")
    print("  - HTML report: htmlcov/index.html")
    print("  - XML report: coverage.xml")


def run_linting():
    """Run code linting"""
    print("\n🔍 Running code linting...")
    
    # Check if flake8 is available
    try:
        import flake8
        cmd = [
            'flake8', 'archie_core/', 'api/',
            '--max-line-length=127',
            '--extend-ignore=E203,W503',
            '--statistics'
        ]
        run_command(cmd, "Flake8 linting", ignore_errors=True)
    except ImportError:
        print("⚠️  flake8 not installed, skipping linting")


def run_type_checking():
    """Run type checking with mypy"""
    print("\n🔍 Running type checking...")
    
    try:
        import mypy
        cmd = [
            'mypy', 'archie_core/', 'api/',
            '--ignore-missing-imports',
            '--no-strict-optional'
        ]
        run_command(cmd, "MyPy type checking", ignore_errors=True)
    except ImportError:
        print("⚠️  mypy not installed, skipping type checking")


def cleanup_test_files():
    """Clean up test artifacts"""
    print("\n🧹 Cleaning up test artifacts...")
    
    cleanup_patterns = [
        '.coverage*',
        'junit.xml',
        '.pytest_cache/',
        '__pycache__/',
        '*.pyc',
        'test_*.db',
        'htmlcov/',
        'coverage.xml'
    ]
    
    for pattern in cleanup_patterns:
        cmd = ['find', '.', '-name', pattern, '-delete']
        run_command(cmd, f"Cleaning {pattern}", ignore_errors=True)


def main():
    """Main test runner function"""
    parser = argparse.ArgumentParser(description='ArchieOS Test Runner')
    parser.add_argument('--unit', action='store_true', help='Run unit tests only')
    parser.add_argument('--integration', action='store_true', help='Run integration tests only')
    parser.add_argument('--api', action='store_true', help='Run API tests only')
    parser.add_argument('--all', action='store_true', help='Run all tests')
    parser.add_argument('--coverage', action='store_true', help='Generate coverage report')
    parser.add_argument('--lint', action='store_true', help='Run linting')
    parser.add_argument('--type-check', action='store_true', help='Run type checking')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--no-coverage', action='store_true', help='Skip coverage collection')
    parser.add_argument('--clean', action='store_true', help='Clean test artifacts first')
    parser.add_argument('--pattern', '-k', help='Run tests matching pattern')
    
    args = parser.parse_args()
    
    # Set up environment
    setup_environment()
    
    # Clean first if requested
    if args.clean:
        cleanup_test_files()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    success = True
    
    # Run specific test patterns
    if args.pattern:
        success &= run_specific_tests(args.pattern, args.verbose)
        if args.coverage:
            run_coverage_report()
        return 0 if success else 1
    
    # Run linting if requested
    if args.lint:
        run_linting()
    
    # Run type checking if requested
    if args.type_check:
        run_type_checking()
    
    # Run specific test suites
    coverage = not args.no_coverage
    
    if args.unit or (not args.integration and not args.api and not args.all):
        success &= run_unit_tests(args.verbose, coverage)
    
    if args.integration or args.all:
        success &= run_integration_tests(args.verbose)
    
    if args.api or args.all:
        success &= run_api_tests(args.verbose)
    
    # Generate coverage report if requested or if coverage was collected
    if args.coverage or (coverage and not args.no_coverage):
        run_coverage_report()
    
    # Summary
    print("\n" + "="*60)
    if success:
        print("🎉 All tests completed successfully!")
    else:
        print("❌ Some tests failed. Check the output above.")
    print("="*60)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())