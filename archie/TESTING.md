# ArchieOS Testing Guide

This document provides comprehensive information about testing ArchieOS, including setup, running tests, coverage reporting, and continuous integration.

## Quick Start

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-asyncio coverage

# Run all tests with coverage
./run_tests.py --all --coverage

# Or use pytest directly
pytest tests/ --cov=archie_core --cov=api --cov-report=html
```

## Test Structure

### Test Organization

```
tests/
├── conftest.py                 # Global test configuration and fixtures
├── test_auth.py               # Authentication system tests
├── test_db.py                 # Database operations tests
├── test_main_api.py           # FastAPI application tests
├── test_memory_manager.py     # Memory management tests
├── test_models.py             # Pydantic model tests
├── test_council/              # Council collaboration tests
├── test_jobs/                 # Job scheduling tests
├── test_ocr/                  # OCR processing tests
└── test_enrichers/            # Data enrichment tests
```

### Test Categories

Tests are organized using pytest markers:

- `@pytest.mark.unit` - Unit tests for individual components
- `@pytest.mark.integration` - Integration tests across components  
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.auth` - Authentication tests
- `@pytest.mark.db` - Database tests
- `@pytest.mark.memory` - Memory management tests
- `@pytest.mark.council` - Council collaboration tests
- `@pytest.mark.jobs` - Job scheduling tests
- `@pytest.mark.ocr` - OCR processing tests
- `@pytest.mark.enricher` - Data enrichment tests
- `@pytest.mark.slow` - Performance/long-running tests
- `@pytest.mark.external` - Tests requiring external services

## Running Tests

### Using the Test Runner Script

The `run_tests.py` script provides convenient test execution:

```bash
# Run unit tests only
./run_tests.py --unit

# Run integration tests
./run_tests.py --integration

# Run API tests
./run_tests.py --api

# Run all tests
./run_tests.py --all

# Run with coverage
./run_tests.py --all --coverage

# Run specific test pattern
./run_tests.py --pattern "test_memory"

# Clean and run with verbose output
./run_tests.py --clean --verbose --all
```

### Using pytest Directly

```bash
# Run all tests
pytest tests/

# Run specific test categories
pytest tests/ -m unit
pytest tests/ -m integration
pytest tests/ -m "api and not slow"

# Run specific test files
pytest tests/test_memory_manager.py
pytest tests/test_auth.py -v

# Run tests matching pattern
pytest tests/ -k "test_store_memory"

# Run with coverage
pytest tests/ --cov=archie_core --cov=api --cov-report=html

# Run in parallel (if pytest-xdist installed)
pytest tests/ -n auto
```

### Test Configuration Options

The test configuration is defined in `pytest.ini`:

```ini
[tool:pytest]
testpaths = tests
addopts = 
    --verbose
    --cov=archie_core
    --cov=api
    --cov-report=term-missing
    --cov-report=html:htmlcov
    --cov-fail-under=85
```

## Coverage Reporting

### Coverage Configuration

Coverage settings are in `.coveragerc`:

- **Source**: `archie_core/` and `api/`
- **Target**: 85% minimum coverage
- **Reports**: Terminal, HTML, XML, JSON formats

### Viewing Coverage

```bash
# Generate coverage report
coverage report

# Generate HTML report
coverage html
# View at: htmlcov/index.html

# Generate XML report (for CI)
coverage xml
```

### Coverage Exclusions

Lines excluded from coverage:
- `pragma: no cover`
- Debug methods (`__repr__`, `__str__`)
- Error handling (`raise AssertionError`)
- Platform-specific code
- Type checking imports
- Logging debug statements

## Test Environment

### Environment Variables

Tests use these environment variables:

```bash
ARCHIE_TEST_MODE=true
ARCHIE_LOG_LEVEL=WARNING
ARCHIE_SECRET_KEY=test-secret-key
ARCHIE_JWT_ISS=archie-test
ARCHIE_JWT_EXP_DAYS=1
```

### Test Fixtures

Key fixtures in `conftest.py`:

- `temp_db_dir` - Temporary database directory
- `test_database` - Isolated test database
- `memory_manager_mock` - Mocked memory manager
- `personality_mock` - Mocked personality engine  
- `test_client` - FastAPI test client
- `sample_memory_data` - Test data samples

### Isolation

Each test runs in isolation:
- Temporary databases and directories
- Mocked external dependencies
- Clean global state between tests
- No shared state between test runs

## Continuous Integration

### GitHub Actions

The CI pipeline (`.github/workflows/test.yml`) includes:

1. **Multi-Python Testing**: Python 3.9, 3.10, 3.11
2. **Dependency Installation**: System and Python packages
3. **Test Execution**: Unit, integration, and API tests
4. **Coverage Reporting**: HTML and XML reports
5. **Security Scanning**: Bandit and Safety checks
6. **Performance Testing**: Benchmark tests
7. **Documentation**: API docs generation

### CI Workflow Steps

```yaml
- name: Run unit tests
  run: pytest tests/ -m "unit or not integration" --cov
  
- name: Run integration tests  
  run: pytest tests/ -m "integration" --cov-append
  
- name: Generate coverage
  run: coverage xml && coverage html
```

