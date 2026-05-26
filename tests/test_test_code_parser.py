"""test_code Markdown 解析器测试。"""

from agents.dev_pipeline.test_code_parser import parse_test_bundle


def test_parse_two_files():
    text = """
## file: src/__tests__/app.test.ts
```typescript
import { describe, it, expect } from 'vitest';
describe('app', () => { it('works', () => { expect(1).toBe(1); }); });
```

## file: src/__tests__/util.test.ts
```typescript
it('util', () => { expect(true).toBe(true); });
```
"""
    bundle = parse_test_bundle(text)
    assert len(bundle.files) == 2
    assert bundle.files[0].path == "src/__tests__/app.test.ts"
    assert "vitest" in bundle.files[0].code
    assert bundle.files[1].path == "src/__tests__/util.test.ts"


def test_parse_single_fence_without_heading():
    text = """
```python
def test_ok():
    assert True
```
"""
    bundle = parse_test_bundle(text)
    assert len(bundle.files) == 1
    assert bundle.files[0].path.endswith(".py")
    assert "test_ok" in bundle.files[0].code


def test_fallback_on_empty():
    bundle = parse_test_bundle("   ")
    assert len(bundle.files) == 1
    assert bundle.files[0].code


def test_fallback_on_unparseable_prose():
    bundle = parse_test_bundle("Here are some notes without code fences.")
    assert len(bundle.files) == 1
    assert "notes" in bundle.files[0].code
