# Documentation Tests

Automated tests for py_accountant documentation to ensure examples remain valid and up-to-date.

## Overview

These tests validate:
- **Code examples**: All Python code blocks in documentation are syntactically valid
- **Links**: All internal documentation links point to existing files
- **Imports**: All py_accountant imports in examples are current and valid
- **Configuration**: All environment variables are documented

## Test Files

### `test_code_examples.py`
Extracts and validates Python code blocks from markdown files.

**Tests:**
- `test_readme_examples_valid_syntax` - Validates README.md code examples
- `test_api_reference_examples_valid_syntax` - Validates API_REFERENCE.md examples (40+)
- `test_config_reference_examples_valid_syntax` - Validates CONFIG_REFERENCE.md examples
- `test_integration_guide_examples_valid_syntax` - Validates INTEGRATION_GUIDE.md examples
- `test_all_markdown_files_syntax` - Validates all Python code blocks (60+)

**Coverage:**
- 60+ Python code blocks validated
- Detects syntax errors, missing imports, invalid type hints
- Skips placeholder/signature-only examples

### `test_links.py`
Validates internal documentation links.

**Tests:**
- `test_index_links_valid` - Validates INDEX.md links
- `test_readme_links_valid` - Validates README.md links
- `test_all_internal_links_valid` - Validates all internal links (50+)
- `test_no_legacy_references` - Ensures no references to removed components

**Coverage:**
- 50+ internal links checked
- Validates file existence
- Detects broken references
- Skips external URLs (http://, https://)

### `test_imports.py`
Validates imports in documentation examples.

**Tests:**
- `test_py_accountant_imports_valid` - All py_accountant imports are importable (20+)
- `test_no_legacy_imports` - No imports from removed modules (sdk, presentation)
- `test_use_cases_async_imports_preferred` - Async imports preferred over sync

**Coverage:**
- 20+ py_accountant imports validated
- Detects removed/renamed modules
- Ensures async-first approach in examples

### `test_config_variables.py`
Validates environment variable documentation.

**Tests:**
- `test_all_code_variables_documented` - All settings.py variables documented
- `test_all_documented_variables_exist` - All documented variables exist in code
- `test_variable_count_matches` - Count consistency check (25+)

**Coverage:**
- 25+ environment variables validated
- Ensures code/docs synchronization
- Extracts from both CONFIG_REFERENCE.md and settings.py

## Running Tests

### Run all documentation tests
```bash
poetry run pytest tests/docs/ -v
```

### Run specific test file
```bash
poetry run pytest tests/docs/test_code_examples.py -v
poetry run pytest tests/docs/test_links.py -v
poetry run pytest tests/docs/test_imports.py -v
poetry run pytest tests/docs/test_config_variables.py -v
```

### Run with timing information
```bash
poetry run pytest tests/docs/ -v --durations=10
```

### Run and show only failures
```bash
poetry run pytest tests/docs/ -v --tb=short
```

## Performance

Expected execution time: **< 5 seconds** for all tests

## Integration

These tests are part of the test suite and can be run in CI/CD:
- No external dependencies required
- No database setup needed
- Fast execution for quick feedback

## Maintenance

### Adding new documentation files
Update `all_markdown_files` fixture in test files if new markdown files are added outside of `docs/` or `examples/` directories.

### Skipping specific examples
If a code block is intentionally non-executable (e.g., pseudocode):
- Add explicit markers like `# ...` or `...` 
- The `is_example_only_code()` function will automatically skip it

### Skipping legacy checks
If a file documents removed components (historical/audit docs), add it to `skip_files` set in `test_links.py::test_no_legacy_references`.

## What These Tests Catch

✅ **Syntax errors** in code examples  
✅ **Broken internal links** between documentation files  
✅ **Invalid imports** (removed/renamed modules)  
✅ **Undocumented environment variables**  
✅ **Legacy references** to removed components  
✅ **Type hint errors** (e.g., `|` vs `|`)  

## Example Test Output

```
tests/docs/test_code_examples.py::TestCodeExamples::test_readme_examples_valid_syntax PASSED
tests/docs/test_code_examples.py::TestCodeExamples::test_api_reference_examples_valid_syntax PASSED
tests/docs/test_links.py::TestDocumentationLinks::test_all_internal_links_valid PASSED
tests/docs/test_imports.py::TestDocumentationImports::test_py_accountant_imports_valid PASSED
tests/docs/test_config_variables.py::TestConfigurationVariables::test_variable_count_matches PASSED

15 passed in 2.5s
```

## Troubleshooting

### Test fails with "Syntax error"
Check the reported line in the markdown file. The code block may have:
- Invalid Python syntax
- Type hint errors (use `|` not `|`)
- Incomplete code fragments

### Test fails with "Broken link"
Check that the target file exists at the expected path. Relative paths are resolved from the source file's directory.

### Test fails with "Invalid import"
The module may have been removed or renamed. Update the documentation to use current imports:
- Use `py_accountant.application.use_cases_async.*` (not `.use_cases`)
- No `py_accountant.sdk.*` imports
- No `py_accountant.presentation.*` imports

### Test fails with "Undocumented variable"
Add documentation for the variable in `docs/CONFIG_REFERENCE.md` with a level-4 header:
```markdown
#### VARIABLE_NAME
Description...
```

## Related Documentation

- [API_REFERENCE.md](../../docs/API_REFERENCE.md) - API documentation with examples
- [CONFIG_REFERENCE.md](../../docs/CONFIG_REFERENCE.md) - Environment variables
- [INTEGRATION_GUIDE.md](../../docs/INTEGRATION_GUIDE.md) - Integration examples

## Created

Sprint S6 - November 25, 2025