### Artifact Collection

CI collects these artifacts:
- Test results (JUnit XML)
- Coverage reports (HTML/XML)
- Security scan reports
- Performance benchmarks
- Log files

## Writing Tests

### Test Naming Convention

```python
# Test files: test_<module_name>.py
# Test classes: Test<ClassName>
# Test methods: test_<functionality>_<scenario>

def test_store_memory_success():
    """Test successful memory storage"""
    pass

def test_store_memory_validation_error():
    """Test memory storage with validation errors"""
    pass
```

### Test Structure

```python
class TestMemoryManager:
    """Test memory manager functionality"""
    
    def test_store_memory_minimal_data(self, memory_manager):
        """Test storing memory with minimal required data"""
        # Arrange
        content = "Test memory"
        entry_type = "test"
        
        # Act
        memory_id = memory_manager.store_memory(content, entry_type)
        
        # Assert
        assert memory_id > 0
        # Verify storage...
```

### Using Fixtures

```python
def test_search_memories(self, populated_memory_manager, sample_search_data):
    """Test memory search functionality"""
    results = populated_memory_manager.search_memories(**sample_search_data)
    assert isinstance(results, list)
```

### Mocking External Dependencies

```python
@patch('archie_core.memory_manager.Database')
def test_memory_manager_init(self, mock_db_class):
    """Test memory manager initialization"""
    mock_db = Mock()
    mock_db_class.return_value = mock_db
    
    manager = MemoryManager()
    mock_db.initialize.assert_called_once()
```

### Async Testing

```python
@pytest.mark.asyncio
async def test_async_endpoint(test_client):
    """Test async API endpoint"""
    response = await test_client.get("/async-endpoint")
    assert response.status_code == 200
```

## Performance Testing

### Benchmark Tests

Use `pytest-benchmark` for performance tests:

```python
@pytest.mark.slow
def test_bulk_memory_storage_performance(memory_manager, benchmark):
    """Test bulk memory storage performance"""
    def store_memories():
        for i in range(1000):
            memory_manager.store_memory(f"Memory {i}", "bulk")
    
    result = benchmark(store_memories)
    assert result is not None
```

### Load Testing

For API load testing:

```python
@pytest.mark.external
def test_api_load_handling():
    """Test API under load"""
    import concurrent.futures
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_api_request) for _ in range(100)]
        results = [future.result() for future in futures]
    
    assert all(r.status_code == 200 for r in results)
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Add project root to PYTHONPATH
   export PYTHONPATH=$(pwd):$PYTHONPATH
   pytest tests/
   ```

2. **Database Lock Errors**
   ```python
   # Use isolated test databases
   @pytest.fixture
   def temp_db(temp_db_dir):
       return Database(str(temp_db_dir))
   ```

3. **Async Test Issues**
   ```python
   # Ensure asyncio mode is set
   pytest.ini:
   asyncio_mode = auto
   ```

4. **Coverage Not Working**
   ```bash
   # Install coverage plugin
   pip install pytest-cov
   
   # Use correct source paths
   pytest --cov=archie_core --cov=api
   ```

### Debug Test Failures

```bash
# Run with verbose output
pytest tests/ -v

# Stop at first failure
pytest tests/ -x

# Enter debugger on failure
pytest tests/ --pdb

# Run last failed tests
pytest tests/ --lf
```

## Code Quality

### Linting

```bash
# Install linting tools
pip install flake8 black isort

# Run linting
flake8 archie_core/ api/
black --check archie_core/ api/
isort --check-only archie_core/ api/
```

### Type Checking

```bash
# Install mypy
pip install mypy

# Run type checking
mypy archie_core/ --ignore-missing-imports
```

### Security Scanning

```bash
# Install security tools
pip install bandit safety

# Run security scans
bandit -r archie_core/ api/
safety check
```

## Best Practices

### Test Writing Guidelines

1. **One Assert Per Test**: Focus tests on single behaviors
2. **Clear Test Names**: Describe what is being tested
3. **Arrange-Act-Assert**: Structure tests clearly
4. **Use Fixtures**: Share setup code efficiently
5. **Mock External Dependencies**: Keep tests isolated
6. **Test Edge Cases**: Include error conditions
7. **Performance Awareness**: Mark slow tests appropriately

### Test Maintenance

1. **Keep Tests DRY**: Use fixtures and utilities
2. **Update Tests with Code**: Maintain test relevance
3. **Review Test Coverage**: Aim for meaningful coverage
4. **Clean Up Resources**: Use proper teardown
5. **Document Complex Tests**: Add docstrings and comments

### CI/CD Integration

1. **Fast Feedback**: Prioritize quick unit tests
2. **Parallel Execution**: Use test parallelization
3. **Artifact Collection**: Save test reports
4. **Failure Analysis**: Include debugging information
5. **Quality Gates**: Enforce coverage thresholds

## Resources

- [pytest Documentation](https://pytest.org/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [GitHub Actions](https://docs.github.com/en/actions)